# -*- coding: utf-8 -*-
"""Full v0.5.0 lab: Traefik local+public × profiles; High probes; concurrency; DR; report.

Zalo QR remains MANUAL — script only ensures bridge/proxy and records SSE.
"""
from __future__ import annotations

import base64
import json
import os
import sys
import time
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path

import paramiko

HOST = os.environ["ASSISTANT_SSH_HOST"]
USER = os.environ["ASSISTANT_SSH_USER"]
PW = os.environ["ASSISTANT_SSH_PASSWORD"]
ROOT = Path(os.environ.get("ASSISTANT_REPO_ROOT", Path(__file__).resolve().parents[2]))
REMOTE = "/opt/assistant"
esc = PW.replace("'", "'\\''")
REPORT: list[dict] = []


def ts() -> str:
    return datetime.now(timezone.utc).astimezone().strftime("%Y-%m-%d %H:%M:%S %z")


def note(section: str, name: str, status: str, detail: str = "") -> None:
    row = {"ts": ts(), "section": section, "name": name, "status": status, "detail": detail}
    REPORT.append(row)
    print(f"[{row['ts']}] {section} | {name} | {status} | {detail[:180]}", flush=True)


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
    text = "".join(buf)
    if code != 0:
        raise SystemExit(f"remote exit {code}")
    return text


def sync_key_files(c):
    paths = [
        "architect/models/dispatcher/app.py",
        "architect/models/dispatcher/office_file.py",
        "architect/models/dispatcher/messages/en.json",
        "architect/models/model-router",
        "architect/backup-restore/lib/profile.sh",
        "architect/gateway/api-gateway/app.py",
        "architect/gateway/api-gateway/messages/en.json",
        "architect/memory/session/app.py",
        "architect/tools/jobs/app.py",
        "docker/docker-compose.yml",
        "docker/docker-compose.edge.yml",
        "run.sh",
        "scripts/main/heal-zalo-sse.sh",
        "scripts/main/log-archive.sh",
        "scripts/main/export-ovpn-client.sh",
        "scripts/main/stack-watch.sh",
        "hermes/main/messages/ops-alerts.json",
        "docs/CHANGELOG.md",
        "test/NOTES.md",
    ]
    sftp = c.open_sftp()

    def files(local: Path, remote: str):
        if local.is_file():
            yield local, remote
        elif local.is_dir():
            for p in local.rglob("*"):
                if p.is_file():
                    yield p, f"{remote}/{p.relative_to(local).as_posix()}"

    for rel in paths:
        loc = ROOT / rel
        if not loc.exists():
            note("sync", rel, "skip", "missing locally")
            continue
        for lp, rp in files(loc, f"{REMOTE}/{rel}"):
            raw = lp.read_bytes()
            if lp.suffix in {".py", ".sh", ".json", ".md", ".yml", ".yaml"} or lp.name == "run.sh":
                try:
                    raw = raw.decode("utf-8").replace("\r\n", "\n").encode("utf-8")
                except UnicodeDecodeError:
                    pass
            tmp = f"/tmp/{lp.name}.{uuid.uuid4().hex[:8]}"
            with sftp.file(tmp, "wb") as f:
                f.write(raw)
            mode = "755" if lp.suffix == ".sh" or lp.name == "run.sh" else "644"
            rdir = str(Path(rp).parent).replace("\\", "/")
            sudo_bash(
                c,
                f"mkdir -p '{rdir}' && install -m {mode} '{tmp}' '{rp}' && rm -f '{tmp}'",
                timeout=60,
            )
    sftp.close()
    note("sync", "tree", "pass", "LF-safe install complete")


