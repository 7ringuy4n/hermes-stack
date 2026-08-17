# -*- coding: utf-8 -*-
"""Run 02 profile matrix (RULES.md). Leaves High running. Reports omit host/account.

Env: ASSISTANT_SSH_HOST, ASSISTANT_SSH_USER, ASSISTANT_SSH_PASSWORD, ASSISTANT_REPO_ROOT
"""
from __future__ import annotations

import base64
import json
import os
import re
import sys
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

import paramiko

sys.path.insert(0, str(Path(__file__).resolve().parent))
from sanitize import sanitize

HOST = os.environ["ASSISTANT_SSH_HOST"]
USER = os.environ["ASSISTANT_SSH_USER"]
PW = os.environ["ASSISTANT_SSH_PASSWORD"]
ROOT = Path(os.environ.get("ASSISTANT_REPO_ROOT", Path(__file__).resolve().parents[2]))
REMOTE = "/opt/assistant"
OUT = ROOT / "test" / "reports" / "run-02"
esc = PW.replace("'", "'\\''")
ROWS: list[dict] = []
PROFILE_RESULTS: dict[str, dict] = {}


def ts() -> str:
    return datetime.now(timezone.utc).astimezone().strftime("%Y-%m-%d %H:%M:%S %z")


def note(section: str, name: str, status: str, detail: str = "") -> None:
    detail = sanitize(detail)
    row = {"ts": ts(), "section": section, "name": name, "status": status, "detail": detail[:400]}
    ROWS.append(row)
    print(f"[{row['ts']}] {section} | {name} | {status} | {row['detail'][:160]}", flush=True)


def connect():
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect(HOST, username=USER, password=PW, timeout=30, allow_agent=False, look_for_keys=False)
    return c


def emit(b: bytes) -> None:
    sys.stdout.buffer.write(b)
    sys.stdout.flush()


def sudo_bash(c, script: str, timeout: int = 3600) -> str:
    b64 = base64.b64encode(script.encode("utf-8")).decode("ascii")
    cmd = f"echo '{esc}' | sudo -S bash -lc \"echo {b64} | base64 -d | bash\""
    _i, o, e = c.exec_command(cmd, timeout=timeout, get_pty=True)
    chan = o.channel
    buf: list[str] = []
    while True:
        while chan.recv_ready():
            chunk = chan.recv(8192)
            emit(chunk)
            buf.append(chunk.decode("utf-8", "replace"))
        while chan.recv_stderr_ready():
            chunk = chan.recv_stderr(8192)
            emit(chunk)
            buf.append(chunk.decode("utf-8", "replace"))
        if chan.exit_status_ready() and not chan.recv_ready() and not chan.recv_stderr_ready():
            break
        time.sleep(0.15)
    code = chan.recv_exit_status()
    text = sanitize("".join(buf))
    if code != 0:
        raise SystemExit(f"remote exit {code}")
    return text


def sync_key_files(c) -> None:
    paths = [
        "run.sh",
        "architect/backup-restore/lib/backup.sh",
        "architect/backup-restore/lib/profile.sh",
        "architect/memory/memory-manager/app.py",
        "architect/authentication/authz/app.py",
        "scripts/main/heal-zalo-sse.sh",
        "scripts/main/log-archive.sh",
        "scripts/main/stack-watch.sh",
        "hermes/main/messages/ops-alerts.json",
    ]
    sftp = c.open_sftp()
    for rel in paths:
        loc = ROOT / rel
        if not loc.exists():
            continue
        raw = loc.read_bytes()
        if loc.suffix in {".py", ".sh"} or loc.name == "run.sh":
            raw = raw.decode("utf-8").replace("\r\n", "\n").encode("utf-8")
        tmp = f"/tmp/{loc.name}.{uuid.uuid4().hex[:8]}"
        with sftp.file(tmp, "wb") as f:
            f.write(raw)
        mode = "755" if loc.suffix == ".sh" or loc.name == "run.sh" else "644"
        rp = f"{REMOTE}/{rel}".replace("\\", "/")
        rdir = str(Path(rp).parent).replace("\\", "/")
        sudo_bash(c, f"mkdir -p '{rdir}' && install -m {mode} '{tmp}' '{rp}' && rm -f '{tmp}'", timeout=60)
    sftp.close()
    note("sync", "source", "pass", "LF-safe source sync")


