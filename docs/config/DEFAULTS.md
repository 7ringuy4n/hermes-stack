# Platform defaults (non-secret)

The checked-in `.env.example` documents supported settings. Every non-placeholder
credential-shaped value (`*_API_KEY`, `*_TOKEN`, `*_PASSWORD`, `*_SECRET`, and
equivalents) is discovered during setup, merged into OpenBao, and scrubbed from
`.env` after import. The one bootstrap
exception is generated in a mode-600 external token file because OpenBao cannot
contain the only credential required to unlock itself.

After first setup, the terminal prints the root-only access command for that
bootstrap file. The default is `sudo cat /data/assistant/openbao/root-token`;
do not paste its output into reports or chat.

## Paths and locale

```env
STACK_ROOT=/opt/assistant
ASSISTANT_DATA_DIR=/data/assistant
HERMES_DATA_DIR=/data/assistant
SKILLS_DIR=/data/assistant/skills
CLOUDDRIVE_MIRROR_DIR=/data/clouddrive
BACKUP_DIR=/data/assistant/backups
TZ=Asia/Ho_Chi_Minh
DEPLOY_MODE=local
```

## Core

The core compose graph contains PostgreSQL, Valkey, Qdrant, memory, session,
workflow, embedding, ingest, model-router, OmniRoute, omni-attribution, Hermes,
Traefik, and API Gateway. Backup/restore is a host lifecycle responsibility.

```env
ENABLE_MODEL_ROUTER=active
ENABLE_OMNIROUTER=active
OMNIROUTER_DEFAULT_COMBO=hermes
OMNIROUTER_CLASSIFY_COMBO=classifier
HERMES_DEFAULT_MODEL=hermes
IMAGE_GEN_COMBO=image-gen
VISION_OCR_COMBO=vision-ocr
EMBEDDING_MODEL=embedding
HERMES_REPLICAS=1
VALKEY_URL=redis://valkey:6379/0
ENABLE_TRAEFIK=active
ENABLE_API_GATEWAY=active
TRAEFIK_MODE=local
```

`OMNIROUTER_*` is retained as an environment compatibility namespace for
OmniRoute. `ADMIN_API_TOKEN`, `ENABLE_9ROUTER`, OCR-engine keys, ComfyUI keys,
video combo keys, and direct image-vendor pins are retired.

## Optional workers

Optional workers are enabled with `run.sh`; do not recreate tier profiles.

| Worker | Command | Services/capability |
|---|---|---|
| Schedule | `bash run.sh install schedule` | schedule-worker and timed delivery |
| Media/File | `bash run.sh install media` | dispatcher, jobs, jobs-worker, SearXNG |
| Security | `bash run.sh install security` | OpenBao and policy/security services |
| Notification | `bash run.sh install notify` | notify and alert watcher |
| Message | `bash run.sh install message` | Zalo proxy/API and optional channels |
| Monitoring | `bash run.sh install monitor` | Prometheus, Grafana, Loki, Alloy |

Use `bash run.sh workers` to inspect the effective state. Worker flags are
maintained by `architect/backup-restore/lib/workers.sh`.

## Secret lifecycle

1. Copy `.env.example` to `.env` and supply only required bootstrap values.
2. Run `bash run.sh up`.
3. Import/store provider and service secrets in OpenBao.
4. Scrub plaintext/retired keys from root and `/data/assistant/.env`.
5. Back up and verify OpenBao plus OmniRoute before lifecycle mutations.

Zalo uses only `ZALO_API_TOKEN`. Tests receive a Zalo identity through
`ZALO_TEST_USER_ID`; a numeric personal identity must not be committed.

## First installation

```bash
cp .env.example .env
bash run.sh up
bash run.sh install schedule media security notify message monitor
bash run.sh first-setup-omnirouter
bash scripts/main/setup-zalo.sh
```

`first-setup-omnirouter` is setup-only: it must not generate media or inject
test messages, and it must preserve current AI Box/provider combo membership.
Run verification separately using [test/RULES.md](../../test/RULES.md).

## Edge defaults

Traefik and API Gateway are enabled in local/VPN mode. Public exposure is
opt-in and requires the firewall/TLS controls in
[05-edge-networking.md](../05-edge-networking.md). Database, queue, vector,
secret, Docker, and router administration endpoints must not be public.
