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
    is_secret_env_name,
)
_load_spec = importlib.util.spec_from_file_location(
    "load_openbao_env",
    ROOT / "scripts" / "main" / "load-openbao-env.py",
)
assert _load_spec and _load_spec.loader
load_openbao_env = importlib.util.module_from_spec(_load_spec)
_load_spec.loader.exec_module(load_openbao_env)
_restore_spec = importlib.util.spec_from_file_location(
    "restore_openbao_kv",
    ROOT / "architect" / "backup-restore" / "lib" / "restore_openbao_kv.py",
)
assert _restore_spec and _restore_spec.loader
restore_openbao_kv = importlib.util.module_from_spec(_restore_spec)
_restore_spec.loader.exec_module(restore_openbao_kv)
_migrate_spec = importlib.util.spec_from_file_location(
    "migrate_openbao_token",
    ROOT / "scripts" / "main" / "migrate-openbao-token.py",
)
assert _migrate_spec and _migrate_spec.loader
migrate_openbao_token = importlib.util.module_from_spec(_migrate_spec)
_migrate_spec.loader.exec_module(migrate_openbao_token)


def main() -> int:
    assert "OMNIROUTER_API_KEY" in SEED_KEYS
    assert "OMNIROUTER_API_KEY" in ENV_SCRUB_KEYS
    assert "OPENBAO_DEV_ROOT_TOKEN" not in ENV_SCRUB_KEYS
    assert "OMNIROUTER_API_KEY" in COMPOSE_HOST_KEYS
    assert "POLLINATIONS_API_KEY" in SEED_KEYS
    assert "POLLINATIONS_API_KEY" in ENV_SCRUB_KEYS
    assert "POLLINATIONS_API_KEY" not in OBSOLETE_SECRET_KEYS
    for key in ("EMBED_API_KEY", "OCR_API_KEY", "LLM_JUDGE_KEY", "GOOGLE_API_KEY", "OPENAI_API_KEY"):
        assert key in SEED_KEYS
    assert is_secret_env_name("FUTURE_PROVIDER_API_KEY")
    assert is_secret_env_name("SERVICE_PASSWORD")
    assert not is_secret_env_name("OPENBAO_DEV_ROOT_TOKEN")
    assert not is_secret_env_name("HERMES_REPLICAS")
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
        historical = data_dir / "env.openbao"
        historical.write_text("API_SERVER_KEY=redacted\nEMPTY=\n", encoding="utf-8")
        assert restore_openbao_kv.load_backup_payload(historical) == {
            "API_SERVER_KEY": "redacted"
        }
        source_env = data_dir / ".env"
        token_path = data_dir / "openbao" / "root-token"
        source_env.write_text(
            "ENABLE_OPENBAO=active\nOPENBAO_DEV_ROOT_TOKEN=bootstrap-secret\n",
            encoding="utf-8",
        )
        migrate_openbao_token.ENV_PATH = source_env
        migrate_openbao_token.TOKEN_PATH = token_path
        with patch.dict(migrate_openbao_token.os.environ, {}, clear=True):
            assert migrate_openbao_token.migrate()
        assert token_path.read_text(encoding="utf-8").strip() == "bootstrap-secret"
        assert "OPENBAO_DEV_ROOT_TOKEN" not in source_env.read_text(encoding="utf-8")
        if migrate_openbao_token.os.name == "posix":
            assert token_path.stat().st_mode & 0o777 == 0o600
    print("OK openbao_common unit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
