"""Unit coverage for deterministic, private case-index evidence."""
from __future__ import annotations

from run_case_index_lab import report_cell


def main() -> int:
    raw = "[sudo: authenticate] Password:\nPASS `done` | stable"
    cell = report_cell(raw)
    assert "Password" not in cell
    assert "\n" not in cell and "\r" not in cell
    assert cell == "PASS 'done' \\| stable", cell
    print("run_case_index_unit: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
