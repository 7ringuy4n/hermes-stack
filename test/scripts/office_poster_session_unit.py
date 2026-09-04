# -*- coding: utf-8 -*-
"""Office body + text-poster from classify JSON fields (no prose regex)."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "architect" / "models" / "dispatcher"))
sys.path.insert(0, str(ROOT / "hermes" / "main" / "plugins" / "zalo"))

from office_file import (  # noqa: E402
    is_compound_office_request,
    parse_office,
    parse_office_jobs,
    write_pdf,
)
from classify_client import (  # noqa: E402
    plan_allows_office_shortcut,
    plan_allows_poster_shortcut,
    plan_allows_scene_image,
    plan_allows_search_then_composed_image,
    plan_allows_search_then_office,
    plan_image_render_mode,
    plan_media_shortcut_gate,
    plan_skips_media_shortcut,
)
from media_shortcuts import (  # noqa: E402
    build_office_body_from_search,
    scene_prompt_from_instruction,
    shortcut_consumed,
    shortcut_ok,
    shortcut_was_consumed,
)
try:
    from text_poster import parse_text_poster  # type: ignore  # noqa: E402
except Exception:  # noqa: BLE001
    parse_text_poster = None  # type: ignore[assignment]


def main() -> int:
    ext, body = parse_office("1", "pdf")
    assert ext == ".pdf" and body == "1", (ext, body)
    ext, body = parse_office("hello", "txt")
    assert ext == ".txt" and body == "hello", (ext, body)
    # Host must not extract kind/body from Vietnamese wrappers.
    wrapped = "tạo 1 file pdf và điền vào số 1"
    ext, body = parse_office(wrapped, "")
    assert ext == ".txt" and body == wrapped, (ext, body)

    compound = (
        "tạo 1 file pdf chứa số 1 và gửi cho tôi, sau đó tạo 1 file text "
        "chứa số 1  cũng gửi cho tôi"
    )
    assert is_compound_office_request(compound) is False
    # Host shortcut requires classify JSON — compound multi-instruction skips.
    assert plan_allows_office_shortcut(
        {
            "ok": True,
            "task_hint": "file",
            "task_type": "file_processing",
            "instructions": ["tạo pdf chứa 1", "tạo txt chứa 1"],
        }
    ) is False

    assert plan_allows_office_shortcut(
        {
            "ok": True,
            "task_hint": "file",
            "task_type": "file_processing",
            "output_type": "pdf",
            "instructions": ["1"],
        }
    ) is True
    weather_pdf = {
        "ok": True,
        "task_hint": "file",
        "task_type": "file_processing",
        "skill": "web_search",
        "instructions": ["tạo 1 file pdf thể hiện thời tiết hồ chí minh hiện tại"],
    }
    assert plan_skips_media_shortcut(weather_pdf) is True
    assert plan_allows_office_shortcut(weather_pdf) is False
    assert plan_allows_search_then_office(weather_pdf) is False
    weather_pdf_split = {
        "ok": True,
        "task_hint": "file",
        "task_type": "file_processing",
        "output_type": "pdf",
        "instructions": [
            "current weather Ho Chi Minh City temperature humidity",
            "TITLE: Thời tiết TP.HCM\nICON: cloud\n- placeholder",
        ],
        "task_details": [
            {"task_type": "search", "output_type": None},
            {"task_type": "file_processing", "output_type": "pdf"},
        ],
    }
    assert plan_allows_search_then_office(weather_pdf_split) is False
    assert plan_allows_office_shortcut(weather_pdf_split) is False
    body = build_office_body_from_search(
        file_instruction="TITLE: Thời tiết TP.HCM\nICON: rain",
        user_ask="pdf weather",
        search={
            "answer": "Nhiệt độ: 31°C\nĐộ ẩm: 70%",
            "results": [{"title": "HCM", "content": "light rain"}],
        },
    )
    assert "TITLE:" not in body, body
    assert "31°C" in body and "Độ ẩm" in body, body
    # Create-verb wrapper must not become the PDF title; host never scrapes SERP results
    messy = build_office_body_from_search(
        file_instruction=(
            "Tạo file PDF thời tiết Hồ Chí Minh thật bắt mắt. "
            "TITLE: Thời tiết hiện tại — Hồ Chí Minh. SUBTITLE: Cập nhật. "
            "ICON: cloud|rain."
        ),
        user_ask="hãy thiết kế pdf thời tiết",
        search={
            "answer": None,
            "results": [
                {
                    "title": "Xem Dự Báo | Dubaothoitiet.info",
                    "content": "Nhiệt độ Đà Nẵng khoảng 30°C, trời nhiều mây",
                },
                {"title": "AccuWeather: # Thành phố", "content": ""},
            ],
        },
    )
    assert "Tạo file PDF" not in messy, messy
    assert "Dubaothoitiet" not in messy and "AccuWeather" not in messy, messy
    assert messy.strip() in {"", " "}, messy
    # JSON / dict dumps in search answer are skipped (structural junk)
    jsony = build_office_body_from_search(
        file_instruction="TITLE: Thời tiết — Hồ Chí Minh\nSUBTITLE: Live\nICON: cloud",
        user_ask="pdf",
        search={
            "answer": (
                "{'location': {'name': 'Ho Chi Minh City'}, "
                "'current': {'temp_c': 31, 'humidity': 70}}"
            ),
            "results": [],
        },
    )
    assert "{'location'" not in jsony and "temp_c" not in jsony, jsony
    # Plain answer prose lines pass through
    good = build_office_body_from_search(
        file_instruction="- Nhiệt độ:\n- Độ ẩm:",
        user_ask="pdf",
        search={
            "answer": "Nhiệt độ: 30°C\nĐộ ẩm: 78%\nTình trạng: Cloudy",
            "results": [],
        },
    )
    assert "Nhiệt độ: 30°C" in good and "Độ ẩm: 78%" in good, good

    mixed_img_pdf = {
        "ok": True,
        "task_hint": "tool",
        "task_type": "media_generation",
        "instructions": ["draw weather", "make pdf"],
        "task_details": [
            {"task_type": "media_generation", "output_type": "image"},
            {"task_type": "file_processing", "output_type": "pdf"},
        ],
    }
    assert plan_allows_search_then_office(mixed_img_pdf) is False

    scenic_plan = {
        "ok": True,
        "task_hint": "tool",
        "task_type": "media_generation",
        "output_type": "image",
        "instructions": [
            "SCENE: Ho Chi Minh City skyline at golden hour, photorealistic photograph, real camera photo"
        ],
    }
    assert plan_image_render_mode(scenic_plan) == ""
    assert plan_allows_scene_image(scenic_plan) is True
    assert plan_allows_search_then_composed_image(scenic_plan) is False
    assert (
        scene_prompt_from_instruction(scenic_plan["instructions"][0])
        == "Ho Chi Minh City skyline at golden hour, photorealistic photograph, real camera photo"
    )

    composed_image = {
        "ok": True,
        "task_hint": "tool",
        "task_type": "media_generation",
        "output_type": "image",
        "instructions": [
            "current public information for the requested subject",
            (
                "RENDER: composed-image\n"
                "SCENE: editorial city illustration with calm negative space"
            ),
        ],
        "task_details": [
            {"task_type": "search", "output_type": None},
            {"task_type": "media_generation", "output_type": "image"},
        ],
    }
    assert plan_image_render_mode(composed_image) == "composed-image"
    assert plan_allows_search_then_composed_image(composed_image) is True
    assert plan_allows_scene_image(composed_image) is False
    assert plan_media_shortcut_gate(scenic_plan) == "scene_image"
    assert plan_media_shortcut_gate(composed_image) == "composed_image"
    assert shortcut_ok({"ok": True, "file": "x.png"}) is True
    assert shortcut_ok(shortcut_consumed()) is False
    assert shortcut_was_consumed(shortcut_consumed()) is True
    assert parse_office_jobs("1", "pdf") == [(".pdf", "1")]
    try:
        out = ROOT / "scripts" / "temp" / "_html_weather_unit.pdf"
        out.parent.mkdir(parents=True, exist_ok=True)
        write_pdf(
            out,
            """<!DOCTYPE html>
