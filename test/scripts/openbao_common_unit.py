#!/usr/bin/env python3
"""Unit: OpenBao seed merge + scrub key lists."""
from __future__ import annotations

import sys
import tempfile
import importlib.util
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts" / "main"))

from openbao_common import (  # noqa: E402
    COMPOSE_HOST_KEYS,
    ENV_SCRUB_KEYS,
    OBSOLETE_SECRET_KEYS,
    SEED_KEYS,
)
_load_spec = importlib.util.spec_from_file_location(
    "load_openbao_env",
    ROOT / "scripts" / "main" / "load-openbao-env.py",
)
assert _load_spec and _load_spec.loader
load_openbao_env = importlib.util.module_from_spec(_load_spec)
_load_spec.loader.exec_module(load_openbao_env)


def main() -> int:
    assert "OMNIROUTER_API_KEY" in SEED_KEYS
    assert "OMNIROUTER_API_KEY" in ENV_SCRUB_KEYS
    assert "OPENBAO_DEV_ROOT_TOKEN" not in ENV_SCRUB_KEYS
    assert "OMNIROUTER_API_KEY" in COMPOSE_HOST_KEYS
    assert "POLLINATIONS_API_KEY" in SEED_KEYS
    assert "POLLINATIONS_API_KEY" in ENV_SCRUB_KEYS
    assert "POLLINATIONS_API_KEY" not in OBSOLETE_SECRET_KEYS
    assert "FAL_KEY" in OBSOLETE_SECRET_KEYS
    # Merge semantics (mirror first-setup-openbao)
    existing = {"OMNIROUTER_API_KEY": "old", "TAVILY_API_KEY": "keep"}
    incoming = {"OMNIROUTER_API_KEY": "new"}
    merged = dict(existing)
    merged.update(incoming)
    assert merged["OMNIROUTER_API_KEY"] == "new"
    assert merged["TAVILY_API_KEY"] == "keep"
    # Obsolete purge semantics
    data = {"OMNIROUTER_API_KEY": "x", "FAL_KEY": "gone"}
    for k in OBSOLETE_SECRET_KEYS:
        data.pop(k, None)
    assert "FAL_KEY" not in data
    assert data["OMNIROUTER_API_KEY"] == "x"

    # A privileged refresh must not leave .env.openbao owned by root when the
    # runtime data directory belongs to the normal stack operator.
    with tempfile.TemporaryDirectory() as tmp:
        data_dir = Path(tmp)
        export_path = data_dir / ".env.openbao"
        export_path.write_text("KEY=redacted\n", encoding="utf-8")
        st = data_dir.stat()
        with patch.object(load_openbao_env.os, "chown", create=True) as chown:
            assert load_openbao_env.match_export_owner(export_path, data_dir)
            chown.assert_called_once_with(export_path, st.st_uid, st.st_gid)
    print("OK openbao_common unit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