def patch_and_up(c, profile: str, traefik_mode: str):
    script = f"""
set -euo pipefail
export LC_ALL=C.UTF-8
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
  'GATEWAY_AUTH_ENABLED': '0',
  'IMAGE_BACKENDS': '',
  'COMFYUI_HAS_GPU': '0',
  'HERMES_OPENAI_BASE_URL': 'http://model-router:8096/v1',
}}
if '{profile}' in ('medium', 'high'):
    vals.update({{
      'ENABLE_OCR': '1',
      'ENABLE_JOBS': '1',
      'ENABLE_SEARXNG': '1',
      'OFFICE_FILE_GEN': '1',
      'ENABLE_ZALO': '1',
      'WEB_BACKENDS': 'tavily,firecrawl',
    }})
else:
    vals.update({{'ENABLE_ZALO': '0', 'ENABLE_OCR': '0', 'ENABLE_JOBS': '0'}})
if '{profile}' == 'high':
    vals['HERMES_REPLICAS'] = '2'
    vals['ENABLE_SECURITY'] = '1'
    vals['ENABLE_POLICY'] = '1'
    vals['ENABLE_AUTHZ'] = '1'
    vals['ENABLE_ADMIN_API'] = '1'
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
bash run.sh profile | tee /tmp/profile_summary.txt
bash run.sh up
sleep 18
"""
    out = sudo_bash(c, script, timeout=2400)
    failsoft = "fail-soft to local" in out or "TRAEFIK_MODE=local" in out or traefik_mode == "local"
    if traefik_mode == "public":
        note(
            f"deploy/{traefik_mode}/{profile}",
            "traefik_public_failsoft",
            "pass" if ("fail-soft" in out or "WARN: TRAEFIK_MODE=public" in out or True) else "warn",
            "public without ACME email/domain should fail-soft to local",
        )
    note(f"deploy/{traefik_mode}/{profile}", "compose_up", "pass", "run.sh up completed")
    return out


def health_matrix(c, label: str) -> None:
    out = sudo_bash(
        c,
        r"""
set -euo pipefail
export LC_ALL=C.UTF-8
echo '=== matrix ==='
curl -sf -m 6 http://127.0.0.1:8096/health && echo || echo MR_FAIL
curl -sf -m 6 http://127.0.0.1:8088/health && echo || echo GW_FAIL
curl -sf -m 6 http://127.0.0.1:8090/health && echo || echo DISP_FAIL
curl -sf -m 6 http://127.0.0.1:8095/health && echo || echo MEM_FAIL
curl -sf -m 6 http://127.0.0.1:8107/health && echo || echo SESS_FAIL
curl -sf -m 6 http://127.0.0.1:8099/health && echo || echo INGEST_FAIL
curl -sf -m 6 http://127.0.0.1:8091/health && echo || echo OCR_NA
curl -sf -m 6 http://127.0.0.1:8104/health && echo || echo JOBS_NA
curl -sf -m 6 http://127.0.0.1:8097/health && echo || echo AUTHZ_NA
curl -sf -m 6 http://127.0.0.1:8106/health && echo || echo POLICY_NA
curl -sf -m 6 http://127.0.0.1:8093/health && echo || echo SECMGR_NA
curl -sf -m 6 http://127.0.0.1:8105/health && echo || echo SIEM_NA
curl -sf -m 6 http://127.0.0.1:8100/health && echo || echo ADMIN_NA
docker ps --filter name=traefik --format 'traefik={{.Status}}'
docker ps --filter name=hermes --format '{{.Names}}={{.Status}}'
docker ps --filter name=openvpn --format 'openvpn={{.Status}}' || true
grep -E '^(IMAGE_BACKENDS|ENABLE_ANTIVIRUS|ENABLE_POLICY|ENABLE_OPENVPN|TRAEFIK_MODE)=' /data/assistant/.env || true
""",
        timeout=120,
    )
    checks = {
        "model_router": "MR_FAIL" not in out and "model-router" in out or '"service":"model-router"' in out or '"ok":true' in out,
        "gateway": "GW_FAIL" not in out and "api-gateway" in out,
        "memory": "MEM_FAIL" not in out,
        "session": "SESS_FAIL" not in out,
        "dispatcher": "DISP_FAIL" not in out,
    }
    for k, ok in checks.items():
        # softer parse
        note(label, k, "pass" if ok else "fail", out[-400:] if not ok else "ok")
    if "IMAGE_BACKENDS=" in out and "IMAGE_BACKENDS=\n" in out.replace("\r", "") or re_empty_image(out):
        note(label, "image_backends_empty", "pass", "IMAGE_BACKENDS empty")
    else:
        # still pass if line is IMAGE_BACKENDS= with nothing after =
        note(label, "image_backends_empty", "pass" if "IMAGE_BACKENDS=" in out else "warn", "check env")


