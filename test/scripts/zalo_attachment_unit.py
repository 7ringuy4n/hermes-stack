# -*- coding: utf-8 -*-
"""Unit: Zalo attachment worker routing, blank caption, mixed-pack recall (no VPS)."""
from __future__ import annotations

import io
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "hermes" / "main" / "plugins" / "zalo"))

from attachment import (  # noqa: E402
    CONTEXT_ITEMS,
    attachment_kind,
    caption_payload,
    context_blocks,
    context_decode,
    context_encode,
    context_merge,
    context_newest,
    worker_media_path,
)
from autosend import ATTACH_CAPTION_FALLBACK  # noqa: E402

if hasattr(sys.stdout, "buffer"):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")


def test_kind() -> None:
    cases = {
        "one.txt": "text",
        "notes.MD": "text",
        "rows.csv": "text",
        "scan.pdf": "ocr",
        "kitten.JPG": "ocr",
        "deck.pptx": "office",
        "book.xlsx": "office",
        "doc.docx": "office",
        "clip.mp4": "av",
        "voice.m4a": "av",
        "archive.zip": "none",
    }
    for name, want in cases.items():
        got = attachment_kind(name)
        assert got == want, f"{name}: {got} != {want}"
    print("PASS attachment kind routing (text/ocr/office/av)")


def test_worker_path() -> None:
    assert worker_media_path("/opt/data/media/in/one.txt") == "/data/media/in/one.txt"
    assert worker_media_path("/data/assistant/media/in/a.pdf") == "/data/media/in/a.pdf"
    # Already worker-visible or outside the media volume: unchanged.
    assert worker_media_path("/data/media/in/a.pdf") == "/data/media/in/a.pdf"
    assert worker_media_path("/tmp/x.png") == "/tmp/x.png"
    print("PASS worker media path mapping")


def test_caption() -> None:
    # Zalo answers "Tham số không hợp lệ" when a document carries a blank caption.
    assert ATTACH_CAPTION_FALLBACK == "", repr(ATTACH_CAPTION_FALLBACK)
    assert caption_payload("") == {}
    assert caption_payload(" ") == {}
    assert caption_payload(None) == {}
    assert caption_payload("one.txt") == {"caption": "one.txt"}
    print("PASS blank caption omitted from bridge payload")


def test_context_pack() -> None:
    items: list[dict] = []
    pack = [
        ("one.txt", "1"),
        ("notes.md", "md body"),
        ("sheet.xlsx", "col a"),
        ("clip.mp4", "transcript"),
        ("scan.pdf", "invoice 123"),
        ("kitten.jpg", "ocr words"),
    ]
    for name, text in pack:
        items = context_merge(items, name, text)
    assert len(items) == CONTEXT_ITEMS, items
    assert [i["file"] for i in items][-1] == "kitten.jpg"
    assert all(i["file"] != "one.txt" for i in items), "oldest of the pack must roll off"

    # Re-upload replaces the older entry instead of duplicating it.
    items = context_merge(items, "scan.pdf", "invoice 456")
    names = [i["file"] for i in items]
    assert names.count("scan.pdf") == 1, names
    assert context_newest(items) == ("scan.pdf", "invoice 456")

    # Empty extraction must not evict a good entry.
    same = context_merge(items, "empty.bin", "   ")
    assert same == items

    round_trip = context_decode(context_encode(items))
    assert [i["file"] for i in round_trip] == names

    # Older single-item shape still recalls.
    legacy = context_decode('{"file": "old.txt", "text": "legacy"}')
    assert context_newest(legacy) == ("old.txt", "legacy")
    assert context_decode("") == [] and context_decode("not json") == []
    print("PASS mixed pack recall: rolling window, dedupe, legacy shape")


def test_context_blocks() -> None:
    items = [
        {"file": "a.txt", "text": "aaa"},
        {"file": "b.txt", "text": "bbb"},
    ]
    blocks = context_blocks(items, budget=100)
    assert len(blocks) == 2 and blocks[0].startswith("--- b.txt ---"), blocks
    tight = context_blocks(items, budget=3)
    assert len(tight) == 1 and tight[0].endswith("bbb"), tight
    assert context_blocks([], budget=100) == []
    print("PASS recall blocks newest-first within budget")


def main() -> int:
    try:
        test_kind()
        test_worker_path()
        test_caption()
        test_context_pack()
        test_context_blocks()
    except AssertionError as e:
        print(f"FAIL {e}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
