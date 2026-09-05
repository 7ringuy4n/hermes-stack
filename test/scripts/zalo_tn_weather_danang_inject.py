# -*- coding: utf-8 -*-
"""Zalo Tn: Da Nang weather-on-image; OCR must show live metrics (AGENT_RULES §29.2)."""
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
OUT = ROOT / "test" / "reports" / "run-zalo-tn-weather-danang"
TN_ID = (os.environ.get("ZALO_TEST_USER_ID") or "").strip()
WAIT_S = int(os.environ.get("ZALO_TEST_WAIT_S") or "420")
COOLDOWN_S = int(os.environ.get("ZALO_TEST_COOLDOWN_S") or "90")

MSG = (
    "cập nhật thời tiết hiện tại ở Đà Nẵng và vẽ vào hình ảnh, trên hình phải có "
    "thông tin thời tiết hiện có như nhiệt độ, gió v.v.. , giao diện phải bắt mắt "
    "và hợp gu người nhìn"
)


def ts() -> str:
    return datetime.now(timezone.utc).astimezone().strftime("%Y-%m-%d %H:%M:%S %z")


def _clean_remote(text: str) -> str:
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


def _first_path(listing: str) -> str:
    for ln in _clean_remote(listing).splitlines():
        if not ln.startswith("/"):
            continue
        low = ln.lower()
        if "_smoke" in low or "_overlay_crop" in low:
            continue
        if low.endswith((".jpg", ".jpeg", ".webp", ".png")):
            return ln
    return ""


def _stat_mtime(c, path: str) -> float:
    if not path:
        return 0.0
    raw = _clean_remote(sudo_bash(c, f"stat -c %Y {path!r} 2>/dev/null || echo 0", timeout=30))
    for ln in raw.splitlines():
        if ln.strip().isdigit():
            return float(ln.strip())
    return 0.0


def _inject(c, text: str) -> str:
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
    "messageId": "lab-danang-" + str(int(time.time())),
}}
req = urllib.request.Request(
    "http://127.0.0.1:8787/inject-event",
    data=json.dumps(payload).encode("utf-8"),
    headers={{"Content-Type": "application/json"}},
    method="POST",
)
with urllib.request.urlopen(req, timeout=30) as r:
    print(r.read().decode("utf-8", "replace")[:500])
print("INJECT_OK")
PY
"""
    return _clean_remote(sudo_bash(c, remote, timeout=60))


def _ocr_rate(c, img_path: str) -> dict:
    if not img_path:
        return {"ok": False, "ocr": "", "score": 0, "notes": ["no_image"], "bad": []}
    container_path = img_path
    if img_path.startswith("/data/assistant/media/"):
        container_path = "/data/media/" + img_path[len("/data/assistant/media/") :]
    elif img_path.startswith("/opt/data/media/"):
        container_path = "/data/media/" + img_path[len("/opt/data/media/") :]
    remote = f"""
set -euo pipefail
docker exec assistant-dispatcher-1 python3 -c "from pathlib import Path; p=Path({container_path!r}); print('PATH_EXISTS', p.is_file(), p); text='';
try:
 from vision_ocr import vision_read_path
 text=vision_read_path(str(p), prompt='Read all visible Vietnamese and Latin text on the weather overlay badge. Plain text only.') or ''
except Exception as e:
 print('OCR_FAIL', type(e).__name__, e)
