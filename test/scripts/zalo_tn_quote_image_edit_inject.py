#!/usr/bin/env python3
"""VPS lab: edit a staged image by replying to its Zalo quote and deliver it."""
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
OUT = ROOT / "test" / "reports" / "run-zalo-tn-quote-image-edit"
TN_ID = (os.environ.get("ZALO_TEST_USER_ID") or "233767886566872937").strip()
TN_NAME = (os.environ.get("ZALO_TEST_USER_NAME") or "Tn").strip()
INSTRUCTION = (
    os.environ.get("ZALO_IMAGE_EDIT_INSTRUCTION")
    or "Giữ nguyên ngôi nhà, cây, mặt trời và bố cục; chuyển ảnh thành tranh màu nước tinh tế."
).strip()
WAIT_S = int(os.environ.get("ZALO_IMAGE_EDIT_WAIT_S") or "420")


def ts() -> str:
    return datetime.now(timezone.utc).astimezone().strftime("%Y-%m-%d %H:%M:%S %z")


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    client = connect()
    try:
        remote = rf'''
set -euo pipefail
cd /opt/assistant
set -a; . ./.env; set +a
python3 - <<'PY'
import json, os, pwd, struct, subprocess, time, urllib.request, zlib
from pathlib import Path

uid={TN_ID!r}
uname={TN_NAME!r}
instruction={INSTRUCTION!r}
wait_s={WAIT_S}
tag="quote-edit-" + str(int(time.time()))

def png(width, height):
    rows=[]
    for y in range(height):
        row=bytearray([0])
        for x in range(width):
            color=(145, 205, 238, 255) if y < 530 else (88, 158, 82, 255)
            if (x - 625) ** 2 + (y - 120) ** 2 < 62 ** 2:
                color=(251, 196, 55, 255)
            if 225 <= x <= 505 and 360 <= y <= 565:
                color=(239, 205, 153, 255)
            roof_height=abs(x - 365) * 3 // 4
            if 185 <= x <= 545 and 255 + roof_height <= y <= 370:
                color=(153, 65, 54, 255)
            if 330 <= x <= 405 and 445 <= y <= 565:
                color=(111, 72, 52, 255)
            if (260 <= x <= 315 or 440 <= x <= 485) and 405 <= y <= 460:
                color=(82, 151, 188, 255)
            if 575 <= x <= 610 and 375 <= y <= 565:
                color=(104, 70, 42, 255)
            if (x - 592) ** 2 + (y - 330) ** 2 < 92 ** 2:
                color=(47, 125, 67, 255)
            row.extend(color)
        rows.append(bytes(row))
    def chunk(kind, data):
        return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data) & 0xffffffff)
    return b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0)) + chunk(b"IDAT", zlib.compress(b"".join(rows), 9)) + chunk(b"IEND", b"")

def hermes_name():
    names=subprocess.check_output(["docker","ps","--format","{{{{.Names}}}}"], text=True).splitlines()
    return next((name for name in names if name.startswith("assistant-hermes-")), "")

def logs(since="10m"):
    name=hermes_name()
    if not name:
        return ""
    return subprocess.check_output(["docker","logs","--since",since,name], stderr=subprocess.STDOUT, text=True, errors="replace")

def zalo_journal(since_epoch):
    try:
        account=os.environ.get("SUDO_USER") or "tn"
        runtime="/run/user/" + str(pwd.getpwnam(account).pw_uid)
        return subprocess.check_output(
            [
                "runuser", "-u", account, "--", "env",
                "XDG_RUNTIME_DIR=" + runtime,
                "DBUS_SESSION_BUS_ADDRESS=unix:path=" + runtime + "/bus",
                "journalctl", "--user", "-u", "com.hermes.zaloplugin",
                "--since", "@" + str(int(since_epoch)), "--no-pager",
            ],
            stderr=subprocess.STDOUT,
            text=True,
            errors="replace",
        )
    except subprocess.CalledProcessError:
        return ""

health=json.loads(urllib.request.urlopen("http://127.0.0.1:8787/health", timeout=8).read().decode() or "{{}}")
if not health.get("loggedIn"):
    raise SystemExit("BRIDGE_NOT_LOGGED_IN")
if not hermes_name():
    raise SystemExit("NO_HERMES")

host_dir=Path("/data/assistant/media/inbound") / uid
host_dir.mkdir(parents=True, exist_ok=True)
host_source=host_dir / (tag + ".png")
host_source.write_bytes(png(768, 768))
container_source="/opt/data/media/inbound/" + uid + "/" + host_source.name
started=time.time()

token=(os.environ.get("ZALO_PLUGIN_TOKEN") or "").strip()
headers={{"Content-Type":"application/json"}}
if token:
    headers["Authorization"]="Bearer " + token
quoted={{
    "msgType":"chat.photo",
    "msgId":"source-" + tag,
    "cliMsgId":"source-" + tag,
    "content":container_source,
}}
payload={{"type":"message","payload":{{
    "threadId":uid,
    "threadType":"user",
    "senderId":uid,
    "senderName":uname,
    "messageId":tag,
    "text":instruction,
    "isSelf":False,
    "quote":quoted,
    "quoted":quoted,
}}}}
request=urllib.request.Request(
    "http://127.0.0.1:8787/inject-event",
    data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
    method="POST",
    headers=headers,
)
reply=json.loads(urllib.request.urlopen(request, timeout=15).read().decode() or "{{}}")
print("INJECT_OK", reply.get("ok"), "TAG", tag)

artifact=None
delivered=False
deadline=time.time()+wait_s
while time.time() < deadline:
    candidates=[]
    for root in (Path("/data/assistant/media/out"), Path("/opt/data/media/out")):
        if root.is_dir():
            candidates.extend(p for p in root.glob("image-edit-*") if p.is_file() and p.stat().st_mtime >= started)
    if candidates:
        artifact=max(candidates, key=lambda p: p.stat().st_mtime)
    recent=logs("10m")
    journal=zalo_journal(started)
    delivered=(
        ("send-attachment path" in recent and "image-edit-" in recent)
        or (
            "RAW message: type=user thread=" + uid in journal
            and "self=true msgType=chat.photo" in journal
        )
    )
    if artifact is not None and delivered and "image_edit_shortcut" in recent:
        break
    time.sleep(2)

if artifact is None:
    raise SystemExit("FAIL_NO_EDIT_ARTIFACT")
blob=artifact.read_bytes()
magic_ok=blob.startswith(b"\x89PNG\r\n\x1a\n") or blob.startswith(b"\xff\xd8\xff") or (blob.startswith(b"RIFF") and blob[8:12] == b"WEBP")
if not magic_ok or len(blob) < 80000:
    raise SystemExit("FAIL_BAD_EDIT_ARTIFACT")
if not delivered:
    raise SystemExit("FAIL_NOT_DELIVERED_TO_ZALO")

recent=logs("10m")
for line in recent.splitlines():
    if tag in line or "image_edit_shortcut" in line or ("send-attachment path" in line and "image-edit-" in line):
        print(line[:300])
for line in zalo_journal(started).splitlines():
    if "RAW message: type=user thread=" + uid in line or "self=true msgType=chat.photo" in line:
        print(line[:300])
print("ARTIFACT", artifact.name, "BYTES", len(blob))
print("PASS_QUOTED_IMAGE_EDIT_DELIVERED")
PY
'''
        output = sudo_bash(client, remote, timeout=WAIT_S + 180)
    finally:
        client.close()

    safe = _sanitize(output or "")
    (OUT / "raw.log").write_text(safe, encoding="utf-8", errors="replace")
    passed = "PASS_QUOTED_IMAGE_EDIT_DELIVERED" in safe and "FAIL_" not in safe
    (OUT / "summary.json").write_text(
        json.dumps({"ok": passed, "user_name": TN_NAME, "ts": ts()}, indent=2) + "\n",
        encoding="utf-8",
    )
    print(safe, flush=True)
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