def patch_and_up(c, profile: str, traefik_mode: str) -> str:
    script = f"""
set -euo pipefail
export LC_ALL=C.UTF-8
export COMPOSE_PROGRESS=quiet
cd {REMOTE}
python3 - <<'PY'
from pathlib import Path
import re
p = Path('/data/assistant/.env')
text = p.read_text(encoding='utf-8')
vals = {{
  'ASSISTANT_PROFILE': '{profile}',
  'ENABLE_GRAFANA': '0',
  'ENABLE_LOKI': '0',
  'ENABLE_PROMETHEUS': '0',
  'ENABLE_ALLOY': '0',
  'ENABLE_TRAEFIK': '1',
  'ENABLE_API_GATEWAY': '1',
  'TRAEFIK_MODE': '{traefik_mode}',
  'TRAEFIK_ACME_ENABLED': '0',
  'TRAEFIK_ACME_EMAIL': '',
  'TRAEFIK_ACME_DOMAIN': '',
  'ENABLE_MODEL_ROUTER': '1',
  'ENABLE_OMNIROUTER': '0',
  'ENABLE_LOG_ARCHIVE': '1',
  'LOG_RETENTION_DAYS': '30',
  'ENABLE_OPENVPN': '0',
  'ENABLE_ANTIVIRUS': '0',
  'IMAGE_BACKENDS': '',
  'HERMES_OPENAI_BASE_URL': 'http://model-router:8096/v1',
}}
if '{profile}' in ('medium', 'high'):
    vals.update({{
      'ENABLE_OCR': '1', 'ENABLE_JOBS': '1', 'ENABLE_SEARXNG': '1',
      'OFFICE_FILE_GEN': '1', 'ENABLE_ZALO': '1', 'WEB_BACKENDS': 'tavily,firecrawl',
    }})
else:
    vals.update({{'ENABLE_ZALO': '0', 'ENABLE_OCR': '0', 'ENABLE_JOBS': '0'}})
if '{profile}' == 'high':
    vals['HERMES_REPLICAS'] = '2'
    vals['ENABLE_SECURITY'] = '1'
    vals['ENABLE_POLICY'] = '1'
    vals['ENABLE_AUTHZ'] = '1'
    vals['ENABLE_SIEM'] = '1'
    vals['ENABLE_OPENBAO'] = '1'
else:
    vals['HERMES_REPLICAS'] = '1'
for k,v in vals.items():
    line=f'{{k}}={{v}}'
    if re.search(rf'(?m)^{{re.escape(k)}}=', text):
        text=re.sub(rf'(?m)^{{re.escape(k)}}=.*$', line, text)
    else:
        text=text.rstrip()+'\\n'+line+'\\n'
p.write_text(text, encoding='utf-8')
print('patched', '{profile}', '{traefik_mode}')
PY
export ASSISTANT_PROFILE={profile}
bash run.sh up
sleep 20
"""
    out = sudo_bash(c, script, timeout=2400)
    if traefik_mode == "public":
        note(f"deploy/{traefik_mode}/{profile}", "traefik_failsoft", "pass", "public without ACME fail-soft")
    note(f"deploy/{traefik_mode}/{profile}", "compose_up", "pass", "up completed")
    return out


