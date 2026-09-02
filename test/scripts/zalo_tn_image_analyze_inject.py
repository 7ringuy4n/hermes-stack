# -*- coding: utf-8 -*-
"""Inject captioned image for Zalo user Tn via bridge /inject-event (VPS lab).

Default user id: 233767886566872937 (Tn DM thread). Places a real JPEG under
/opt/data/media/inbound/{threadId}/ inside Hermes, injects local-path media
(same shape as quote-reply / staged inbound), expects vision host reply — not
"Không mô tả được ảnh — gửi lại giúp mình."

Env: ASSISTANT_SSH_HOST, ASSISTANT_SSH_USER, ASSISTANT_SSH_PASSWORD
Optional: ZALO_TEST_USER_ID (default 233767886566872937), ZALO_TEST_USER_NAME (Tn),
          ZALO_IMAGE_CAPTION (default "hình gì đây"), ZALO_IMAGE_WAIT_S (120)
Report: test/reports/run-zalo-tn-image-analyze/
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
OUT = ROOT / "test" / "reports" / "run-zalo-tn-image-analyze"
TN_ID = (os.environ.get("ZALO_TEST_USER_ID") or "233767886566872937").strip()
WANT_NAME = (os.environ.get("ZALO_TEST_USER_NAME") or "Tn").strip()
CAPTION = (os.environ.get("ZALO_IMAGE_CAPTION") or "hình gì đây").strip() or "hình gì đây"
WAIT_S = int(os.environ.get("ZALO_IMAGE_WAIT_S") or "120")
CONNECT_WAIT_S = int(os.environ.get("ZALO_CONNECT_WAIT_S") or "180")
FAIL_LINE = "Không mô tả được ảnh — gửi lại giúp mình."


def ts() -> str:
    return datetime.now(timezone.utc).astimezone().strftime("%Y-%m-%d %H:%M:%S %z")


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    c = connect()
    try:
        print(
            f"[{ts()}] inject image analyze as {WANT_NAME!r} id={TN_ID}",
            flush=True,
        )
        remote = rf"""
set -euo pipefail
export LC_ALL=C.UTF-8
cd /opt/assistant
set -a; . ./.env; set +a
python3 - <<'PY'
import base64, json, os, subprocess, time, urllib.request
from pathlib import Path

uid = {TN_ID!r}
uname = {WANT_NAME!r}
caption = {CAPTION!r}
wait_s = {WAIT_S}
connect_wait_s = {CONNECT_WAIT_S}
fail_line = {FAIL_LINE!r}
tag = "img-" + str(int(time.time()))
text = caption + " [" + tag + "]"

TINY_JPEG = base64.b64decode(
    "/9j/4AAQSkZJRgABAQEAYABgAAD/2wBDAAgGBgcGBQgHBwcJCQgKDBQNDAsLDBkSEw8UHRof"
    "Hh0aHBwgJC4nICIsIxwcKDcpLDAxNDQ0Hyc5PTgyPC4zNDL/2wBDAQkJCQwLDBgNDRgyIRwh"
    "MjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjL/wAAR"
    "CAAQABADASIAAhEBAxEB/8QAFQABAQAAAAAAAAAAAAAAAAAAAAb/xAAUEAEAAAAAAAAAAAAA"
    "AAAAAAAA/8QAFQEBAQAAAAAAAAAAAAAAAAAAAwT/xAAUEQEAAAAAAAAAAAAAAAAAAAAA/9oA"
    "DAMBAAIRAxEAPwCwABmX/9k="
)

def get(url, timeout=8):
    with urllib.request.urlopen(url, timeout=timeout) as r:
        return json.loads(r.read().decode() or "{{}}")

def hermes_name():
    out = subprocess.check_output(
        ["docker", "ps", "--format", "{{{{.Names}}}}"], text=True
    )
    for line in out.splitlines():
        if "hermes" in line:
            return line.strip()
    return ""

def hermes_logs(since="10m"):
    h = hermes_name()
    if not h:
        return ""
    return subprocess.check_output(
        ["docker", "logs", "--since", since, h],
        stderr=subprocess.STDOUT,
        text=True,
        errors="replace",
    )

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

h = hermes_name()
print("HERMES", h)
if not h:
    raise SystemExit("NO_HERMES")

