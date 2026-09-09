# -*- coding: utf-8 -*-
"""Live Zalo gate: a two-minute composed-image schedule fires one image.

The destination identity is resolved from the runtime allowlist. No account,
host, group, or credential is written to the report.
"""
from __future__ import annotations

import base64
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from deploy_stack import connect, sudo_bash  # noqa: E402
from sanitize import sanitize as _sanitize  # noqa: E402


ROOT = Path(os.environ.get("ASSISTANT_REPO_ROOT", Path(__file__).resolve().parents[2]))
OUT = ROOT / "test" / "reports" / "run-zalo-scheduled-composed-image"
WAIT_S = int(os.environ.get("ZALO_SCHEDULED_IMAGE_WAIT_S", "480"))
REQUEST = (
    "2 phút nữa vẽ cho tôi hình thời tiết hồ chí minh hiện tại không chia tách hình, "
    "thông tin thời tiết bên trái phía dưới, bên phải phía dưới cập nhật giá xăng "
    "E5 RON92 và E10 RON95"
)


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    OUT.mkdir(parents=True, exist_ok=True)
    marker = f"scheduled-composed-{int(time.time())}"
    request_b64 = base64.b64encode(REQUEST.encode("utf-8")).decode("ascii")
    remote = rf"""
set -euo pipefail
cd /opt/assistant
set -a; . ./.env; set +a
export LAB_REQUEST_B64={request_b64}
export LAB_MARKER={marker}
export LAB_WAIT_S={WAIT_S}
python3 - <<'PY'
import base64, json, os, re, subprocess, time, urllib.request
from datetime import datetime, timezone
from pathlib import Path

request = base64.b64decode(os.environ["LAB_REQUEST_B64"]).decode("utf-8")
marker = os.environ["LAB_MARKER"]
wait_s = int(os.environ["LAB_WAIT_S"])

def get_json(url):
    with urllib.request.urlopen(url, timeout=10) as response:
        return json.loads(response.read().decode() or "{{}}")

def post_json(url, body):
    data = json.dumps(body, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(
        url, data=data, method="POST", headers={{"Content-Type": "application/json"}}
    )
    with urllib.request.urlopen(req, timeout=30) as response:
        return json.loads(response.read().decode() or "{{}}")

admin_id = ""
for raw_path in ("/data/assistant/zalo_admin_users.txt", "/opt/data/zalo_admin_users.txt"):
    try:
        lines = Path(raw_path).read_text(encoding="utf-8", errors="replace").splitlines()
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

started = time.time()
since_iso = datetime.fromtimestamp(started - 5, timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
accepted = post_json(
    "http://127.0.0.1:8787/inject-event",
    {{
        "type": "message",
        "threadId": admin_id,
        "threadType": "user",
        "senderId": admin_id,
        "senderName": "test-user",
        "text": request,
        "messageId": marker,
    }},
)
if not accepted.get("ok"):
    raise SystemExit("FAIL_INJECT")
print("INJECT PASS destination=runtime-admin-dm")

row = None
deadline = time.time() + min(wait_s, 180)
while time.time() < deadline:
    rows = get_json("http://127.0.0.1:8110/v1/schedules").get("schedules") or []
    for candidate in rows:
        context = candidate.get("context") if isinstance(candidate.get("context"), dict) else {{}}
        if context.get("original_request") == request:
            row = candidate
            break
    if row:
        break
    time.sleep(3)
if not isinstance(row, dict):
    raise SystemExit("FAIL_SCHEDULE_NOT_STORED")

sid = str(row.get("id") or "")
if not re.fullmatch(r"[A-Za-z0-9_-]+", sid):
    raise SystemExit("FAIL_BAD_SCHEDULE_ID")
context = row.get("context") if isinstance(row.get("context"), dict) else {{}}
plan = context.get("plan") if isinstance(context.get("plan"), dict) else {{}}
details = plan.get("task_details") if isinstance(plan.get("task_details"), list) else []
search_indexes = [
    index for index, item in enumerate(details)
    if isinstance(item, dict) and str(item.get("task_type") or "") == "search"
]
media = [
    item for item in details
    if isinstance(item, dict) and str(item.get("task_type") or "") == "media_generation"
]
dependencies = media[0].get("depends_on") if len(media) == 1 else []
stored_ok = (
    plan.get("task_hint") == "schedule"
    and context.get("schedule_delivery") == "process"
    and len(search_indexes) >= 2
    and len(media) == 1
    and all(index in dependencies for index in search_indexes)
    and "2 phút nữa" not in str(row.get("fire_text") or "").lower()
)
if not stored_ok:
    print(json.dumps({{"hint": plan.get("task_hint"), "types": [d.get("task_type") for d in details if isinstance(d, dict)]}}))
    raise SystemExit("FAIL_STORED_PLAN")
print("STORED_PLAN PASS searches=%s media=1 delivery=process" % len(search_indexes))

pg = subprocess.check_output(
    ["docker", "ps", "--filter", "label=com.docker.compose.service=postgres", "--format", "{{{{.Names}}}}"],
    text=True,
).splitlines()[0]
db_user = os.environ.get("MEMORY_DB_USER", "hermes")
db_name = os.environ.get("MEMORY_DB_NAME", "hermes_memory")
db_password = os.environ.get("MEMORY_DB_PASSWORD", "")

def delivery_row():
    sql = (
        "SELECT count(*),coalesce(max(meta->>'file_name'),'') "
        "FROM zalo_message_history WHERE event='delivered' "
        "AND meta->>'attachment_kind'='image' "
        f"AND meta->>'source_message_id' LIKE 'schedule:{{sid}}:%' "
        f"AND created_at >= to_timestamp({{int(started - 5)}});"
    )
    raw = subprocess.check_output(
        ["docker", "exec", "-e", "PGPASSWORD=" + db_password, pg, "psql", "-U", db_user,
         "-d", db_name, "-At", "-F", "|", "-c", sql],
        text=True,
        errors="replace",
    ).strip()
    count, _, file_name = raw.partition("|")
    return int(count or "0"), Path(file_name).name

file_name = ""
deadline = started + wait_s
while time.time() < deadline:
    count, file_name = delivery_row()
    if count == 1 and file_name:
        break
    time.sleep(5)
else:
    raise SystemExit("FAIL_NO_SOURCE_CORRELATED_IMAGE")

logs = ""
for name in subprocess.check_output(
    ["docker", "ps", "--filter", "label=com.docker.compose.service=hermes", "--format", "{{{{.Names}}}}"],
    text=True,
).splitlines():
    captured = subprocess.run(
        ["docker", "logs", "--since", since_iso, name],
        text=True,
        errors="replace",
        capture_output=True,
    )
    logs += captured.stdout + captured.stderr
if "search_composed_image_shortcut" not in logs:
    raise SystemExit("FAIL_COMPOSED_SHORTCUT_NOT_OBSERVED")
if "image structured planning invalid" in logs:
    raise SystemExit("FAIL_STRUCTURED_PLAN_INVALID")
if "reply-quote send failed" in logs:
    raise SystemExit("FAIL_SYNTHETIC_QUOTE_ATTEMPT")

image_path = Path("/data/assistant/media/out") / file_name
if not image_path.is_file() or image_path.stat().st_size < 80000:
    raise SystemExit("FAIL_IMAGE_ARTIFACT_QUALITY_FLOOR")
print(json.dumps({{
    "ok": True,
    "elapsed_s": round(time.time() - started, 2),
    "stored_searches": len(search_indexes),
    "deliveries": 1,
    "source_correlated": True,
    "artifact": file_name,
    "bytes": image_path.stat().st_size,
    "generic_fallback": False,
    "synthetic_quote_attempt": False,
}}, ensure_ascii=False, separators=(",", ":")))
PY
"""

    client = connect()
    try:
        output = sudo_bash(client, remote, timeout=WAIT_S + 240)
    finally:
        client.close()
    clean = _sanitize(output)
    (OUT / "raw.log").write_text(clean, encoding="utf-8")
    ok = '"ok":true' in clean and "STORED_PLAN PASS" in clean
    (OUT / "SUMMARY.md").write_text(
        "\n".join(
            [
                "# Scheduled composed-image fire",
                "",
                f"- Timestamp: `{datetime.now(timezone.utc).isoformat()}`",
                f"- Result: **{'PASS' if ok else 'FAIL'}**",
                "- Destination identity: runtime-only admin DM",
                "- Delay: two minutes from receipt",
                "- Contract: persisted two-search dependency graph → one source-correlated image",
                "",
            ]
        ),
        encoding="utf-8",
    )
    print(clean[-3000:], flush=True)
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
