# scripts/temp — session-only hotfix / deploy probes

**Not committed** (see root `.gitignore`). Allowed durable-looking helper:

- `generate_env_secrets.py` — fill `CHANGE_ME_*` in `.env` from `.env.example`

Everything else here is **session junk** and must be deleted after the lab/fix
round (AGENT_RULES: clean `scripts/temp` when done).

Use for one-off VPS probes only. Product entrypoints belong in `scripts/main/`
with `ASSISTANT_SSH_*` — never bake lab host/password defaults into committed code.
