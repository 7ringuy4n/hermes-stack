# Platform defaults (non-secret)

Copy secrets from `.env.example` → `.env` **first**.  
`architect/backup-restore/lib/workers.sh` turns optional workers **active** or **inactive**. Bundled `ENABLE_*` flags live on each worker, not here.

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

postgres, Valkey (`valkey`), qdrant, memory, session, embedding, ingest, 9router, router-worker, hermes, backup/restore, Traefik local, API Gateway, inbound Valkey queue.

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

Set a worker to `active` (or `ENABLE_*=1`) in host `.env`. Worker-bundled flags:

| Worker | Bundled defaults when active |
|--------|------------------------------|
| Schedule | `SCHEDULE_URL=http://schedule-worker:8110`, `SCHEDULE_WORKER=1` |
| Media\|File | dispatcher, OCR, Jobs, office file-gen, Comfy CPU, `IMAGE_BACKENDS=llm,vendor,comfy-cpu,comfy-gpu` |
| Security | security-manager overlay |
| Notification | notify + alert-watch |
| Message | Zalo proxy + zalo-api (and Telegram when enabled) |
| Monitor | Grafana, Prometheus, Loki, Alloy |

## First setup (host)

1. `sudo bash scripts/main/install-docker.sh` if Docker is missing (uses the SSH login user via `SUDO_USER`; or `bash run.sh install-docker`).
2. `bash run.sh up` (or deploy pack).
3. `python3 scripts/main/first-setup-9router-hermes.py` — copies **Default Key**, builds/updates combo **`hermes`** from all current OpenCode Free (`oc/*`) models, sets combo strategy to **round-robin** (rotate each request), Hermes default model id = `hermes`, then **disk cleanup** (docker builder/image prune + temp files).
4. Optional: add paid providers in 9Router UI later (OpenRouter, DeepSeek, …).

```env
N9ROUTER_DEFAULT_COMBO=hermes
HERMES_DEFAULT_MODEL=hermes
N9ROUTER_COMBO_STRATEGY=round-robin
N9ROUTER_COMBO_STICKY_LIMIT=1
N9ROUTER_API_KEY=
ENABLE_OMNIROUTER=1
ENABLE_TRAEFIK=1
ENABLE_API_GATEWAY=1
TRAEFIK_MODE=local
HERMES_REPLICAS=1
VALKEY_URL=valkey://valkey:6379/0
```

## Edge (VPN/LAN — default)

| Flag | Role |
|------|------|
| `ENABLE_TRAEFIK` | Traefik LB → Hermes (**core default 1**) |
| `TRAEFIK_MODE` | **`local`** (VPN/localhost). `public` is opt-in and still fail-softs without ACME email/domain |
| `TRAEFIK_ACME_ENABLED` | Let's Encrypt TLS on Traefik (needs public 80/443 for HTTP-01; default **0**) |
| `ENABLE_API_GATEWAY` | HTTP entry + Valkey global rate limit (**core default 1**; coding/schedule paths skip RL) |
| `ENABLE_OPENVPN` | Private admin VPN stub (default **inactive**) |

Details: [docs/05-edge-networking.md](../05-edge-networking.md). Snippet: [edge.env.snippet](./edge.env.snippet).

**Zalo** never goes through the API Gateway (local bridge only). Message worker owns Zalo.

```env
ZALO_HOME_CHANNEL=
ZALO_AUTO_SETHOME=1
ZALO_AUTO_SETHOME_DM_ONLY=1
ZALO_INBOUND_QUEUE=1
ZALO_INBOUND_QUEUE_MAX=8
ZALO_INBOUND_QUEUE_TTL_S=3600
```

Compound multi-request jobs use the **workflow** service (async job runner). Timed runs use **Schedule Worker**. Those are different components.

When `HERMES_REPLICAS>1`, host ports `:28642`/`:29119` are **not** published. Reach Hermes via Traefik (`:8080`) or API Gateway (`:8088`).

Sizing: [docs/HARDWARE.md](../HARDWARE.md).

## Connectivity tests

- Always-on **9Router** + default **router-worker**: [test/cases/21-defaults-routers-connected.md](../../test/cases/21-defaults-routers-connected.md)
- When Grafana is on: [test/cases/20-grafana-component-integration.md](../../test/cases/20-grafana-component-integration.md)
- Simple chat must answer in **≤ 5s** on the host unless the delay is free-model failover or quota ([test/cases/17-zalo-latency-slo.md](../../test/cases/17-zalo-latency-slo.md)).
