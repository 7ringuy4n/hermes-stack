#!/usr/bin/env python3
"""Unit: every component-change backup reloads and re-scrubs OpenBao secrets."""
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def function_body(source: str, name: str) -> str:
    start_token = name + "() {"
    start = source.index(start_token)
    next_function = source.find("\n}\n\n", start)
    if next_function < 0:
        raise AssertionError("function boundary missing: " + name)
    return source[start : next_function + 3]


def main() -> int:
    source = (ROOT / "run.sh").read_text(encoding="utf-8")
    body = function_body(source, "do_archive_before_change")
    load_at = body.index("do_prepare_openbao_env_for_compose")
    backup_at = body.index('do_backup_first "$reason"')
    scrub_at = body.index("do_scrub_plaintext_env")
    assert load_at < backup_at < scrub_at
    assert 'return "$backup_status"' in body
    print("OK component-change OpenBao lifecycle")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
