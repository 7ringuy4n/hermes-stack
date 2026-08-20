# scripts/main — product ops

Committed with the repo. Invoked by `run.sh` and first-setup docs.

| Script | Role |
|---|---|
| `install-docker.sh` | Official Docker CE; adds **current SSH login user** (`SUDO_USER`) to `docker` group |
| `first-setup-omnirouter.py` | **Default** — OmniRoute key + chat combo `hermes` + classify combo `classifier` (all OpenCode Free `oc/*`) |
| `first-setup-omnirouter.sh` | Thin wrapper |
| `first-setup-9router-hermes.py` | Optional — only when `ENABLE_9ROUTER=1` |
| `first-setup-9router-hermes.sh` | Thin wrapper |
| `setup-zalo.sh` | Install Zalo bridge + adapter after core ready (no QR) |
| `login-zalo.sh` | Manual QR login (last step) |
| `stack-watch.sh` | Health / auto-heal timers |

Workers: see `docs/00-workers.md` and `bash run.sh workers`.
