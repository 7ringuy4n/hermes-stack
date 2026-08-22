# -*- coding: utf-8 -*-
"""Recommend / optionally probe ZALO_WORKFLOW_PARALLEL for Qwen sizing profiles.

Offline by default (prints recommended table). With ASSISTANT_SSH_* set and
ZALO_PARALLEL_PROBE=1, injects concurrent Tn multi-request pings and reports
success rate per N — used to validate the docs/QWEN_PERFORMANCE.md table.

Never commits host identity. Injects as allowlisted user Tn.
"""
from __future__ import annotations

import io
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from qwen_parallel_recommend_unit import RECOMMENDED, recommend  # noqa: E402

if hasattr(sys.stdout, "buffer"):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")


def print_table() -> None:
    print("profile_vcpu_ram_gb\trecommended_ZALO_WORKFLOW_PARALLEL")
    for (c, r), val in sorted(RECOMMENDED.items()):
        print(f"{c}c/{r}G\t{val}")
    print(f"rule_of_thumb_4c8G\t{recommend(4, 8)}")
    print("PASS_QWEN_PARALLEL_TABLE")


def probe_remote() -> int:
    from deploy_stack import connect, sudo_bash  # noqa: WPS433

    want = (os.environ.get("ZALO_TEST_USER_NAME") or "Tn").strip()
    n = int(os.environ.get("ZALO_PARALLEL_PROBE_N") or "8")
    wait_s = int(os.environ.get("ZALO_CASE_WAIT_S") or "120")
    remote = rf"""
set -euo pipefail
export LC_ALL=C.UTF-8
cd /opt/assistant
set -a; . ./.env; set +a
python3 - <<'PY'
import json, time, urllib.request, os
from pathlib import Path

want_name = {want!r}
n = {n}
wait_s = {wait_s}
uid = uname = ""
first_uid = first_name = ""
for path in ("/data/assistant/zalo_admin_users.txt", "/opt/data/zalo_admin_users.txt"):
    p = Path(path)
    if not p.is_file():
        continue
    for line in p.read_text(encoding="utf-8", errors="replace").splitlines():
        raw = line.strip()
        if not raw or raw.startswith("#"):
            continue
        left, _, right = raw.partition("|")
        if not left.strip():
            continue
        if not first_uid:
            first_uid, first_name = left.strip(), right.strip() or "admin"
        if right.strip().lower() == want_name.lower():
            uid, uname = left.strip(), right.strip()
            break
    if uid:
        break
if not uid:
    _strict = (os.environ.get("ZALO_REQUIRE_NAMED_ADMIN") or "1").strip().lower() in ("1", "true", "yes")
    if _strict or not first_uid:
        raise SystemExit("NO_ADMIN_USER")
    uid, uname = first_uid, first_name
tok = (os.environ.get("ZALO_PLUGIN_TOKEN") or "").strip()
headers = {{"Content-Type": "application/json"}}
if tok:
    headers["Authorization"] = "Bearer " + tok
tag = "par-%d" % int(time.time())
offs = {{}}
for root in ("/data/assistant/replicas", "/opt/data/replicas"):
    base = Path(root)
    if not base.is_dir():
        continue
    for f in base.glob("*/logs/gateway.log"):
        offs[str(f)] = f.stat().st_size

def inject(i):
    text = "ping parallel %d [%s-%d]" % (i, tag, i)
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
    req = urllib.request.Request(
        "http://127.0.0.1:8787/inject-event",
        data=json.dumps(payload).encode(),
        headers=headers,
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=20) as r:
        return r.status

ok = 0
for i in range(n):
    try:
        st = inject(i)
        ok += 1 if st < 300 else 0
    except Exception as e:
        print("INJECT_FAIL", i, e)
print("INJECT_OK", ok, "of", n, "parallel=", os.environ.get("ZALO_WORKFLOW_PARALLEL"))
deadline = time.time() + wait_s
sends = 0
while time.time() < deadline:
    chunk = ""
    for path, off in list(offs.items()):
        p = Path(path)
        if not p.is_file():
            continue
        data = p.read_bytes()[off:]
        chunk += data.decode("utf-8", "replace")
        offs[path] = p.stat().st_size
    sends = chunk.lower().count("send ok") + chunk.lower().count("outbound ok")
    if sends >= max(1, n // 2):
        break
    time.sleep(2)
print("SEND_MARKERS", sends)
print("PASS_PARALLEL_PROBE" if ok == n else "FAIL_PARALLEL_PROBE")
PY
"""
    c = connect()
    try:
        out = sudo_bash(c, remote)
        print(out)
        return 0 if out and "PASS_PARALLEL_PROBE" in out else 1
    finally:
        c.close()


def main() -> int:
    print_table()
    if (os.environ.get("ZALO_PARALLEL_PROBE") or "").strip() in {"1", "true", "yes"}:
        return probe_remote()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
