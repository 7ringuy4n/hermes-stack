"""Unit: quote media URLs, folder-zip media members, archive empty-OCR listing contract."""
from __future__ import annotations

import io
import json
import sys
import tempfile
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "architect" / "tools" / "ingest"))
sys.path.insert(0, str(ROOT / "hermes" / "main" / "plugins" / "zalo"))

from archive_media import extract_media_members, is_media_member  # noqa: E402
from attachment import extract_media_from_quote, attachment_kind  # noqa: E402


def test_quote_fileurl() -> None:
    media = extract_media_from_quote(
        {
            "cliMsgType": 46,
            "attach": {
                "title": "pack.zip",
                "params": {
                    "fileExt": "zip",
                    "fileUrl": "https://cdn.example/pack.zip",
                    "fileSize": 12,
                },
            },
        }
    )
    assert media, media
    assert media["url"].endswith("pack.zip"), media
    assert media["fileName"].endswith(".zip"), media
    assert attachment_kind(media["fileName"]) == "archive"

    pre = extract_media_from_quote(
        {
            "msgType": "share.file",
            "media": {
                "kind": "file",
                "url": "https://cdn.example/prebuilt.docx",
                "fileName": "note.docx",
                "ext": "docx",
                "mime": "application/octet-stream",
                "size": 1,
            },
        }
    )
    assert pre and pre["url"].endswith("prebuilt.docx"), pre


def test_folder_zip_media() -> None:
    assert is_media_member("Folder/sub/photo.png") is True
    assert is_media_member(r"Folder\sub\note.txt") is True
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("Folder/a.txt", "hello folder")
        zf.writestr("Folder/skip.exe", "MZ")
        zf.writestr("Folder/img/x.png", b"\x89PNG\r\n\x1a\n")
    with tempfile.TemporaryDirectory() as td:
        zpath = Path(td) / "folder.zip"
        zpath.write_bytes(buf.getvalue())
        dest = Path(td) / "out"
        got = extract_media_members(zpath, dest)
        assert got.get("ok") is True, got
        names = sorted(x["name"] for x in (got.get("written") or []))
        assert "a.txt" in names, names
        assert "x.png" in names, names
        assert "skip.exe" not in names


def main() -> int:
    test_quote_fileurl()
    test_folder_zip_media()
    print("quote_folder_archive_unit OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
