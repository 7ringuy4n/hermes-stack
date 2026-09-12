# -*- coding: utf-8 -*-
"""Office PPTX + HTML→PDF unit (no LLM)."""
from __future__ import annotations

import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DISP = ROOT / "architect" / "models" / "dispatcher"
sys.path.insert(0, str(DISP))

import office_file  # noqa: E402
from office_file import parse_office, write_office, write_pdf  # noqa: E402

OUT = ROOT / "scripts" / "temp" / "office_pptx_unit"


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)

    ext, body = parse_office(
        "# Thời tiết Vũng Tàu\n## Hiện tại\n- Nhiệt độ: 30°C\n- Độ ẩm: 70%\n- Thời tiết: nắng nhẹ\n",
        "pptx",
    )
    assert ext == ".pptx", ext
    dest = write_office(OUT / "vung-tau.pptx", ext, body)
    assert dest.suffix.lower() == ".pptx", dest
    assert dest.is_file() and dest.stat().st_size > 2000, dest.stat().st_size

    from PIL import Image
    from pptx import Presentation

    scenic = OUT / "weather-scene.jpg"
    Image.new("RGB", (1600, 900), (55, 110, 165)).save(scenic, quality=90)
    office_file._MEDIA_ROOTS = (OUT,)
    visual_body = f"""# Dự báo thời tiết Thành phố Hồ Chí Minh
IMAGE: {scenic}
LAYOUT: full-bleed
## Tình hình hiện tại
- Nhiệt độ: 29°C
- Điều kiện: Nhiều mây
## Diễn biến hôm nay
- Buổi chiều: Có mưa rào
- Buổi tối: Dịu hơn
"""
    visual = write_office(OUT / "weather-visual.pptx", ".pptx", visual_body)
    deck = Presentation(str(visual))
    assert len(deck.slides) == 3
    with zipfile.ZipFile(visual) as archive:
        assert any(name.startswith("ppt/media/") for name in archive.namelist())

    html = """<!DOCTYPE html>
<html lang="vi"><head><meta charset="utf-8"/><title>t</title></head>
<body><h1>Thời tiết TP.HCM</h1><h2>Cập nhật</h2>
<div>Nhiệt độ: 27°C</div><div>Độ ẩm: 77%</div>
<p>Trời âm u.</p></body></html>"""
    pdf = write_pdf(OUT / "hero.pdf", html)
    assert pdf.is_file() and pdf.stat().st_size > 800, pdf.stat().st_size
    assert pdf.read_bytes()[:4] == b"%PDF"
    import pymupdf

    compact_doc = pymupdf.open(str(pdf))
    assert len(compact_doc) == 1
    assert compact_doc[0].rect.height < pymupdf.paper_rect("a4").height * 0.8
    compact_doc.close()

    # Placeholders must not appear when HTML is authored cleanly
    bad = write_pdf(
        OUT / "plain.pdf",
        "Nhiệt độ: 27°C\nĐộ ẩm: 70%\n",
    )
    assert bad.is_file() and bad.read_bytes()[:4] == b"%PDF"

    print("OFFICE_PPTX_OK", dest.name, pdf.name)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
