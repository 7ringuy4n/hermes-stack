# -*- coding: utf-8 -*-
"""Simulate concurrent Zalo-originated chat turns against a live lab stack.

Uses zalo-api POST /v1/zalo/chat when available; falls back to Hermes health-only
if token/API missing (records SKIP). Never opens a second Zalo SSE client.

Env: ASSISTANT_SSH_HOST, ASSISTANT_SSH_USER, ASSISTANT_SSH_PASSWORD
Optional: ZALO_API_TOKEN, ZALO_CONCURRENT_MAX (default 24)
Reports: test/reports/run-zalo-concurrent/ (no host/account)
"""
from __future__ import annotations

import base64
import json
import os
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path

import paramiko

sys.path.insert(0, str(Path(__file__).resolve().parent))
from sanitize import sanitize

HOST = os.environ["ASSISTANT_SSH_HOST"]
USER = os.environ["ASSISTANT_SSH_USER"]
PW = os.environ["ASSISTANT_SSH_PASSWORD"]
ROOT = Path(os.environ.get("ASSISTANT_REPO_ROOT", Path(__file__).resolve().parents[2]))
OUT = ROOT / "test" / "reports" / "run-zalo-concurrent"
MAX_N = int(os.environ.get("ZALO_CONCURRENT_MAX", "24"))
esc = PW.replace("'", "'\\''")


def ts() -> str:
    return datetime.now(timezone.utc).astimezone().strftime("%Y-%m-%d %H:%M:%S %z")


def connect():
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect(HOST, username=USER, password=PW, timeout=30, allow_agent=False, look_for_keys=False)
    return c


def sudo_bash(c, script: str, timeout: int = 600) -> str:
    b64 = base64.b64encode(script.encode("utf-8")).decode("ascii")
    cmd = f"echo '{esc}' | sudo -S bash -lc \"echo {b64} | base64 -d | bash\""
    _i, o, e = c.exec_command(cmd, timeout=timeout, get_pty=True)
    chan = o.channel
    buf: list[str] = []
    while True:
        while chan.recv_ready():
            chunk = chan.recv(8192).decode("utf-8", "replace")
            sys.stdout.write(chunk)
            sys.stdout.flush()
            buf.append(chunk)
        while chan.recv_stderr_ready():
            chunk = chan.recv_stderr(8192).decode("utf-8", "replace")
            sys.stdout.write(chunk)
            sys.stdout.flush()
            buf.append(chunk)
        if chan.exit_status_ready() and not chan.recv_ready() and not chan.recv_stderr_ready():
            break
        time.sleep(0.1)
    code = chan.recv_exit_status()
    text = sanitize("".join(buf))
    if code != 0:
        raise SystemExit(f"remote exit {code}")
    return text


def bridge_health(c) -> dict:
    out = sudo_bash(
        c,
        r'''
set -euo pipefail
curl -fsS -m 8 http://127.0.0.1:8787/health || echo '{"ok":false}'
''',
        timeout=60,
    )
    line = [x for x in out.strip().splitlines() if x.startswith("{")][-1]
    try:
        return json.loads(line)
    except json.JSONDecodeError:
        return {"ok": False, "raw": sanitize(out)[:200]}