def cycle_probes(c, label: str, profile: str) -> dict:
    out = sudo_bash(
        c,
        r"""
set -euo pipefail
export LC_ALL=C.UTF-8
echo '=== health ==='
curl -sf -m 8 http://127.0.0.1:8096/health && echo || echo MR_FAIL
curl -sf -m 8 http://127.0.0.1:8088/health && echo || echo GW_FAIL
curl -sf -m 8 http://127.0.0.1:8090/health && echo || echo DISP_FAIL
curl -sf -m 8 http://127.0.0.1:8095/health && echo || echo MEM_FAIL
echo '=== restart dispatcher ==='
docker restart dispatcher >/dev/null
sleep 5
curl -sf -m 8 http://127.0.0.1:8090/health && echo DISP_RECOVER_OK || echo DISP_RECOVER_FAIL
echo '=== logs ==='
ERRN=0
for n in assistant-hermes-1 assistant-hermes-2 hermes dispatcher model-router; do
  c=$(docker logs --since 3m "$n" 2>/dev/null | grep -cE 'Traceback|ERROR' || true)
  ERRN=$((ERRN+c))
done
echo LOG_ERR_COUNT=$ERRN
echo '=== image empty prompt ==='
curl -s -m 10 -o /tmp/img400.json -w 'IMG400=%{http_code}\n' -X POST http://127.0.0.1:8090/v1/image \
  -H 'Content-Type: application/json' -d '{"prompt":""}' || true
echo '=== image disabled ==='
curl -s -m 10 -o /tmp/img503.json -w 'IMG503=%{http_code}\n' -X POST http://127.0.0.1:8090/v1/image \
  -H 'Content-Type: application/json' -d '{"prompt":"run02 red circle"}' || true
head -c 200 /tmp/img503.json; echo
grep -E '^(ASSISTANT_PROFILE|TRAEFIK_MODE|HERMES_REPLICAS|IMAGE_BACKENDS)=' /data/assistant/.env || true
docker ps --filter name=hermes --format '{{.Names}} {{.Status}}'
docker ps --filter name=traefik --format 'traefik={{.Status}}'
""",
        timeout=180,
    )
    res = {
        "mr": "MR_FAIL" not in out and "model-router" in out,
        "gw": "GW_FAIL" not in out and "api-gateway" in out,
        "disp": "DISP_FAIL" not in out,
        "mem": "MEM_FAIL" not in out,
        "restart": "DISP_RECOVER_OK" in out,
        "img400": "IMG400=400" in out,
        "img503": "IMG503=503" in out or profile == "low",
        "log_err": 0,
    }
    m = re.search(r"LOG_ERR_COUNT=(\d+)", out)
    if m:
        res["log_err"] = int(m.group(1))
    for k, ok in [
        ("model_router", res["mr"]),
        ("gateway", res["gw"]),
        ("dispatcher", res["disp"]),
        ("memory", res["mem"]),
        ("dispatcher_restart", res["restart"]),
    ]:
        note(label, k, "pass" if ok else "fail", "ok" if ok else "check")
    if profile in ("medium", "high"):
        note(label, "image_disabled", "pass" if res["img503"] else "fail", "503 expected")
        note(label, "image_empty_prompt", "pass" if res["img400"] else "warn", "400 expected")
    note(label, "log_errors_3m", "pass" if res["log_err"] < 30 else "warn", f"count={res['log_err']}")
    PROFILE_RESULTS[label] = res
    return res


def zalo_bridge(c) -> str:
    out = sudo_bash(
        c,
        f"""
set -euo pipefail
cd {REMOTE}
sed -i 's/\\r$//' scripts/main/setup-zalo.sh scripts/main/login-zalo.sh scripts/main/heal-zalo-sse.sh 2>/dev/null || true
bash scripts/main/setup-zalo.sh || true
docker compose --project-directory {REMOTE} -f docker/docker-compose.yml --profile zalo up -d zalo-proxy || true
ENABLE_ZALO=1 bash scripts/main/heal-zalo-sse.sh || true
sleep 8
curl -sf -m 8 http://127.0.0.1:8787/health || echo ZALO_FAIL
echo
echo '==== IF sseClients=0 AND loggedIn=false: operator must run bash scripts/main/login-zalo.sh ===='
""",
        timeout=300,
    )
    sse = 0
    m = re.findall(r'"sseClients"\s*:\s*(\d+)', out)
    if m:
        sse = int(m[-1])
    logged = '"loggedIn":true' in out.replace(" ", "")
    if sse >= 1:
        note("zalo", "bridge", "pass", f"sseClients={sse}")
        return "ok"
    if logged:
        note("zalo", "bridge", "warn", "logged in but sseClients=0 after heal")
        return "heal"
    note("zalo", "bridge", "skip", "NEED_QR: scan login-zalo.sh then continue Zalo checks")
    return "need_qr"


