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
    for name in ("do_add_components", "do_remove_components"):
        change_body = function_body(source, name)
        write_at = change_body.index('env_upsert "$k" "$v"')
        export_at = change_body.index('export "$k=$v"')
        apply_at = change_body.index("_apply_component_change")
        assert write_at < export_at < apply_at
    print("OK component-change OpenBao lifecycle")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