def fire_burst(c, n: int, tag: str) -> dict:
    """Run N parallel !zalo whoami-style probes via zalo-api on the VPS."""
    script = f'''
set -euo pipefail
cd /opt/assistant
set -a; . ./.env; set +a
TOK="${{ZALO_API_TOKEN:-}}"
PORT="${{ZALO_API_PORT:-8100}}"
if [[ -z "$TOK" ]]; then
  echo 'RESULT:{{"status":"SKIP","reason":"no_zalo_api_token"}}'
  exit 0
fi
# bridge ownId as bot; synthetic senders
OWN=$(curl -fsS -m 5 http://127.0.0.1:8787/health | python3 -c 'import sys,json;print(json.load(sys.stdin).get("ownId",""))' || true)
export TOK PORT OWN
N={n}
TAG={tag}
ok=0; fail=0
tmpdir=$(mktemp -d)
fire() {{
  i="$1"
  sid="9${{i}}001${{i}}22"
  code=$(curl -sS -m 45 -o "$tmpdir/r-$i.json" -w "%{{http_code}}" \
    -X POST "http://127.0.0.1:${{PORT}}/v1/zalo/chat" \
    -H "Authorization: Bearer ${{TOK}}" -H "Content-Type: application/json" \
    -d "{{\\"sender_id\\":\\"$sid\\",\\"thread_id\\":\\"$sid\\",\\"text\\":\\"$TAG-$i ping\\",\\"chat_type\\":\\"user\\",\\"bot_id\\":\\"$OWN\\"}}" || echo 000)
  echo "$code" > "$tmpdir/c-$i.txt"
}}
export -f fire
export tmpdir TAG
seq 1 $N | xargs -P $N -I{{}} bash -c 'fire "$@"' _ {{}}
for i in $(seq 1 $N); do
  code=$(cat "$tmpdir/c-$i.txt" 2>/dev/null || echo 000)
  if [[ "$code" =~ ^2 ]]; then ok=$((ok+1)); else fail=$((fail+1)); fi
done
rm -rf "$tmpdir"
echo "RESULT:{{\\"status\\":\\"DONE\\",\\"n\\":$N,\\"ok\\":$ok,\\"fail\\":$fail,\\"tag\\":\\"$TAG\\"}}"
'''
    out = sudo_bash(c, script, timeout=900)
    for line in out.splitlines():
        if line.startswith("RESULT:"):
            return json.loads(line[len("RESULT:") :])
    return {"status": "ERROR", "detail": sanitize(out)[-300:]}


def hermes_ok(c) -> bool:
    out = sudo_bash(
        c,
        r'''
set -euo pipefail
ids=$(docker ps -q --filter name=hermes || true)
n=$(echo "$ids" | grep -c . || true)
echo "hermes_count=$n"
docker ps --filter name=hermes --format '{{.Names}} {{.Status}}' || true
''',
        timeout=60,
    )
    return "hermes_count=0" not in out


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    c = connect()
    report: dict = {"ts": ts(), "bursts": [], "bridge_before": {}, "bridge_after": {}}
    report["bridge_before"] = bridge_health(c)
    print("bridge_before", sanitize(json.dumps(report["bridge_before"])), flush=True)

    last_ok = 0
    first_fail = None
    for n in (4, 8, 16, 24):
        if n > MAX_N:
            break
        tag = f"zalo-c-a"
        t0 = time.time()
        res = fire_burst(c, n, tag)
        res["elapsed_s"] = round(time.time() - t0, 2)
        report["bursts"].append(res)
        print("burst", sanitize(json.dumps(res)), flush=True)
        if res.get("status") == "SKIP":
            break
        if res.get("fail", 1) == 0 and res.get("ok", 0) == n:
            last_ok = n
        else:
            first_fail = n
            break
        time.sleep(2)

    report["bridge_after"] = bridge_health(c)
    report["hermes_up"] = hermes_ok(c)
    report["last_all_success_n"] = last_ok
    report["first_fail_n"] = first_fail
    report["sse_ok"] = (
        report["bridge_after"].get("sseClients") == 1
        and report["bridge_after"].get("loggedIn") is True
    )

    (OUT / "raw.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    md = [
        "# Zalo concurrent lab",
        "",
        f"- Timestamp: `{report['ts']}`",
        f"- Last all-success N: **{last_ok}**",
        f"- First-fail N: **{first_fail if first_fail is not None else 'none ≤ max'}**",
        f"- SSE single owner after: **{report['sse_ok']}**",
        f"- Hermes up: **{report['hermes_up']}**",
        "",
        "## Bursts",
        "",
    ]
    for b in report["bursts"]:
        md.append(f"- `{sanitize(json.dumps(b))}`")
    (OUT / "SUMMARY.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    print("wrote", OUT, flush=True)
    c.close()


if __name__ == "__main__":
    main()
