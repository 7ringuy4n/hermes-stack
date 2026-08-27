"""Unit: archive always host-acks; turn wait floor is 15 minutes."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "hermes" / "main" / "plugins" / "zalo"))

from attachment import attachment_kind  # noqa: E402


def host_ack(attach_bare: bool, attach_kind: str, excerpt_meaningful: bool) -> bool:
    """Mirror adapter host_ack rule for archives."""
    return (
        attach_bare
        or attach_kind == "archive"
        or (attach_kind in {"office", "text", "ocr"} and not excerpt_meaningful)
    )


def main() -> int:
    assert attachment_kind("a.zip") == "archive"
    # Caption + extracted text must still host-ack (never Hermes).
    assert host_ack(False, "archive", True) is True
    assert host_ack(True, "archive", True) is True
    assert host_ack(False, "archive", False) is True
    # Office with text + caption still goes to Hermes path (not forced host-ack).
    assert host_ack(False, "office", True) is False
    assert host_ack(False, "office", False) is True

    src = (ROOT / "hermes" / "main" / "plugins" / "zalo" / "adapter.py").read_text(
        encoding="utf-8"
    )
    assert "ZALO_TURN_WAIT_DEFAULT_S = 900.0" in src
    assert "ATTACHMENT_ARCHIVE_TIMEOUT_S = 600.0" in src
    assert 'or attach_kind == "archive"' in src
    print("archive_host_ack_wait_unit OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
