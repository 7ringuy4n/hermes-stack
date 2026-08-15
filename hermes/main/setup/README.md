# hermes/main/setup/

Optional **inbox** for extra docs packs to index after Hermes + 9Router are ready.

`scripts/main/post-ready-learn.py` (called by `run.sh up` / `update`) will:

1. Wait for 9Router + Hermes + ingest.
2. If `hermes/main/skills/` has real skills (`SKILL.md`, not only `_example`):
   - Mirror skill markdown into `$ASSISTANT_DATA_DIR/docs/skills/`
   - Mirror this folder into `$ASSISTANT_DATA_DIR/docs/setup/`
   - Mirror `hermes/main/docs/` (if present) into `$ASSISTANT_DATA_DIR/docs/hermes-docs/`
   - Run ingest `learn/scan` (auto-ingest when `LEARN_REQUIRE_APPROVE=0`).

Hermes already loads skills via compose bind mount — this step is for **knowledge** cite/list.

Drop `.md` / `.txt` / `.pdf` files or subfolders here. Do not put secrets.
