"""Unit coverage for deterministic, private case-index evidence."""
from __future__ import annotations

import os
from unittest.mock import patch

from run_case_index_lab import candidate_sha, progress_line, report_cell, unit_command


def main() -> int:
    raw = "[sudo: authenticate] Password:\nPASS `done` | stable"
    cell = report_cell(raw)
    assert "Password" not in cell
    assert "\n" not in cell and "\r" not in cell
    assert cell == "PASS 'done' \\| stable", cell
    assert progress_line(16, 103, "unit", "x", "demo_unit.py") == (
        "running test case 16/103: unit x demo_unit.py"
    )
    with patch.dict(os.environ, {"ASSISTANT_CANDIDATE_SHA": "AbCdEf1"}):
        assert candidate_sha() == "abcdef1"
    with patch.dict(os.environ, {"ASSISTANT_CANDIDATE_SHA": "not a sha"}):
        with patch("run_case_index_lab.subprocess.check_output", side_effect=OSError):
            assert candidate_sha() == "unknown"
    with patch.dict(os.environ, {"ASSISTANT_TEST_LOCAL": "1"}):
        assert unit_command("router_worker_identity_unit.py")[0] != "docker"
        gateway = unit_command("workflow_gateway_unit.py")
        dispatcher = unit_command("media_unicode_smoke_unit.py")
        assert gateway[0:3] == ["docker", "run", "--rm"]
        assert "assistant-api-gateway" in gateway
        assert "assistant-dispatcher" in dispatcher
    print("run_case_index_unit: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
