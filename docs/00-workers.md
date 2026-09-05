# Workers

Optional workers are **inactive** until you install them. They are **not** in `.env.example` — use `bash run.sh install`.

Core (always on): Hermes, memory/session/workflow, PostgreSQL, Valkey,
Qdrant, embedding, ingest, Model Router, OmniRoute, attribution, Traefik local,
API Gateway, and watchdog.

Runtime data stays on the host (`ASSISTANT_DATA_DIR`, default `/data/assistant`).

Optional workers use **compose-scoped container names** (no global `container_name`). `bash run.sh install …` removes legacy fixed-name orphans (e.g. old `searxng`) before `up`.

| Worker | `run.sh install` | What starts |
|--------|------------------|-------------|
| **Schedule** | `schedule` | Schedule worker (Postgres via `DATABASE_URL`; SQLite only if DSN unset) |
| **Media** | `media` | Dispatcher, Jobs, jobs-worker, and SearXNG (bundled) |
| **Security** | `security` | security-manager, authz, SIEM, policy-center + OpenBao |
| **OpenBao only** | `openbao` | Same as `security` + `ENABLE_OPENBAO=active` |
| **Notification** | `notify` | notify + alert-watch (does **not** start Security core) |
| **Message / Zalo** | `message` or `zalo` | zalo-proxy + zalo-api (+ Telegram when configured) |
| **Monitor** | `monitor` | Grafana, Prometheus, Loki, Alloy (bundled) |

Attachable extras (also via `install`):

| Name | Command | Notes |
|------|---------|-------|
| Jobs / SearXNG | `jobs`, `searxng` | Usually covered by `install media` |
| Grafana / Prometheus / Loki | `grafana`, `prometheus`, `loki`, `alloy` | Usually covered by `install monitor` |
| Antivirus | `antivirus` | ClamAV + av-gateway profile |
| CloudDrive mirror | `clouddrive` | Backup sync to rclone remote |
| OpenVPN | `openvpn` | Edge overlay |
| Traefik / Gateway | `traefik`, `gateway` | Core defaults on; use to re-enable after `uninstall` |

## First setup (clean OS)

Set the **host OS timezone** before first `up` so schedules and logs match wall clock (containers also read `TZ` from `.env`, default `Asia/Ho_Chi_Minh`):

```bash
sudo timedatectl set-timezone Asia/Ho_Chi_Minh   # or your region
timedatectl status                               # confirm
```

```bash
cp .env.example .env
python3 scripts/temp/generate_env_secrets.py --out .env --force   # optional
sudo bash scripts/main/install-docker.sh                          # if Docker missing

bash run.sh up                         # core only — all workers still inactive
bash run.sh workers                    # confirm inactive

# Install what you need (each runs backup+verify, writes .env, then up):
bash run.sh install schedule
bash run.sh install media
bash run.sh install security           # or: bash run.sh install openbao
bash run.sh install notify
bash run.sh install message            # Zalo
bash run.sh install monitor

# Or several at once:
bash run.sh install schedule media security notify message monitor

bash run.sh install list               # full name catalog
bash run.sh workers                    # confirm active
```

### Zalo (Message worker)

```bash
bash scripts/main/setup-zalo.sh        # QR first → then bridge + zalo-api (deploy user, not sudo)
bash scripts/main/login-zalo.sh        # re-login only when stack already installed
```

## Traefik modes

| Mode | Behavior |
|------|----------|
| `TRAEFIK_MODE=local` (**default**) | HTTP on `127.0.0.1:8080` only (VPN / SSH tunnel) |
| `TRAEFIK_MODE=public` | Prefer ACME when email+domain set; otherwise **fail-soft to local** |

When `HERMES_REPLICAS>1`, host ports `:29119` / `:28642` are not published — use Traefik (`8080`) and/or API Gateway (`8088`).

Grafana pairs with Prometheus. Loki pairs with Alloy. Extra usage: [HARDWARE.md](./HARDWARE.md).

## Change workers later

Every install/uninstall **backs up and verifies** first. On failure the change is aborted.

```bash
bash run.sh install media schedule
bash run.sh uninstall zalo
bash run.sh uninstall traefik          # turn Traefik off (not add-components ENABLE_TRAEFIK=inactive)
bash run.sh uninstall gateway          # turn API Gateway off
bash run.sh install traefik            # turn back on
```

Runtime/core flags (OmniRoute and inbound queue) — use `add-components` then
**`update`** on a running host. The `OMNIROUTER_*` spelling is retained for
compatibility and does not represent a second router:

```bash
bash run.sh add-components ENABLE_OMNIROUTER=active --update
bash run.sh add-components ZALO_INBOUND_QUEUE=0 --update
```

First deploy only: `bash run.sh up` after editing `.env` secrets (before any workers installed).

Advanced: raw `add-components KEY=VAL` without `--update` still runs `up` (fine for first boot).

Overlays: `docker/docker-compose.media.yml`, `docker/docker-compose.security.yml`, `docker/docker-compose.edge.yml`.

When `notify` alone is active, only `notify` / `alert-watch` start from the security overlay. OpenBao, authz, SIEM, and policy-center require `install security` or `install openbao`.
