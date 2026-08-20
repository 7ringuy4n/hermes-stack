# Docker Compose layouts (project root = repo root)

Compose YAML lives here so the repo root stays clean. **`run.sh` always passes
`--project-directory <repo-root>`**, so volume paths like `./architect/...` and
`./config/...` still resolve from the repository root.

| File | Role |
|------|------|
| `docker-compose.yml` | Core + optional profiles (schedule, zalo, omnirouter, 9router, …) |
| `docker-compose.media.yml` | Media\|File Worker overlay (dispatcher, OCR, Jobs, Comfy CPU) |
| `docker-compose.security.yml` | Security / Notify / Monitor overlay |
| `docker-compose.edge.yml` | Traefik / API Gateway / OpenVPN |
| `docker-compose.hermes-hostports.yml` | Host `:28642` / `:29119` when `HERMES_REPLICAS=1` |
| `docker-compose.medium.yml` / `docker-compose.high.yml` | Legacy overlays (prefer workers + media/security) |

## Compose profiles (components)

| Profile | Enable via |
|---------|------------|
| `schedule` | `WORKER_SCHEDULE=active` / `ENABLE_SCHEDULE=1` |
| `media` | `WORKER_MEDIA_FILE=active` |
| `zalo` | `ENABLE_ZALO=1` (Message worker) — **both** `zalo-proxy` and `zalo-api` |
| `omnirouter` | `ENABLE_OMNIROUTER=1` (**default**) |
| `9router` | `ENABLE_9ROUTER=1` (**optional**, off by default) |
| `notify` | `WORKER_NOTIFY=active` / `ENABLE_NOTIFY=1` |
| `grafana` / `prometheus` / `loki` / `alloy` | Monitor worker / matching `ENABLE_*` |
| `traefik` / `gateway` / `openvpn` | `ENABLE_TRAEFIK` / `ENABLE_API_GATEWAY` / `ENABLE_OPENVPN` |

Example — Schedule + Media|File + Notify + Message:

```bash
# In .env:
# WORKER_SCHEDULE=active
# WORKER_MEDIA_FILE=active
# WORKER_NOTIFY=active
# WORKER_MESSAGE=active
# ENABLE_ZALO=1
# ENABLE_OMNIROUTER=1
# ENABLE_9ROUTER=0
bash run.sh up
```

Sizing: [docs/HARDWARE.md](../docs/HARDWARE.md). Workers: [docs/00-workers.md](../docs/00-workers.md). DR: [architect/backup-restore/README.md](../architect/backup-restore/README.md).