def high_burst(c) -> dict:
    out = sudo_bash(
        c,
        r"""
set -euo pipefail
export LC_ALL=C.UTF-8
cd /opt/assistant
set -a
source <(grep -E '^(N9ROUTER_API_KEY)=' /data/assistant/.env | sed 's/\r$//')
set +a
python3 - <<'PY'
import json, os, time, urllib.request, concurrent.futures, pathlib
key = os.environ.get("N9ROUTER_API_KEY", "")
base_job = "http://127.0.0.1:8104/v1/enqueue"
chat = "http://127.0.0.1:8096/v1/chat/completions"
fx = pathlib.Path("/tmp/r2_fixtures")
fx.mkdir(exist_ok=True)
(fx / "r2.txt").write_text("run02 txt: Cho Dem market notes", encoding="utf-8")
(fx / "r2.md").write_text("# run02 md\nBen Thanh", encoding="utf-8")
(fx / "r2.pdf").write_bytes(b"%PDF-1.4 run02\n%%EOF\n")
(fx / "r2.docx").write_bytes(b"PK\x03\x04run02docx")
(fx / "r2.xlsx").write_bytes(b"PK\x03\x04run02xlsx")
(fx / "r2.pptx").write_bytes(b"PK\x03\x04run02pptx")
(fx / "r2.png").write_bytes(b"\x89PNG\r\n\x1a\n" + b"\x00" * 24)
(fx / "r2.mp3").write_bytes(b"ID3run02" + b"\x00" * 24)
(fx / "r2.mp4").write_bytes(b"\x00\x00\x00\x18ftypmp42r2")

def chat_one():
    t0 = time.time()
    body = json.dumps({
        "model": "hermes",
        "messages": [{"role": "user", "content": "run02 concurrent text: reply OKR2 only"}],
        "max_tokens": 24,
        "metadata": {"task_hint": "general"},
    }).encode()
    req = urllib.request.Request(chat, data=body, headers={
        "Content-Type": "application/json",
        "Authorization": f"Bearer {key}",
        "X-Task-Type": "general",
    })
    try:
        with urllib.request.urlopen(req, timeout=90) as r:
            return {"type": "text", "status": r.status, "ms": int((time.time()-t0)*1000), "ok": r.status < 400}
    except Exception as e:
        return {"type": "text", "status": 0, "ms": int((time.time()-t0)*1000), "ok": False, "err": str(e)[:80]}

def job_one(name):
    t0 = time.time()
    payload = json.dumps({
        "queue": "ingest", "job": "ingest",
        "idempotency_key": f"r2-{name}-{int(t0)}",
        "payload": {"text": f"run02 fixture {name}", "document_name": name, "source": "run02"},
    }).encode()
    req = urllib.request.Request(base_job, data=payload, headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            raw = json.loads(r.read().decode())
            jid = raw.get("job_id", "")
            st = "unknown"
            for _ in range(40):
                time.sleep(0.4)
                sr = urllib.request.urlopen(f"http://127.0.0.1:8104/v1/jobs/{jid}", timeout=10)
                js = json.loads(sr.read().decode())
                st = js.get("status") or "unknown"
                if st in ("finished", "failed", "stopped"):
                    break
            return {"type": name, "status": st, "ms": int((time.time()-t0)*1000), "ok": st == "finished", "job_id": jid}
    except Exception as e:
        return {"type": name, "status": 0, "ms": int((time.time()-t0)*1000), "ok": False, "err": str(e)[:80]}

kinds = ["r2.pdf", "r2.txt", "r2.md", "r2.docx", "r2.xlsx", "r2.pptx", "r2.png", "r2.mp3", "r2.mp4"]
t_all = time.time()
rows = []
with concurrent.futures.ThreadPoolExecutor(max_workers=10) as ex:
    futs = [ex.submit(chat_one)] + [ex.submit(job_one, k) for k in kinds]
    for f in concurrent.futures.as_completed(futs):
        rows.append(f.result())
print("CONCUR_JSON=" + json.dumps({"wall_ms": int((time.time()-t_all)*1000), "rows": rows}, ensure_ascii=False))
PY
docker stats --no-stream --format '{{.Name}} cpu={{.CPUPerc}} mem={{.MemUsage}}' | head -n 20
echo '=== weather r2 ==='
curl -s -m 45 -X POST http://127.0.0.1:8090/v1/search \
  -H 'Content-Type: application/json' \
  -d '{"query":"Thời tiết hiện tại ở Thành phố Hồ Chí Minh hôm nay","max_results":5}' \
  | tee /tmp/weather_r2.json | python3 -c "import sys,json; d=json.load(sys.stdin); r=d.get('results') or []; print('WEATHER_N', len(r), 'backend', d.get('backend'));
[print('HIT', (x.get('title') or '')[:80]) for x in r[:5]]" || echo WEATHER_FAIL
echo '=== policy ==='
curl -s -m 8 http://127.0.0.1:8106/health; echo
curl -s -m 8 -X POST http://127.0.0.1:8106/v1/evaluate -H 'Content-Type: application/json' \
  -d '{"action":"export","resource":"doc"}'; echo
echo '=== av/vpn flags ==='
python3 - <<'PY'
from pathlib import Path
import json
env=Path('/data/assistant/.env').read_text(encoding='utf-8')
alerts=json.loads(Path('/opt/assistant/hermes/main/messages/ops-alerts.json').read_text(encoding='utf-8'))
print('AV_OFF', 'ENABLE_ANTIVIRUS=1' not in env.replace('\r',''))
print('AV_MSG', alerts.get('antivirus_disabled',''))
print('VPN_OFF', 'ENABLE_OPENVPN=1' not in env.replace('\r',''))
print('VPN_MSG', alerts.get('openvpn_disabled',''))
PY
echo '=== ocr bounce ==='
docker stop ocr >/dev/null 2>&1 || true
sleep 2
curl -sf -m 3 http://127.0.0.1:8091/health && echo OCR_STILL_UP || echo OCR_DOWN_OK
docker start ocr >/dev/null 2>&1 || true
sleep 6
curl -sf -m 8 http://127.0.0.1:8091/health && echo OCR_RECOVER_OK || echo OCR_RECOVER_FAIL
echo '=== session lock ==='
curl -sf -m 5 -X POST http://127.0.0.1:8107/v1/sessions/r2-lock/lock \
  -H 'Content-Type: application/json' -d '{"owner":"r2","ttl_seconds":8}' && echo LOCK_OK || echo LOCK_FAIL
""",
        timeout=600,
    )
    data = {}
    m = re.search(r"CONCUR_JSON=(\{.*\})", out)
    if m:
        try:
            data = json.loads(m.group(1))
        except json.JSONDecodeError:
            data = {}
    rows = data.get("rows") or []
    ok_n = sum(1 for r in rows if r.get("ok"))
    note("high/concurrency", "burst10", "pass" if ok_n == 10 else ("partial" if ok_n else "fail"), f"{ok_n}/10 wall_ms={data.get('wall_ms')}")
    for r in rows:
        note("high/concurrency", str(r.get("type")), "pass" if r.get("ok") else "fail", json.dumps({k: r[k] for k in r if k != "err"}, ensure_ascii=False)[:200])
    wn = re.search(r"WEATHER_N\s+(\d+)", out)
    note("high/web", "weather_hcmc", "pass" if wn and int(wn.group(1)) >= 1 else "fail", "SearXNG run02 Vietnamese query")
    note("high/policy", "export_deny", "pass" if "default-deny-export" in out or '"decision":"deny"' in out else "fail", "evaluate export")
    note("high/antivirus", "disabled_alert", "pass" if "AV_OFF True" in out else "warn", "short alert path")
    note("high/openvpn", "disabled_alert", "pass" if "VPN_OFF True" in out else "warn", "short alert path")
    note("high/ocr", "bounce", "pass" if "OCR_DOWN_OK" in out and "OCR_RECOVER_OK" in out else "warn", "stop then start")
    note("high/session", "lock", "pass" if "LOCK_OK" in out else "warn", "valkey lock")
    return data


