# -*- coding: utf-8 -*-
"""Concurrent Tn inject: scenic Hanoi image + Da Nang weather PDF (AGENT_RULES §29.2).

Must deliver ONE new image and ONE substantial weather PDF — not two PDFs / zero images.
Env: ASSISTANT_SSH_* ; ZALO_TEST_USER_ID ; ZALO_TEST_WAIT_S ; ZALO_TEST_COOLDOWN_S (default 0 — no artificial Omni queue wait)
Report: test/reports/run-zalo-tn-concurrent-scenic-pdf/
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
OUT = ROOT / "test" / "reports" / "run-zalo-tn-concurrent-scenic-pdf"
TN_ID = (os.environ.get("ZALO_TEST_USER_ID") or "").strip()
WAIT_S = int(os.environ.get("ZALO_TEST_WAIT_S") or "480")
COOLDOWN_S = int(os.environ.get("ZALO_TEST_COOLDOWN_S") or "0")
GAP_S = int(os.environ.get("ZALO_TEST_INJECT_GAP_S") or "8")

MSG_SCENE = "vẽ hình thành phố hà nội giờ hiện tại"
MSG_PDF = (
    "cập nhật thời tiết hiện tại ở Đà Nẵng và vẽ vào file pdf, "
    "giao diện phải bắt mắt và hợp gu người nhìn"
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


def _list_media(c, glob_pat: str, n: int = 20) -> list[str]:
    raw = _clean(
        sudo_bash(
            c,
            f"ls -1t /data/assistant/media/out/{glob_pat} 2>/dev/null | head -{n} || true",
            timeout=30,
        )
    )
    out = []
    for ln in raw.splitlines():
        if ln.startswith("/") and "_smoke" not in ln.lower() and "_overlay_crop" not in ln.lower():
            out.append(ln)
    return out


def _stat_mtime_size(c, path: str) -> tuple[float, int]:
    if not path:
        return 0.0, 0
    raw = _clean(
        sudo_bash(c, f"stat -c '%Y %s' {path!r} 2>/dev/null || echo '0 0'", timeout=30)
    )
    for ln in raw.splitlines():
        parts = ln.split()
        if len(parts) >= 2 and parts[0].isdigit() and parts[1].isdigit():
            return float(parts[0]), int(parts[1])
    return 0.0, 0


def _inject(c, text: str, label: str) -> str:
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
    "messageId": "lab-conc-" + {label!r} + "-" + str(int(time.time())),
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
    return _clean(sudo_bash(c, remote, timeout=60))


def _to_container(path: str) -> str:
    if path.startswith("/data/assistant/media/"):
        return "/data/media/" + path[len("/data/assistant/media/") :]
    if path.startswith("/opt/data/media/"):
        return "/data/media/" + path[len("/opt/data/media/") :]
    return path


def _vision_rate_image(c, img_path: str) -> dict:
    if not img_path:
        return {"ok": False, "notes": ["no_image"], "desc": "", "score": 0}
    cp = _to_container(img_path)
    remote = f"""
set -euo pipefail
set -a; . /opt/assistant/.env; set +a
cat > /tmp/rate_vision_img.py <<'PY'
import base64, json, os, urllib.request, io
from pathlib import Path
p = Path({cp!r})
print("PATH_EXISTS", p.is_file(), p.stat().st_size if p.is_file() else 0)
if not p.is_file():
    raise SystemExit(0)
blob = p.read_bytes()
mime = "image/jpeg"
try:
    from PIL import Image
    im = Image.open(io.BytesIO(blob)).convert("RGB")
    im.thumbnail((1280, 1280))
    buf = io.BytesIO()
    im.save(buf, format="JPEG", quality=85)
    blob = buf.getvalue()
except Exception as e:
    print("PIL_FALLBACK", type(e).__name__)
    low = p.suffix.lower()
    mime = "image/png" if low == ".png" else ("image/webp" if low == ".webp" else "image/jpeg")
