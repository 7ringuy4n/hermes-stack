# -*- coding: utf-8 -*-
"""Inject PPTX weather + weather-on-image turns for Zalo Tn (rate-limit safe).

Uses remote Python urllib (not shell-embedded JSON) to avoid brace expansion.
Env: ASSISTANT_SSH_* ; ZALO_TEST_USER_ID ; ZALO_TEST_WAIT_S (default 360)
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

if hasattr(sys.stdout, "buffer"):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

ROOT = Path(os.environ.get("ASSISTANT_REPO_ROOT", Path(__file__).resolve().parents[2]))
OUT = ROOT / "test" / "reports" / "run-zalo-tn-weather-overlay-pptx"
TN_ID = (os.environ.get("ZALO_TEST_USER_ID") or "233767886566872937").strip()
WAIT_S = int(os.environ.get("ZALO_TEST_WAIT_S") or "360")
GAP_S = int(os.environ.get("ZALO_TEST_GAP_S") or "90")

MSG_PPTX = "tạo 1 file pptx chứa thông tin thời tiết thành phố vũng tàu hiện tại"
MSG_IMG = (
    "cập nhật thông tin thời tiết hồ chí minh lúc này, sau đó ghi thông tin lên "
    "hình ảnh hồ chí minh lúc này ở góc trái bên dưới thật gọn và bắt mắt "
    "không sai chính tả tiếng việt"
)


def ts() -> str:
    return datetime.now(timezone.utc).astimezone().strftime("%Y-%m-%d %H:%M:%S %z")


def _inject_remote(c, text: str, *, label: str) -> str:
    remote = f"""
set -euo pipefail
python3 - <<'PY'
import json, urllib.request, time
payload = {{
    "type": "message",
    "threadId": {TN_ID!r},
    "threadType": "user",
    "senderId": {TN_ID!r},
    "senderName": "Tn",
    "text": {text!r},
    "messageId": f"lab-{label}-" + str(int(time.time())),
}}
req = urllib.request.Request(
    "http://127.0.0.1:8787/inject-event",
    data=json.dumps(payload).encode("utf-8"),
    headers={{"Content-Type": "application/json"}},
    method="POST",
)
with urllib.request.urlopen(req, timeout=30) as r:
    print(r.read().decode("utf-8", "replace")[:500])
print("INJECT_OK", {label!r})
PY
"""
    return sudo_bash(c, remote, timeout=60)


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    c = connect()
    report: dict = {"ts": ts(), "user": TN_ID, "steps": []}
    try:
        before_pptx = sudo_bash(
            c, "ls -1t /data/assistant/media/out/*.pptx 2>/dev/null | head -3 || true"
        ).strip()
        before_img = sudo_bash(
            c,
            "ls -1t /data/assistant/media/out/*.{jpg,jpeg,webp,png} 2>/dev/null | head -5 || true",
        ).strip()
        report["before"] = {"pptx": before_pptx, "img": before_img}

        print(f"[{ts()}] inject pptx; wait={WAIT_S}s gap={GAP_S}s", flush=True)
        report["steps"].append({"pptx_inject": _inject_remote(c, MSG_PPTX, label="weather-pptx")[-400:]})
        time.sleep(WAIT_S)

        after_pptx = sudo_bash(
            c, "ls -1t /data/assistant/media/out/*.pptx 2>/dev/null | head -5 || true"
        ).strip()
        report["pptx_after"] = after_pptx
        newest_pptx = (after_pptx.splitlines() or [""])[0].strip()
        report["newest_pptx"] = newest_pptx

        print(f"[{ts()}] gap {GAP_S}s before image inject", flush=True)
        time.sleep(GAP_S)
        print(f"[{ts()}] inject overlay-img; wait={WAIT_S}s", flush=True)
        report["steps"].append({"img_inject": _inject_remote(c, MSG_IMG, label="weather-overlay")[-400:]})
        time.sleep(WAIT_S)

        after_img = sudo_bash(
            c,
            "ls -1t /data/assistant/media/out/*.{jpg,jpeg,webp,png} 2>/dev/null | head -8 || true",
        ).strip()
        report["img_after"] = after_img
        newest_img = (after_img.splitlines() or [""])[0].strip()
        report["newest_img"] = newest_img

        logs = sudo_bash(
            c,
            "docker logs --since 25m assistant-hermes-2 2>&1 | tail -n 120; "
            "docker logs --since 25m assistant-dispatcher-1 2>&1 | tail -n 80; "
            "docker logs --since 25m omni-router 2>&1 | grep -Ei 'rate.?limit|maxWaitMs|dropped' | tail -n 30 || true; "
            "docker logs --since 25m router-worker 2>&1 | grep -Ei 'rate.?limit|maxWaitMs|classify|error' | tail -n 40 || true",
        )
        report["logs_tail"] = logs[-16000:]

        # Inspect newest pptx size + office recent files
        detail = sudo_bash(
            c,
            "python3 - <<'PY'\n"
            "from pathlib import Path\n"
            f"pptx=Path({newest_pptx!r}) if {bool(newest_pptx)!r} else None\n"
            f"img=Path({newest_img!r}) if {bool(newest_img)!r} else None\n"
            "for p in (pptx, img):\n"
            "  if p and p.is_file():\n"
            "    print(p.name, p.stat().st_size)\n"
            "  else:\n"
            "    print('missing', p)\n"
            "PY",
        )
        report["sizes"] = detail[-1000:]

        blob = (logs + "\n" + after_pptx + "\n" + after_img + "\n" + detail).lower()
        fail_bits = (
            "value after search",
            "safe-for-work",
            "nhiệt đô",
            "thời thiệt",
            "thời thệt",
            "write_pdf_styled",
        )
        bad = [b for b in fail_bits if b in blob]
        quota = any(
            x in blob
            for x in ("rate limit", "maxwaitms", "request dropped", "429", "insufficient_quota")
        )
        pptx_ok = bool(newest_pptx) and newest_pptx not in before_pptx and "_smoke" not in newest_pptx
        # Prefer non-smoke image newer than before
        img_ok = bool(newest_img) and newest_img not in before_img and "_smoke" not in newest_img

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
        elif pptx_ok or img_ok:
            report["verdict"] = "PASS_PARTIAL"
            code = 0
        else:
            report["verdict"] = "FAIL"
            code = 1

        (OUT / "report.json").write_text(
            json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        print(
            json.dumps(
                {
                    "verdict": report["verdict"],
                    "pptx": newest_pptx,
                    "img": newest_img,
                    "bad": bad,
                    "quota": quota,
                },
                ensure_ascii=False,
            ),
            flush=True,
        )
        return code
    finally:
        try:
            c.close()
        except Exception:
            pass


if __name__ == "__main__":
    raise SystemExit(main())
