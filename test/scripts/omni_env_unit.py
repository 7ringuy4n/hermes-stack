#!/usr/bin/env python3
"""Unit tests for omni_env key resolution."""
from __future__ import annotations

import importlib.util
import os
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location(
    "omni_env",
    ROOT / "hermes" / "main" / "plugins" / "zalo" / "omni_env.py",
)
mod = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(mod)


def test_resolve_from_process_env(monkeypatch=None) -> None:
    os.environ["OMNIROUTER_API_KEY"] = "sk-test-key"
    try:
        assert mod.resolve_omni_api_key() == "sk-test-key"
    finally:
        os.environ.pop("OMNIROUTER_API_KEY", None)


def test_resolve_from_env_file() -> None:
    with tempfile.TemporaryDirectory() as td:
        envp = Path(td) / ".env"
        envp.write_text("OMNIROUTER_API_KEY=sk-from-file\n", encoding="utf-8")
        old = os.environ.pop("OMNIROUTER_API_KEY", None)
        old_open = os.environ.pop("OPENAI_API_KEY", None)
        try:
            val = mod._read_env_file(envp).get("OMNIROUTER_API_KEY")
            assert val == "sk-from-file"
        finally:
            if old:
                os.environ["OMNIROUTER_API_KEY"] = old
            if old_open:
                os.environ["OPENAI_API_KEY"] = old_open


def test_literal_newline_env_file() -> None:
    with tempfile.TemporaryDirectory() as td:
        envp = Path(td) / ".env"
        envp.write_text("OMNIROUTER_API_KEY=sk-x\\nENABLE_MEDIA_FILE=active", encoding="utf-8")
        data = mod._read_env_file(envp)
        assert data.get("OMNIROUTER_API_KEY") == "sk-x"
        assert data.get("ENABLE_MEDIA_FILE") == "active"


def main() -> None:
    test_resolve_from_process_env()
    test_resolve_from_env_file()
    test_literal_newline_env_file()
    print("OK omni_env_unit")


if __name__ == "__main__":
    main()
