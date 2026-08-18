# -*- coding: utf-8 -*-
"""Unit: locale UX copy (no VPS)."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "hermes" / "main" / "plugins" / "zalo"))

from ux_copy import pick_localized, reply_lang  # noqa: E402


def main() -> int:
    fails = 0
    if reply_lang("every day at 16:40 GMT+7") != "en":
        print("FAIL en detect")
        fails += 1
    if reply_lang("hằng ngày lúc 16:40") != "vi":
        print("FAIL vi detect")
        fails += 1
    spec = {
        "default": "en",
        "en": "Schedule saved.",
        "vi": "Đã lưu lịch.",
        "ko": "일정이 저장되었습니다.",
    }
    if pick_localized(spec, "vi", "x") != "Đã lưu lịch.":
        print("FAIL pick vi")
        fails += 1
    if pick_localized(spec, "en", "x") != "Schedule saved.":
        print("FAIL pick en")
        fails += 1
    if pick_localized(spec, "fr", "x") != "Schedule saved.":
        print("FAIL pick fallback en")
        fails += 1
    if pick_localized("plain", "vi", "x") != "plain":
        print("FAIL string spec")
        fails += 1
    if fails:
        return 1
    print("PASS ux_copy locale pick")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
