# scripts/main — product ops

Committed with the repo. Invoked by `run.sh` and first-setup docs.

| Script | Role |
|---|---|
| `install-docker.sh` | Official Docker CE; adds **current SSH login user** (`SUDO_USER`) to `docker` group |
| `install-component.sh` | Resolve `run.sh install` / `uninstall` short names → `WORKER_*` / `ENABLE_*` |
| `first-setup-omnirouter.py` | **Default** — OmniRoute key + chat combo `hermes` + classify combo `classifier` |
| `first-setup-omnirouter.sh` | Thin wrapper |
| `first-setup-9router-hermes.py` | Optional — only when `ENABLE_9ROUTER=1` |
| `first-setup-9router-hermes.sh` | Thin wrapper |
| `first-setup-openbao.py` | Seed OpenBao KV when Security/OpenBao worker is active |
| `setup-zalo.sh` | Install Zalo bridge + adapter after core ready |
| `login-zalo.sh` | Manual QR login (last step) |
| `zalo-common.sh` / `zalo-watch.sh` | Shared Zalo ops + host watch |
| `heal-zalo-sse.sh` | Clear owner lock; restart zalo-proxy + Hermes replicas |
| `backup-zalo-session.sh` / `restore-zalo-session.sh` | Preserve / restore Zalo session between labs |
| `seed-zalo-admin-from-postgres.sh` | Lab/post-restore admin seed helper |
| `patch_zalo_bridge_inject.py` | Bridge inject + media proxy (heal / zalo-watch / setup) |
| `zalo-bridge/` | Durable host bridge overlays (`zaloClient.js`, `markdownToZalo.js`) installed by `zalo-common.sh` |
| `patch-hermes-model-router.py` | Hermes→router wiring used by setup / first-setup |
| `stack-watch.sh` | Health / auto-heal timer |
| `log-archive.sh` | Log retention timer target |
| `check-media.sh` / `check-security.sh` | Smoke checks (`run.sh check-*`) |
| `post-lab-restore.sh` | Post-lab Zalo session + Omni combo + chat smoke |
| `hermes-cron-share.sh` | Shared cron helper for backup/learn timers |
| `post-ready-learn.py` | One-shot learn after stack ready |
| `render-traefik-acme.sh` | Traefik ACME render helper |
| `export-ovpn-client.sh` | Export OpenVPN client profile when OpenVPN worker on |
| `Apply-EdgeUpdate.ps1` | Windows helper to push edge updates to a remote host |

Workers: see `docs/00-workers.md` and `bash run.sh workers`.
