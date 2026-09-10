#!/usr/bin/env python3
"""Regression checks for non-chat OmniRoute attribution completion."""
from __future__ import annotations

import importlib.util
import json
import sqlite3
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
APP = ROOT / "architect/models/omni-attribution/app.py"


def main() -> int:
    spec = importlib.util.spec_from_file_location("omni_attribution", APP)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    with tempfile.TemporaryDirectory() as temp:
        db = Path(temp) / "storage.sqlite"
        conn = sqlite3.connect(db)
        conn.execute("create table combos (name text, data text)")
        conn.execute(
            "create table call_logs (path text, model text, requested_model text, "
            "combo_name text, api_key_name text)"
        )
        for name in ("image-gen", "embedding", "web-search"):
            conn.execute("insert into combos values (?, ?)", (name, json.dumps({"name": name})))
        rows = (
            ("/v1/images/generations", "ai-box/qwen-image", None, None, "assistant-stack"),
            ("/v1/embeddings", "ai-box/qwen-embed", None, None, "assistant-stack"),
            ("/v1/search", "tavily-search", None, None, None),
            ("/v1/embeddings", "direct-model", None, None, "another-key"),
            ("/v1/embeddings", "kept-model", "original", "custom", "assistant-stack"),
        )
        conn.executemany("insert into call_logs values (?, ?, ?, ?, ?)", rows)
        conn.commit()
        conn.close()

        changed = module.reconcile_once(db)
        conn = sqlite3.connect(db)
        got = list(conn.execute("select requested_model,combo_name from call_logs order by rowid"))
        conn.close()
    checks = {
        "four stack endpoint rows normalized": changed == 4,
        "image combo attributed": got[0] == ("image-gen", "image-gen"),
        "embedding combo attributed": got[1] == ("embedding", "embedding"),
        "search combo attributed": got[2] == ("web-search", "web-search"),
        "other API key untouched": got[3] == (None, None),
        "stack endpoint normalized": got[4] == ("embedding", "embedding"),
    }
    for name, ok in checks.items():
        print(("PASS" if ok else "FAIL"), name)
    return 0 if all(checks.values()) else 1


if __name__ == "__main__":
    raise SystemExit(main())
