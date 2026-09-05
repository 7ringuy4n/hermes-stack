# -*- coding: utf-8 -*-
"""High fail-events: EICAR AV, concurrency ramp until fail, Hermes/Zalo auto-heal.

Leaves High running. Reports omit host/account.
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

EICAR = r"X5O!P%@AP[4\PZX54(P^)7CC)7}$EICAR-STANDARD-ANTIVIRUS-TEST-FILE!$H+H*"


def ts() -> str:
    return datetime.now(timezone.utc).astimezone().strftime("%Y-%m-%d %H:%M:%S %z")


def note(section: str, name: str, status: str, detail: str = "") -> None:
    detail = sanitize(detail)
    row = {"ts": ts(), "section": section, "name": name, "status": status, "detail": detail[:500]}
    ROWS.append(row)
    print(f"[{row['ts']}] {section} | {name} | {status} | {row['detail'][:180]}", flush=True)


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


def sync_watch(c) -> None:
    loc = ROOT / "scripts/main/stack-watch.sh"
    raw = loc.read_bytes().decode("utf-8").replace("\r\n", "\n").encode("utf-8")
    tmp = f"/tmp/stack-watch.{uuid.uuid4().hex[:8]}"
    sftp = c.open_sftp()
    with sftp.file(tmp, "wb") as f:
        f.write(raw)
    sftp.close()
    sudo_bash(c, f"install -m 755 '{tmp}' '{REMOTE}/scripts/main/stack-watch.sh' && rm -f '{tmp}'", timeout=60)
    note("sync", "stack-watch", "pass", "crash-recovery restart for exited Hermes")


def av_infected(c) -> None:
    out = sudo_bash(
        c,
        rf"""
set -euo pipefail
export LC_ALL=C.UTF-8
cd {REMOTE}
python3 - <<'PY'
from pathlib import Path
import re
p = Path('/data/assistant/.env')
t = p.read_text(encoding='utf-8')
if re.search(r'(?m)^ENABLE_ANTIVIRUS=', t):
    t = re.sub(r'(?m)^ENABLE_ANTIVIRUS=.*$', 'ENABLE_ANTIVIRUS=1', t)
else:
    t = t.rstrip() + '\nENABLE_ANTIVIRUS=1\n'
p.write_text(t, encoding='utf-8')
print('AV_FLAG=1')
PY
export ENABLE_ANTIVIRUS=1 ASSISTANT_PROFILE=high
# Bring ClamAV + av-gateway without tearing down High
set -a; source <(tr -d '\r' < /data/assistant/.env); set +a
docker compose --project-directory {REMOTE} -f docker/docker-compose.yml -f docker/docker-compose.media.yml -f docker/docker-compose.security.yml \
  --profile antivirus --env-file /data/assistant/.env up -d clamav av-gateway
echo 'wait clamd...'
ok=0
for i in $(seq 1 48); do
  if curl -sf -m 4 http://127.0.0.1:8098/health 2>/dev/null | grep -q '"clamd":true'; then
    echo CLAMD_READY i=$i
    ok=1
    break
  fi
  sleep 5
done
curl -s -m 8 http://127.0.0.1:8098/health || echo AV_HEALTH_FAIL
echo
if [ "$ok" != 1 ]; then
  echo CLAMD_NOT_READY
