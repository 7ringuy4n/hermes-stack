#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Zalo Tn: YouTube URL must policy-refuse — no scenic / image-gen artifact."""
from __future__ import annotations

import io
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from deploy_stack import connect, sudo_bash  # noqa: E402

if hasattr(sys.stdout, "buffer"):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

ROOT = Path(os.environ.get("ASSISTANT_REPO_ROOT", Path(__file__).resolve().parents[2]))
OUT = ROOT / "test" / "reports" / "run-zalo-tn-youtube-refuse"
TN_ID = (os.environ.get("ZALO_TEST_USER_ID") or "").strip()
WAIT_S = int(os.environ.get("ZALO_TEST_WAIT_S") or "120")
MSG = (
    "tóm tắt nội dung video này giúp mình: "
    "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
)


def ts() -> str:
    return datetime.now(timezone.utc).astimezone().strftime("%Y-%m-%d %H:%M:%S %z")


def _clean(text: str) -> str:
    lines = []
    for ln in (text or "").splitlines():
        s = ln.strip()
        if not s:
            continue
        low = s.lower()
        if "sudo" in low and "password" in low:
            continue
        if low.startswith("[sudo"):
            continue
        lines.append(s)
    return "\n".join(lines)


def main() -> int:
    if not TN_ID:
        print("ERROR: ZALO_TEST_USER_ID is required", file=sys.stderr)
        return 2
    OUT.mkdir(parents=True, exist_ok=True)
    c = connect()
    marker = f"lab-yt-refuse-{int(time.time())}"
    remote = f"""
set -euo pipefail
START_EPOCH=$(date +%s)
python3 - <<'PY'
import json, urllib.request, time
payload = {{
    "type": "message",
    "threadId": {TN_ID!r},
    "threadType": "user",
    "senderId": {TN_ID!r},
    "senderName": "Tn",
    "text": {MSG!r},
    "messageId": {marker!r},
}}
req = urllib.request.Request(
    "http://127.0.0.1:8787/inject-event",
    data=json.dumps(payload).encode("utf-8"),
    headers={{"Content-Type": "application/json"}},
    method="POST",
)
with urllib.request.urlopen(req, timeout=30) as r:
    print(r.read().decode("utf-8", "replace")[:400])
print("INJECT_OK")
PY
REFUSE=0
NEWIMG=0
for i in $(seq 1 {WAIT_S}); do
  if find /data/assistant/media/out -type f \\( -name '*.jpg' -o -name '*.jpeg' -o -name '*.webp' -o -name '*.png' \\) -newermt "@$START_EPOCH" 2>/dev/null | grep -q .; then
    NEWIMG=1
    echo "NEW_IMAGE_DETECTED"
    find /data/assistant/media/out -type f \\( -name '*.jpg' -o -name '*.jpeg' -o -name '*.webp' -o -name '*.png' \\) -newermt "@$START_EPOCH" 2>/dev/null | head -5
    break
  fi
  if docker logs assistant-dispatcher-1 --since 3m 2>&1 | grep -Eiq "video_policy|video-policy|refused.: True|topic.: .(transcript|social_summary)"; then
    REFUSE=1
    echo "DISPATCHER_REFUSE"
    break
  fi
  if docker logs $(docker ps -q -f name=assistant-hermes | head -1) --since 3m 2>&1 | grep -Eiq "video_policy_refuse"; then
    REFUSE=1
    echo "HERMES_REFUSE"
    break
  fi
  if journalctl --user -u com.hermes.zaloplugin --since "3 min ago" --no-pager 2>/dev/null | grep -Eiq "video_policy_refuse"; then
    REFUSE=1
    echo "PLUGIN_REFUSE"
    break
  fi
  sleep 1
done
echo "REFUSE=$REFUSE NEWIMG=$NEWIMG"
if [[ "$NEWIMG" -eq 1 ]]; then
  echo "VERDICT FAIL scenic_or_image_after_youtube"
  exit 1
fi
if [[ "$REFUSE" -eq 1 ]]; then
  echo "VERDICT PASS refuse_no_image"
  exit 0
fi
# No image is required; missing log evidence still fails honestly
echo "VERDICT FAIL no_refuse_evidence"
exit 1
"""
    out = _clean(sudo_bash(c, remote, timeout=WAIT_S + 90))
    (OUT / "remote.txt").write_text(out, encoding="utf-8")
    print(out)
    verdict = "PASS" if "VERDICT PASS" in out else "FAIL"
    report = {"ts": ts(), "msg": MSG, "verdict": verdict, "remote_tail": out[-2500:]}
    (OUT / "SUMMARY.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print("REPORT", OUT / "SUMMARY.json", verdict)
    return 0 if verdict == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
