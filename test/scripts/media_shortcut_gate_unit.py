# -*- coding: utf-8 -*-
"""Unit: host media shortcut gate blocks Hermes/workflow fallthrough."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "hermes" / "main" / "plugins" / "zalo"))

from classify_client import (  # noqa: E402
    normalize_plan,
    plan_allows_office_shortcut,
    plan_media_shortcut_gate,
    plan_allows_scene_image,
)


def test_scenic_plan_gate() -> None:
    raw = {
        "ok": True,
        "task_hint": "tool",
        "task_type": "media_generation",
        "execution_class": "async",
        "response_mode": "ack_then_deliver",
        "skill": "media_file",
        "skill_action": "generate_media",
        "process_original_message": True,
        "instructions": [
            "SCENE: Da Lat city, Vietnam, photorealistic photograph, street-level view"
        ],
        "task_details": [
            {
                "execution_class": "async",
                "task_type": "media_generation",
                "response_mode": "ack_then_deliver",
            }
        ],
    }
    plan = normalize_plan(raw, "vẽ hình thành phố đà lạt", "Asia/Ho_Chi_Minh")
    assert plan_media_shortcut_gate(plan) == "scene_image", plan
    assert plan_allows_scene_image(plan) is True
    assert plan.get("process_original_message") is False


def test_pure_media_process_false() -> None:
    raw = {
        "ok": True,
        "task_hint": "tool",
        "task_type": "media_generation",
        "execution_class": "async",
        "skill": "media_file",
        "instructions": ["SCENE: mountain lake at dawn"],
        "task_details": [{"task_type": "media_generation", "execution_class": "async"}],
    }
    plan = normalize_plan(raw, "vẽ hồ núi lúc bình minh", "Asia/Ho_Chi_Minh")
    assert plan.get("process_original_message") is False


def test_grounded_information_image_gate() -> None:
    raw = {
        "ok": True,
        "task_hint": "tool",
        "task_type": "media_generation",
        "execution_class": "async",
        "response_mode": "ack_then_deliver",
        "skill": "media_file",
        "skill_action": "generate_media",
        "output_type": "image",
        "instructions": [
            "current public information for the requested subject",
            "RENDER: composed-image\nSCENE: editorial city illustration with calm negative space",
        ],
        "task_details": [
            {"task_type": "search", "output_type": None},
            {"task_type": "media_generation", "output_type": "image"},
        ],
    }
    plan = normalize_plan(
        raw,
        "cập nhật thông tin thời tiết hồ chí minh, ghi thông tin lên hình góc trái bên dưới",
        "Asia/Ho_Chi_Minh",
    )
    assert plan_media_shortcut_gate(plan) == "composed_image", plan


def test_another_subject_uses_same_composed_gate() -> None:
    raw = {
        "ok": True,
        "task_hint": "tool",
        "task_type": "media_generation",
        "execution_class": "async",
        "skill": "media_file",
        "skill_action": "generate_media",
        "output_type": "image",
        "instructions": [
            "current public rankings for the requested event",
            "RENDER: composed-image\nSCENE: energetic stadium illustration with negative space",
        ],
        "task_details": [
            {"task_type": "search"},
            {"task_type": "media_generation", "output_type": "image"},
        ],
    }
    plan = normalize_plan(raw, "create an image with current rankings", "Asia/Ho_Chi_Minh")
    assert plan_media_shortcut_gate(plan) == "composed_image", plan


def test_file_hint_does_not_override_explicit_image_contract() -> None:
    raw = {
        "ok": True,
        "task_hint": "file",
        "task_type": "media_generation",
        "execution_class": "async",
        "skill": "media_file",
        "skill_action": "generate_media",
        "output_type": "image",
        "instructions": [
            "Obtain current public information for the requested subject.",
            "RENDER: composed-image\nSCENE: adaptive scenic background with negative space.",
        ],
        "task_details": [
            {"task_type": "search"},
            {"task_type": "media_generation", "output_type": "image", "depends_on": [0]},
        ],
    }
    plan = normalize_plan(raw, "grounded information image", "Asia/Ho_Chi_Minh")
    assert plan_media_shortcut_gate(plan) == "composed_image", plan


def test_scheduled_render_contract_survives_flattened_child_types() -> None:
    """A provider may label child tasks chat; the render contract remains executable."""
    raw = {
        "ok": True,
        "task_hint": "tool",
        "task_type": "create_schedule",
        "output_type": "image",
        "instructions": [
            "Obtain current public information for the requested subject.",
            "RENDER: composed-image\nSCENE: adaptive editorial illustration with clear text space.",
        ],
        "task_details": [
            {"task_type": "chat"},
            {"task_type": "chat"},
        ],
    }
    plan = normalize_plan(raw, "scheduled information image", "Asia/Ho_Chi_Minh")
    assert plan_media_shortcut_gate(plan) == "composed_image", plan


def test_scenic_misrouted_as_pdf_coerced() -> None:
    """Classify wrongly put SCENE draw under pdf — host must restore scene_image."""
    raw = {
        "ok": True,
        "task_hint": "file",
        "task_type": "file_processing",
        "execution_class": "async",
        "skill": "media_file",
        "skill_action": "process_file",
        "output_type": "pdf",
        "process_original_message": True,
        "instructions": [
            "SCENE: Hanoi Vietnam street-level photorealistic photograph, evening lighting"
        ],
        "task_details": [
            {"task_type": "file_processing", "output_type": "pdf"},
        ],
    }
    plan = normalize_plan(raw, "vẽ hình thành phố hà nội giờ hiện tại", "Asia/Ho_Chi_Minh")
    assert plan.get("output_type") == "image", plan
    assert plan_media_shortcut_gate(plan) == "scene_image", plan
    assert plan_allows_scene_image(plan) is True
    assert plan.get("process_original_message") is False


def test_weather_pdf_with_search_not_coerced_to_image() -> None:
    raw = {
        "ok": True,
        "task_hint": "file",
        "task_type": "file_processing",
        "execution_class": "async",
        "skill": "media_file",
        "skill_action": "process_file",
        "output_type": "pdf",
        "process_original_message": True,
        "instructions": [
            "current weather Da Nang",
            "Thời tiết Đà Nẵng — PDF",
        ],
        "task_details": [
            {"task_type": "search", "output_type": None},
            {"task_type": "file_processing", "output_type": "pdf"},
        ],
    }
    plan = normalize_plan(
        raw,
        "cập nhật thời tiết hiện tại ở Đà Nẵng và vẽ vào file pdf",
        "Asia/Ho_Chi_Minh",
    )
    assert plan.get("output_type") == "pdf", plan
    assert plan_allows_scene_image(plan) is False
    assert plan_media_shortcut_gate(plan) != "scene_image"


def test_model_authored_office_instruction_never_becomes_document_body() -> None:
    plan = normalize_plan(
        {
            "ok": True,
            "task_hint": "file",
            "task_type": "file_processing",
            "execution_class": "async",
            "skill": "media_file",
            "skill_action": "process_file",
            "output_type": "pdf",
            "process_original_message": True,
            "instructions": [
                "Retrieve current facts, author the complete PDF with skill file-gen, and deliver it."
            ],
            "task_details": [
                {"task_type": "file_processing", "output_type": "pdf", "depends_on": []}
            ],
        },
        "create a polished current briefing PDF",
        "Asia/Ho_Chi_Minh",
    )
    assert plan_allows_office_shortcut(plan) is False


def main() -> int:
    test_scenic_plan_gate()
    test_pure_media_process_false()
    test_grounded_information_image_gate()
    test_file_hint_does_not_override_explicit_image_contract()
    test_another_subject_uses_same_composed_gate()
    test_scheduled_render_contract_survives_flattened_child_types()
    test_scenic_misrouted_as_pdf_coerced()
    test_weather_pdf_with_search_not_coerced_to_image()
    test_model_authored_office_instruction_never_becomes_document_body()
    adapter_source = (ROOT / "hermes" / "main" / "plugins" / "zalo" / "adapter.py").read_text(
        encoding="utf-8"
    )
    assert "and not schedule_fire" not in "\n".join(
        line
        for line in adapter_source.splitlines()
        if "plan_media_shortcut_gate(plan)" in line
        or "plan_is_search_then_image_turn(plan)" in line
    )
    assert adapter_source.count(
        ') and (schedule_fire or plan.get("task_hint") != "schedule")'
    ) == 2
    assert "media_urls=media_urls" in adapter_source
    assert "has_image_attachment=attach_is_image" in adapter_source
    assert "media_urls=list(event.media_urls or [])" in adapter_source
    assert "if edit_plan and (not has_image_attachment or not urls):" in adapter_source
    assert 'plan=m.get("plan") if isinstance(m.get("plan"), dict) else None' in adapter_source
    assert 'early_plan["task_hint"] = "tool"' in adapter_source
    assert adapter_source.count("schedule_fire=schedule_fire,") >= 4
    assert "creation plan must continue" in adapter_source
    assert "if schedule_fire:" in adapter_source
    assert "Zalo: scheduleFire received thread=%s schedule=%s execution=%s plan=%s hint=%s" in adapter_source
    assert "and not self._as_inbound_queue_enabled()" in adapter_source
    assert "sock_connect=15, sock_read=45" in adapter_source
    assert '("classify", "failed")' in adapter_source
    classify_source = (ROOT / "hermes" / "main" / "plugins" / "zalo" / "classify_client.py").read_text(
        encoding="utf-8"
    )
    assert "DEFAULT_TIMEOUT_S = 120.0" in classify_source
    assert "HTTP_ATTEMPTS = 1" in classify_source
    schedule_source = (ROOT / "architect" / "schedule-worker" / "main.go").read_text(
        encoding="utf-8"
    )
    assert 'if plan, ok := sch.Context["plan"]; ok && plan != nil' in schedule_source
    assert 'payload["plan"] = plan' in schedule_source
    assert '"messageId":         "schedule:" + sch.ID' in schedule_source
    print("media_shortcut_gate_unit OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