<html lang="vi"><head><meta charset="utf-8"/><title>w</title></head>
<body>
<h1>Thời tiết TP. Hồ Chí Minh</h1>
<h2>Cập nhật trực tiếp</h2>
<ul>
<li>Nhiệt độ: 31°C (cảm giác 36°C)</li>
<li>Độ ẩm: 70%</li>
<li>Điều kiện: Nắng</li>
</ul>
<p>Trời quang, oi bức.</p>
</body></html>""",
        )
        assert out.is_file() and out.stat().st_size > 400, out.stat().st_size
        try:
            from pypdf import PdfReader

            extracted = PdfReader(str(out)).pages[0].extract_text() or ""
            assert "Thời tiết" in extracted, extracted
            assert "|------" not in extracted, extracted
            assert "31°C" in extracted or "70%" in extracted, extracted
        except ImportError:
            print("SKIP pdf text extract (no pypdf)")
        out.unlink(missing_ok=True)
    except Exception as e:  # noqa: BLE001
        print(f"SKIP html pdf render ({type(e).__name__})")

    if parse_text_poster is None:
        print("SKIP text_poster (optional dep missing)")
    else:
        assert parse_text_poster("vẽ hình ảnh điền vào 5 dòng hello và gửi cho tôi") is None
        spec = parse_text_poster(phrase="hello", n=5, bw=False)
        assert spec and spec["n"] == 5 and spec["phrase"].lower() == "hello", spec
        assert plan_allows_poster_shortcut(
            {"ok": True, "poster_n": 5, "poster_phrase": "hello", "task_hint": "tool"}
        ) is True

    daily_sched = {
        "ok": True,
        "task_hint": "schedule",
        "task_type": "create_schedule",
        "instructions": ["mô tả thơ"],
    }
    assert plan_skips_media_shortcut(daily_sched) is True
    assert plan_allows_office_shortcut(daily_sched) is False

    img_txt = {
        "ok": True,
        "task_hint": "tool",
        "task_type": "media_generation",
        "instructions": [
            "vẽ 1 tấm hình trắng đen ghi vào chào buổi sáng",
            "tạo 1 file text ghi vào đã xong",
        ],
        "task_details": [
            {"task_type": "media_generation", "output_type": "image"},
            {"task_type": "file_processing", "output_type": "txt"},
        ],
    }
    assert plan_skips_media_shortcut(img_txt) is True
    assert plan_allows_office_shortcut(img_txt) is False

    soul = (ROOT / "hermes" / "main" / "SOUL.md").read_text(encoding="utf-8")
    needle = "do not tell the user"
    if needle in soul.lower():
        print("FAIL SOUL still has deception_hide trigger phrase", file=sys.stderr)
        return 1
    import session_memory  # noqa: F401

    print("OK office/poster from classify JSON + soul/session")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
