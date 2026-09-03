# -*- coding: utf-8 -*-
"""Inject PPTX weather + weather-on-image overlay turns for Zalo user Tn.

User id default: 233767886566872937.
Env: ASSISTANT_SSH_* ; ZALO_TEST_USER_ID ; ZALO_TEST_WAIT_S (default 300)
Report: test/reports/run-zalo-tn-weather-overlay-pptx/
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
OUT = ROOT / "test" / "reports" / "run-zalo-tn-weather-overlay-pptx"
TN_ID = (os.environ.get("ZALO_TEST_USER_ID") or "233767886566872937").strip()
WAIT_S = int(os.environ.get("ZALO_TEST_WAIT_S") or "300")

MSG_PPTX = "tạo 1 file pptx chứa thông tin thời tiết thành phố vũng tàu hiện tại"
MSG_IMG = (
    "cập nhật thông tin thời tiết hồ chí minh lúc này, sau đó ghi thông tin lên "
    "hình ảnh hồ chí minh lúc này ở góc trái bên dưới thật gọn và bắt mắt "
    "không sai chính tả tiếng việt"
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
    report: dict = {"ts": ts(), "user": TN_ID, "steps": []}
    try:
        before_pptx = sudo_bash(
            c, "ls -1t /data/assistant/media/out/*.pptx 2>/dev/null | head -1 || true"
        ).strip()
        before_img = sudo_bash(
            c,
            "ls -1t /data/assistant/media/out/*.{jpg,jpeg,webp,png} 2>/dev/null | head -1 || true",
        ).strip()
        report["before"] = {"pptx": before_pptx, "img": before_img}

        report["steps"].append(_inject_text(c, MSG_PPTX, label="weather-pptx"))
        print(f"INJECTED pptx wait={WAIT_S}s", flush=True)
        time.sleep(WAIT_S)

        after_pptx = sudo_bash(
            c, "ls -1t /data/assistant/media/out/*.pptx 2>/dev/null | head -3 || true"
        ).strip()
        report["pptx_after"] = after_pptx
        newest_pptx = (after_pptx.splitlines() or [""])[0].strip()
        report["newest_pptx"] = newest_pptx

        # Rate-limit cushion between Omni calls
        time.sleep(60)
        report["steps"].append(_inject_text(c, MSG_IMG, label="weather-overlay-img"))
        print(f"INJECTED overlay-img wait={WAIT_S}s", flush=True)
        time.sleep(WAIT_S)

        after_img = sudo_bash(
            c,
            "ls -1t /data/assistant/media/out/*.{jpg,jpeg,webp,png} 2>/dev/null | head -5 || true",
        ).strip()
        report["img_after"] = after_img
        newest_img = (after_img.splitlines() or [""])[0].strip()
        report["newest_img"] = newest_img

        logs = sudo_bash(
            c,
            "docker logs --since 20m assistant-hermes-2 2>&1 | tail -n 100; "
            "docker logs --since 20m assistant-dispatcher-1 2>&1 | tail -n 80; "
            "journalctl --user -u com.hermes.zaloplugin -n 80 --no-pager 2>/dev/null || true",
        )
        report["logs_tail"] = logs[-16000:]

        blob = (logs + "\n" + after_pptx + "\n" + after_img).lower()
        fail_bits = (
            "value after search",
            "safe-for-work",
            "nhiệt đô",
            "thời thiệt",
            "thời thệt",
        )
        bad = [b for b in fail_bits if b in blob]
        pptx_ok = bool(newest_pptx) and newest_pptx != before_pptx
        img_ok = bool(newest_img) and newest_img != before_img
        # Quota/rate-limit soft skip
        quota = any(
            x in blob
            for x in ("rate limit", "429", "quota", "maxwaitms", "insufficient_quota")
        )
        report["pptx_ok"] = pptx_ok
        report["img_ok"] = img_ok
        report["bad_tokens"] = bad
        report["quota_soft"] = quota

        if bad and not quota:
            report["verdict"] = "FAIL"
            code = 1
        elif pptx_ok and img_ok:
            report["verdict"] = "PASS"
            code = 0
        elif quota and (pptx_ok or img_ok):
            report["verdict"] = "PASS_PARTIAL_QUOTA"
            code = 0
        else:
            report["verdict"] = "FAIL"
            code = 1

        (OUT / "report.json").write_text(
            json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        print(json.dumps({"verdict": report["verdict"], "pptx": newest_pptx, "img": newest_img, "bad": bad}, ensure_ascii=False))
        return code
    finally:
        try:
            c.close()
        except Exception:
            pass


if __name__ == "__main__":
    raise SystemExit(main())
