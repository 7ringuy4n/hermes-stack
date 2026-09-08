#!/usr/bin/env python3
"""Unit checks for external fixture discovery from nested worktrees."""
from __future__ import annotations

import os
import tempfile
from pathlib import Path

from fixture_paths import test_docs_root


def main() -> int:
    previous = os.environ.pop("ASSISTANT_TEST_DOCS", None)
    try:
        with tempfile.TemporaryDirectory() as raw:
            workspace = Path(raw) / "workspace"
            docs = workspace / "test docs"
            nested = workspace / "repo" / ".worktrees" / "release"
            docs.mkdir(parents=True)
            nested.mkdir(parents=True)
            assert test_docs_root(nested) == docs.resolve()
            configured = workspace / "fixtures"
            os.environ["ASSISTANT_TEST_DOCS"] = str(configured)
            assert test_docs_root(nested) == configured
    finally:
        if previous is None:
            os.environ.pop("ASSISTANT_TEST_DOCS", None)
        else:
            os.environ["ASSISTANT_TEST_DOCS"] = previous
    print("fixture_paths_unit: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
