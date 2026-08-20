# Platform defaults (non-secret)

Copy secrets from `.env.example` → `.env` **first** (or `python3 scripts/temp/generate_env_secrets.py`).  
`architect/backup-restore/lib/workers.sh` turns optional workers **active** or **inactive**. Bundled `ENABLE_*` flags live on each worker.

## Host paths

```env
STACK_ROOT=/opt/assistant
ASSISTANT_DATA_DIR=/data/assistant
HERMES_DATA_DIR=/data/assistant
SKILLS_DIR=/data/assistant/skills
CLOUDDRIVE_MIRROR_DIR=/data/clouddrive
BACKUP_DIR=/data/assistant/backups
TZ=Asia/Ho_Chi_Minh
DEPLOY_MODE=local
LEARN_REQUIRE_APPROVE=0
LEARN_LIST_LIMIT=5
```

## Core (always on)

postgres, Valkey (`valkey`), qdrant, memory, session, embedding, ingest, **router-worker (Model Router)**, hermes, backup/restore, Traefik local, API Gateway, inbound Valkey queue.

**OmniRouter** is the default LLM path (`ENABLE_OMNIROUTER=1`). **9Router** is optional (`ENABLE_9ROUTER=0`).

Dispatcher (search / image / office HTTP) belongs to the **Media|File Worker** — it is not core.

> **LTM:** Memory Manager + Postgres only.

## Default setup — optional workers

```env
WORKER_SCHEDULE=inactive
WORKER_MEDIA_FILE=inactive
WORKER_SECURITY=inactive
WORKER_NOTIFY=inactive
WORKER_MESSAGE=inactive
WORKER_MONITOR=inactive
```

Set a worker to `active` (or compatible `ENABLE_*=1`) in host `.env`. Worker-bundled flags:

| Worker | Bundled defaults when active |
|--------|------------------------------|
| Schedule | `SCHEDULE_URL=http://schedule-worker:8110`, `SCHEDULE_WORKER=1` |
| Media\|File | dispatcher, OCR, Jobs, office file-gen, Comfy CPU, web search top-3 |
| Security | security-manager overlay |
| Notification | notify + alert-watch |
| Message | Zalo proxy + zalo-api (and Telegram when enabled) |
| Monitor | Grafana, Prometheus, Loki, Alloy |

## First setup (clean OS)

1. `sudo bash scripts/main/install-docker.sh` if Docker is missing (or `bash run.sh install-docker`).
2. Install fail2ban on public VPS before opening SSH widely.
3. `cp .env.example .env` then fill `CHANGE_ME_*` (or `python3 scripts/temp/generate_env_secrets.py --out .env --force`).
4. Set workers you need (`WORKER_MESSAGE=active` + `ENABLE_ZALO=1` for Zalo, etc.).
5. `bash run.sh up`
6. OmniRouter wiring runs on `up` when `ENABLE_OMNIROUTER=1`. Re-run: `bash run.sh first-setup-omnirouter`.
7. Zalo (Message worker): `bash scripts/main/setup-zalo.sh` then **manual** `bash scripts/main/login-zalo.sh` (QR).

```env
ENABLE_OMNIROUTER=1
ENABLE_9ROUTER=0
OMNIROUTER_DEFAULT_COMBO=hermes
HERMES_DEFAULT_MODEL=hermes
ENABLE_TRAEFIK=1
ENABLE_API_GATEWAY=1
TRAEFIK_MODE=local
HERMES_REPLICAS=1
VALKEY_URL=redis://valkey:6379/0
```

## Edge (VPN/LAN — default)

| Flag | Role |
|------|------|
| `ENABLE_TRAEFIK` | Traefik LB → Hermes (**core default 1**) |
| `TRAEFIK_MODE` | **`local`** (VPN/localhost). `public` is opt-in |
| `TRAEFIK_ACME_ENABLED` | Let's Encrypt (default **0**) |
| `ENABLE_API_GATEWAY` | HTTP entry + Valkey rate limit (**core default 1**) |
| `ENABLE_OPENVPN` | Private admin VPN stub (default **inactive**) |

## Related

- [00-workers.md](../00-workers.md)
- [06-model-routing.md](../06-model-routing.md)
