#!/usr/bin/env python3
"""Static contract for fencing queue-owned background agent sessions."""
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
ADAPTER = ROOT / "hermes" / "main" / "plugins" / "zalo" / "adapter.py"
LAB = ROOT / "test" / "scripts" / "zalo_dm_group_concurrency_lab.py"


def main() -> int:
    source = ADAPTER.read_text(encoding="utf-8")
    lab = LAB.read_text(encoding="utf-8")

    idle_failure = 'raise RuntimeError("agent session did not become idle")'
    cancel = "await self.cancel_session_processing(session_key)"
    assert cancel in source
    assert source.index(cancel) < source.index(idle_failure)
    assert "outer_timeout = turn_task.cancelled()" in source
    assert "The request took too long and was stopped." in source
    assert "not dm_content_exact or not group_content_exact" in lab
    print("zalo_queue_session_timeout_unit: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
