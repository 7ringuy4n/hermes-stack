# Workers

Optional workers are **inactive** by default. Core (Hermes, Memory, Router Worker, Traefik local, API Gateway, Valkey queue, watchdog) is always on.

Runtime data stays on the host (`ASSISTANT_DATA_DIR`, default `/data/assistant`).

| Worker | Intent |
|--------|--------|
| **Schedule** | Timed runs (Go SQLite clock). Not the async compound-job runner. |
| **Media\|File** | Dispatcher (search/image/office), OCR, Jobs, Comfy CPU |
| **Security** | AV / judge / sandbox / YARA overlay |
| **Notification** | SMS / email / Zalo notify channel |
| **Message** | Zalo (proxy + zalo-api), Telegram, Lark |
| **Monitor** | Grafana / Loki / Prometheus |

```bash
# Activate workers in .env, then:
bash run.sh up
```

```env
WORKER_SCHEDULE=inactive
WORKER_MEDIA_FILE=inactive
WORKER_SECURITY=inactive
WORKER_NOTIFY=inactive
WORKER_MESSAGE=inactive
WORKER_MONITOR=inactive
```

## Traefik modes

| Mode | Behavior |
|------|----------|
| `TRAEFIK_MODE=local` (**default**) | HTTP on `127.0.0.1:8080` only (VPN / SSH tunnel) |
| `TRAEFIK_MODE=public` | Prefer ACME when email+domain set; otherwise **fail-soft to local** |

When `HERMES_REPLICAS>1`, host ports `:29119` / `:28642` are not published — use Traefik (`8080`) and/or API Gateway (`8088`).

Grafana pairs with Prometheus. Loki pairs with Alloy. Extra usage: [HARDWARE.md](./HARDWARE.md).

## Change workers

Activating or deactivating workers **backs up and verifies** first. If backup or verify fails, the change is aborted.

```bash
bash run.sh add-components WORKER_MEDIA_FILE=active WORKER_SCHEDULE=active
```

Overlays: `docker/docker-compose.media.yml` (media/file), `docker/docker-compose.security.yml` (security/notify/monitor), `docker/docker-compose.edge.yml` (Traefik / API Gateway / OpenVPN).
