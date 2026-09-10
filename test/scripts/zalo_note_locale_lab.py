#!/usr/bin/env python3
"""Live Zalo gate for a Vietnamese note request and host-owned reply locale."""
from __future__ import annotations

import base64
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from deploy_stack import connect, sudo_bash  # noqa: E402
from sanitize import sanitize  # noqa: E402


ROOT = Path(os.environ.get("ASSISTANT_REPO_ROOT", Path(__file__).resolve().parents[2]))
OUT = ROOT / "test" / "reports" / "run-zalo-note-locale"
REQUEST = "note giúp tôi hôm nay cần bàn giao công việc"


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    marker = f"note-locale-{int(time.time())}"
    request_b64 = base64.b64encode(REQUEST.encode("utf-8")).decode("ascii")
    remote = r"""
set -euo pipefail
cd /opt/assistant
set -a; . ./.env; set +a
export LAB_REQUEST_B64=__REQUEST_B64__
export LAB_MARKER=__MARKER__
python3 - <<'PY'
import base64, json, os, subprocess, time, urllib.request
from pathlib import Path

request = base64.b64decode(os.environ["LAB_REQUEST_B64"]).decode("utf-8")
marker = os.environ["LAB_MARKER"]
admin_id = ""
for path in ("/data/assistant/zalo_admin_users.txt", "/opt/data/zalo_admin_users.txt"):
    try:
        lines = Path(path).read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        continue
    for line in lines:
        value = line.strip()
        if value and not value.startswith("#"):
            admin_id = value.partition("|")[0].strip()
            break
    if admin_id:
        break
if not admin_id:
    raise SystemExit("FAIL_NO_ADMIN_DM")

data = json.dumps({
    "type": "message", "threadId": admin_id, "threadType": "user",
    "senderId": admin_id, "senderName": "test-user", "text": request,
    "messageId": marker,
}, ensure_ascii=False).encode("utf-8")
req = urllib.request.Request(
    "http://127.0.0.1:8787/inject-event", data=data, method="POST",
    headers={"Content-Type": "application/json"},
)
with urllib.request.urlopen(req, timeout=30) as response:
    accepted = json.loads(response.read().decode() or "{}")
if not accepted.get("ok"):
    raise SystemExit("FAIL_INJECT")

pg = subprocess.check_output(
    ["docker", "ps", "--filter", "label=com.docker.compose.service=postgres",
     "--format", "{{.Names}}"], text=True,
).splitlines()[0]
db_user = os.environ.get("MEMORY_DB_USER", "hermes")
db_name = os.environ.get("MEMORY_DB_NAME", "hermes_memory")
db_password = os.environ.get("MEMORY_DB_PASSWORD", "")
reply = ""
deadline = time.time() + 150
while time.time() < deadline:
    sql = (
        "SELECT coalesce(content,'') FROM zalo_message_history "
        "WHERE event='delivered' "
        f"AND meta->>'source_message_id'='{marker}' ORDER BY id DESC LIMIT 1;"
    )
    reply = subprocess.check_output(
        ["docker", "exec", "-e", "PGPASSWORD=" + db_password, pg, "psql",
         "-U", db_user, "-d", db_name, "-At", "-c", sql],
        text=True, errors="replace",
    ).strip()
    if reply:
        break
    time.sleep(3)
if reply != "Đã lưu ghi chú.":
    print(json.dumps({"reply": reply}, ensure_ascii=False))
    raise SystemExit("FAIL_NOTE_REPLY_LOCALE")
print(json.dumps({"ok": True, "reply": reply, "destination": "runtime-admin-dm"},
                 ensure_ascii=False, separators=(",", ":")))
PY
"""
    remote = remote.replace("__REQUEST_B64__", request_b64).replace("__MARKER__", marker)
    client = connect()
    try:
        output = sudo_bash(client, remote, timeout=240)
    finally:
        client.close()
    clean = sanitize(output)
    ok = '"ok":true' in clean and "Đã lưu ghi chú." in clean
    (OUT / "raw.log").write_text(clean, encoding="utf-8")
    (OUT / "SUMMARY.md").write_text(
        "\n".join([
            "# Zalo note locale gate", "",
            f"- Timestamp: `{datetime.now(timezone.utc).isoformat()}`",
            f"- Result: **{'PASS' if ok else 'FAIL'}**",
            "- Request language: Vietnamese",
            "- Reply: exact localized host-owned confirmation",
            "",
        ]),
        encoding="utf-8",
    )
    print(clean)
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
