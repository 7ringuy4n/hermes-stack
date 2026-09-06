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
TN_ID = (os.environ.get("ZALO_TEST_USER_ID") or "").strip()
TN_NAME = (os.environ.get("ZALO_TEST_USER_NAME") or "Tn").strip()
INSTRUCTION = (
    os.environ.get("ZALO_IMAGE_EDIT_INSTRUCTION")
    or "Giữ nguyên ngôi nhà, cây, mặt trời và bố cục; chuyển ảnh thành tranh màu nước tinh tế."
).strip()
WAIT_S = int(os.environ.get("ZALO_IMAGE_EDIT_WAIT_S") or "300")


def ts() -> str:
    return datetime.now(timezone.utc).astimezone().strftime("%Y-%m-%d %H:%M:%S %z")


def main() -> int:
    if not TN_ID:
        print("ERROR: ZALO_TEST_USER_ID is required", file=sys.stderr)
        return 2
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

def hermes_names():
    names=subprocess.check_output(["docker","ps","--format","{{{{.Names}}}}"], text=True).splitlines()
    return [name for name in names if name.startswith("assistant-hermes-")]

def logs(since="10m"):
    names=hermes_names()
    if not names:
        return ""
    chunks=[]
    for name in names:
        chunks.append(subprocess.check_output(["docker","logs","--since",since,name], stderr=subprocess.STDOUT, text=True, errors="replace"))
    return "\n".join(chunks)

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
if not hermes_names():
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

def post(path, body):
    req=urllib.request.Request(
        "http://127.0.0.1:8787" + path,
        data=json.dumps(body, ensure_ascii=False).encode("utf-8"),
        method="POST",
        headers=headers,
    )
    return json.loads(urllib.request.urlopen(req, timeout=60).read().decode() or "{{}}")

sent=post("/send-attachment", {{
    "threadId":uid,
    "threadType":"user",
    "path":str(host_source),
    "caption":"Source image for reply-edit verification " + tag,
}})
result=sent.get("result") if isinstance(sent, dict) else {{}}
result=result if isinstance(result, dict) else {{}}

def first_value(node, wanted):
    if isinstance(node, dict):
        for key, value in node.items():
            if str(key).replace("_", "").lower() in wanted and value not in (None, ""):
                return str(value)
        for value in node.values():
            found=first_value(value, wanted)
            if found:
                return found
    if isinstance(node, list):
        for value in node:
            found=first_value(value, wanted)
            if found:
                return found
    return ""

real_id=first_value(result, {{"msgid", "messageid", "climsgid"}})
if not real_id:
    print("SEND_RESULT_KEYS", sorted(str(key) for key in result.keys()))
    raise SystemExit("FAIL_REAL_SOURCE_MESSAGE_ID")
attachments=result.get("attachment")
if not isinstance(attachments, list):
    attachments=result.get("attachments")