b64 = base64.b64encode(blob).decode("ascii")
key = (os.environ.get("OMNIROUTER_API_KEY") or "").strip()
base = (os.environ.get("OMNIROUTER_BASE_URL") or "http://omni-router:20129/v1").rstrip("/")
model = (os.environ.get("OCR_MODEL") or os.environ.get("OMNIROUTER_VISION_COMBO") or "vision-ocr").strip()
body = json.dumps({{
    "model": model,
    "stream": False,
    "max_tokens": 220,
    "messages": [{{
        "role": "user",
        "content": [
            {{"type": "text", "text": "Describe this image in 3 short lines. Is it a photorealistic outdoor city/place photograph (not a blank page, not a PDF page dump)? Mention city cues if any. Plain text only."}},
            {{"type": "image_url", "image_url": {{"url": "data:" + mime + ";base64," + b64}}}},
        ],
    }}],
}}).encode()
req = urllib.request.Request(
    base + "/chat/completions",
    data=body,
    method="POST",
    headers={{"Authorization": "Bearer " + key, "Content-Type": "application/json"}},
)
text = ""
try:
    with urllib.request.urlopen(req, timeout=120) as resp:
        data = json.loads(resp.read().decode() or "{{}}")
    text = (((data.get("choices") or [{{}}])[0].get("message") or {{}}).get("content") or "").strip()
except Exception as e:
    err = ""
    if hasattr(e, "read"):
        try:
            err = e.read().decode("utf-8", "replace")[:240]
        except Exception:
            err = ""
    print("VISION_FAIL", type(e).__name__, getattr(e, "code", None), err)
print("VISION_BEGIN")
print(text)
print("VISION_END")
PY
docker cp /tmp/rate_vision_img.py assistant-dispatcher-1:/tmp/rate_vision_img.py
docker exec -e OMNIROUTER_API_KEY -e OMNIROUTER_BASE_URL=http://omni-router:20129/v1 -e OCR_MODEL -e OMNIROUTER_VISION_COMBO assistant-dispatcher-1 python3 /tmp/rate_vision_img.py
"""
    raw = _clean(sudo_bash(c, remote, timeout=240))
    desc = ""
    if "VISION_BEGIN" in raw and "VISION_END" in raw:
        desc = raw.split("VISION_BEGIN", 1)[1].split("VISION_END", 1)[0].strip()
    low = (desc or "").lower()
    notes: list[str] = []
    score = 0
    if any(
        x in low
        for x in (
            "photo",
            "photograph",
            "city",
            "street",
            "skyline",
            "building",
            "hanoi",
            "hà nội",
            "ha noi",
            "motorbike",
            "bridge",
        )
    ):
        score += 3
        notes.append("city_photo_cues")
    # Negated phrases like "not a blank page / PDF dump" must not fail a real photo.
    check = low
    for neg in (
        "not a blank page",
        "not a blank/pdf page",
        "not a pdf",
        "not blank",
        "not a document",
        "pdf dump",
    ):
        check = check.replace(neg, " ")
    if any(x in check for x in ("blank page", "empty page", "pdf page dump", "document page", "screenshot of text")):
        notes.append("bad_doc_like")
        score = min(score, 1)
    if "VISION_FAIL" in raw:
        notes.append("vision_fail")
    size_ok = "PATH_EXISTS True" in raw
    try:
        size_line = [ln for ln in raw.splitlines() if ln.startswith("PATH_EXISTS")][0]
        size = int(size_line.split()[-1])
    except Exception:
        size = 0
    if size >= 80_000:
        score += 1
        notes.append("size_ok")
    return {
        "ok": score >= 3 and "bad_doc_like" not in notes and size_ok,
        "score": score,
        "notes": notes,
        "desc": desc[:1500],
        "size": size,
        "raw_tail": raw[-800:],
    }


def _rate_pdf(c, pdf_path: str) -> dict:
    if not pdf_path:
        return {"ok": False, "notes": ["no_pdf"], "text": "", "size": 0, "score": 0}
    cp = _to_container(pdf_path)
    remote = f"""
set -euo pipefail
cat > /tmp/rate_pdf_doc.py <<'PY'
from pathlib import Path
p = Path({cp!r})
print("EXISTS", p.is_file())
print("SIZE", p.stat().st_size if p.is_file() else 0)
text = ""
try:
    import pymupdf
    doc = pymupdf.open(str(p))
    text = "\\n".join((page.get_text() or "") for page in doc[:2])
    print("PAGES", doc.page_count)
except Exception as e1:
    try:
        from pypdf import PdfReader
        r = PdfReader(str(p))
        text = "\\n".join((pg.extract_text() or "") for pg in r.pages[:2])
        print("PAGES", len(r.pages))
    except Exception as e2:
        print("EXTRACT_FAIL", type(e1).__name__, type(e2).__name__)
