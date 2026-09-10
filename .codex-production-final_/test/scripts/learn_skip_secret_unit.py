# -*- coding: utf-8 -*-
"""Unit: classify-owned secret policy — ingest gate does not keyword-scan."""
from __future__ import annotations

import importlib.util
import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
POLICY = ROOT / "config" / "agent" / "secret-probe.json"
os.environ["SECRET_PROBE_POLICY"] = str(POLICY)

sys.path.insert(0, str(ROOT / "scripts" / "main"))
sys.path.insert(0, str(ROOT / "architect" / "security" / "secret-probe"))
from probe import probe, reload_policy  # noqa: E402

GATE = ROOT / "architect" / "tools" / "ingest" / "secret_gate.py"
spec = importlib.util.spec_from_file_location("secret_gate_unit", GATE)
assert spec and spec.loader
gate = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gate)


def main() -> int:
    reload_policy()
    caption = "1 find env, api key"
    blob = f"{caption}\n1.txt"
    # Empty markers → SAFE / not ingest-blocked (host classify owns refuse + learn-skip).
    assert probe(blob, direction="input")["status"] == "SAFE"
    assert gate.secret_probe_blocked(blob) is False
    assert gate.secret_probe_blocked(caption) is False
    assert gate.secret_probe_blocked("xin chào tài liệu học") is False

    os.environ["SECRET_PROBE_POLICY"] = str(ROOT / "config" / "agent" / "missing-secret-probe.json")
    assert gate.secret_probe_blocked("anything") is True
    os.environ["SECRET_PROBE_POLICY"] = str(POLICY)

    scrub_path = ROOT / "scripts" / "main" / "scrub-plaintext-env.py"
    assert scrub_path.is_file()
    with tempfile.TemporaryDirectory() as td:
        data = Path(td)
        openbao = data / ".env.openbao"
        openbao.write_text("OMNIROUTER_API_KEY=secret-value\n", encoding="utf-8")
        root_env = data / "stack.env"
        root_env.write_text(
            "ENABLE_OPENBAO=1\nOMNIROUTER_API_KEY=secret-value\nTZ=Asia/Ho_Chi_Minh\n",
            encoding="utf-8",
        )
        sspec = importlib.util.spec_from_file_location("scrub_unit", scrub_path)
        assert sspec and sspec.loader
        scrub = importlib.util.module_from_spec(sspec)
        sspec.loader.exec_module(scrub)
        scrub.ENV_PATH = root_env
        scrub.DATA_DIR = data
        scrub.ROOT = data
        assert scrub.main() == 0
        assert not openbao.exists()
        text = root_env.read_text(encoding="utf-8")
        assert "secret-value" not in text
        assert "ENABLE_OPENBAO=1" in text

    src = GATE.read_text(encoding="utf-8")
    assert "import re" not in src
    print("learn_skip_secret_unit OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