attachment=attachments[0] if isinstance(attachments, list) and attachments and isinstance(attachments[0], dict) else None
# zca-js returns the real photo message id but not the later CDN echo payload
# from this endpoint. The injected reply therefore uses the exact shared source
# path that was just sent, while retaining the genuine outbound quote identity.
quote_content=container_source
quoted={{
    "msgType":"chat.photo",
    "msgId":real_id,
    "cliMsgId":real_id,
    "content":quote_content,
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
reply=post("/inject-event", payload)
print("REAL_SOURCE_MESSAGE_ID_PRESENT")
print("SOURCE_ATTACHMENT_METADATA", bool(attachment))
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

dispatcher=next(
    (
        name for name in subprocess.check_output(
            ["docker", "ps", "--format", "{{{{.Names}}}}"], text=True
        ).splitlines()
        if name.startswith("assistant-dispatcher-")
    ),
    "",
)
if not dispatcher:
    raise SystemExit("FAIL_NO_DISPATCHER_FOR_VISUAL_EVALUATION")
container_artifact="/data/media/out/" + artifact.name
evaluation_code="""
import base64, io, json, os, urllib.request
from pathlib import Path
p=Path(os.environ["EVAL_IMAGE_PATH"])
blob=p.read_bytes()
mime="image/jpeg"
try:
    from PIL import Image
    image=Image.open(io.BytesIO(blob)).convert("RGB")
    image.thumbnail((1280, 1280))
    buf=io.BytesIO()
    image.save(buf, format="JPEG", quality=85)
    blob=buf.getvalue()
except Exception:
    if p.suffix.lower() == ".png":
        mime="image/png"
    elif p.suffix.lower() == ".webp":
        mime="image/webp"
body=json.dumps({{
    "model":(os.environ.get("OMNIROUTER_VISION_COMBO") or "vision-ocr"),
    "stream":False,
    "max_tokens":220,
    "messages":[{{"role":"user","content":[
        {{"type":"text","text":"Evaluate this edited image. Describe its style and whether it remains a coherent scene containing a house, a tree, and a sun. Note any unsafe or offensive visible text. Give a concise quality rating from 1 to 10 with reasons."}},
        {{"type":"image_url","image_url":{{"url":"data:"+mime+";base64,"+base64.b64encode(blob).decode("ascii")}}}},
    ]}}],
}}).encode()
base=(os.environ.get("OMNIROUTER_BASE_URL") or "http://omni-router:20129/v1").rstrip("/")
key=(os.environ.get("OMNIROUTER_API_KEY") or "").strip()
req=urllib.request.Request(base+"/chat/completions", data=body, method="POST", headers={{"Authorization":"Bearer "+key,"Content-Type":"application/json"}})
with urllib.request.urlopen(req, timeout=180) as response:
    data=json.loads(response.read().decode() or "{{}}")
print((((data.get("choices") or [{{}}])[0].get("message") or {{}}).get("content") or "").strip())
"""
evaluated=subprocess.run(
    [
        "docker", "exec", "-i", "-e", "EVAL_IMAGE_PATH=" + container_artifact,
        dispatcher, "python3", "-",
    ],
    input=evaluation_code,
    text=True,
    capture_output=True,
    timeout=240,
)
evaluation=(evaluated.stdout or "").strip()
if evaluated.returncode != 0:
    error=(evaluated.stderr or "").strip().replace("\n", " ")[:240]
    if any(token in error.lower() for token in ("quota", "rate limit", "429", "free")):
        raise SystemExit("SKIP_VISUAL_EVALUATOR_QUOTA " + error)
    raise SystemExit("FAIL_VISUAL_EVALUATOR " + error)
if len(evaluation) < 40:
    raise SystemExit("FAIL_EMPTY_VISUAL_EVALUATION")

recent=logs("10m")
for line in recent.splitlines():
    if tag in line or "image_edit_shortcut" in line or ("send-attachment path" in line and "image-edit-" in line):
        print(line[:300])
for line in zalo_journal(started).splitlines():
    if "RAW message: type=user thread=" + uid in line or "self=true msgType=chat.photo" in line:
        print(line[:300])
print("ARTIFACT", artifact.name, "BYTES", len(blob))
print("VISUAL_EVALUATION_BEGIN")
print(evaluation[:1200])
print("VISUAL_EVALUATION_END")
print("PASS_REAL_QUOTED_IMAGE_EDIT_DELIVERED")
PY
'''
        output = sudo_bash(client, remote, timeout=WAIT_S + 180)
    finally:
        client.close()

    safe = _sanitize(output or "")
    (OUT / "raw.log").write_text(safe, encoding="utf-8", errors="replace")
    passed = "PASS_REAL_QUOTED_IMAGE_EDIT_DELIVERED" in safe and "FAIL_" not in safe
    (OUT / "summary.json").write_text(
        json.dumps({"ok": passed, "user_name": TN_NAME, "ts": ts()}, indent=2) + "\n",
        encoding="utf-8",
    )
    print(safe, flush=True)
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
