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

postgres, Valkey (container service name often still `redis`), qdrant, memory, session, embedding, ingest, dispatcher, 9router, hermes, backup/restore.

> **LTM:** Memory Manager + Postgres only.
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
ZALO_API_TOKEN=
# ADMIN_API_TOKEN=   # legacy alias for zalo-api
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
ENABLE_ZALO=0
GATEWAY_API_KEYS=
GATEWAY_REQUIRE_AUTH=1
GATEWAY_TRUST_FORWARDED=0
GATEWAY_RL_FAIL_CLOSED=1
SECURITY_YARA=1
SECURITY_SANDBOX=0
SECURITY_LLM_JUDGE=0
ENABLE_LLM_JUDGE=0
SECURITY_FAIL_CLOSED=0
ENABLE_TELEGRAM=0
ENABLE_TRAEFIK=0
ENABLE_API_GATEWAY=0
ENABLE_OPENVPN=0
ENABLE_WHATSAPP=0
```

Zalo home channel (when `ENABLE_ZALO=1`):

```bash
# Empty = silent auto-sethome from first allowed DM (stops Hermes /sethome spam)
ZALO_HOME_CHANNEL=
ZALO_AUTO_SETHOME=1
ZALO_AUTO_SETHOME_DM_ONLY=1
```

| Profile | Optional on |
|---|---|
| low | none by default; **Traefik/API Gateway forced off** |
| medium | OCR, SearXNG, Jobs, office file-gen, web backends + compact; **Traefik + API Gateway default ON**; **HERMES_REPLICAS=2**; OpenVPN opt-in |
| high | Medium + OpenBao UI, security-manager (YARA), SIEM, authz, policy, monitor; AV/sandbox/LLM judge **off** unless opted in; zalo-api with Zalo; notify opt-in; CloudDrive; **Traefik + API Gateway default ON** (`TRAEFIK_MODE=local`); **HERMES_REPLICAS=2**; OpenVPN opt-in |

High overlay: `docker-compose.high.yml`. Edge overlay: `docker-compose.edge.yml` when `ENABLE_TRAEFIK` / `ENABLE_API_GATEWAY` / `ENABLE_OPENVPN` is `1`. Smoke: `bash run.sh check-high`. Seed keys: `bash run.sh first-setup-openbao`.

## Edge (VPN/LAN — default)

| Flag | Role |
|------|------|
| `ENABLE_TRAEFIK` | Traefik LB → Hermes (**default 1 on medium/high**, forced 0 on low) |
| `TRAEFIK_MODE` | **`local`** (VPN/localhost). `public` is opt-in and still fail-softs without ACME email/domain |
| `TRAEFIK_ACME_ENABLED` | Let's Encrypt TLS on Traefik (needs public 80/443 for HTTP-01; default **0**) |
| `ENABLE_API_GATEWAY` | HTTP entry + Valkey global rate limit (**default 1 on medium/high**, forced 0 on low; coding paths skip RL) |
| `ENABLE_OPENVPN` | Private admin VPN stub (init PKI before use; default **0**) |

Details: [docs/05-edge-networking.md](../05-edge-networking.md). Snippet: [edge.env.snippet](./edge.env.snippet).

**Zalo** never goes through the API Gateway (local bridge only).

## Hermes replicas

```env
# Low: forced 1. Medium/High: default 2 (override in .env).
# HERMES_REPLICAS=2
```

When `HERMES_REPLICAS>1`, host ports `:28642`/`:29119` are **not** published (avoid bind clash). Reach Hermes via Traefik (`:8080`) or API Gateway (`:8088`). Low (`replicas=1`) still publishes localhost gateway/dashboard ports.
