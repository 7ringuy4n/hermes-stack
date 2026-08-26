"""Blank office extract ack uses ingest/media path — not Hermes docx forensics."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "hermes" / "main" / "plugins" / "zalo"))

from attachment import attachment_kind, file_extract_ack_message  # noqa: E402


def main() -> int:
    assert attachment_kind("blank.docx") == "office"
    assert attachment_kind("notes.txt") == "text"
    # Whitespace-only = blank office ack (not "chưa đọc được")
    ack = file_extract_ack_message("blank.docx", " \n\t ", kind="office")
    assert "trống" in ack.casefold() or "trong" in ack.casefold() or "empty" in ack.casefold() or "không có nội dung" in ack
    assert "zipfile" not in ack.casefold()
    assert "metadata" not in ack.casefold()
    # Real content still summarized path
    filled = file_extract_ack_message("doc.docx", "Hello world content here", kind="office")
    assert "Hello world" in filled
    assert "trống" not in filled
    print("blank_office_media_ack_unit OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
