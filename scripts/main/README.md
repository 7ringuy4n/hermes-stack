# scripts/main — product ops

Committed with the repo. Invoked by `run.sh` and first-setup docs.

| Script | Role |
|---|---|
| `install-docker.sh` | Official Docker CE; adds **current SSH login user** (`SUDO_USER`) to `docker` group |
| `first-setup-9router-hermes.py` | Default Key → Hermes + combo `hermes` (OpenCode Free, round-robin) |
| `first-setup-9router-hermes.sh` | Thin wrapper around the Python script |
| `first-setup-omnirouter.py` | OmniRoute Default Key + combo `hermes` (OpenCode Free `oc/*`, round-robin). Grafana/Prometheus starts `omni-exporter` with OmniRouter. |
| `first-setup-omnirouter.sh` | Thin wrapper around the Python script |
