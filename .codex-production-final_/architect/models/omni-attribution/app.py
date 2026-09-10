#!/usr/bin/env python3
"""Complete OmniRoute call attribution omitted by non-chat handlers.

OmniRoute records the resolved provider/model for image, embedding, and search
calls, but those handlers do not consistently retain the requested combo alias.
This worker restores that stack-owned request attribution while leaving the
resolved backend in ``model``. It never changes combo definitions, providers,
or combo membership.
"""
from __future__ import annotations

import os
import sqlite3
import time
from pathlib import Path

DB_PATH = Path(os.environ.get("OMNIROUTE_DB_PATH") or "/omni-data/storage.sqlite")
INTERVAL_SECONDS = max(1.0, float(os.environ.get("ATTRIBUTION_INTERVAL_SECONDS") or "5"))
API_KEY_NAME = (os.environ.get("ATTRIBUTION_API_KEY_NAME") or "assistant-stack").strip()


def endpoint_combos() -> dict[str, str]:
    configured = {
        "/v1/images/generations": os.environ.get("IMAGE_GEN_COMBO") or "image-gen",
        "/v1/images/edits": os.environ.get("IMAGE_EDIT_COMBO") or "image-edit",
        "/v1/embeddings": os.environ.get("EMBED_COMBO") or "embedding",
        "/v1/search": os.environ.get("WEB_SEARCH_COMBO") or "web-search",
    }
    return {path: combo.strip() for path, combo in configured.items() if combo.strip()}


def _columns(conn: sqlite3.Connection, table: str) -> set[str]:
    return {str(row[1]) for row in conn.execute(f"pragma table_info({table})")}


def reconcile_once(db_path: Path = DB_PATH) -> int:
    if not db_path.is_file():
        return 0
    conn = sqlite3.connect(str(db_path), timeout=10)
    try:
        needed = {"path", "model", "requested_model", "combo_name", "api_key_name"}
        if not needed.issubset(_columns(conn, "call_logs")):
            return 0
        combos = {
            str(row[0])
            for row in conn.execute("select name from combos")
            if row[0] is not None
        }
        changed = 0
        for path, combo in endpoint_combos().items():
            if combo not in combos:
                continue
            owner_clause = "api_key_name=?"
            if path == "/v1/search":
                # OmniRoute's search handler currently omits API-key identity as
                # well as requested-model attribution. Keep this exception tied
                # to the search endpoint; other endpoint rows remain key-scoped.
                owner_clause = "(api_key_name=? or api_key_name is null)"
            cursor = conn.execute(
                "update call_logs "
                "set requested_model=?, combo_name=? "
                f"where path=? and {owner_clause} "
                "and model is not null "
                "and (requested_model is not ? or combo_name is not ?)",
                (combo, combo, path, API_KEY_NAME, combo, combo),
            )
            changed += max(0, int(cursor.rowcount))
        conn.commit()
        return changed
    finally:
        conn.close()


def main() -> int:
    print(f"omni-attribution db={DB_PATH} interval={INTERVAL_SECONDS:g}s")
    while True:
        try:
            changed = reconcile_once()
            if changed:
                print(f"omni-attribution completed_rows={changed}")
        except (OSError, sqlite3.Error) as exc:
            print(f"omni-attribution retry error={type(exc).__name__}")
        time.sleep(INTERVAL_SECONDS)


if __name__ == "__main__":
    raise SystemExit(main())
