"""Unit coverage for deterministic, private case-index evidence."""
from __future__ import annotations

from run_case_index_lab import progress_line, report_cell


def main() -> int:
    raw = "[sudo: authenticate] Password:\nPASS `done` | stable"
    cell = report_cell(raw)
    assert "Password" not in cell
    assert "\n" not in cell and "\r" not in cell
    assert cell == "PASS 'done' \\| stable", cell
    assert progress_line(16, 103, "unit", "x", "demo_unit.py") == (
        "running test case 16/103: unit x demo_unit.py"
    )
    print("run_case_index_unit: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
