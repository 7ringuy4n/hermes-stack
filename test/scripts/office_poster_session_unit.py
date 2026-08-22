# -*- coding: utf-8 -*-
"""Office body + text-poster phrase extraction."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "architect" / "models" / "dispatcher"))
sys.path.insert(0, str(ROOT / "hermes" / "main" / "plugins" / "zalo"))

from office_file import parse_office  # noqa: E402
from text_poster import parse_text_poster  # noqa: E402


def main() -> int:
    ext, body = parse_office("tạo 1 file pdf và điền vào số 1")
    assert ext == ".pdf" and body == "1", (ext, body)
    ext, body = parse_office("tạo file PDF chỉ chứa số 1")
    assert ext == ".pdf" and body == "1", (ext, body)
    ext, body = parse_office("tạo 1 file pdf điền số 1 gửi cho tôi")
    assert ext == ".pdf" and body == "1", (ext, body)

    spec = parse_text_poster("vẽ hình ảnh điền vào 5 dòng hello và gửi cho tôi")
    assert spec and spec["n"] == 5 and spec["phrase"].lower() == "hello", spec
    spec = parse_text_poster("vẽ hình ảnh điền vào 5 dòng hello")
    assert spec and spec["phrase"].lower() == "hello", spec

    soul = (ROOT / "hermes" / "main" / "SOUL.md").read_text(encoding="utf-8")
    import re

    if re.search(r"do\s+not\s+tell\s+the\s+user", soul, re.I):
        print("FAIL SOUL still has deception_hide trigger phrase", file=sys.stderr)
        return 1
    # session module importable
    import session_memory  # noqa: F401
    import media_shortcuts  # noqa: F401

    print("OK office/poster/soul/session units")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
