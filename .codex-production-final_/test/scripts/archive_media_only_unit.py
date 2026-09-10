"""Unit: archive extract keeps media members only; password reasons."""
from __future__ import annotations

import io
import sys
import tempfile
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "architect" / "tools" / "ingest"))
sys.path.insert(0, str(ROOT / "hermes" / "main" / "plugins" / "zalo"))

from archive_media import (  # noqa: E402
    archive_kind,
    extract_media_members,
    is_media_member,
    member_path_safe,
)
from attachment import (  # noqa: E402
    archive_password_ack_message,
    attachment_kind,
    file_extract_ack_message,
)


def main() -> int:
    assert attachment_kind("pack.zip") == "archive"
    assert attachment_kind("a.7z") == "archive"
    assert attachment_kind("b.rar") == "archive"
    assert attachment_kind("c.tar.gz") == "archive"
    assert archive_kind("x.zip") == "zip"
    assert archive_kind("x.7z") == "7z"
    assert archive_kind("x.rar") == "rar"
    assert archive_kind("x.tar.gz") == "tar"
    assert is_media_member("docs/a.docx") is True
    assert is_media_member("img/photo.png") is True
    assert is_media_member("bin/run.exe") is False
    assert is_media_member("nested/inner.zip") is False
    assert is_media_member("../evil.txt") is False
    assert member_path_safe("ok/file.txt") is True

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("readme.txt", "hello media")
        zf.writestr("malware.exe", "MZ")
        zf.writestr("nested/more.zip", b"PK\x03\x04")
    with tempfile.TemporaryDirectory() as td:
        zpath = Path(td) / "t.zip"
        zpath.write_bytes(buf.getvalue())
        dest = Path(td) / "out"
        got = extract_media_members(zpath, dest)
        assert got.get("ok") is True, got
        names = sorted(x["name"] for x in (got.get("written") or []))
        assert names == ["readme.txt"], names
        assert (dest / "00_readme.txt").read_text(encoding="utf-8") == "hello media"

    ack = file_extract_ack_message("pack.zip", "", kind="archive")
    assert "media" in ack.casefold()
    pwd_ack = archive_password_ack_message("secret.7z")
    assert "mật khẩu" in pwd_ack.casefold() or "password" in pwd_ack.casefold()
    print("archive_media_only_unit OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
