# -*- coding: utf-8 -*-
"""Unit: vision refuse — HTTP/API only; structural chunk quality (no phrase scan)."""
from __future__ import annotations

import io
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "architect" / "lib"))

from vision_refuse import llm_refused, vision_chunk_usable, vision_text_echoes_prompt  # noqa: E402
from vision_ocr import empty_scan_result  # noqa: E402

if hasattr(sys.stdout, "buffer"):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

OCR_DUMP = "Yutak\nES\nMAK"
REAL = [
    "HOA DON 1250000 VND",
    "| Ngay | So tien |\n| 01/08 | 250.000 |",
    "Invoice total: 1,250,000 VND\nCustomer: Nguyen Van A",
    (
        "Bức ảnh chụp skyline TP.HCM bên sông Sài Gòn lúc hoàng hôn, "
        "nổi bật tòa Bitexco và các tòa cao ốc ven sông."
    ),
]

DESCRIBE_PROMPT = (
    "Viết 2–4 câu tiếng Việt mô tả cảnh trong ảnh: vật thể chính, bối cảnh, ánh sáng, "
    "và chữ nhìn thấy (nếu có). Mô tả bằng câu hoàn chỉnh — không chỉ liệt kê nhãn/chữ "
    "rời trên vật thể."
)

BLIND_VI = (
    "Chào bạn, tôi đã sẵn sàng mô tả hình ảnh theo đúng yêu cầu của bạn. Tuy nhiên, "
    "hiện tại tôi chưa thấy hình ảnh nào được đính kèm trong tin nhắn. Vui lòng gửi ảnh "
    "lên để tôi có thể phân tích chi tiết bối cảnh, ánh sáng và các dòng chữ xuất hiện "
    "trong khung hình nhé."
)


def test_llm_refused_http_only() -> None:
    for status in (413, 422, 502):
        if not llm_refused(status, "", "HOA DON"):
            raise SystemExit(f"FAIL status {status} not treated as failure")
    if llm_refused(200, "", "HOA DON 1250000 VND"):
        raise SystemExit("FAIL 200 with clean text treated as HTTP failure")
    if not llm_refused(200, '{"error":{"message":"model_not_found"}}', ""):
        raise SystemExit("FAIL JSON error body not refused")
    # Wording alone must not trip refuse (combo retry + reply filters handle blind models).
    blind = "I don't see any image attached. Please upload the image."
    if llm_refused(200, "", blind):
        raise SystemExit("FAIL phrase blind reply treated as HTTP failure")
    print("OK llm_refused HTTP/API only")


def test_vision_text_echoes_prompt() -> None:
    if not vision_text_echoes_prompt(BLIND_VI, DESCRIBE_PROMPT):
        raise SystemExit("FAIL blind meta reply not detected as prompt echo")
    scene = REAL[-1]
    if vision_text_echoes_prompt(scene, DESCRIBE_PROMPT):
        raise SystemExit("FAIL real scene rejected as prompt echo")
    print("OK vision_text_echoes_prompt structural")


def test_vision_chunk_usable() -> None:
    if vision_chunk_usable(OCR_DUMP):
        raise SystemExit("FAIL OCR dump accepted")
    for text in REAL:
        if not vision_chunk_usable(text):
            raise SystemExit(f"FAIL real text rejected: {text[:60]!r}")
    print(f"OK vision_chunk_usable structural ({len(REAL)} samples)")


def test_empty_scan_ok() -> None:
    out = empty_scan_result("vision-ocr")
    assert out["ok"] is True and out["empty"] is True and out["text"] == ""
    assert out["via"] == "vision-ocr"
    assert empty_scan_result("")["via"] == "none"
    print("OK empty local scan is success, not ocr_failed")


def main() -> int:
    test_llm_refused_http_only()
    test_vision_text_echoes_prompt()
    test_vision_chunk_usable()
    test_empty_scan_ok()
    print("PASS ocr_refuse_unit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