fi
printf '%s' '{EICAR}' > /tmp/eicar.com
printf 'hello clean run02\n' > /tmp/clean.txt
# clean
curl -s -m 60 -X POST http://127.0.0.1:8098/v1/scan -F session_id=r2-av-clean -F file=@/tmp/clean.txt || echo CLEAN_SCAN_FAIL
echo
# infected
curl -s -m 60 -X POST http://127.0.0.1:8098/v1/scan -F session_id=r2-av-eicar -F file=@/tmp/eicar.com || echo EICAR_SCAN_FAIL
echo
sleep 3
echo '=== CLEAN READY ==='
curl -s -m 8 http://127.0.0.1:8098/v1/sessions/r2-av-clean/ready; echo
echo '=== EICAR READY ==='
curl -s -m 8 http://127.0.0.1:8098/v1/sessions/r2-av-eicar/ready; echo
echo '=== SEC MGR EICAR ==='
curl -s -m 90 -X POST http://127.0.0.1:8093/v1/scan -F session_id=r2-sec-eicar -F file=@/tmp/eicar.com || echo SEC_FAIL
echo
""",
        timeout=420,
    )
    if "CLAMD_READY" in out:
        note("av", "clamd", "pass", "clamd ping true")
    else:
        note("av", "clamd", "fail", "clamd not ready in wait window")
    if '"infected":1' in out or '"blocked":true' in out or "INFECTED" in out:
        note("av", "eicar_infected", "pass", "EICAR blocked/infected")
    else:
        note("av", "eicar_infected", "fail", "no INFECTED/BLOCKED in EICAR session")
    if '"clean":1' in out or '"blocked":false' in out:
        note("av", "clean_file", "pass", "clean file not blocked")
    else:
        note("av", "clean_file", "warn", "clean verdict unclear")
    if "File contains risks" in out or "RISK" in out or "infected" in out.lower():
        note("av", "short_alert", "pass", "short user-facing risk/infected path")
    else:
        note("av", "short_alert", "warn", "security-manager message not seen")


def ramp_until_fail(c) -> None:
    out = sudo_bash(
        c,
        r"""
set -euo pipefail
export LC_ALL=C.UTF-8
set -a
source <(grep -E '^(OMNIROUTER_API_KEY)=' /data/assistant/.env | sed 's/\r$//')
set +a
python3 - <<'PY'
import json, os, time, urllib.request, concurrent.futures
key = os.environ.get("OMNIROUTER_API_KEY", "")
url = "http://127.0.0.1:8096/v1/chat/completions"

def one(i, n):
    t0 = time.time()
    body = json.dumps({
        "model": "hermes",
        "messages": [{"role": "user", "content": f"ramp n={n} i={i}: reply OK only"}],
        "max_tokens": 8,
        "metadata": {"task_hint": "general"},
    }).encode()
    req = urllib.request.Request(url, data=body, headers={
        "Content-Type": "application/json",
        "Authorization": f"Bearer {key}",
        "X-Task-Type": "general",
    })
    try:
        with urllib.request.urlopen(req, timeout=45) as r:
            return True, r.status, int((time.time()-t0)*1000)
    except Exception as e:
        return False, 0, int((time.time()-t0)*1000), str(e)[:80]

last_ok = 0
first_fail = None
fail_mode = ""
for n in (8, 16, 24, 32, 48):
    t0 = time.time()
    ok = 0
    errs = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=n) as ex:
        futs = [ex.submit(one, i, n) for i in range(n)]
        for f in concurrent.futures.as_completed(futs):
            res = f.result()
            if res[0]:
                ok += 1
            else:
                errs.append(res[-1] if len(res) > 3 else "fail")
    wall = int((time.time()-t0)*1000)
    print(f"RAMP n={n} ok={ok}/{n} wall_ms={wall} err={errs[:2]!r}")
    if ok == n:
        last_ok = n
    else:
        first_fail = n
        fail_mode = str(errs[:1])
        break
else:
    print("RAMP_NO_FAIL last_ok", last_ok)
print("LAST_ALL_SUCCESS", last_ok)
print("FIRST_FAIL", first_fail)
print("FAIL_MODE", fail_mode)
PY
""",
        timeout=600,
    )
    m_ok = re.search(r"LAST_ALL_SUCCESS\s+(\d+)", out)
    m_fail = re.search(r"FIRST_FAIL\s+(\S+)", out)
    last_ok = int(m_ok.group(1)) if m_ok else 0
    first_fail = m_fail.group(1) if m_fail else "None"
    note(
        "concurrency",
        "ramp_until_fail",
        "pass" if last_ok > 0 else "fail",
        f"last_all_success={last_ok} first_fail={first_fail}",
    )


def autoheal(c) -> None:
    out = sudo_bash(
        c,
        f"""
