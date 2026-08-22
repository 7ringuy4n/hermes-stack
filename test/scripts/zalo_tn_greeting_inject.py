# -*- coding: utf-8 -*-
"""Inject Vietnamese morning greeting as Zalo user Tn via bridge /inject-event.

Resolves Tn from zalo_admin_users.txt on the lab host (id never committed).
Expects Hermes inbound + outbound send. Report: test/reports/run-zalo-tn-greeting/

Env: ASSISTANT_SSH_HOST, ASSISTANT_SSH_USER, ASSISTANT_SSH_PASSWORD
Optional: ZALO_TEST_USER_NAME (default Tn), ZALO_GREETING_TEXT,
          ZALO_GREETING_WAIT_S (default 90), ZALO_CONNECT_WAIT_S (default 180)
"""
from __future__ import annotations

import io
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from deploy_stack import connect, sudo_bash  # noqa: E402
from sanitize import sanitize as _sanitize  # noqa: E402

if hasattr(sys.stdout, "buffer"):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

ROOT = Path(os.environ.get("ASSISTANT_REPO_ROOT", Path(__file__).resolve().parents[2]))
OUT = ROOT / "test" / "reports" / "run-zalo-tn-greeting"
WANT_NAME = (os.environ.get("ZALO_TEST_USER_NAME") or "Tn").strip()
TEXT = (
    os.environ.get("ZALO_GREETING_TEXT") or "chúc một buổi sáng tốt lành"
).strip() or "chúc một buổi sáng tốt lành"
WAIT_S = int(os.environ.get("ZALO_GREETING_WAIT_S") or "90")
CONNECT_WAIT_S = int(os.environ.get("ZALO_CONNECT_WAIT_S") or "180")


