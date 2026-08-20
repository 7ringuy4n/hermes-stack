# 02b — Commands (workers runtime)

> **Prefer the combined page:** [02-components-and-commands.md](./02-components-and-commands.md) (components + commands).

All commands go through the repo root:

```bash
cd /opt/assistant
bash run.sh <command> [args…]
```

Set secrets in `.env` **before** `up`. On a clean host, copy `.env.example` to `.env`, fill every `CHANGE_ME_*`, then activate only the workers you need.

---

## Quick matrix

| Command | Availability | What it does |
|---|---|---|
| `up` / `down` / `ps` / `logs` | all installs | Compose lifecycle |
| `destroy` | all installs | Backup+verify, then remove this project's containers + networks (volumes/data kept) |
| `update` | all installs | Backup+verify, rebuild stack, refresh router bootstrap, prune disk |
| `workers` / `profile` | all installs | Show worker activation + core flags |
| `add-components KEY=VAL…` | all installs | Backup+verify, update worker / component flags, then `up` |
| `switch-profile <…>` | removed | Fails fast with a worker hint |
| `backup` / `restore` / `verify` / `migrate` | all installs | DR stamp lifecycle |
| `auto-learn` / `learn-status` | all installs | Knowledge ingest status / one-shot run |
| `compact` / `optimize-memory` | Media\|File worker | Memory housekeeping |
| `check-media` | Media\|File worker | Dispatcher / OCR / Jobs / SearXNG smoke |
| `check-security` | Security / Monitor / OpenBao components | Security stack smoke |
| `install-timers` | all installs | systemd timers: auto-learn, backup, stack-watch, and worker-specific extras |
| `backup-sync-clouddrive` | when `ENABLE_CLOUDDRIVE=1` | Copy latest stamp to CloudDrive mirror |
| `channel-status` | all installs | Show attached social-app flags |

---

## First setup (clean OS)

```bash
git clone <your-repo-url> /opt/assistant
cd /opt/assistant
cp .env.example .env
python3 scripts/temp/generate_env_secrets.py --out .env --force   # optional local helper
# edit .env: replace remaining values, choose WORKER_*=active as needed
sudo bash scripts/main/install-docker.sh   # if Docker is missing
bash run.sh up
bash run.sh first-setup-omnirouter
```

For Zalo:

```bash
# .env:
# WORKER_MESSAGE=active
# ENABLE_ZALO=1
bash run.sh up
bash scripts/main/setup-zalo.sh
bash scripts/main/login-zalo.sh   # manual QR step
```

`first-setup-llm` is **optional** and only used when `ENABLE_9ROUTER=1`.

---

## Stack lifecycle

```bash
bash run.sh up
bash run.sh down
bash run.sh destroy
bash run.sh ps
bash run.sh logs [service]
bash run.sh workers
bash run.sh add-components WORKER_MEDIA_FILE=active WORKER_SCHEDULE=active
bash run.sh update
```

Full recreate:

```bash
bash run.sh destroy
bash run.sh up
```

Typical source update on a deployed host:

```bash
cd /opt/assistant
git pull
bash run.sh update
```

---

## Worker changes

Optional workers are off by default:

```env
WORKER_SCHEDULE=inactive
WORKER_MEDIA_FILE=inactive
WORKER_SECURITY=inactive
WORKER_NOTIFY=inactive
WORKER_MESSAGE=inactive
WORKER_MONITOR=inactive
```

Turn them on with `.env` edits or `add-components`:

```bash
bash run.sh add-components WORKER_MEDIA_FILE=active
bash run.sh add-components WORKER_SCHEDULE=active WORKER_MESSAGE=active ENABLE_ZALO=1
bash run.sh add-components WORKER_SECURITY=active WORKER_MONITOR=active
```

Every worker change runs **backup + verify first** and aborts on failure.

---

## Backup / restore / migrate

Stamps land in `BACKUP_DIR` (default **`/data/assistant/backups`**).

```bash
bash run.sh backup
bash run.sh verify
bash run.sh verify 20260815_003000
bash run.sh restore
bash run.sh restore 20260815_003000
bash run.sh migrate
```

CloudDrive mirror is separate and optional:

```bash
bash run.sh backup-sync-clouddrive   # only when ENABLE_CLOUDDRIVE=1
```

Stamps include `config/env.sealed` (full `.env`) and `config/profile-options.env` (non-secret runtime flags).

---

## Knowledge + maintenance

```bash
bash run.sh auto-learn
bash run.sh learn-status
```

`compact` / `optimize-memory` require the Media\|File worker path (`ENABLE_MEDIA_FILE=1` or bundled OCR / Jobs flags).

```bash
bash run.sh compact
bash run.sh optimize-memory
bash run.sh check-media
```

Security / monitor checks:

```bash
bash run.sh check-security
```

---

## Timers

```bash
sudo bash run.sh install-timers
```

Installed timers depend on enabled components:

| Timer | When |
|---|---|
| `assistant-auto-learn.timer` | all installs |
| `assistant-backup.timer` | all installs |
| `assistant-stack-watch.timer` | all installs |
| `assistant-compact.timer` | when Media\|File worker is enabled |
| `assistant-zalo-watch.timer` | when `ENABLE_ZALO=1` |

---

## See also

- [02-components-and-commands.md](./02-components-and-commands.md) — components + commands  
- [00-workers.md](./00-workers.md)  
- [config/DEFAULTS.md](./config/DEFAULTS.md)  
- [architect/backup-restore/README.md](../architect/backup-restore/README.md)
