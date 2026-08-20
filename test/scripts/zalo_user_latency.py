# -*- coding: utf-8 -*-
"""Zalo Bridge latency: send a short user line as an allowlisted DM (SSE inject).

Uses POST {bridge}/inject-event so Hermes consumes the same SSE path as a real
Zalo inbound. Does not open a second SSE client. Does not call Traefik chat.

Env: ASSISTANT_SSH_HOST, ASSISTANT_SSH_USER, ASSISTANT_SSH_PASSWORD
Optional: ZALO_TEST_USER_NAME (match zalo_admin_users.txt display name),
          ZALO_LATENCY_TEXT (default hi), ZALO_LATENCY_SLO_MS (default 5000),
          ZALO_LATENCY_WAIT_S (default 90)
          ZALO_CONNECT_WAIT_S (default 180)
Reports: test/reports/run-zalo-user-latency/ (no host/account/ids)
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
OUT = ROOT / "test" / "reports" / "run-zalo-user-latency"
WANT_NAME = (os.environ.get("ZALO_TEST_USER_NAME") or "Tn").strip()
TEXT = (os.environ.get("ZALO_LATENCY_TEXT") or "hi").strip() or "hi"
SLO_MS = int(os.environ.get("ZALO_LATENCY_SLO_MS") or "5000")
WAIT_S = int(os.environ.get("ZALO_LATENCY_WAIT_S") or "90")
CONNECT_WAIT_S = int(os.environ.get("ZALO_CONNECT_WAIT_S") or "180")


def ts() -> str:
    return datetime.now(timezone.utc).astimezone().strftime("%Y-%m-%d %H:%M:%S %z")


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    c = connect()
    try:
        print(f"[{ts()}] inject via Zalo bridge as named admin user", flush=True)
        remote = rf"""
set -euo pipefail
export LC_ALL=C.UTF-8
cd /opt/assistant
set -a; . ./.env; set +a
python3 - <<'PY'
import json, time, urllib.request, subprocess
from pathlib import Path

want_name = {WANT_NAME!r}
text = {TEXT!r}
wait_s = {WAIT_S}
connect_wait_s = {CONNECT_WAIT_S}
slo_ms = {SLO_MS}

def get(url, timeout=8):
    with urllib.request.urlopen(url, timeout=timeout) as r:
        return json.loads(r.read().decode() or "{{}}")

def hermes_logs(since="10m"):
    chunks = []
    ids = subprocess.check_output(["docker", "ps", "-q", "--filter", "name=hermes"], text=True).split()
    for cid in ids:
        chunks.append(
            subprocess.check_output(
                ["docker", "logs", "--since", since, cid],
                stderr=subprocess.STDOUT,
                text=True,
                errors="replace",
            )
        )
    for root in ("/opt/data/replicas", "/data/assistant/replicas"):
        base = Path(root)
        if not base.is_dir():
            continue
        for rep in base.glob("*"):
            for rel in (
                "logs/agent.log",
                "logs/gateway.log",
                "logs/gateways/default/current",
            ):
                p = rep / rel
                try:
                    if p.is_file():
                        chunks.append(p.read_text(encoding="utf-8", errors="replace")[-200000:])
                except OSError:
                    pass
            gs = rep / "gateway_state.json"
            try:
                if gs.is_file():
                    chunks.append(gs.read_text(encoding="utf-8", errors="replace"))
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
    blob = hermes_logs("15m")
    if zalo_connected(blob):
        print("ZALO_CONNECTED")
        break
    time.sleep(3)
else:
    raise SystemExit("ZALO_NOT_CONNECTED")

uid = ""
uname = ""
for path in ("/data/assistant/zalo_admin_users.txt", "/opt/data/zalo_admin_users.txt"):
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

tok = ( __import__("os").environ.get("ZALO_PLUGIN_TOKEN") or "" ).strip()
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
noise = False
needle = "name=" + repr(uname)
cut = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(t0))
while time.time() < deadline:
    logs = hermes_logs("3m")
    fresh = []
    for line in logs.splitlines():
        if len(line) >= 19 and line[0:4].isdigit() and line[:19] < cut:
            continue
        fresh.append(line)
    logs = "\n".join(fresh)
    if inbound_ms is None and "Zalo inbound:" in logs:
        inbound_ms = int((time.time() - t0) * 1000)
        print("INBOUND_MS", inbound_ms)
    if "Zalo: send ok" in logs:
        send_ms = int((time.time() - t0) * 1000)
        print("SEND_OK_MS", send_ms)
        break
    if "[Zalo] Send failed" in logs:
        send_ms = int((time.time() - t0) * 1000)
        print("SEND_FAIL_MS", send_ms)
        raise SystemExit("ZALO_SEND_DISCONNECTED")
    if "drop gateway noise" in logs or ("Request payload too large (413)" in logs):
        noise = True
        print("NOISE_OR_413")
        break
    time.sleep(1)

h2 = get("http://127.0.0.1:8787/health")
print("SSE_AFTER", h2.get("sseClients"), "loggedIn", h2.get("loggedIn"))
if send_ms is None:
    print("RESULT_FAIL timeout_or_no_send inbound_ms", inbound_ms, "noise", noise)
    raise SystemExit(2)
ok_slo = send_ms <= slo_ms
quotaish = False
blob = logs.lower()
for tok in ("429", "quota", "rate limit", "rate-limit", "no healthy", "failover", "switching model", "try next", "provider unavailable"):
    if tok in blob:
        quotaish = True
        break
print("RESULT", json.dumps({{"send_ms": send_ms, "inbound_ms": inbound_ms, "slo_ms": slo_ms, "pass": ok_slo or quotaish, "quota_or_model_switch": quotaish, "text_len": len(text)}}))
if not ok_slo and quotaish:
    print("SLO_EXEMPT quota_or_free_model_switch")
elif not ok_slo:
    raise SystemExit(3)
PY
"""
        out = sudo_bash(c, remote, timeout=WAIT_S + CONNECT_WAIT_S + 90)
        print(_sanitize(out), flush=True)
        (OUT / "raw.txt").write_text(_sanitize(out), encoding="utf-8")
        if "RESULT" not in out or "RESULT_FAIL" in out:
            print("FAIL zalo user latency", flush=True)
            return 1
        print(f"[{ts()}] done", flush=True)
        return 0
    finally:
        c.close()


if __name__ == "__main__":
    raise SystemExit(main())