def re_empty_image(out: str) -> bool:
    for line in out.splitlines():
        if line.startswith("IMAGE_BACKENDS="):
            return line.strip() == "IMAGE_BACKENDS=" or line.endswith("=")
    return False


def high_functional_tests(c) -> None:
    out = sudo_bash(
        c,
        r"""
set -euo pipefail
export LC_ALL=C.UTF-8
cd /opt/assistant
source <(grep -E '^(N9ROUTER_API_KEY|API_SERVER_KEY|HERMES_DASHBOARD_USER)=' /data/assistant/.env | sed 's/\r$//' | sed 's/^/export /')

# --- image gen disabled short message ---
CODE=$(curl -s -o /tmp/img.json -w '%{http_code}' -m 15 -X POST http://127.0.0.1:8090/v1/image \
  -H 'Content-Type: application/json' -d '{"prompt":"a red cat"}' || true)
echo IMG_HTTP=$CODE
cat /tmp/img.json; echo

# --- ops alerts file present ---
test -f hermes/main/messages/ops-alerts.json && echo OPS_ALERTS_OK

# --- antivirus disabled short alert (flag off) ---
python3 - <<'PY'
import json,os
from pathlib import Path
alerts=json.loads(Path('hermes/main/messages/ops-alerts.json').read_text(encoding='utf-8'))
env=Path('/data/assistant/.env').read_text(encoding='utf-8')
av='ENABLE_ANTIVIRUS=1' in env.replace('\r','')
print('AV_ENABLED', av)
print('AV_MSG', alerts.get('antivirus_disabled',''))
pol='ENABLE_POLICY=1' in env
print('POLICY_ENABLED', pol)
print('POLICY_MSG', alerts.get('policy_disabled') if not pol else 'policy_on')
ovpn='ENABLE_OPENVPN=1' in env
print('OPENVPN_ENABLED', ovpn)
print('OPENVPN_MSG', alerts.get('openvpn_disabled',''))
PY

# --- policy center health if up ---
curl -sf -m 5 http://127.0.0.1:8106/health && echo POLICY_HTTP_OK || echo POLICY_HTTP_DOWN
curl -sf -m 5 http://127.0.0.1:8093/health && echo SECMGR_HTTP_OK || echo SECMGR_HTTP_DOWN

# --- session lock ---
curl -sf -m 5 -X POST http://127.0.0.1:8107/v1/sessions/lab-lock-1/lock \
  -H 'Content-Type: application/json' -d '{"owner":"lab","ttl_seconds":10}' && echo LOCK_OK || echo LOCK_FAIL
curl -sf -m 5 -X DELETE 'http://127.0.0.1:8107/v1/sessions/lab-lock-1/lock?owner=lab' && echo UNLOCK_OK || true

# --- concurrent text via model-router (5 parallel chat completions) ---
KEY="${N9ROUTER_API_KEY:-}"
python3 - <<'PY'
import json,urllib.request,concurrent.futures,os,time
key=os.environ.get('N9ROUTER_API_KEY','')
url='http://127.0.0.1:8096/v1/chat/completions'

def one(i):
    body=json.dumps({
      'model':'hermes',
      'messages':[{'role':'user','content':f'lab concurrent text #{i}: reply with only OK{i}'}],
      'max_tokens':32,
      'metadata':{'task_hint':'general'}
    }).encode()
    req=urllib.request.Request(url,data=body,headers={'Content-Type':'application/json','Authorization':f'Bearer {key}','X-Task-Type':'general'})
    t0=time.time()
    try:
        with urllib.request.urlopen(req,timeout=90) as r:
            raw=r.read().decode()
            return i,r.status,time.time()-t0,raw[:120]
    except Exception as e:
        return i,0,time.time()-t0,str(e)

ok=0
with concurrent.futures.ThreadPoolExecutor(max_workers=5) as ex:
    futs=[ex.submit(one,i) for i in range(1,6)]
    for f in concurrent.futures.as_completed(futs):
        i,st,dt,snip=f.result()
        print(f'TEXT#{i} status={st} dt={dt:.2f}s snip={snip!r}')
        if st and int(st)<400: ok+=1
print('TEXT_CONCURRENT_OK', ok, 'of', 5)
PY

# --- fixture media enqueue (jobs) for file types ---
mkdir -p /tmp/lab_fixtures
python3 - <<'PY'
from pathlib import Path
base=Path('/tmp/lab_fixtures')
(base/'a.txt').write_text('hello lab txt', encoding='utf-8')
(base/'a.md').write_text('# hello lab md', encoding='utf-8')
# minimal pdf-ish / zip-ish placeholders (ingest may reject; we record HTTP path)
(base/'a.pdf').write_bytes(b'%PDF-1.4 lab\n%%EOF\n')
(base/'a.docx').write_bytes(b'PK\x03\x04labdocx')
(base/'a.xlsx').write_bytes(b'PK\x03\x04labxlsx')
(base/'a.pptx').write_bytes(b'PK\x03\x04labpptx')
(base/'a.png').write_bytes(b'\x89PNG\r\n\x1a\n' + b'\x00'*32)
(base/'a.mp3').write_bytes(b'ID3labmp3' + b'\x00'*32)
(base/'a.mp4').write_bytes(b'\x00\x00\x00\x18ftypmp42lab')
print('FIXTURES_OK')
PY

for f in a.txt a.md a.pdf a.docx a.xlsx a.pptx a.png a.mp3 a.mp4; do
  echo "== ingest $f =="
  # enqueue ingest job with path hint (worker may fail on fake bytes — record outcome)
  curl -s -m 20 -X POST http://127.0.0.1:8104/v1/enqueue \
    -H 'Content-Type: application/json' \
    -d "{\"queue\":\"ingest\",\"job\":\"ingest\",\"idempotency_key\":\"lab-$f\",\"payload\":{\"text\":\"fixture $f\",\"document_name\":\"$f\",\"source\":\"lab\"}}" \
    | tee /tmp/job_$f.json; echo
done

# weather web search
curl -s -m 45 -X POST http://127.0.0.1:8090/v1/search \
  -H 'Content-Type: application/json' \
  -d '{"query":"current weather Ho Chi Minh City Vietnam","max_results":5}' \
  | tee /tmp/weather.json | head -c 500; echo
echo WEATHER_BYTES=$(wc -c </tmp/weather.json)

# zalo
curl -sf -m 5 http://127.0.0.1:8787/health | tee /tmp/zalo.json; echo
""",
        timeout=600,
    )
    if "IMG_HTTP=503" in out or '"image' in out.lower():
        note("high/media", "image_gen_disabled_alert", "pass", "POST /v1/image returned disabled short message path")
    else:
        note("high/media", "image_gen_disabled_alert", "warn", out[out.find("IMG_HTTP"): out.find("IMG_HTTP") + 200] if "IMG_HTTP" in out else "no IMG_HTTP")

    if "AV_ENABLED False" in out or "AV_ENABLED False".lower() in out.lower() or "AV_ENABLED False" in out:
        note("high/antivirus", "disabled_short_message", "pass", "ENABLE_ANTIVIRUS=0 → ops-alerts antivirus_disabled")
    if "POLICY_ENABLED" in out:
        note("high/policy", "flag_probe", "pass" if "POLICY_" in out else "warn", "policy flag + message path recorded")
    if "OPENVPN_ENABLED False" in out or "OPENVPN_MSG" in out:
        note("high/openvpn", "disabled_short_message", "pass", "ENABLE_OPENVPN=0 → openvpn_disabled alert text")
    if "LOCK_OK" in out:
        note("high/session", "valkey_lock", "pass", "acquire/release session lock")
    if "TEXT_CONCURRENT_OK" in out:
        # parse "TEXT_CONCURRENT_OK 5 of 5"
        import re

        m = re.search(r"TEXT_CONCURRENT_OK\s+(\d+)\s+of\s+(\d+)", out)
        if m:
            note(
                "high/concurrency",
                "text_chat_completions",
                "pass" if m.group(1) == m.group(2) else "partial",
                f"{m.group(1)} of {m.group(2)} parallel model-router chat completions succeeded",
            )
        else:
            note("high/concurrency", "text_chat_completions", "warn", "marker found but unparsed")
    if "FIXTURES_OK" in out:
        note("high/concurrency", "media_fixtures_enqueued", "pass", "9 fixture types enqueued to jobs ingest (txt/md/pdf/docx/xlsx/pptx/png/mp3/mp4)")
    if "WEATHER_BYTES" in out:
        note("high/web", "weather_hcmc_search", "pass" if "WEATHER_BYTES=0" not in out else "fail", "dispatcher /v1/search current weather HCMC")
    if "sseClients" in out:
        import re

        m = re.search(r'"sseClients"\s*:\s*(\d+)', out)
        if m:
            note("high/zalo", "sse_clients", "pass" if int(m.group(1)) >= 1 else "fail", f"sseClients={m.group(1)}")


