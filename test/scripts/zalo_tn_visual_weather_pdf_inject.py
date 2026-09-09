# -*- coding: utf-8 -*-
"""Inject visual weather PDF turn for Zalo user Tn (VPS lab).

The target user id is required through ``ZALO_TEST_USER_ID``.
Message asks for attractive PDF + city imagery — must NOT dump SERP chrome.
Env: ASSISTANT_SSH_* ; ZALO_TEST_USER_ID ; ZALO_TEST_WAIT_S (default 240);
ZALO_TEST_MESSAGE (optional exact fixture)
Report: test/reports/run-zalo-tn-visual-weather-pdf/
"""
from __future__ import annotations

import io
import json
import os
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from deploy_stack import connect, sudo_bash  # noqa: E402
from sanitize import sanitize as _sanitize  # noqa: E402

if hasattr(sys.stdout, "buffer"):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

ROOT = Path(os.environ.get("ASSISTANT_REPO_ROOT", Path(__file__).resolve().parents[2]))
OUT = ROOT / "test" / "reports" / "run-zalo-tn-visual-weather-pdf"
TN_ID = (os.environ.get("ZALO_TEST_USER_ID") or "").strip()
WAIT_S = int(os.environ.get("ZALO_TEST_WAIT_S") or "240")
MSG = (os.environ.get("ZALO_TEST_MESSAGE") or (
    "cập nhật thời tiết hiện tại ở Đà Nẵng và vẽ vào file pdf, "
    "giao diện phải bắt mắt và hợp gu người nhìn"
)).strip()


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
    marker = f"lab-visual-weather-pdf-{int(time.time())}"
    report: dict = {
        "ts": ts(),
        "target": "runtime-authorized-user",
        "message": MSG,
        "marker": marker,
    }
    try:
        before = _clean(
            sudo_bash(c, "ls -1t /data/assistant/media/out/*.pdf 2>/dev/null | head -1 || true")
        ).strip()
        report["pdf_before"] = before
        image_before = _clean(
            sudo_bash(
                c,
                "find /data/assistant/media/out -maxdepth 1 -type f "
                "\\( -name '*.png' -o -name '*.jpg' -o -name '*.jpeg' -o -name '*.webp' \\) "
                "-printf '%T@ %p\\n' 2>/dev/null | sort -nr | head -1 || true",
            )
        ).strip()
        report["image_before"] = image_before

        # Do not pipe JSON through sanitize() — it redacts 127.0.0.1 and breaks curl.
        remote = f"""
set -euo pipefail
START_EPOCH=$(date +%s)
python3 - <<'PY'
import json, urllib.request
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
NEWPDF=""
NEWIMAGE=""
for i in $(seq 1 {WAIT_S}); do
  cand=$(find /data/assistant/media/out -type f -name '*.pdf' -newermt "@$START_EPOCH" 2>/dev/null | head -1 || true)
  NEWIMAGE=$(find /data/assistant/media/out -maxdepth 1 -type f \
    \\( -name '*.png' -o -name '*.jpg' -o -name '*.jpeg' -o -name '*.webp' \\) \
    -newermt "@$START_EPOCH" 2>/dev/null | head -1 || true)
  if [[ -n "$cand" ]]; then
    NEWPDF="$cand"
    echo "NEW_PDF $cand"
    break
  fi
  sleep 1
done
if [[ -n "$NEWIMAGE" ]]; then
  echo "UNEXPECTED_NEW_IMAGE $NEWIMAGE"
fi
if [[ -z "$NEWPDF" ]]; then
  echo "NO_NEW_PDF"
  ls -1t /data/assistant/media/out/*.pdf 2>/dev/null | head -3 || true
  exit 0
fi
HOST_PDF="$NEWPDF"
CONT_PDF="${{HOST_PDF/\\/data\\/assistant\\/media/\\/data\\/media}}"
DISPATCHER_ID=$(docker ps \
  --filter label=com.docker.compose.service=dispatcher \
  --format '{{{{.ID}}}}' | head -1)
if [[ -z "$DISPATCHER_ID" ]]; then
  echo "NO_DISPATCHER_CONTAINER"
  exit 1
fi
docker exec -i -e P="$CONT_PDF" -e P2="$HOST_PDF" "$DISPATCHER_ID" python - <<'PY'
import base64
import json
import os
import urllib.request
from pathlib import Path
import fitz

p = Path(os.environ.get("P") or "")
if not p.is_file():
    p = Path(os.environ.get("P2") or "")
print("size", p.stat().st_size if p.is_file() else 0)
if not p.is_file():
    raise SystemExit("FAIL_PDF_NOT_SHARED")
doc = fitz.open(str(p))
if len(doc) < 1:
    raise SystemExit("FAIL_PDF_NO_PAGES")
page = doc[0]
text = (page.get_text("text") or "").strip()
pix = page.get_pixmap(matrix=fitz.Matrix(1.5, 1.5), alpha=False)
image = pix.tobytes("png")
print("PDF_PAGE_COUNT", len(doc))
print("PDF_TEXT_CHARS", len(text))
print(text[:2000])
if len(text) < 80 or len(image) < 10000:
    raise SystemExit("FAIL_PDF_UNREADABLE")

body = json.dumps(dict(
    model=os.environ.get("OMNIROUTER_VISION_COMBO") or "vision-ocr",
    stream=False,
    max_tokens=260,
    messages=[dict(role="user", content=[
        dict(type="text", text=(
            "Evaluate this rendered PDF page as a professional information document. "
            "Check visual hierarchy, readability, spacing, contrast, factual labels, "
            "and whether any interface chrome or unrelated title leaked into the page. "
            "Give a concise quality rating from 1 to 10 with reasons."
        )),
        dict(type="image_url", image_url=dict(url=(
            "data:image/png;base64," + base64.b64encode(image).decode("ascii")
        ))),
    ])],
)).encode("utf-8")
base = (os.environ.get("OMNIROUTER_BASE_URL") or "http://omni-router:20129/v1").rstrip("/")
key = (os.environ.get("OMNIROUTER_API_KEY") or "").strip()
request = urllib.request.Request(
    base + "/chat/completions",
    data=body,
    method="POST",
    headers=dict([
        ("Authorization", "Bearer " + key),
        ("Content-Type", "application/json"),
    ]),
)
with urllib.request.urlopen(request, timeout=180) as response:
    result = json.loads(response.read().decode("utf-8") or "{{}}")
evaluation = str((((result.get("choices") or [dict()])[0].get("message") or dict()).get("content") or "")).strip()
if len(evaluation) < 40:
    raise SystemExit("FAIL_PDF_VISUAL_EVALUATION")
print("PDF_VISUAL_EVALUATION_BEGIN")
print(evaluation[:1600])
print("PDF_VISUAL_EVALUATION_END")
print("PDF_STRUCTURE_OK")
PY
ZALO_API_ID=$(docker ps \
  --filter label=com.docker.compose.service=zalo-api \
  --format '{{{{.ID}}}}' | head -1)
docker exec -e SOURCE_ID={marker!r} "$ZALO_API_ID" python3 -c '
import os, psycopg
with psycopg.connect(os.environ["DATABASE_URL"]) as c:
    row = c.execute(
        "select count(*) from zalo_message_history "
        "where event='"'"'delivered'"'"' "
        "and meta->>'"'"'attachment_kind'"'"'='"'"'image'"'"' "
        "and meta->>'"'"'source_message_id'"'"'=%s",
        (os.environ["SOURCE_ID"],),
    ).fetchone()
print("DELIVERED_IMAGE_COUNT", int(row[0] if row else 0))
'
"""
        print(f"INJECTED wait up to {WAIT_S}s", flush=True)
        out = _clean(sudo_bash(c, remote, timeout=WAIT_S + 120))
        report["remote"] = _sanitize(out)[-8000:]
        print(out[-2000:], flush=True)

        logs = _clean(
            sudo_bash(
                c,
                "for c in $(docker ps --format '{{.Names}}' | grep '^assistant-hermes-'); do "
                "docker logs --since 8m $c 2>&1 | tail -n 80; done",
                timeout=60,
            )
        )
        report["logs_tail"] = _sanitize(logs)[-8000:]

        blob = (out + "\n" + logs).lower()
        fail_bits = (
            "dubaothoitiet",
            "accuweather",
            "pm2.5",
            "quận 1",
            "có thể bạn quan",
            "tạo file pdf dự báo",
            "tạo file pdf bản tin",
            "|------",
        )
        bad = [b for b in fail_bits if b in blob]
        greeting_leak = (
            "gõ /help" in blob
            and "share.file" not in logs.lower()
            and "fileext" not in blob
        )
        report["fail_bits"] = bad
        report["greeting_leak"] = greeting_leak
        new_pdf = "NEW_PDF" in out
        report["new_pdf"] = new_pdf
        report["pdf_structure_ok"] = "PDF_STRUCTURE_OK" in out
        report["visual_evaluation"] = (
            out.split("PDF_VISUAL_EVALUATION_BEGIN", 1)[1]
            .split("PDF_VISUAL_EVALUATION_END", 1)[0]
            .strip()
            if "PDF_VISUAL_EVALUATION_BEGIN" in out
            and "PDF_VISUAL_EVALUATION_END" in out
            else ""
        )
        unexpected_image = "UNEXPECTED_NEW_IMAGE" in out
        report["unexpected_image"] = unexpected_image
        delivered_image = not re.search(r"DELIVERED_IMAGE_COUNT\s+0(?:\s|$)", out)
        report["unexpected_image_delivery"] = delivered_image

        out_path = OUT / f"report-{datetime.now().strftime('%Y%m%d-%H%M%S')}.json"
        out_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"REPORT {out_path}", flush=True)
        if "INJECT_OK" not in out:
            print("FAIL inject", flush=True)
            return 1
        if bad:
            print("FAIL serp/create chrome in pdf/logs:", bad, flush=True)
            return 1
        if greeting_leak:
            print("FAIL hello/help leak without file delivery", flush=True)
            return 1
        if delivered_image:
            print("FAIL requested PDF also delivered a standalone image", flush=True)
            return 1
        if not new_pdf:
            print("FAIL no new pdf produced (quota/rate-limit → skip)", flush=True)
            if "maxwaitms" in blob or "rate-limit" in blob or "quota" in blob:
                print("SKIP rate-limit/quota", flush=True)
                return 0
            return 1
        if "PDF_STRUCTURE_OK" not in out:
            if "rate-limit" in blob or "quota" in blob or "429" in blob:
                print("SKIP visual evaluator rate-limit/quota", flush=True)
                return 0
            print("FAIL PDF structure or visual evaluation", flush=True)
            return 1
        print("PASS visual weather pdf", flush=True)
        return 0
    finally:
        c.close()


if __name__ == "__main__":
    raise SystemExit(main())