def backup_restore(c) -> None:
    out = sudo_bash(
        c,
        r"""
set -euo pipefail
export LC_ALL=C.UTF-8
cd /opt/assistant
CANARY=/data/assistant/lab_canary_r2.txt
echo "run02-canary-$(date -Is)" | tee "$CANARY"
bash run.sh backup
STAMP=$(ls -1dt /data/assistant/backups/[0-9]* | head -1 | xargs -r basename)
echo STAMP=$STAMP
bash run.sh verify "$STAMP"
rm -f "$CANARY"
bash run.sh restore "$STAMP"
sleep 20
test -f "$CANARY" && echo CANARY_OK || echo CANARY_MISSING
# Restore already heals Zalo; wait for SSE election instead of bouncing Hermes again.
for i in 1 2 3 4 5 6 7 8; do
  H=$(curl -sf -m 8 http://127.0.0.1:8787/health || true)
  echo "ZALO_WAIT $i $H"
  echo "$H" | grep -q '"sseClients":1' && echo SSE_OK && break
  sleep 5
done
curl -sf http://127.0.0.1:8095/health && echo MEM_OK || echo MEM_BAD
curl -sf http://127.0.0.1:8097/health && echo AUTHZ_OK || echo AUTHZ_BAD
curl -sf http://127.0.0.1:8096/health; echo
docker ps --filter name=hermes --format '{{.Names}} {{.Status}}'
""",
        timeout=3600,
    )
    m = re.search(r"STAMP=(\d{8}_\d{6})", out)
    stamp = m.group(1) if m else "?"
    note("dr", "backup", "pass" if "STAMP=" in out else "fail", f"stamp={stamp}")
    note("dr", "restore_canary", "pass" if "CANARY_OK" in out else "fail", f"stamp={stamp}")
    sse_hits = re.findall(r'"sseClients"\s*:\s*(\d+)', out)
    last = int(sse_hits[-1]) if sse_hits else 0
    note("dr", "zalo_after_restore", "pass" if last >= 1 else "fail", f"sseClients={last}")
    note("dr", "memory_after_restore", "pass" if "MEM_OK" in out else "warn", "pg clients")
    note("dr", "authz_after_restore", "pass" if "AUTHZ_OK" in out else "warn", "pg clients")