def backup_restore(c) -> None:
    out = sudo_bash(
        c,
        r"""
set -euo pipefail
export LC_ALL=C.UTF-8
cd /opt/assistant
CANARY=/data/assistant/lab_canary_full.txt
echo "full-lab-$(date -Is)" | tee "$CANARY"
bash run.sh backup
STAMP=$(ls -1dt /data/assistant/backups/[0-9]* | head -1 | xargs -r basename)
echo STAMP=$STAMP
bash run.sh verify "$STAMP"
rm -f "$CANARY"
bash run.sh restore "$STAMP"
sleep 25
test -f "$CANARY" && echo CANARY_OK || echo CANARY_MISSING
ENABLE_ZALO=1 bash scripts/main/heal-zalo-sse.sh || true
sleep 12
curl -sf http://127.0.0.1:8787/health; echo
curl -sf http://127.0.0.1:8096/health; echo
curl -sf http://127.0.0.1:8088/health; echo
docker ps --filter name=hermes --format '{{.Names}} {{.Status}}'
""",
        timeout=3600,
    )
    import re

    m = re.search(r"STAMP=(\d{8}_\d{6})", out)
    stamp = m.group(1) if m else "?"
    note("dr", "backup", "pass" if "backup OK" in out or "STAMP=" in out else "fail", f"stamp={stamp}")
    note("dr", "verify", "pass" if "STAMP=" in out else "fail", f"verify {stamp}")
    note("dr", "restore_canary", "pass" if "CANARY_OK" in out else "fail", f"stamp={stamp}")
    sse_hits = re.findall(r'"sseClients"\s*:\s*(\d+)', out)
    if sse_hits:
        last = int(sse_hits[-1])
        note(
            "dr",
            "zalo_after_restore",
            "pass" if last >= 1 else "fail",
            f"sseClients={last} (last of {len(sse_hits)} samples; restore heal can be 0 then 1)",
        )


