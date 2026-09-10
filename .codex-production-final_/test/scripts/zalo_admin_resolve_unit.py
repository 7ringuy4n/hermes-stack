# -*- coding: utf-8 -*-
"""Unit: admin resolve prefers named user, else first admin (main/any)."""
from __future__ import annotations

import tempfile
from pathlib import Path

from zalo_admin_resolve import resolve_admin_user


def main() -> int:
    with tempfile.TemporaryDirectory() as td:
        p = Path(td) / "admins.txt"
        p.write_text("# x\n111|Alice\n222|Tn\n", encoding="utf-8")
        uid, name = resolve_admin_user("Tn", paths=(str(p),), strict_name=True)
        assert uid == "222" and name == "Tn"
        uid, name = resolve_admin_user("", paths=(str(p),))
        assert uid == "111" and name == "Alice"
        uid, name = resolve_admin_user("Missing", paths=(str(p),), strict_name=False)
        assert uid == "111" and name == "Alice"
        try:
            resolve_admin_user("Missing", paths=(str(p),), strict_name=True)
            raise AssertionError("expected fail")
        except RuntimeError:
            pass
        uid, name = resolve_admin_user("", paths=(str(p),), want_id="222")
        assert uid == "222"
    print("PASS_ZALO_ADMIN_RESOLVE")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