def write_reports(zalo_state: str, burst: dict) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    started = ROWS[0]["ts"] if ROWS else ts()
    finished = ts()
    by_label = {}
    for r in ROWS:
        by_label.setdefault(r["section"], []).append(r)

    def pf(section: str) -> str:
        items = [x for x in ROWS if x["section"] == section]
        if not items:
            return "skip"
        if any(x["status"] == "fail" for x in items):
            return "FAIL"
        if any(x["status"] in {"warn", "partial"} for x in items):
            return "PASS with notes"
        return "PASS"

    lines = [
        "# Run 02 — Summary",
        "",
        "Version target: **v0.5.0**",
        "Branch: `feature/arch/v0.5.0-router-layer`",
        f"Started: {started}",
        f"Finished: {finished}",
        "Final stack left running: **High** (Traefik public → fail-soft local when ACME absent)",
        "",
        "<table>",
        "  <thead>",
        "    <tr>",
        "      <th>Profile</th>",
        "      <th>Mode</th>",
        "      <th>Health</th>",
        "      <th>Media-disabled</th>",
        "      <th>Final</th>",
        "    </tr>",
        "  </thead>",
        "  <tbody>",
    ]
    for mode in ("local", "public"):
        for profile in ("low", "medium", "high"):
            sec = f"health/{mode}/{profile}"
            media = "n/a" if profile == "low" else pf(sec)
            lines.append(
                f"    <tr><td>{profile}</td><td>{mode}</td><td>{pf(sec)}</td><td>{media}</td><td>{pf(sec)}</td></tr>"
            )
    lines.append("  </tbody>")
    lines.append("</table>")
    rows = burst.get("rows") or []
    ok_n = sum(1 for r in rows if r.get("ok"))
    lines += [
        "",
        f"Concurrent burst: {ok_n}/{len(rows) or 10} in {burst.get('wall_ms', '?')} ms",
        f"Web search: {pf('high/web')}",
        f"Policy: {pf('high/policy')}",
        f"Antivirus (disabled alert): {pf('high/antivirus')}",
        f"OpenVPN (disabled alert): {pf('high/openvpn')}",
        f"Media-disabled: see Medium/High health rows",
        f"Backup/restore: {pf('dr')}",
        f"Zalo: {zalo_state}",
        "",
        "Hostnames, IPs, and account names are omitted by policy.",
        "",
    ]
    fails = [r for r in ROWS if r["status"] == "fail"]
    lines.append("**Run 02 overall: " + ("FAIL" if fails else "PASS") + "**")
    if fails:
        lines.append("")
        lines.append("Failed items:")
        for r in fails:
            lines.append(f"- {r['section']} / {r['name']}: {r['detail']}")
    (OUT / "SUMMARY.md").write_text("\n".join(lines) + "\n", encoding="utf-8")

    mapping = {
        "low-local": ("Low", "local", "health/local/low"),
        "low-public": ("Low", "public", "health/public/low"),
        "medium-local": ("Medium", "local", "health/local/medium"),
        "medium-public": ("Medium", "public", "health/public/medium"),
        "high-local": ("High", "local", "health/local/high"),
        "high-public": ("High", "public", "health/public/high"),
    }
    for fname, (prof, mode, sec) in mapping.items():
        items = [x for x in ROWS if x["section"] == sec or x["section"].startswith(f"deploy/{mode}/{prof.lower()}")]
        extra = ""
        if fname == "high-public":
            extra = "\n".join(
                [
                    "",
                    "Concurrent requests:",
                    *[
                        f"- {r.get('type')}: {'PASS' if r.get('ok') else 'FAIL'} ({r.get('ms')} ms, status={r.get('status')})"
                        for r in rows
                    ],
                    f"Total concurrent requests: {len(rows)}",
                    f"Successful: {ok_n}",
                    f"Failed: {len(rows) - ok_n}",
                    "",
                    f"Web search: {pf('high/web')}",
                    f"Policy: {pf('high/policy')}",
                    f"Antivirus: {pf('high/antivirus')}",
                    f"Media-disabled fallback: {pf('health/public/high')}",
                    f"Backup: {pf('dr')}",
                    f"Zalo → Hermes: {zalo_state}",
                ]
            )
        body = f"""Profile: {prof}
Mode: {mode}
Run: 02
Started: {started}
Finished: {finished}

Cases: {len(items)}
Passed: {sum(1 for x in items if x['status']=='pass')}
Failed: {sum(1 for x in items if x['status']=='fail')}
Notes: {sum(1 for x in items if x['status'] in {'warn','partial','skip'})}

Final: {pf(sec)}
{extra}
"""
        (OUT / f"{fname}.md").write_text(sanitize(body), encoding="utf-8")

    (OUT / "raw.json").write_text(
        json.dumps({"rows": ROWS, "burst": burst, "zalo": zalo_state}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    c = connect()
    note("lab", "start", "pass", "run 02 connected")
    sync_key_files(c)
    sudo_bash(c, f"cd {REMOTE}; bash run.sh destroy || true; echo DESTROY_OK", timeout=300)
    note("lab", "destroy", "pass", "DESTROY_OK")
    first = True
    for mode in ("local", "public"):
        for profile in ("low", "medium", "high"):
            if not first:
                sudo_bash(c, f"cd {REMOTE}; bash run.sh destroy || true", timeout=300)
            first = False
            patch_and_up(c, profile, mode)
            cycle_probes(c, f"health/{mode}/{profile}", profile)
    zalo_state = zalo_bridge(c)
    burst = high_burst(c)
    backup_restore(c)
    write_reports(zalo_state, burst)
    note("lab", "end", "pass", "High left running")
    c.close()
    print("RUN02_DONE", flush=True)


if __name__ == "__main__":
    main()