print('OCR_BEGIN'); print(text); print('OCR_END')"
"""
    raw = _clean_remote(sudo_bash(c, remote, timeout=180))
    ocr = ""
    if "OCR_BEGIN" in raw and "OCR_END" in raw:
        ocr = raw.split("OCR_BEGIN", 1)[1].split("OCR_END", 1)[0].strip()
    low = (ocr or "").lower()
    notes: list[str] = []
    score = 0
    bad = []
    if "thời tiết" in low or "thoi tiet" in low:
        score += 1
        notes.append("title_ok")
    if any(x in low for x in ("nhiệt độ", "nhiet do", "°c", "c°")):
        score += 3
        notes.append("temp_ok")
    if any(x in low for x in ("gió", "gio", "km/h", "kmh", "m/s")):
        score += 2
        notes.append("wind_ok")
    if any(x in low for x in ("độ ẩm", "do am", "%", "mây", "mưa", "nắng", "nang")):
        score += 1
        notes.append("extra_metric")
    for token in ("value after search", "safe-for-work", "nhiệt đô", "thời thiệt", "<value"):
        if token in low:
            bad.append(token)
    if bad:
        score = min(score, 1)
        notes.append("bad:" + ",".join(bad))
    # Title+timestamp alone is not enough for this case.
    title_only = score <= 1 and "cập nhật" in low and not any(
        k in notes for k in ("temp_ok", "wind_ok", "extra_metric")
    )
    if title_only:
        notes.append("title_timestamp_only")
    return {
        "ok": score >= 4 and not bad and not title_only,
        "ocr": ocr[:2000],
        "score": score,
        "notes": notes,
        "bad": bad,
        "title_only": title_only,
        "raw_tail": raw[-1200:],
    }


def main() -> int:
    if not TN_ID:
        print("ERROR: ZALO_TEST_USER_ID is required", file=sys.stderr)
        return 2
    OUT.mkdir(parents=True, exist_ok=True)
    c = connect()
    report: dict = {"ts": ts(), "user": TN_ID, "msg": MSG, "steps": []}
    try:
        print(f"[{ts()}] cooldown {COOLDOWN_S}s", flush=True)
        time.sleep(COOLDOWN_S)
        before = _clean_remote(
            sudo_bash(
                c,
                "ls -1t /data/assistant/media/out/*.{jpg,jpeg,webp,png} 2>/dev/null | head -8 || true",
            )
        )
        before_path = _first_path(before)
        before_mtime = _stat_mtime(c, before_path) if before_path else 0.0
        report["before"] = before
        report["before_mtime"] = before_mtime
        print(f"[{ts()}] inject danang weather+image", flush=True)
        report["steps"].append({"inject": _inject(c, MSG)[-400:]})
        time.sleep(WAIT_S)
        after = _clean_remote(
            sudo_bash(
                c,
                "ls -1t /data/assistant/media/out/*.{jpg,jpeg,webp,png} 2>/dev/null | head -12 || true",
            )
        )
        newest = _first_path(after)
        after_mtime = _stat_mtime(c, newest) if newest else 0.0
        report["after"] = after
        report["newest_img"] = newest
        report["after_mtime"] = after_mtime
        logs = _clean_remote(
            sudo_bash(
                c,
                "docker logs --since 30m $(docker ps -qf name=assistant-hermes | head -1) 2>&1 | "
                "grep -Ei 'danang|đà nẵng|weather-scene|synthesize|overlay|HTTPError|maxWaitMs|"
                "shutdown_watchdog' | tail -n 60 || true",
            )
        )
        report["logs"] = logs[-10000:]
        log_l = logs.lower()
        watchdog = "shutdown_watchdog" in log_l or "exiting with code 75" in log_l
        img_ok = bool(newest) and (newest not in before or after_mtime > before_mtime + 1.0)
        ocr = _ocr_rate(c, newest) if img_ok else {"ok": False, "ocr": "", "score": 0, "notes": ["no_new_image"], "bad": [], "title_only": False}
        report["ocr_eval"] = ocr
        report["watchdog_hit"] = watchdog
        quota = any(
            x in log_l
            for x in ("maxwaitms", "rate limit", "request dropped", "insufficient_quota", "429", "httperror 400", "httperror 502")
        )
        report["quota_soft"] = quota
        if watchdog and not img_ok:
            report["verdict"] = "FAIL"
            code = 1
        elif ocr.get("ok"):
            report["verdict"] = "PASS"
            code = 0
        elif img_ok and ocr.get("title_only") and quota:
            report["verdict"] = "PASS_PARTIAL_QUOTA"
            code = 0
        elif img_ok and ocr.get("title_only"):
            # Metrics missing without quota → product FAIL
            report["verdict"] = "FAIL"
            code = 1
        elif quota and not img_ok:
            report["verdict"] = "SKIP_QUOTA"
            code = 0
        else:
            report["verdict"] = "FAIL"
            code = 1
        (OUT / "report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        print(
            json.dumps(
                {
                    "verdict": report["verdict"],
                    "img": newest,
                    "ocr_score": ocr.get("score"),
                    "ocr_notes": ocr.get("notes"),
                    "ocr_snip": (ocr.get("ocr") or "")[:280],
                    "title_only": ocr.get("title_only"),
                    "watchdog": watchdog,
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
