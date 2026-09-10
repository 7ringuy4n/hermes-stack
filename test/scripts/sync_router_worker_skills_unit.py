# -*- coding: utf-8 -*-
"""Unit: router-worker skill sync replaces root-owned bake via atomic rename."""
from __future__ import annotations

import os
import stat
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts" / "main"))

from sync_router_worker_skills import _atomic_copy  # noqa: E402


def main() -> int:
    with tempfile.TemporaryDirectory() as raw:
        base = Path(raw)
        src = base / "src.json"
        dst = base / "dst.json"
        src.write_text('{"ok": true}\n', encoding="utf-8")
        dst.write_text('{"old": true}\n', encoding="utf-8")
        # Simulate a prior root-owned bake: remove user write bit.
        os.chmod(dst, stat.S_IRUSR | stat.S_IRGRP | stat.S_IROTH)
        assert not os.access(dst, os.W_OK), "fixture must be non-writable"
        _atomic_copy(src, dst)
        assert dst.read_text(encoding="utf-8") == '{"ok": true}\n', dst.read_text(
            encoding="utf-8"
        )
    print("sync_router_worker_skills_unit: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
