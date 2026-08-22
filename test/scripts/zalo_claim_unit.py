# -*- coding: utf-8 -*-
"""!zalo claim: QR-login account (sender==bot_id) must be able to become admin."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "architect" / "zalo-api"))

from app import claim_admin_decision  # noqa: E402


def main() -> int:
    bot = "1001"
    tn = "1001"
    other = "2002"
    assert claim_admin_decision("", bot, set()) == "missing_sender"
    assert claim_admin_decision(tn, bot, set()) == "ok"
    assert claim_admin_decision(tn, bot, {bot}) == "ok"
    assert claim_admin_decision(tn, "", set()) == "ok"
    assert claim_admin_decision(other, bot, {bot}) == "ok"
    assert claim_admin_decision(other, bot, {"9999"}) == "has_other_admin"
    print("PASS_ZALO_CLAIM_DECISION")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