print("PDF_TEXT_BEGIN")
print(text[:3000])
print("PDF_TEXT_END")
PY
docker cp /tmp/rate_pdf_doc.py assistant-dispatcher-1:/tmp/rate_pdf_doc.py
docker exec assistant-dispatcher-1 python3 /tmp/rate_pdf_doc.py
"""
    raw = _clean(sudo_bash(c, remote, timeout=120))
    text = ""
    if "PDF_TEXT_BEGIN" in raw and "PDF_TEXT_END" in raw:
        text = raw.split("PDF_TEXT_BEGIN", 1)[1].split("PDF_TEXT_END", 1)[0].strip()
    size = 0
    for ln in raw.splitlines():
        if ln.startswith("SIZE "):
            try:
                size = int(ln.split()[1])
            except Exception:
                pass
    low = (text or "").lower()
    notes: list[str] = []
    score = 0
    bad: list[str] = []
    if any(x in low for x in ("đà nẵng", "da nang", "danang")):
        score += 2
        notes.append("city_ok")
    if any(x in low for x in ("nhiệt độ", "nhiet do", "°c", "c°")):
        score += 3
        notes.append("temp_ok")
    if any(x in low for x in ("độ ẩm", "do am", "gió", "gio", "thời tiết", "thoi tiet", "%", "km/h")):
        score += 2
        notes.append("metric_ok")
    if size >= 12_000:
        score += 1
        notes.append("size_ok")
    elif size > 0 and size < 5000:
        bad.append("tiny_pdf")
        notes.append("tiny_pdf")
    for token in ("value after search", "safe-for-work", "|------", "accuweather", "dubaothoitiet"):
        if token in low:
            bad.append(token)
    if any(x in low for x in ("hà nội", "ha noi", "hanoi")) and "đà nẵng" not in low and "da nang" not in low:
        bad.append("wrong_city")
        notes.append("wrong_city")
    return {
        "ok": score >= 5 and not bad and size >= 12_000,
        "score": score,
        "notes": notes,
        "bad": bad,
        "text": text[:2000],
        "size": size,
        "raw_tail": raw[-1000:],
    }

def main() -> int:
    if not TN_ID:
        print("ERROR: ZALO_TEST_USER_ID is required", file=sys.stderr)
        return 2
    OUT.mkdir(parents=True, exist_ok=True)
    c = connect()
    report: dict = {
        "ts": ts(),
        "user": TN_ID,
        "msgs": {"scene": MSG_SCENE, "pdf": MSG_PDF},
        "steps": [],
    }
    try:
        if COOLDOWN_S > 0:
            print(f"[{ts()}] cooldown {COOLDOWN_S}s (optional)", flush=True)
            time.sleep(COOLDOWN_S)
        else:
            print(f"[{ts()}] no cooldown (ZALO_TEST_COOLDOWN_S=0)", flush=True)

        imgs_before = _list_media(c, "*.{jpg,jpeg,webp,png}")
        pdfs_before = _list_media(c, "*.pdf")
        report["imgs_before"] = imgs_before[:8]
        report["pdfs_before"] = pdfs_before[:8]
        b_img_m = {p: _stat_mtime_size(c, p) for p in imgs_before[:5]}
        b_pdf_m = {p: _stat_mtime_size(c, p) for p in pdfs_before[:5]}

        print(f"[{ts()}] inject scenic Hanoi", flush=True)
        report["steps"].append({"scene_inject": _inject(c, MSG_SCENE, "hanoi")[-400:]})
        time.sleep(GAP_S)
        print(f"[{ts()}] inject Da Nang weather PDF", flush=True)
        report["steps"].append({"pdf_inject": _inject(c, MSG_PDF, "danang-pdf")[-400:]})

        print(f"[{ts()}] wait {WAIT_S}s", flush=True)
        time.sleep(WAIT_S)

        imgs_after = _list_media(c, "*.{jpg,jpeg,webp,png}")
        pdfs_after = _list_media(c, "*.pdf")
        report["imgs_after"] = imgs_after[:12]
        report["pdfs_after"] = pdfs_after[:12]

        new_imgs = []
        for p in imgs_after:
            mt, sz = _stat_mtime_size(c, p)
            old = b_img_m.get(p)
            if p not in b_img_m or (old and mt > old[0] + 1):
                if p not in {x[0] for x in new_imgs}:
                    new_imgs.append((p, mt, sz))
        # Prefer files newer than inject window start: use top after list not in before
        new_imgs2 = [p for p in imgs_after if p not in imgs_before][:5]
        if not new_imgs2:
            # rewritten same name — take newest if mtime advanced
            if imgs_after:
                p = imgs_after[0]
                mt, sz = _stat_mtime_size(c, p)
                if not b_img_m or mt > max((v[0] for v in b_img_m.values()), default=0) + 1:
                    new_imgs2 = [p]

        new_pdfs = [p for p in pdfs_after if p not in pdfs_before][:5]
        if not new_pdfs and pdfs_after:
            p = pdfs_after[0]
            mt, sz = _stat_mtime_size(c, p)
            if not b_pdf_m or mt > max((v[0] for v in b_pdf_m.values()), default=0) + 1:
                new_pdfs = [p]

        report["new_imgs"] = new_imgs2
        report["new_pdfs"] = new_pdfs

        logs = _clean(
            sudo_bash(
                c,
                "docker logs --since 25m $(docker ps -qf name=assistant-hermes | head -1) 2>&1 | "
                "grep -Ei 'hanoi|hà nội|đà nẵng|danang|scene_image|weather|office|maxWaitMs|"
                "rate-limit|HTTPError|shutdown_watchdog|share.file|pdf' | tail -n 80 || true; "
                "journalctl --user -u com.hermes.zaloplugin -n 40 --no-pager 2>/dev/null || true",
                timeout=60,
            )
        )
        report["logs"] = logs[-12000:]
        log_l = logs.lower()
        quota = any(
            x in log_l
            for x in ("maxwaitms", "rate limit", "request dropped", "insufficient_quota", "429")
        )
        report["quota_soft"] = quota

        # Evaluate artifacts (space vision calls)
        img_eval = {"ok": False, "notes": ["no_new_image"]}
        if new_imgs2:
            print(f"[{ts()}] vision-rate image {new_imgs2[0]}", flush=True)
            time.sleep(15)
            img_eval = _vision_rate_image(c, new_imgs2[0])
        report["img_eval"] = img_eval

        pdf_evals = []
        for i, pdf in enumerate(new_pdfs[:3]):
            print(f"[{ts()}] rate pdf {pdf}", flush=True)
            if i:
                time.sleep(8)
            pdf_evals.append({"path": pdf, **_rate_pdf(c, pdf)})
        report["pdf_evals"] = pdf_evals

        best_pdf = next((p for p in pdf_evals if p.get("ok")), None)
        tiny_only = bool(pdf_evals) and all(
            (p.get("size") or 0) < 5000 or "tiny_pdf" in (p.get("bad") or []) for p in pdf_evals
        )
        two_pdfs_no_img = len(new_pdfs) >= 2 and not new_imgs2
        wrong = any("wrong_city" in (p.get("bad") or []) for p in pdf_evals)

        if two_pdfs_no_img:
            report["verdict"] = "FAIL"
            report["fail_reason"] = "two_pdfs_no_image"
            code = 1
        elif wrong:
            report["verdict"] = "FAIL"
            report["fail_reason"] = "wrong_city_in_pdf"
            code = 1
        elif tiny_only and new_pdfs and not (img_eval.get("ok") and best_pdf):
            report["verdict"] = "FAIL"
            report["fail_reason"] = "tiny_or_empty_pdf"
            code = 1
        elif img_eval.get("ok") and best_pdf:
            report["verdict"] = "PASS"
            code = 0
        elif quota and (not new_imgs2 or not new_pdfs):
            report["verdict"] = "SKIP_QUOTA"
            code = 0
        elif img_eval.get("ok") and new_pdfs and not best_pdf and quota:
            report["verdict"] = "PASS_PARTIAL_QUOTA"
            code = 0
        else:
            report["verdict"] = "FAIL"
            report["fail_reason"] = "missing_or_weak_artifacts"
            code = 1

        (OUT / "report.json").write_text(
            json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        print(
            json.dumps(
                {
                    "verdict": report["verdict"],
                    "fail_reason": report.get("fail_reason"),
                    "new_imgs": new_imgs2,
                    "new_pdfs": new_pdfs,
                    "img_ok": img_eval.get("ok"),
                    "img_notes": img_eval.get("notes"),
                    "img_desc": (img_eval.get("desc") or "")[:220],
                    "pdf_best": bool(best_pdf),
                    "pdf_sizes": [p.get("size") for p in pdf_evals],
                    "pdf_notes": [p.get("notes") for p in pdf_evals],
                    "pdf_snip": ((best_pdf or (pdf_evals[0] if pdf_evals else {})).get("text") or "")[
                        :220
                    ],
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
