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
)
from classify_client import (  # noqa: E402
    plan_allows_office_shortcut,
    plan_allows_poster_shortcut,
    plan_skips_media_shortcut,
)
from text_poster import parse_text_poster  # noqa: E402


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
    assert parse_office_jobs("1", "pdf") == [(".pdf", "1")]

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
