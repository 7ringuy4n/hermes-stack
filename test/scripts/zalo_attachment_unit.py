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
    file_extract_ack_message,
    image_ocr_ack_message,
    image_analyze_ack_message,
    ocr_excerpt_for_ack,
    pick_sheet_section,
    prefer_workbook_head,
    sheet_ref_from_text,
    split_workbook_sheets,
    stage_shared_media,
    workbook_sheet_reply,
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
        "archive.zip": "archive",
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


def test_stage_shared_media(tmp_path: Path | None = None) -> None:
    import tempfile

    root = Path(tempfile.mkdtemp(prefix="zalo-stage-"))
    try:
        src = root / "replica-cache" / "img_abc.jpg"
        src.parent.mkdir(parents=True)
        src.write_bytes(b"\xff\xd8\xfffakejpeg")
        inbound = root / "inbound"
        staged = stage_shared_media(
            str(src), "image.jpg", thread_id="2337", inbound_root=str(inbound)
        )
        assert staged, "expected staged path"
        sp = Path(staged)
        assert sp.is_file(), staged
        inbound_n = str(inbound).replace("\\", "/")
        staged_n = str(sp).replace("\\", "/")
        assert inbound_n in staged_n, (inbound_n, staged_n)
        assert sp.read_bytes() == src.read_bytes()
        # Already under shared media — no second copy.
        again = stage_shared_media(
            staged, "image.jpg", thread_id="2337", inbound_root=str(inbound)
        )
        assert again.replace("\\", "/") == staged.replace("\\", "/")
        print("PASS stage_shared_media copies replica cache into inbound")
    finally:
        import shutil

        shutil.rmtree(root, ignore_errors=True)


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


def test_image_ocr_ack() -> None:
    empty = image_ocr_ack_message("")
    assert "OCR không đọc được" in empty, empty
    empty_analyze = image_analyze_ack_message("")
    assert empty_analyze == "", empty_analyze
    full = image_ocr_ack_message("HOA DON 1250000 VND")
    assert "HOA DON 1250000 VND" in full and "Đã đọc chữ" in full, full
    vision = image_analyze_ack_message("A tired man sitting on a bench in a park.")
    assert "tired man" in vision and len(vision) > 20, repr(vision[:80])
    noise = "\n".join(list("naotoeeeeeeie"))
    assert ocr_excerpt_for_ack(noise) == "", noise
    assert "OCR không đọc được" in image_ocr_ack_message(noise)
    print("PASS bare-image OCR ack never silent")


def test_file_extract_ack() -> None:
    csv_ack = file_extract_ack_message(
        "usage.csv", "col_a,col_b\n1,2", kind="text"
    )
    assert "usage.csv" in csv_ack and "col_a" in csv_ack, csv_ack
    xlsx_ack = file_extract_ack_message(
        "report.xlsx", "Sheet1\nA B", kind="office"
    )
    assert "report.xlsx" in xlsx_ack and "Sheet1" in xlsx_ack, xlsx_ack
    empty_av = file_extract_ack_message("clip.mp4", "", kind="av")
    assert "Chưa lấy được transcript" in empty_av, empty_av
    mp3 = file_extract_ack_message("song.mp3", "lyrics line", kind="av")
    assert "song.mp3" in mp3 and "lyrics line" in mp3, mp3
    empty_txt = file_extract_ack_message("note.txt", "", kind="text")
    assert "Chưa đọc được nội dung" in empty_txt, empty_txt
    print("PASS bare-file extract ack never silent")


def test_workbook_sheet_recall() -> None:
    raw = (
        "Workbook sheets:\n"
        "1. Overview\n"
        "2. Detail\n"
        "\n"
        "## Sheet 1 (Overview)\n"
        "a\tb\n"
        "1\t2\n"
        "## Sheet 2 (Detail)\n"
        "x\ty\n"
        "hello sheet two\n"
    )
    sheets = split_workbook_sheets(raw)
    assert len(sheets) == 2, sheets
    assert sheets[1][0] == 2 and sheets[1][1] == "Detail"
    title, body = pick_sheet_section(raw, "2")
    assert title == "Detail" and "hello sheet two" in body, (title, body)
    title2, _ = pick_sheet_section(raw, "Detail")
    assert title2 == "Detail"
    assert sheet_ref_from_text("SHEET_REF: 2\nother") == "2"
    reply = workbook_sheet_reply("book.xlsx", raw, "2")
    assert "Detail" in reply and "hello sheet two" in reply, reply
    # Truncation must keep inventory + sheet-2 header/body start.
    huge = raw + ("pad\n" * 8000)
    kept = prefer_workbook_head(huge)
    assert "Workbook sheets:" in kept and "## Sheet 2 (Detail)" in kept, kept[:400]
    merged = context_merge([], "book.xlsx", huge)
    assert merged and "Workbook sheets:" in merged[0]["text"]
    print("PASS workbook sheet inventory + SHEET_REF recall")


def main() -> int:
    try:
        test_kind()
        test_worker_path()
        test_stage_shared_media()
        test_caption()
        test_context_pack()
        test_context_blocks()
        test_image_ocr_ack()
        test_file_extract_ack()
        test_workbook_sheet_recall()
    except AssertionError as e:
        print(f"FAIL {e}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
