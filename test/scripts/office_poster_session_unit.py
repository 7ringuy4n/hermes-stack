# -*- coding: utf-8 -*-
"""Office body + text-poster phrase extraction."""
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
from media_shortcuts import looks_office_create, looks_schedule_create, looks_text_poster  # noqa: E402
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
    assert looks_office_create(compound) is False

    # Same kind twice + "sau đó" is NOT detected here — classify/LLM must split.
    same_kind = "tạo pdf chứa 1 sau đó tạo pdf chứa 2"
    assert is_compound_office_request(same_kind) is False
    assert looks_office_create("tạo 1 file pdf chứa số 1 và gửi cho tôi") is True
    weather_pdf = "tạo 1 file pdf thể hiện thời tiết hồ chí minh hiện tại"
    assert looks_office_create(weather_pdf) is False, weather_pdf
    assert parse_office(compound) == (".pdf", "1"), parse_office(compound)
    # Dispatcher does not regex-split compounds — classify emits one instruction per file.
    assert parse_office_jobs(compound) == [parse_office(compound)], parse_office_jobs(compound)

    spec = parse_text_poster("vẽ hình ảnh điền vào 5 dòng hello và gửi cho tôi")
    assert spec and spec["n"] == 5 and spec["phrase"].lower() == "hello", spec
    spec = parse_text_poster("vẽ hình ảnh điền vào 5 dòng hello")
    assert spec and spec["phrase"].lower() == "hello", spec

    # Real poster still matches; "xanh" must not trip _DRAW via "anh"; schedule never posters.
    assert looks_text_poster('vẽ poster 5 dòng chữ "KHÁT QUÁ"') is True
    import media_shortcuts as _ms  # noqa: E402

    assert _ms._DRAW.search("trời xanh gió mát") is None
    daily_sched = (
        "đặt lịch chạy hằng ngày lúc 06:00 vào Zalo LC Group nội dung: "
        "mô tả 1 bài thơ ngắn 4 dòng về trời xanh gió mát chim hót líu lo chào ngày mới, "
        "cập nhật giá xăng E5 RON92 và E10 RON95 mới nhất, "
        "dự báo thời tiết hồ chí minh trong ngày"
    )
    assert looks_schedule_create(daily_sched) is True
    assert looks_text_poster(daily_sched) is False
    assert looks_office_create(daily_sched) is False

    # Image + txt compound must not take the single-file office shortcut.
    from media_shortcuts import is_compound_media_file_request  # noqa: E402

    img_txt = (
        "vẽ 1 tấm hình trắng đen ghi vào chào buổi sáng, tạo 1 file text ghi vào đã xong"
    )
    assert is_compound_media_file_request(img_txt) is True
    assert looks_office_create(img_txt) is False
    assert looks_schedule_create("1 phút nữa gửi vào Zalo LC Group: hello") is True

    soul = (ROOT / "hermes" / "main" / "SOUL.md").read_text(encoding="utf-8")
    import re

    if re.search(r"do\s+not\s+tell\s+the\s+user", soul, re.I):
        print("FAIL SOUL still has deception_hide trigger phrase", file=sys.stderr)
        return 1
    # session module importable
    import session_memory  # noqa: F401

    print("OK office/poster/soul/session units")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
