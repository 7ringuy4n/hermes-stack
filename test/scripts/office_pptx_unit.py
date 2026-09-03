# -*- coding: utf-8 -*-
"""Office PPTX + PDF hero metric unit (no LLM)."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DISP = ROOT / "architect" / "models" / "dispatcher"
sys.path.insert(0, str(DISP))

from office_file import (  # noqa: E402
    _hero_metric,
    parse_office,
    write_office,
)

OUT = ROOT / "scripts" / "temp" / "office_pptx_unit"


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    hero = _hero_metric(
        [
            "Nhiệt độ: 27°C (cảm giác như 29°C)",
            "Độ ẩm: 77%",
        ]
    )
    assert hero == "27°C", hero

    ext, body = parse_office(
        "# Thời tiết Vũng Tàu\n## Hiện tại\n- Nhiệt độ: 30°C\n- Độ ẩm: 70%\n- Thời tiết: nắng nhẹ\n",
        "pptx",
    )
    assert ext == ".pptx", ext
    dest = write_office(OUT / "vung-tau.pptx", ext, body)
    assert dest.suffix.lower() == ".pptx", dest
    assert dest.is_file() and dest.stat().st_size > 2000, dest.stat().st_size

    # Placeholder bullets must not become body facts for PDF either
    from office_file import write_pdf_styled

    pdf = write_pdf_styled(
        OUT / "hero.pdf",
        "# Thời tiết TP.HCM\n## Cập nhật\n- Nhiệt độ: 27°C (cảm giác như 29°C)\n"
        "- Độ ẩm: <value after search>\n- Thời tiết: trời âm u\n",
    )
    assert pdf.is_file()
    print("OFFICE_PPTX_OK", dest.name, pdf.name, hero)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