def ts() -> str:
    return datetime.now(timezone.utc).astimezone().strftime("%Y-%m-%d %H:%M:%S %z")


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    c = connect()
    try:
        print(f"[{ts()}] inject greeting via Zalo bridge as {WANT_NAME!r}", flush=True)
        remote = rf"""
set -euo pipefail
export LC_ALL=C.UTF-8
cd /opt/assistant
set -a; . ./.env; set +a
python3 - <<'PY'
import json, time, urllib.request, subprocess, os
from pathlib import Path

want_name = {WANT_NAME!r}
text = {TEXT!r}
wait_s = {WAIT_S}
connect_wait_s = {CONNECT_WAIT_S}
tag = "greet-" + str(int(time.time()))
text = text + " [" + tag + "]"

def get(url, timeout=8):
    with urllib.request.urlopen(url, timeout=timeout) as r:
        return json.loads(r.read().decode() or "{{}}")

def hermes_logs(since="10m"):
    chunks = []
    ids = subprocess.check_output(
        ["docker", "ps", "-q", "--filter", "name=hermes"], text=True
    ).split()
    for cid in ids:
        try:
            chunks.append(
                subprocess.check_output(
                    ["docker", "logs", "--since", since, cid],
                    stderr=subprocess.STDOUT,
                    text=True,
                    errors="replace",
                )
            )
        except Exception:
            pass
    # Gateway often logs to replica files, not docker stdout.
    for root in ("/opt/data/replicas", "/data/assistant/replicas"):
        base = Path(root)
        if not base.is_dir():
            continue
        for glog in base.glob("*/logs/gateway.log"):
            try:
                chunks.append(glog.read_text(encoding="utf-8", errors="replace")[-400000:])
            except OSError:
                pass
        for alog in base.glob("*/logs/agent.log"):
            try:
                chunks.append(alog.read_text(encoding="utf-8", errors="replace")[-200000:])
            except OSError:
                pass
    return "\n".join(chunks)

def zalo_connected(blob: str) -> bool:
    if "Zalo: connected to bridge" in blob:
        return True
    for root in ("/opt/data/replicas", "/data/assistant/replicas"):
        base = Path(root)
        if not base.is_dir():
            continue
        for gs in base.glob("*/gateway_state.json"):
            try:
                st = json.loads(gs.read_text(encoding="utf-8", errors="replace"))
            except (OSError, json.JSONDecodeError):
                continue
            plat = (st.get("platforms") or {{}}).get("zalo") or {{}}
            if plat.get("state") == "connected":
                return True
    return False

health = get("http://127.0.0.1:8787/health")
if not health.get("loggedIn"):
    raise SystemExit("BRIDGE_NOT_LOGGED_IN")
print("SSE_CLIENTS", health.get("sseClients"))

ready_deadline = time.time() + connect_wait_s
while time.time() < ready_deadline:
    if zalo_connected(hermes_logs("15m")):
        print("ZALO_CONNECTED")
        break
    time.sleep(3)
else:
    raise SystemExit("ZALO_NOT_CONNECTED")

uid = ""
uname = ""
for path in (
    "/data/assistant/zalo_admin_users.txt",
    "/opt/data/zalo_admin_users.txt",
):
    p = Path(path)
    if not p.is_file():
        continue
    for line in p.read_text(encoding="utf-8", errors="replace").splitlines():
        raw = line.strip()
        if not raw or raw.startswith("#"):
            continue
        left, sep, right = raw.partition("|")
        cand = left.strip()
        name = right.strip()
        if not cand:
            continue
        if want_name and name.lower() == want_name.lower():
            uid, uname = cand, name
            break
        if not uid:
            uid, uname = cand, name or "admin"
    if uid and want_name and uname.lower() == want_name.lower():
        break
if not uid:
    raise SystemExit("NO_ADMIN_USER")
print("USER_NAME", uname)
print("TAG", tag)

tok = (os.environ.get("ZALO_PLUGIN_TOKEN") or "").strip()
headers = {{"Content-Type": "application/json"}}
if tok:
    headers["Authorization"] = "Bearer " + tok
payload = {{
    "type": "message",
    "payload": {{
        "threadId": uid,
        "threadType": "user",
        "senderId": uid,
        "senderName": uname,
        "text": text,
        "isSelf": False,
    }},
}}
body = json.dumps(payload).encode("utf-8")
req = urllib.request.Request(
    "http://127.0.0.1:8787/inject-event",
    data=body,
    method="POST",
    headers=headers,
)
t0 = time.time()
with urllib.request.urlopen(req, timeout=15) as r:
    inj = json.loads(r.read().decode() or "{{}}")
print("INJECT_OK", inj.get("ok"), "sse", health.get("sseClients"))

deadline = t0 + wait_s
inbound_ms = None
send_ms = None
timeout_hit = False
soul_blocked = False
while time.time() < deadline:
    since_s = max(5, int(time.time() - t0) + 5)
    logs = hermes_logs(str(since_s) + "s")
    if "deception_hide" in logs and "SOUL" in logs:
        soul_blocked = True
        print("SOUL_BLOCKED_DECEPTION_HIDE")
        break
    if inbound_ms is None and (tag in logs or "Zalo inbound:" in logs or "inbound queued" in logs or "inbound message:" in logs):
        inbound_ms = int((time.time() - t0) * 1000)
        print("INBOUND_MS", inbound_ms)
    if "queue turn timeout" in logs and (uid[-8:] in logs or tag in logs or uname in logs):
        timeout_hit = True
        print("QUEUE_TURN_TIMEOUT")
        break
    if "Zalo: send ok" in logs:
        send_ms = int((time.time() - t0) * 1000)
        print("SEND_OK_MS", send_ms)
        break
    if "[Zalo] Send failed" in logs:
        print("SEND_FAIL")
        raise SystemExit("ZALO_SEND_FAILED")
    time.sleep(1)

h2 = get("http://127.0.0.1:8787/health")
print("SSE_AFTER", h2.get("sseClients"), "loggedIn", h2.get("loggedIn"))

if soul_blocked:
    raise SystemExit("FAIL_SOUL_BLOCKED")
if timeout_hit:
    raise SystemExit("FAIL_QUEUE_TIMEOUT")
if send_ms is None:
    raise SystemExit("FAIL_NO_REPLY")
print("PASS", "inbound_ms", inbound_ms, "send_ms", send_ms)
PY
"""
        out = sudo_bash(c, remote, timeout=WAIT_S + CONNECT_WAIT_S + 120)
    finally:
        c.close()

    (OUT / "raw.log").write_text(_sanitize(out or ""), encoding="utf-8", errors="replace")
    print(out or "", flush=True)
    summary = {
        "ok": bool(out and "PASS" in out and "FAIL_" not in out),
        "user_name": WANT_NAME,
        "text": TEXT,
        "ts": ts(),
    }
    (OUT / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    if not out or "PASS" not in out or "FAIL_" in out:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
