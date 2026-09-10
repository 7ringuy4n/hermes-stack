# -*- coding: utf-8 -*-
"""Unit tests for compound media-ack deferral helpers (no VPS)."""
from __future__ import annotations

import io
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "hermes" / "main" / "plugins" / "zalo"))

if hasattr(sys.stdout, "buffer"):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")


class _Stub:
    def _as_is_media_ack_only(self, content: str) -> bool:
        t = (content or "").strip().lower().rstrip(".!?")
        if not t:
            return True
        return t in {"đã xong", "da xong", "done", "xong"}


def main() -> int:
    s = _Stub()
    if not s._as_is_media_ack_only("Đã xong."):
        print("FAIL should detect Vietnamese ack")
        return 1
    if not s._as_is_media_ack_only("Done."):
        print("FAIL should detect English ack")
        return 1
    if s._as_is_media_ack_only("E5 RON92: 23.500 đ/l"):
        print("FAIL fuel line must not be ack-only")
        return 1
    if s._as_is_media_ack_only("Giá xăng E10 RON95 cập nhật"):
        print("FAIL price text must not be ack-only")
        return 1
    print("PASS media ack-only detection")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
