# -*- coding: utf-8 -*-
"""Vietnamese font coverage + office/text-poster render smoke (no LLM)."""
from __future__ import annotations

import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

ROOT_CANDIDATES = [
    Path(__file__).resolve().parents[2] if len(Path(__file__).resolve().parts) > 3 else Path("/tmp"),
    Path("/opt/assistant"),
    Path("/tmp"),
]
ROOT = next(
    (
        p
        for p in ROOT_CANDIDATES
        if (p / "architect" / "models" / "dispatcher" / "fonts.py").is_file()
        or (Path("/app") / "fonts.py").is_file()
    ),
    Path("/tmp"),
)
DISP = ROOT / "architect" / "models" / "dispatcher"
if not (DISP / "fonts.py").is_file():
    DISP = Path("/app")
sys.path.insert(0, str(DISP))

from fonts import pillow_font, resolve_font_path  # noqa: E402
from office_file import write_office, write_pdf  # noqa: E402
from text_poster import render_text_poster_bytes  # noqa: E402

OUT = ROOT / "scripts" / "temp" / "media_smoke"
if not (ROOT / "scripts" / "temp").is_dir():
    OUT = Path("/tmp/media_smoke_out")
VI = "Hồ Chí Minh — Thứ Bảy cập nhật mưa"


def _assert_font_covers() -> None:
    path = resolve_font_path(bold=False)
    assert Path(path).is_file(), path
    font = pillow_font(48, bold=True)
    for ch in "ồứậưở":
        mask = font.getmask(ch)
        assert mask.size[0] > 0 and mask.size[1] > 0, (ch, path)
    print("FONT_OK", path)


def _one_pdf(i: int) -> Path:
    p = OUT / f"weather_{i}.pdf"
    body = f"""<!DOCTYPE html>
<html lang="vi"><head><meta charset="utf-8"/><title>w{i}</title></head>
<body>
<h1>Thời tiết TP. Hồ Chí Minh #{i}</h1>
<h2>Cập nhật hiện tại</h2>
<ul>
<li>Nhiệt độ: 27.0°C (cảm giác 32.1°C)</li>
<li>Độ ẩm: 85%</li>
<li>Mưa: 0.00 mm</li>
</ul>
</body></html>"""
    write_pdf(p, body)
    assert p.stat().st_size > 800, p.stat().st_size
    return p


def _one_xlsx(i: int) -> Path:
    p = OUT / f"sheet_{i}.xlsx"
    write_office(p, ".xlsx", f"Thành phố\nHồ Chí Minh\nNhiệt độ 27°C\nrow-{i}")
    assert p.suffix == ".xlsx" and p.stat().st_size > 2000
    return p


def _one_docx(i: int) -> Path:
    p = OUT / f"doc_{i}.docx"
    write_office(p, ".docx", f"Báo cáo thời tiết Hồ Chí Minh\nCập nhật lúc sáng\nMục {i}")
    assert p.suffix == ".docx" and p.stat().st_size > 2000
    return p


def _one_poster(i: int) -> Path:
    p = OUT / f"poster_{i}.png"
    p.write_bytes(
        render_text_poster_bytes(
            {"phrase": f"Xin chào Hồ Chí Minh #{i}", "n": 5, "bw": True}
        )
    )
    assert p.stat().st_size > 3000
    return p


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    for old in OUT.glob("*"):
        old.unlink()
    t0 = time.perf_counter()
    _assert_font_covers()

    jobs = []
    with ThreadPoolExecutor(max_workers=8) as pool:
        for i in range(6):
            jobs.append(pool.submit(_one_pdf, i))
            jobs.append(pool.submit(_one_xlsx, i))
            jobs.append(pool.submit(_one_docx, i))
            jobs.append(pool.submit(_one_poster, i))
        ok = 0
        for fut in as_completed(jobs):
            fut.result()
            ok += 1
    elapsed = time.perf_counter() - t0
    print(f"MEDIA_SMOKE_OK jobs={ok} elapsed_s={elapsed:.2f} out={OUT} (info-card/overlay retired)")
    if elapsed > 25:
        print("WARN slow media smoke", elapsed)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
