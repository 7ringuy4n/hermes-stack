#!/usr/bin/env python3
"""Model context excludes abandoned user-only durable turns."""
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[2]
PLUGIN = ROOT / "hermes" / "main" / "plugins" / "zalo"
sys.path.insert(0, str(PLUGIN))

import session_memory  # noqa: E402


def main() -> int:
    rows = [
        {"role": "user", "content": "completed request"},
        {"role": "assistant", "content": "completed answer"},
        {"role": "user", "content": "abandoned old request"},
        {"role": "user", "content": "newer completed request"},
        {"role": "assistant", "content": "newer completed answer"},
        {"role": "user", "content": "currently abandoned request"},
    ]
    kept = session_memory.completed_context(rows)
    contents = [str(row.get("content") or "") for row in kept]
    assert contents == [
        "completed request",
        "completed answer",
        "newer completed request",
        "newer completed answer",
    ]

    original = session_memory.load_messages
    session_memory.load_messages = lambda *_args, **_kwargs: rows
    try:
        hydrated = session_memory.hydrate_user_text("thread", "user", "current request")
    finally:
        session_memory.load_messages = original
    assert "completed request" in hydrated
    assert "newer completed answer" in hydrated
    assert "abandoned old request" not in hydrated
    assert "currently abandoned request" not in hydrated
    assert hydrated.endswith("current request")

    # Adapter contract: an explicit reply already names the relevant context,
    # so unrelated durable history must not be prepended to that turn.
    adapter_source = (PLUGIN / "adapter.py").read_text(encoding="utf-8")
    assert 'if explicit_quote' in adapter_source
    assert 'and not item.get("explicit_quote")' in adapter_source
    print("session_memory_hygiene_unit: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
