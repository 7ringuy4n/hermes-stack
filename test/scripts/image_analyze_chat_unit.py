# -*- coding: utf-8 -*-
"""Image analyze routes to Hermes chat; OCR noise filtered (no regex)."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "hermes" / "main" / "plugins" / "zalo"))

from attachment import ocr_excerpt_for_ack  # noqa: E402
from classify_client import (  # noqa: E402
    apply_image_analyze_plan_coercion,
    normalize_plan,
    plan_is_image_analyze_chat,
    plan_is_async,
)


def main() -> int:
    assert ocr_excerpt_for_ack("crn ae maa") == ""
    assert ocr_excerpt_for_ack("Hello world from OCR line") != ""

    misclassified = normalize_plan(
        {
            "task_hint": "file",
            "task_type": "file_processing",
            "skill": "media_file",
            "skill_action": "process_file",
            "execution_class": "async",
            "response_mode": "ack_then_deliver",
            "output_type": "txt",
            "process_original_message": False,
            "instructions": [
                "Mô tả ngắn gọn bằng tiếng Việt: ảnh này là gì, cảnh vật/đối tượng chính trong ảnh."
            ],
            "attachments_required": True,
            "attachment_types": ["image"],
        },
        "đây là hình gì",
        "Asia/Ho_Chi_Minh",
    )
    coerced = apply_image_analyze_plan_coercion(misclassified)
    assert plan_is_image_analyze_chat(coerced, has_image=True)
    assert coerced.get("output_type") in (None, "")
    assert coerced.get("process_original_message") is True
    assert coerced.get("execution_class") == "interactive"
    assert plan_is_async(coerced) is False

    skip = normalize_plan(
        {
            "task_hint": "file",
            "task_type": "file_processing",
            "skill": "media_file",
            "skill_action": "process_file",
            "output_type": "txt",
            "attachments_required": True,
            "attachment_types": ["image"],
            "instructions": ["Mô tả ngắn gọn trong chat: hình gì"],
        },
        "đây là hình gì",
        "Asia/Ho_Chi_Minh",
    )
    from classify_client import plan_allows_office_shortcut, plan_skips_media_shortcut  # noqa: E402

    assert plan_skips_media_shortcut(skip) is True
    assert plan_allows_office_shortcut(skip) is False

    pdf_create = normalize_plan(
        {
            "task_hint": "file",
            "task_type": "file_processing",
            "skill": "media_file",
            "skill_action": "process_file",
            "output_type": "pdf",
            "instructions": ["TITLE: Báo cáo\nSUBTITLE: Tuần này"],
        },
        "tạo pdf báo cáo",
        "Asia/Ho_Chi_Minh",
    )
    assert plan_is_image_analyze_chat(pdf_create, has_image=True) is False

    print("OK image_analyze_chat_unit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
