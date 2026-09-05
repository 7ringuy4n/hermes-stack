# -*- coding: utf-8 -*-
"""Unit: Zalo image-analyze path — stage, resolve, classify, vision body (no VPS)."""
from __future__ import annotations

import base64
import io
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

if hasattr(sys.stdout, "buffer"):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "hermes" / "main" / "plugins" / "zalo"))

from attachment import (  # noqa: E402
    IMAGE_ANALYZE_VISION_PROMPT,
    image_analyze_vision_body,
    image_analyze_vision_prompt,
    stage_shared_media,
    vision_image_b64_for_describe,
    vision_scene_is_noise,
)
from classify_client import (  # noqa: E402
    coerce_image_analyze_plan,
    plan_is_image_analyze_chat,
)
from vision_ocr import resolve_media_path  # noqa: E402

TN_THREAD = "test-thread"
CAPTION = "hình gì đây"

# Valid 1x1 JPEG (works for path/b64 pipeline tests).
TINY_JPEG = base64.b64decode(
    "/9j/4AAQSkZJRgABAQEAYABgAAD/2wBDAAgGBgcGBQgHBwcJCQgKDBQNDAsLDBkSEw8UHRof"
    "Hh0aHBwgJC4nICIsIxwcKDcpLDAxNDQ0Hyc5PTgyPC4zNDL/2wBDAQkJCQwLDBgNDRgyIRwh"
    "MjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjL/wAAR"
    "CAAQABADASIAAhEBAxEB/8QAFQABAQAAAAAAAAAAAAAAAAAAAAb/xAAUEAEAAAAAAAAAAAAA"
    "AAAAAAAA/8QAFQEBAQAAAAAAAAAAAAAAAAAAAwT/xAAUEQEAAAAAAAAAAAAAAAAAAAAA/9oA"
    "DAMBAAIRAxEAPwCwABmX/9k="
)


def _skyline_bytes() -> bytes | None:
    assets = ROOT.parent.parent / "assets"
    if not assets.is_dir():
        assets = Path(
            r"C:\Users\7ringuy4n\.cursor\projects\d-Onedrive-Work\assets"
        )
    for pat in ("*skyline*", "*qwen_image*", "*serving_output*"):
        for p in assets.glob(pat):
            if p.is_file() and p.suffix.lower() in {".jpg", ".jpeg", ".png", ".webp"}:
                return p.read_bytes()
    return None


def test_tn_stage_and_resolve() -> None:
    root = Path(tempfile.mkdtemp(prefix="zalo-tn-img-"))
    try:
        cache = root / "replicas" / "hermes-1" / "cache" / "img_zalo.jpg"
        cache.parent.mkdir(parents=True)
        cache.write_bytes(_skyline_bytes() or TINY_JPEG)
        inbound = root / "opt" / "data" / "media" / "inbound"
        staged = stage_shared_media(
            str(cache),
            "skyline.jpg",
            thread_id=TN_THREAD,
            inbound_root=str(inbound),
        )
        assert staged, "stage_shared_media returned empty"
        sp = Path(staged)
        assert sp.is_file(), staged
        assert TN_THREAD in str(sp).replace("\\", "/"), staged

        import os

        os.environ["OCR_MEDIA_ROOT"] = str(root / "opt" / "data" / "media")
        hermes_path = f"/opt/data/media/inbound/{TN_THREAD}/{sp.name}"
        resolved = resolve_media_path(hermes_path)
        assert resolved is not None and resolved.is_file(), (hermes_path, resolved)

        b64 = vision_image_b64_for_describe(hermes_path)
        assert len(b64) > 100, "expected resized base64 for vision"
        print("PASS tn stage + resolve + b64", TN_THREAD)
    finally:
        import shutil

        shutil.rmtree(root, ignore_errors=True)


def test_tn_classify_coerce() -> None:
    plan = coerce_image_analyze_plan(
        {
            "task_hint": "file",
            "task_type": "file_processing",
            "skill": "media_file",
            "skill_action": "process_file",
            "attachments_required": True,
            "attachment_types": ["image"],
            "instructions": ["Mô tả ngắn nội dung ảnh."],
        },
        has_image=True,
        user_text=CAPTION,
    )
    assert plan and plan_is_image_analyze_chat(plan, has_image=True), plan
    assert plan.get("output_type") in (None, "")
    print("PASS tn classify coerce", CAPTION)


def test_tn_vision_body_filters_noise() -> None:
    noise = "Yutak\nES\nMAK"
    assert vision_scene_is_noise(noise) is True
    assert image_analyze_vision_body(noise) == ""
    scene = (
        "Bức ảnh chụp skyline TP.HCM bên sông Sài Gòn lúc hoàng hôn, "
        "nổi bật tòa Bitexco và các tòa cao ốc ven sông."
    )
    assert image_analyze_vision_body(scene) != ""
    p = image_analyze_vision_prompt(CAPTION)
    assert CAPTION in p or IMAGE_ANALYZE_VISION_PROMPT in p
    print("PASS tn vision body noise filter")


def test_tn_vision_describe_mock() -> None:
    root = Path(tempfile.mkdtemp(prefix="zalo-tn-mock-"))
    try:
        inbound = root / "opt" / "data" / "media" / "inbound" / TN_THREAD
        inbound.mkdir(parents=True)
        img = inbound / "probe.jpg"
        img.write_bytes(_skyline_bytes() or TINY_JPEG)

        import os

        os.environ["OCR_MEDIA_ROOT"] = str(root / "opt" / "data" / "media")
        hermes_path = f"/opt/data/media/inbound/{TN_THREAD}/probe.jpg"

        fake = {
            "ok": True,
            "text": (
                "Ảnh chụp đường chân trời thành phố bên sông lúc hoàng hôn, "
                "có nhiều tòa nhà cao tầng và ánh nắng chiều."
            ),
            "via": "vision-ocr",
        }

        with patch("vision_ocr._vision_chat", return_value=(200, "{}", fake["text"])):
            from vision_ocr import vision_describe

            out = vision_describe(path=hermes_path, prompt=image_analyze_vision_prompt(CAPTION))
        assert out.get("ok") is True, out
        reply = image_analyze_vision_body(out.get("text") or "")
        assert reply and "Không mô tả được" not in reply, reply
        print("PASS tn vision_describe mock pipeline")
    finally:
        import shutil

        shutil.rmtree(root, ignore_errors=True)


def test_current_image_reply_clears_prior_media_mute() -> None:
    source = (ROOT / "hermes" / "main" / "plugins" / "zalo" / "adapter.py").read_text(
        encoding="utf-8"
    )
    start = source.index("async def _as_try_image_analyze_vision_reply")
    end = source.index("async def _as_try_workflow_submit", start)
    body = source[start:end]
    assert body.count("self._as_clear_job_file_sent(str(thread_id))") >= 2
    print("PASS current image reply clears prior media mute")


def main() -> int:
    test_tn_stage_and_resolve()
    test_tn_classify_coerce()
    test_tn_vision_body_filters_noise()
    test_tn_vision_describe_mock()
    test_current_image_reply_clears_prior_media_mute()
    print("OK zalo_tn_image_analyze_unit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