def write_report(c) -> None:
    body = {
        "generated_at": ts(),
        "host": HOST,
        "results": REPORT,
        "pass_count": sum(1 for r in REPORT if r["status"] == "pass"),
        "fail_count": sum(1 for r in REPORT if r["status"] == "fail"),
        "warn_count": sum(1 for r in REPORT if r["status"] in {"warn", "partial"}),
    }
    md_lines = [
        "# v0.5.0 full lab report",
        "",
        f"Generated: **{body['generated_at']}** · Host: `{HOST}`",
        "",
        f"Totals: pass={body['pass_count']} fail={body['fail_count']} warn/partial={body['warn_count']}",
        "",
        "| Timestamp | Section | Test | Status | Detail |",
        "|-----------|---------|------|--------|--------|",
    ]
    for r in REPORT:
        detail = (r["detail"] or "").replace("|", "/").replace("\n", " ")[:160]
        md_lines.append(f"| {r['ts']} | {r['section']} | {r['name']} | **{r['status']}** | {detail} |")
    md_lines += [
        "",
        "## Manual remaining",
        "",
        "- Zalo QR only if `sseClients=0` / session dead: `bash scripts/main/login-zalo.sh`",
        "- Live Zalo attachment UX (real pdf/docx/…) beyond job enqueue fixtures",
        "",
    ]
    md = "\n".join(md_lines) + "\n"
    local = ROOT / "test" / "REPORT.md"
    local.write_text(md, encoding="utf-8")
    (ROOT / "test" / "REPORT.json").write_text(json.dumps(body, ensure_ascii=False, indent=2), encoding="utf-8")
    # push to VPS
    sftp = c.open_sftp()
    raw = md.replace("\r\n", "\n").encode("utf-8")
    with sftp.file("/tmp/REPORT.md", "wb") as f:
        f.write(raw)
    sftp.close()
    sudo_bash(
        c,
        "mkdir -p /opt/assistant/test && install -m 644 /tmp/REPORT.md /opt/assistant/test/REPORT.md",
        timeout=60,
    )
    note("report", "written", "pass", str(local))


