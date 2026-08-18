# scripts/temp — local hotfix / deploy probes

**Not committed** (see root `.gitignore`). Use for:

- one-off deploys to a **test host** (`deploy-*.py`)
- health probes (`probe-*.py`)
- temporary bugfix / finish scripts
- any script that needs a real VPS IP, SSH user, or password

Do not put product entrypoints here — those belong in `scripts/main/` and must use `ASSISTANT_SSH_*` env vars with **no** lab host/account defaults.

Never copy host credentials from this folder into `scripts/main/`, `test/`, or docs.
