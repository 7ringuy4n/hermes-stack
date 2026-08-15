# Platform defaults (non-secret)

Copy secrets from `.env.example` → `.env` **first**.  
`architect/backup-restore/lib/profile.sh` sets optional `ENABLE_*` from `ASSISTANT_PROFILE`.

## Host paths

```env
ASSISTANT_PROFILE=low
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

## Must (always on — no ENABLE_* on Low)

postgres, redis (Valkey), qdrant, memory, mem0, session, embedding, ingest, dispatcher, 9router, hermes, backup/restore.

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
N9ROUTER_API_KEY=   # filled by first-setup from 9Router Default Key
```

## Optional (Medium / High / social-app)

```env
ENABLE_OCR=0
ENABLE_SEARXNG=0
ENABLE_JOBS=0
OFFICE_FILE_GEN=0
WEB_BACKENDS=                  # low: forced empty | medium+: tavily,firecrawl (SearXNG fallback in code)
TAVILY_API_KEY=
FIRECRAWL_API_KEY=
SEARXNG_PORT=8888
OCR_PORT=8091
JOBS_PORT=8104

# High — OpenBao is API-key SoT after first-setup-openbao
OPENBAO_DEV_ROOT_TOKEN=
OPENBAO_PORT=8200
GRAFANA_ADMIN_USER=admin
GRAFANA_ADMIN_PASSWORD=
GRAFANA_HOST_PORT=23000
ADMIN_API_TOKEN=
ENABLE_NOTIFY=0                # High default off; set 1 for notify + alert-watch
ENABLE_CLOUDDRIVE=0
CLOUDDRIVE_MIRROR_DIR=/data/clouddrive

ENABLE_GRAFANA=0
ENABLE_LOKI=0
ENABLE_PROMETHEUS=0
ENABLE_ALLOY=0
ENABLE_OPENBAO=0
ENABLE_OPENBAO_AGENT=0
ENABLE_ANTIVIRUS=0
ENABLE_SECURITY=0
ENABLE_SIEM=0
ENABLE_POLICY=0
ENABLE_AUTHZ=0
ENABLE_ADMIN_API=0
ENABLE_ZALO=0
ENABLE_TELEGRAM=0
ENABLE_TRAEFIK=0
ENABLE_OPENVPN=0
ENABLE_WHATSAPP=0
```

| Profile | Optional on |
|---|---|
| low | none (web / OCR / Jobs / file-gen forced off) |
| medium | OCR, SearXNG, Jobs, office file-gen, web backends + compact timer |
| high | Medium + OpenBao UI, AV, security, SIEM, authz, policy, admin-api, monitor; notify opt-in; CloudDrive sync if rclone configured |

High overlay: `docker-compose.high.yml`. Smoke: `bash run.sh check-high`. Seed keys: `bash run.sh first-setup-openbao`.

Traefik and OpenVPN are removed from the product.
