# -*- coding: utf-8 -*-
"""Unit: router-worker skill sync replaces bake via atomic rename."""
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
        _atomic_copy(src, dst)
        assert dst.read_text(encoding="utf-8") == '{"ok": true}\n'

        if os.name == "posix":
            src.write_text('{"ok2": true}\n', encoding="utf-8")
            dst.write_text('{"old2": true}\n', encoding="utf-8")
            os.chmod(dst, stat.S_IRUSR | stat.S_IRGRP | stat.S_IROTH)
            if not os.access(dst, os.W_OK):
                _atomic_copy(src, dst)
                assert dst.read_text(encoding="utf-8") == '{"ok2": true}\n'

    print("sync_router_worker_skills_unit: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
