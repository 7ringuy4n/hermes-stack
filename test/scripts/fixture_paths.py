"""Resolve external lab fixtures from a repository or nested worktree."""
from __future__ import annotations

import os
from pathlib import Path


def test_docs_root(repository_root: Path) -> Path:
    """Return the nearest ancestor's sibling ``test docs`` directory."""
    configured = (os.environ.get("ASSISTANT_TEST_DOCS") or "").strip()
    if configured:
        return Path(configured).expanduser()
    root = repository_root.resolve()
    for parent in root.parents:
        candidate = parent / "test docs"
        if candidate.is_dir():
            return candidate
    return root.parent / "test docs"
