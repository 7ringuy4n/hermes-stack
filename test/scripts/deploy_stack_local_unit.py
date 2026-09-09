#!/usr/bin/env python3
"""The VPS-local lab mode must not require SSH credentials or Paramiko."""
from __future__ import annotations

import importlib.util
import os
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def main() -> int:
    os.environ["ASSISTANT_VPS_LOCAL"] = "1"
    for name in (
        "ASSISTANT_SSH_HOST",
        "ASSISTANT_SSH_USER",
        "ASSISTANT_SSH_PASSWORD",
    ):
        os.environ.pop(name, None)
    path = ROOT / "test" / "scripts" / "deploy_stack.py"
    spec = importlib.util.spec_from_file_location("deploy_stack_local", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    assert module.LOCAL_MODE is True
    client = module.connect()
    assert client.__class__.__name__ == "_LocalClient"
    client.close()
    print("deploy_stack_local_unit: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
