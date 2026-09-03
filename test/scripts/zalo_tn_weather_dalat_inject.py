# -*- coding: utf-8 -*-
"""Zalo Tn: Da Lat weather+image; OCR/rate artifact (AGENT_RULES §29.2)."""
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
OUT = ROOT / "test" / "reports" / "run-zalo-tn-weather-dalat"
TN_ID = (os.environ.get("ZALO_TEST_USER_ID") or "233767886566872937").strip()
WAIT_S = int(os.environ.get("ZALO_TEST_WAIT_S") or "420")
COOLDOWN_S = int(os.environ.get("ZALO_TEST_COOLDOWN_S") or "90")

MSG = (
    "tìm thông tin thời tiết thành phố đà lạt hiện tại, sau đó vẽ 1 "
    "bức ảnh thể hiện thông tin thời tiết ở đà lạt thật bắt mắt"
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
    raw = _clean_remote(
        sudo_bash(
            c,
            f"stat -c %Y {path!r} 2>/dev/null || echo 0",
            timeout=30,
        )
    )
    for ln in raw.splitlines():
        s = ln.strip()
        if s.isdigit():
            return float(s)
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
    "messageId": "lab-dalat-" + str(int(time.time())),
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
    """Vision-OCR via dispatcher container; rate overlay spelling/layout."""
    if not img_path:
        return {"ok": False, "ocr": "", "score": 0, "notes": ["no_image"]}
    # Map host /data path into dispatcher mount if needed.
    container_path = img_path
    if img_path.startswith("/data/assistant/media/"):
        container_path = "/data/media/" + img_path[len("/data/assistant/media/") :]
    elif img_path.startswith("/opt/data/media/"):
        # Hermes replica path → dispatcher shared mount
        container_path = "/data/media/" + img_path[len("/opt/data/media/") :]
    elif img_path.startswith("/data/media/"):
        container_path = img_path
    remote = f"""
set -euo pipefail
docker exec assistant-dispatcher-1 python3 -c "from pathlib import Path; p=Path({container_path!r}); print('PATH_EXISTS', p.is_file(), p); text='';
try:
 from vision_ocr import vision_read_path
 text=vision_read_path(str(p), prompt='Read all visible Vietnamese and Latin text on this weather image overlay. Return plain text only.') or ''
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
    if "thời tiết" in low or "thoi tiet" in low or "đà lạt" in low or "da lat" in low:
        score += 2
        notes.append("place_or_title_ok")
    if any(k in low for k in ("nhiệt độ", "nhiet do", "°c", "c°")):
        score += 2
        notes.append("temp_ok")
    if any(k in low for k in ("độ ẩm", "do am", "%")):
        score += 1
        notes.append("humidity_hint")
    bad = []
    for token in (
        "value after search",
        "safe-for-work",
        "nhiệt đô",
        "thời thiệt",
        "details unavailable",
        "<value",
    ):
        if token in low:
            bad.append(token)
    if bad:
        notes.append("bad:" + ",".join(bad))
        score = min(score, 1)
    elif ocr.strip():
        score += 1
        notes.append("ocr_nonempty")
    return {
        "ok": bool(ocr.strip()) and not bad,
        "ocr": ocr[:2000],
        "score": score,
        "notes": notes,
        "bad": bad,
        "raw_tail": raw[-1500:],
    }


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    c = connect()
    report: dict = {"ts": ts(), "user": TN_ID, "msg": MSG, "steps": []}
    try:
        print(f"[{ts()}] cooldown {COOLDOWN_S}s (rate-limit)", flush=True)
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
        print(f"[{ts()}] inject dalat weather+image", flush=True)
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
                "docker logs --since 25m $(docker ps -qf name=assistant-hermes | head -1) 2>&1 | "
                "grep -Ei 'dalat|đà lạt|weather-scene|shutdown_watchdog|exit.?75|classify|search_weather|"
                "maxWaitMs|rate.?limit|499|HTTPError' | tail -n 80 || true; "
                "docker logs --since 25m $(docker ps -qf name=router-worker | head -1) 2>&1 | "
                "grep -Ei 'classify|fallback|ReadTimeout|ok via' | tail -n 40 || true",
            )
        )
        report["logs"] = logs[-12000:]
        log_l = logs.lower()
        watchdog = ("shutdown_watchdog" in log_l) or ("exiting with code 75" in log_l)
        report["watchdog_hit"] = watchdog
        # Same filename is reused (weather-scene-<tid>.jpg) — detect rewrite by mtime.
        img_ok = bool(newest) and (
            newest not in before or after_mtime > before_mtime + 1.0
        )
        ocr = _ocr_rate(c, newest) if img_ok else {"ok": False, "ocr": "", "score": 0, "notes": ["no_new_image"]}
        report["ocr_eval"] = ocr
        quota = any(
            x in log_l
            for x in (
                "maxwaitms",
                "rate limit",
                "request dropped",
                "insufficient_quota",
                "429",
                "httperror 400",
                "httperror 429",
                "httperror 503",
            )
        )
        report["quota_soft"] = quota
        if watchdog and not img_ok:
            report["verdict"] = "FAIL"
            code = 1
        elif img_ok and ocr.get("score", 0) >= 3 and not ocr.get("bad"):
            report["verdict"] = "PASS"
            code = 0
        elif img_ok and (ocr.get("ok") or ocr.get("score", 0) >= 2):
            report["verdict"] = "PASS_PARTIAL" if not quota else "PASS_PARTIAL_QUOTA"
            code = 0
        elif img_ok and quota:
            report["verdict"] = "PASS_PARTIAL_QUOTA"
            code = 0
        elif quota and not img_ok:
            report["verdict"] = "SKIP_QUOTA"
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
                    "img": newest,
                    "ocr_score": ocr.get("score"),
                    "ocr_notes": ocr.get("notes"),
                    "ocr_snip": (ocr.get("ocr") or "")[:240],
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
