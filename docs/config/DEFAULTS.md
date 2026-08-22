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

Optional workers are **not** in `.env.example`. Defaults (all inactive) come from `architect/backup-restore/lib/workers.sh` until you run:

```bash
bash run.sh install schedule | media | security | notify | message | monitor
bash run.sh install list
```

Worker-bundled flags when active:

| Worker | Install name | Bundled defaults when active |
|--------|--------------|------------------------------|
| Schedule | `schedule` | `SCHEDULE_URL=http://schedule-worker:8110`, `SCHEDULE_WORKER=1` |
| Media\|File | `media` | dispatcher, OCR, Jobs, office file-gen, Comfy CPU, web search top-3 |
| Security | `security` / `openbao` | security-manager overlay, OpenBao, authz, SIEM, policy |
| Notification | `notify` | notify + alert-watch |
| Message | `message` / `zalo` | zalo-proxy + zalo-api (and Telegram when enabled) |
| Monitor | `monitor` | Grafana, Prometheus, Loki, Alloy |

## First setup (clean OS)

1. `sudo bash scripts/main/install-docker.sh` if Docker is missing (or `bash run.sh install-docker`).
2. Install fail2ban on public VPS before opening SSH widely.
3. `cp .env.example .env` then fill `CHANGE_ME_*` (or `python3 scripts/temp/generate_env_secrets.py --out .env --force`).
4. `bash run.sh up` — core stack only.
5. `bash run.sh install …` — each worker you need ([00-workers.md](../00-workers.md)).
6. OmniRouter wiring runs on `up` when `ENABLE_OMNIROUTER=1`. Re-run: `bash run.sh first-setup-omnirouter`.
7. Zalo: `bash scripts/main/setup-zalo.sh` (QR first, then stack — deploy user, not sudo). Re-login: `login-zalo.sh`.

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

Turn Traefik / Gateway **off** or **on**:

```bash
bash run.sh uninstall traefik
bash run.sh uninstall gateway
bash run.sh install traefik
bash run.sh install gateway
```

Do **not** use `add-components ENABLE_TRAEFIK=0` (blocked by `run.sh`).

## Core flags (`bash run.sh workers` line)

| Shown | Change with | Apply on running host |
|-------|-------------|------------------------|
| `OMNI=1` | `ENABLE_OMNIROUTER=1` in section C | `add-components … --update` |
| `N9=0` | `ENABLE_9ROUTER=1` + `N9ROUTER_INITIAL_PASSWORD` | `add-components … --update` then `first-setup-llm` |
| `REPLICAS=1` | `HERMES_REPLICAS=2` | `add-components HERMES_REPLICAS=2 --update` |
| `QUEUE=1` | `ZALO_INBOUND_QUEUE=0` | `add-components ZALO_INBOUND_QUEUE=0 --update` |

`ROUTER=1` (`ENABLE_MODEL_ROUTER`) should stay on in normal installs.

## Related

- [00-workers.md](../00-workers.md)
- [06-model-routing.md](../06-model-routing.md)