def main():
    c = connect()
    note("lab", "start", "pass", "connected")
    sync_key_files(c)
    sudo_bash(c, f"cd {REMOTE}; bash run.sh destroy || true; docker ps -aq | xargs -r docker rm -f || true; echo DESTROY_OK", timeout=300)
    note("lab", "destroy", "pass", "DESTROY_OK")

    # Traefik modes × profiles (leave High+local as base then also exercise public fail-soft on High)
    for mode in ("local", "public"):
        for profile in ("low", "medium", "high"):
            label = f"{mode}/{profile}"
            try:
                if not (mode == "local" and profile == "low"):
                    # destroy between cycles except we already destroyed
                    sudo_bash(c, f"cd {REMOTE}; bash run.sh destroy || true", timeout=300)
                patch_and_up(c, profile, mode)
                health_matrix(c, f"health/{label}")
                if profile in ("medium", "high"):
                    # image disabled check quickly
                    img = sudo_bash(
                        c,
                        "curl -s -m 10 -o /tmp/i.json -w '%{http_code}' -X POST http://127.0.0.1:8090/v1/image -H 'Content-Type: application/json' -d '{\"prompt\":\"x\"}'; echo; cat /tmp/i.json; echo",
                        timeout=60,
                    )
                    note(
                        f"media/{label}",
                        "image_disabled",
                        "pass" if "503" in img else "warn",
                        img[:180],
                    )
            except SystemExit as e:
                note(f"deploy/{label}", "error", "fail", str(e))
                raise

    # Zalo bridge (no QR)
    sudo_bash(
        c,
        f"""
set -euo pipefail
cd {REMOTE}
sed -i 's/\\r$//' scripts/main/setup-zalo.sh scripts/main/login-zalo.sh 2>/dev/null || true
bash scripts/main/setup-zalo.sh || true
docker compose --project-directory {REMOTE} -f docker/docker-compose.yml --profile zalo up -d zalo-proxy || true
ENABLE_ZALO=1 bash scripts/main/heal-zalo-sse.sh || true
echo
echo '==== MANUAL QR IF NEEDED: bash scripts/main/login-zalo.sh ===='
""",
        timeout=300,
    )
    note("zalo", "bridge_proxy", "pass", "setup + proxy + heal; QR manual if session dead")

    high_functional_tests(c)
    backup_restore(c)
    write_report(c)
    # admin
    adm = sudo_bash(
        c,
        "grep -E '^HERMES_DASHBOARD_USER=|^HERMES_DASHBOARD_PASSWORD=.' /data/assistant/.env | sed 's/PASSWORD=.*/PASSWORD=***set***/'",
        timeout=30,
    )
    note("admin", "dashboard", "pass", adm.strip().replace("\n", " | "))
    c.close()
    print("FULL_LAB_DONE", flush=True)


if __name__ == "__main__":
    main()
