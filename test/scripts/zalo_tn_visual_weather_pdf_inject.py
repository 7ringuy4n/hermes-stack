# -*- coding: utf-8 -*-
"""Inject visual weather PDF turn for Zalo user Tn (VPS lab).

User id default: 233767886566872937.
Message asks for attractive PDF + city imagery — must NOT dump SERP chrome.
Env: ASSISTANT_SSH_* ; ZALO_TEST_USER_ID ; ZALO_TEST_WAIT_S (default 240)
Report: test/reports/run-zalo-tn-visual-weather-pdf/
"""
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
from sanitize import sanitize as _sanitize  # noqa: E402

if hasattr(sys.stdout, "buffer"):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

ROOT = Path(os.environ.get("ASSISTANT_REPO_ROOT", Path(__file__).resolve().parents[2]))
OUT = ROOT / "test" / "reports" / "run-zalo-tn-visual-weather-pdf"
TN_ID = (os.environ.get("ZALO_TEST_USER_ID") or "233767886566872937").strip()
WAIT_S = int(os.environ.get("ZALO_TEST_WAIT_S") or "240")
MSG = (
    "cập nhật dự báo thời tiết hồ chí minh hiện tại và điền vào pdf, "
    "layout phải thật bắt mắt có hình ảnh thành phố hồ chí minh"
)


def ts() -> str:
    return datetime.now(timezone.utc).astimezone().strftime("%Y-%m-%d %H:%M:%S %z")


def _inject_text(c, text: str, *, label: str) -> dict:
    payload = {
        "type": "message",
        "threadId": TN_ID,
        "threadType": "user",
        "senderId": TN_ID,
        "senderName": "Tn",
        "text": text,
        "messageId": f"lab-{label}-{int(datetime.now().timestamp())}",
    }
    cmd = (
        "curl -sfS -X POST http://127.0.0.1:8787/inject-event "
        f"-H 'Content-Type: application/json' -d {_sanitize(json.dumps(payload))}"
    )
    raw = sudo_bash(c, cmd)
    return {"label": label, "inject": raw[:500]}


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    c = connect()
    report: dict = {"ts": ts(), "user": TN_ID, "message": MSG, "steps": []}
    try:
        before = sudo_bash(
            c,
            "ls -1t /data/assistant/media/out/*.pdf 2>/dev/null | head -1 || true",
        ).strip()
        report["pdf_before"] = before
        report["steps"].append(_inject_text(c, MSG, label="visual-weather-pdf"))
        print(f"INJECTED wait={WAIT_S}s (rate-limit cushion)", flush=True)
        time.sleep(WAIT_S)

        after = sudo_bash(
            c,
            "ls -1t /data/assistant/media/out/*.pdf 2>/dev/null | head -3 || true",
        ).strip()
        report["pdf_after"] = after
        newest = (after.splitlines() or [""])[0].strip()
        report["newest_pdf"] = newest

        text_extract = ""
        if newest:
            text_extract = sudo_bash(
                c,
                "docker exec assistant-dispatcher-1 python - <<'PY'\n"
                "from pathlib import Path\n"
                f"p=Path({newest!r}.replace('/data/assistant/media','/data/media'))\n"
                "if not p.is_file():\n"
                f" p=Path({newest!r})\n"
                "print('size', p.stat().st_size if p.is_file() else 0)\n"
                "try:\n"
                " from pypdf import PdfReader\n"
                " t=(PdfReader(str(p)).pages[0].extract_text() or '') if p.is_file() else ''\n"
                " print(t[:2000])\n"
                "except Exception as e:\n"
                " print('extract', type(e).__name__, e)\n"
                "PY",
            )
        report["pdf_text"] = text_extract[-4000:]

        logs = sudo_bash(
            c,
            "docker logs --since 8m assistant-hermes-2 2>&1 | tail -n 80; "
            "docker logs --since 8m assistant-hermes-3 2>&1 | tail -n 80; "
            "journalctl --user -u com.hermes.zaloplugin -n 50 --no-pager 2>/dev/null || true",
        )
        report["logs_tail"] = logs[-14000:]

        blob = (text_extract + "\n" + logs).lower()
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
        new_pdf = bool(newest) and newest != before
        report["new_pdf"] = new_pdf

        out_path = OUT / f"report-{datetime.now().strftime('%Y%m%d-%H%M%S')}.json"
        out_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"REPORT {out_path}", flush=True)
        if bad:
            print("FAIL serp/create chrome in pdf/logs:", bad, flush=True)
            return 1
        if greeting_leak:
            print("FAIL hello/help leak without file delivery", flush=True)
            return 1
        if not new_pdf:
            print("FAIL no new pdf produced (quota/rate-limit → skip)", flush=True)
            # Rate-limit / free-model miss: skip rather than hard fail when logs show queue
            if "maxwaitms" in blob or "rate-limit" in blob or "quota" in blob:
                print("SKIP rate-limit/quota", flush=True)
                return 0
            return 1
        print("PASS visual weather pdf", flush=True)
        return 0
    finally:
        c.close()


if __name__ == "__main__":
    raise SystemExit(main())
