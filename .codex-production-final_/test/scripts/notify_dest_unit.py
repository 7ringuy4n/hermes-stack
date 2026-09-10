# -*- coding: utf-8 -*-
"""Unit: notify dest resolution (no VPS, no network)."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "architect" / "notification" / "notify"))

from dest import (  # noqa: E402
    SRC_ADMIN_ENV,
    SRC_ADMIN_FILE,
    SRC_NONE,
    SRC_OVERRIDE,
    SRC_REQUEST,
    parse_admin_env,
    parse_admin_file,
    resolve_zalo_dest,
)


def test_parse_admin_file() -> None:
    text = "# comment\n\n646293 | Alice\n999 should be ignored\n"
    assert parse_admin_file(text) == "646293"
    assert parse_admin_file("") == ""
    assert parse_admin_file("# only\n") == ""
    assert parse_admin_file("uid-only\n") == "uid-only"


def test_parse_admin_env() -> None:
    assert parse_admin_env(" a , b ") == "a"
    assert parse_admin_env("") == ""
    assert parse_admin_env("  ,  x") == "x"


def test_resolve_order() -> None:
    tid, src = resolve_zalo_dest(
        request_thread="req",
        env_thread="env",
        file_text="fileid | n",
        env_admins="envid",
    )
    assert (tid, src) == ("req", SRC_REQUEST)

    tid, src = resolve_zalo_dest(
        request_thread="",
        env_thread="env",
        file_text="fileid",
        env_admins="envid",
    )
    assert (tid, src) == ("env", SRC_OVERRIDE)

    tid, src = resolve_zalo_dest(
        request_thread="  ",
        env_thread="",
        file_text="# c\nadmin-1 | Bob\n",
        env_admins="envid",
    )
    assert (tid, src) == ("admin-1", SRC_ADMIN_FILE)

    tid, src = resolve_zalo_dest(
        request_thread="",
        env_thread="",
        file_text="",
        env_admins="envid,other",
    )
    assert (tid, src) == ("envid", SRC_ADMIN_ENV)

    tid, src = resolve_zalo_dest()
    assert (tid, src) == ("", SRC_NONE)


def main() -> int:
    test_parse_admin_file()
    test_parse_admin_env()
    test_resolve_order()
    print("PASS notify dest: request > override > admin file > admin env")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
