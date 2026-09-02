# -*- coding: utf-8 -*-
"""Image analyze routes to Hermes chat; OCR noise filtered (no regex)."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "hermes" / "main" / "plugins" / "zalo"))

from attachment import (  # noqa: E402
    IMAGE_ANALYZE_VISION_PROMPT,
    image_analyze_vision_body,
    image_analyze_vision_prompt,
    ocr_excerpt_for_ack,
    vision_describe_refused,
)
from classify_client import (  # noqa: E402
    apply_image_analyze_plan_coercion,
    normalize_plan,
    plan_is_image_analyze_chat,
    plan_is_async,
)


def main() -> int:
    assert ocr_excerpt_for_ack("crn ae maa") == ""
    assert ocr_excerpt_for_ack("Hello world from OCR line") != ""

    assert vision_describe_refused("") is True
    assert vision_describe_refused("Yutak\nES\nMAK") is True
    assert vision_describe_refused(
        "Bức ảnh chụp skyline TP.HCM với sông Sài Gòn và tòa nhà Bitexco lúc hoàng hôn."
    ) is False

    p = image_analyze_vision_prompt("hình gì đây")
    assert "Câu hỏi người dùng" in p
    assert image_analyze_vision_body("Yutak\nES\nMAK") == ""
    scene = (
        "Bức ảnh chụp skyline TP.HCM bên sông Sài Gòn lúc hoàng hôn, "
        "nổi bật tòa Bitexco và các tòa cao ốc ven sông."
    )
    assert image_analyze_vision_body(scene) != ""
    assert image_analyze_vision_body(scene, prompt=IMAGE_ANALYZE_VISION_PROMPT) != ""
    blind = (
        "Chào bạn, tôi đã sẵn sàng mô tả hình ảnh theo đúng yêu cầu của bạn. Tuy nhiên, "
        "hiện tại tôi chưa thấy hình ảnh nào được đính kèm trong tin nhắn. Vui lòng gửi ảnh "
        "lên để tôi có thể phân tích chi tiết bối cảnh, ánh sáng và các dòng chữ xuất hiện "
        "trong khung hình nhé."
    )
    assert image_analyze_vision_body(blind, prompt=IMAGE_ANALYZE_VISION_PROMPT) == ""

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