set -euo pipefail
export LC_ALL=C.UTF-8
cd {REMOTE}
echo '=== BEFORE ==='
docker ps --filter name=hermes --format '{{{{.Names}}}} {{{{.Status}}}}'
curl -sf -m 5 http://127.0.0.1:8787/health || echo ZALO_DOWN
echo
echo '=== STOP hermes-1 ==='
docker stop assistant-hermes-1 >/dev/null
sleep 2
docker ps -a --filter name=assistant-hermes-1 --format '{{{{.Names}}}} {{{{.Status}}}}'
bash scripts/main/stack-watch.sh || true
sleep 8
H1=$(docker inspect -f '{{{{.State.Running}}}}' assistant-hermes-1 2>/dev/null || echo false)
echo HERMES1_RUNNING=$H1
docker ps --filter name=hermes --format '{{{{.Names}}}} {{{{.Status}}}}'
# Wait for SSE after Hermes bounce before the proxy fault
for i in 1 2 3 4 5 6 7 8; do
  H=$(curl -sf -m 8 http://127.0.0.1:8787/health || true)
  echo "$H" | grep -q '"sseClients":1' && echo SSE_AFTER_HERMES_OK && break
  sleep 4
done
echo '=== STOP zalo-proxy ==='
docker stop zalo-proxy >/dev/null || true
sleep 2
bash scripts/main/zalo-watch.sh || true
sleep 5
ZP=$(docker inspect -f '{{{{.State.Running}}}}' zalo-proxy 2>/dev/null || echo false)
echo PROXY_RUNNING=$ZP
for i in 1 2 3 4 5 6; do
  H=$(curl -sf -m 8 http://127.0.0.1:8787/health || true)
  echo ZALO_TRY $i $H
  echo "$H" | grep -q '"sseClients":1' && echo SSE_OK && break
  sleep 5
done
echo '=== AFTER ==='
curl -sf -m 8 http://127.0.0.1:8096/health || echo MR_FAIL
echo
docker ps --filter name=hermes --format '{{{{.Names}}}} {{{{.Status}}}}'
""",
        timeout=180,
    )
    if "HERMES1_RUNNING=true" in out:
        note("heal", "hermes_crash", "pass", "stopped replica restored by stack-watch")
    else:
        note("heal", "hermes_crash", "fail", "replica not running after stack-watch")
    if "PROXY_RUNNING=true" in out:
        note("heal", "zalo_proxy", "pass", "zalo-watch restarted proxy")
    else:
        note("heal", "zalo_proxy", "fail", "proxy not running after zalo-watch")
    sse = re.findall(r'"sseClients"\s*:\s*(\d+)', out)
    last = int(sse[-1]) if sse else 0
    note("heal", "zalo_sse", "pass" if last >= 1 else "fail", f"sseClients={last}")


def write_report() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    fails = [r for r in ROWS if r["status"] == "fail"]
    lines = [
        "# Run 02 — Fail events (High, public fail-soft)",
        "",
        f"Started: {ROWS[0]['ts'] if ROWS else ts()}",
        f"Finished: {ts()}",
        "",
        "<table>",
        "  <thead>",
        "    <tr><th>Area</th><th>Fail event</th><th>Result</th><th>Detail</th></tr>",
        "  </thead>",
        "  <tbody>",
    ]
    for r in ROWS:
        if r["section"] in {"av", "concurrency", "heal"}:
            lines.append(
                f"    <tr><td>{r['section']}</td><td>{r['name']}</td><td>{r['status'].upper()}</td><td>{r['detail']}</td></tr>"
            )
    lines += [
        "  </tbody>",
        "</table>",
        "",
        "**Fail-event suite: " + ("FAIL" if fails else "PASS") + "**",
        "",
        "Reports omit hostnames, IPs, and account names.",
        "",
    ]
    (OUT / "fail-events.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    (OUT / "fail-events.json").write_text(json.dumps({"rows": ROWS}, ensure_ascii=False, indent=2), encoding="utf-8")


def main() -> None:
    c = connect()
    note("lab", "start", "pass", "fail-events on running High")
    sync_watch(c)
    av_infected(c)
    ramp_until_fail(c)
    autoheal(c)
    write_report()
    note("lab", "end", "pass", "High left running")
    c.close()
    print("FAIL_EVENTS_DONE", flush=True)


if __name__ == "__main__":
    main()
