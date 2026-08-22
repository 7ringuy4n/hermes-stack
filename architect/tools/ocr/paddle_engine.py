"""PaddleOCR engine — primary local OCR for images (Media Worker boundary).

Lazy-loads a single PaddleOCR instance and runs inference on a dedicated
thread pool so FastAPI request handlers (and sibling Media Worker containers
such as dispatcher/ASR) are not blocked by model load or GPU/CPU inference.
"""
from __future__ import annotations

import io
import os
import threading
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeout
from pathlib import Path
from typing import Any, Optional

# Env (all optional — defaults keep the lab lean):
#   OCR_PADDLE=1|0          enable paddle (default 1 when installed)
#   OCR_PADDLE_LANG         unused on 3.x multilingual PP-OCRv5; kept for docs
#   OCR_PADDLE_TIMEOUT_S    per-image inference budget (default 90)
#   OCR_PADDLE_MOBILE=1     prefer mobile det/rec when the API accepts names
#   OCR_PADDLE_WORKERS      thread pool size (default 1 — model is not re-entrant)

ENABLED = (os.environ.get("OCR_PADDLE") or "1").strip().lower() not in {
    "0",
    "false",
    "no",
    "off",
}
TIMEOUT_S = float(os.environ.get("OCR_PADDLE_TIMEOUT_S", "90"))
MOBILE = (os.environ.get("OCR_PADDLE_MOBILE") or "1").strip().lower() not in {
    "0",
    "false",
    "no",
    "off",
}
WORKERS = max(1, min(int(os.environ.get("OCR_PADDLE_WORKERS", "1")), 2))

_lock = threading.Lock()
_engine: Any = None
_engine_error: str = ""
_pool: ThreadPoolExecutor | None = None


def available() -> bool:
    if not ENABLED:
        return False
    try:
        import paddleocr  # noqa: F401
    except Exception:
        return False
    return True


def ready() -> dict[str, Any]:
    return {
        "paddle": available(),
        "paddle_enabled": ENABLED,
        "paddle_loaded": _engine is not None,
        "paddle_error": _engine_error[:200] if _engine_error else "",
        "paddle_mobile": MOBILE,
    }


def _pool_get() -> ThreadPoolExecutor:
    global _pool
    if _pool is None:
        _pool = ThreadPoolExecutor(max_workers=WORKERS, thread_name_prefix="paddle-ocr")
    return _pool


def _build_engine() -> Any:
    from paddleocr import PaddleOCR

    base = {
        "use_doc_orientation_classify": False,
        "use_doc_unwarping": False,
        "use_textline_orientation": False,
    }
    attempts: list[dict[str, Any]] = []
    if MOBILE:
        attempts.append(
            {
                **base,
                "text_detection_model_name": "PP-OCRv5_mobile_det",
                "text_recognition_model_name": "PP-OCRv5_mobile_rec",
            }
        )
    attempts.append(dict(base))
    attempts.append({})
    # 2.x-compatible last resort (no show_log — rejected by 3.x).
    attempts.append({"use_angle_cls": True, "lang": "en"})

    last: Exception | None = None
    for kwargs in attempts:
        try:
            return PaddleOCR(**kwargs)
        except (TypeError, ValueError) as e:
            last = e
            continue
    raise RuntimeError(f"PaddleOCR init failed: {last}")


def _get_engine() -> Any:
    global _engine, _engine_error
    if _engine is not None:
        return _engine
    with _lock:
        if _engine is not None:
            return _engine
        try:
            _engine = _build_engine()
            _engine_error = ""
        except Exception as e:  # noqa: BLE001
            _engine_error = f"{type(e).__name__}: {e}"
            raise
        return _engine


def _lines_from_result(result: Any) -> list[str]:
    """Normalize paddleocr 2.x/3.x result shapes into plain text lines."""
    lines: list[str] = []
    if result is None:
        return lines

    # 3.x predict() → list of result objects with .json / .get("rec_texts")
    if isinstance(result, list) and result and not isinstance(result[0], list):
        for item in result:
            texts = None
            scores = None
            if hasattr(item, "get"):
                texts = item.get("rec_texts") or item.get("rec_text")
                scores = item.get("rec_scores")
            elif hasattr(item, "json") and isinstance(item.json, dict):
                payload = item.json.get("res") if "res" in item.json else item.json
                if isinstance(payload, dict):
                    texts = payload.get("rec_texts") or payload.get("rec_text")
                    scores = payload.get("rec_scores")
            if isinstance(texts, str):
                texts = [texts]
            if texts:
                for i, t in enumerate(texts):
                    s = str(t or "").strip()
                    if not s:
                        continue
                    if scores and i < len(scores):
                        try:
                            if float(scores[i]) < 0.3:
                                continue
                        except (TypeError, ValueError):
                            pass
                    lines.append(s)
                continue
            # Fallback: print()/str dump is too noisy — skip
        if lines:
            return lines

    # 2.x ocr() → [ [ [box], (text, score) ], ... ] per page
    pages = result if isinstance(result, list) else [result]
    for page in pages:
        if not page:
            continue
        for row in page:
            if not row or len(row) < 2:
                continue
            rec = row[1]
            if isinstance(rec, (list, tuple)) and rec:
                text = str(rec[0] or "").strip()
                score = float(rec[1]) if len(rec) > 1 else 1.0
            else:
                text = str(rec or "").strip()
                score = 1.0
            if text and score >= 0.3:
                lines.append(text)
    return lines


def _run_path(path: str) -> str:
    engine = _get_engine()
    if hasattr(engine, "predict"):
        result = engine.predict(input=path)
    else:
        result = engine.ocr(path, cls=True)
    return "\n".join(_lines_from_result(result)).strip()


def _run_bytes(data: bytes) -> str:
    from PIL import Image
    import tempfile

    im = Image.open(io.BytesIO(data))
    if im.mode not in {"RGB", "L"}:
        im = im.convert("RGB")
    # Prefer a temp file — some paddle builds accept ndarray, not all.
    with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
        im.save(tmp, format="PNG")
        tmp_path = tmp.name
    try:
        return _run_path(tmp_path)
    finally:
        try:
            Path(tmp_path).unlink(missing_ok=True)
        except OSError:
            pass


def extract_text(*, path: Optional[Path] = None, image_b64: Optional[str] = None) -> tuple[str, str]:
    """Return (text, error). Empty text with empty error means no glyphs found."""
    if not ENABLED:
        return "", "paddle_disabled"
    if not available():
        return "", "paddle_not_installed"
    try:
        if path is not None:
            fut = _pool_get().submit(_run_path, str(path))
        elif image_b64:
            import base64

            fut = _pool_get().submit(_run_bytes, base64.b64decode(image_b64))
        else:
            return "", "no_input"
        text = fut.result(timeout=TIMEOUT_S)
        return (text or "").strip(), ""
    except FuturesTimeout:
        return "", "paddle_timeout"
    except Exception as e:  # noqa: BLE001
        return "", f"{type(e).__name__}: {e}"[:200]
