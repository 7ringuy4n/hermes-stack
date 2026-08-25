# -*- coding: utf-8 -*-
"""Office body + text-poster phrase extraction (Dispatcher) + classify-gated shortcut."""
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
from classify_client import plan_allows_office_shortcut, plan_skips_media_shortcut  # noqa: E402
from text_poster import parse_text_poster  # noqa: E402


def main() -> int:
    ext, body = parse_office("tạo 1 file pdf và điền vào số 1")
    assert ext == ".pdf" and body == "1", (ext, body)
    ext, body = parse_office("tạo file PDF chỉ chứa số 1")
    assert ext == ".pdf" and body == "1", (ext, body)
    ext, body = parse_office("tạo 1 file pdf điền số 1 gửi cho tôi")
    assert ext == ".pdf" and body == "1", (ext, body)

    compound = (
        "tạo 1 file pdf chứa số 1 và gửi cho tôi, sau đó tạo 1 file text "
        "chứa số 1  cũng gửi cho tôi"
    )
    assert is_compound_office_request(compound) is True
    # Host shortcut requires classify JSON — compound multi-instruction skips.
    assert plan_allows_office_shortcut(
        {
            "ok": True,
            "task_hint": "file",
            "task_type": "file_processing",
            "instructions": ["tạo pdf chứa 1", "tạo txt chứa 1"],
        }
    ) is False

    same_kind = "tạo pdf chứa 1 sau đó tạo pdf chứa 2"
    assert is_compound_office_request(same_kind) is False
    assert plan_allows_office_shortcut(
        {
            "ok": True,
            "task_hint": "file",
            "task_type": "file_processing",
            "instructions": ["tạo 1 file pdf chứa số 1 và gửi cho tôi"],
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
    assert parse_office(compound) == (".pdf", "1"), parse_office(compound)
    assert parse_office_jobs(compound) == [parse_office(compound)], parse_office_jobs(compound)

    spec = parse_text_poster("vẽ hình ảnh điền vào 5 dòng hello và gửi cho tôi")
    assert spec and spec["n"] == 5 and spec["phrase"].lower() == "hello", spec
    spec = parse_text_poster("vẽ hình ảnh điền vào 5 dòng hello")
    assert spec and spec["phrase"].lower() == "hello", spec

    # Real poster still parses on Dispatcher; schedule plans skip host office shortcut.
    assert parse_text_poster('vẽ poster 5 dòng chữ "KHÁT QUÁ"')
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
    import re

    if re.search(r"do\s+not\s+tell\s+the\s+user", soul, re.I):
        print("FAIL SOUL still has deception_hide trigger phrase", file=sys.stderr)
        return 1
    import session_memory  # noqa: F401

    print("OK office/poster/soul/session units")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