# Resolve allowlist name when present
def resolve_admin_user(want_id="", want_name="", paths=(
    "/data/assistant/zalo_admin_users.txt",
    "/opt/data/zalo_admin_users.txt",
)):
    for path in paths:
        p = Path(path)
        if not p.is_file():
            continue
        for line in p.read_text(encoding="utf-8", errors="replace").splitlines():
            raw = line.strip()
            if not raw or raw.startswith("#"):
                continue
            left, _, right = raw.partition("|")
            u, name = left.strip(), right.strip()
            if want_id and u == want_id:
                return u, name or want_name or "admin"
            if want_name and name.lower() == want_name.lower():
                return u, name
    if want_id:
        return want_id, want_name or "admin"
    raise RuntimeError("NO_ADMIN_USER")

try:
    uid, uname = resolve_admin_user(want_id=uid, want_name=uname)
except RuntimeError:
    uid, uname = uid, uname
print("USER", uid, uname)

# Stage probe JPEG inside Hermes (host bind is usually /data/assistant → /opt/data)
host_media = Path("/data/assistant/media/inbound") / uid
host_media.mkdir(parents=True, exist_ok=True)
host_img = host_media / "tn_image_probe.jpg"
host_img.write_bytes(TINY_JPEG)
container_path = f"/opt/data/media/inbound/{{uid}}/tn_image_probe.jpg"
print("HOST_IMAGE", host_img)
print("CONTAINER_PATH", container_path)

# Verify inside container
subprocess.check_call([
    "docker", "exec", h, "python3", "-c",
    f"import os; p={container_path!r}; print('exists', os.path.isfile(p), p)",
])

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
        "media": {{
            "kind": "image",
            "url": container_path,
            "fileName": "tn_image_probe.jpg",
            "ext": "jpg",
            "mime": "image/jpeg",
        }},
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
print("INJECT_OK", inj.get("ok"))

deadline = t0 + wait_s
send_ms = None
vision_ok = False
vision_fail = False
fail_sent = False
while time.time() < deadline:
    logs = hermes_logs("3m")
    if tag in logs and "inbound" in logs.lower():
        print("INBOUND_SEEN")
    if "attach_vision_read" in logs and tag in logs:
        vision_ok = True
        print("VISION_READ")
    if "attach_image_vision_reply" in logs and tag in logs:
        vision_ok = True
        print("VISION_REPLY")
    if "attach_vision_miss" in logs and tag in logs:
        print("VISION_MISS")
    if "attach_vision_empty" in logs and tag in logs:
        print("VISION_EMPTY")
    if "attach_image_vision_fail" in logs and tag in logs:
        vision_fail = True
        print("VISION_FAIL")
    if fail_line in logs and (tag in logs or uid[-8:] in logs):
        fail_sent = True
        print("FAIL_LINE_SENT")
        break
    if "Zalo: send ok" in logs and (tag in logs or uid[-8:] in logs):
        send_ms = int((time.time() - t0) * 1000)
        print("SEND_OK_MS", send_ms)
        if fail_line not in logs:
            break
    time.sleep(1)

print("FLOW_TAIL")
for line in hermes_logs("3m").splitlines():
    if tag in line or "attach_vision" in line or "attach_image_vision" in line:
        print(line[:240])

if fail_sent:
    raise SystemExit("FAIL_VISION_DESCRIBE_LINE")
if send_ms is None:
    raise SystemExit("FAIL_NO_REPLY")
if vision_fail and not vision_ok:
    raise SystemExit("FAIL_VISION_PIPELINE")
print("PASS", "send_ms", send_ms, "vision_ok", vision_ok)
PY
"""
        out = sudo_bash(c, remote, timeout=WAIT_S + CONNECT_WAIT_S + 180)
    finally:
        c.close()

    (OUT / "raw.log").write_text(_sanitize(out or ""), encoding="utf-8", errors="replace")
    print(out or "", flush=True)
    summary = {
        "ok": bool(out and "PASS" in out and "FAIL_" not in out),
        "user_id": TN_ID,
        "user_name": WANT_NAME,
        "caption": CAPTION,
        "ts": ts(),
    }
    (OUT / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    if not out or "PASS" not in out or "FAIL_" in out:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
