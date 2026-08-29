#!/usr/bin/env python3
"""Unit: office/text/ocr/archive always host-ack; office skips body secret classify."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "hermes" / "main" / "plugins" / "zalo"))

from attachment import attachment_kind  # noqa: E402


def host_ack(attach_bare: bool, attach_kind: str, excerpt_meaningful: bool) -> bool:
    """Mirror adapter host_ack rule (excerpt_meaningful unused for worker kinds)."""
    del excerpt_meaningful
    return attach_bare or attach_kind in {"archive", "office", "text", "ocr"}


def main() -> int:
    assert attachment_kind("a.zip") == "archive"
    assert attachment_kind("excel.xlsx") == "office"
    # Caption + extracted text must still host-ack (never Hermes / office_shortcut).
    assert host_ack(False, "archive", True) is True
    assert host_ack(True, "archive", True) is True
    assert host_ack(False, "office", True) is True
    assert host_ack(False, "office", False) is True
    assert host_ack(False, "text", True) is True
    assert host_ack(False, "ocr", True) is True

    src = (ROOT / "hermes" / "main" / "plugins" / "zalo" / "adapter.py").read_text(
        encoding="utf-8"
    )
    assert "ZALO_TURN_WAIT_DEFAULT_S = 900.0" in src
    assert "ATTACHMENT_ARCHIVE_TIMEOUT_S = 600.0" in src
    assert 'attach_kind in {\n                "archive",\n                "office",\n                "text",\n                "ocr",\n            }' in src or (
        '"office"' in src and "host_ack = attach_bare or attach_kind in" in src
    )
    assert 'if attach_kind not in {"archive", "office"}:' in src
    assert "[Attachment text —" in src
    assert "classify_secret_attachment_body" in src
    core = (
        ROOT / "hermes" / "main" / "skills" / "classify" / "parts" / "core.txt"
    ).read_text(encoding="utf-8")
    assert "spreadsheet/office workbook extracts" in core
    print("archive_host_ack_wait_unit OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
