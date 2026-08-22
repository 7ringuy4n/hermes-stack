# 02b — Commands (workers runtime)

> **Prefer the combined page:** [02-components-and-commands.md](./02-components-and-commands.md) (components + commands).

All commands go through the repo root:

```bash
cd /opt/assistant
bash run.sh <command> [args…]
```

Set secrets in `.env` **before** `up`. Optional workers are **not** in `.env.example` — install them after core `up`.

---

## Quick matrix

| Command | Availability | What it does |
|---|---|---|
| `up` / `down` / `ps` / `logs` | all installs | Compose lifecycle |
| `destroy` | all installs | Backup+verify, then remove this project's containers + networks (volumes/data kept) |
| `update` | all installs | Backup+verify, rebuild stack, refresh router bootstrap, prune disk |
| `workers` / `profile` | all installs | Show worker activation + core flags |
| `install NAME…` | all installs | Short name → `.env` (backup+verify, then `up`) |
| `uninstall NAME…` | all installs | Deactivate by short name |
| `install list` | all installs | Show install name catalog |
| `add-components KEY=VAL…` | all installs | Backup+verify, write `.env`, then `up` (or `--update` on running host) |
| `switch-profile <…>` | removed | Fails fast with a worker hint |
| `backup` / `restore` / `verify` / `migrate` | all installs | DR stamp lifecycle |
| `auto-learn` / `learn-status` | all installs | Knowledge ingest status / one-shot run |
| `compact` / `optimize-memory` | Media\|File worker | Memory housekeeping |
| `check-media` | Media\|File worker | Dispatcher / OCR / Jobs / SearXNG smoke |
| `check-security` | Security / Monitor / OpenBao components | Security stack smoke |
| `install-timers` | all installs | systemd timers: auto-learn, backup, stack-watch, and worker-specific extras |
| `backup-sync-clouddrive` | when CloudDrive installed | Copy latest stamp to CloudDrive mirror |
| `channel-status` | all installs | Show attached social-app flags |

---

## First setup (clean OS)

```bash
git clone <your-repo-url> /opt/assistant
cd /opt/assistant
cp .env.example .env
python3 scripts/temp/generate_env_secrets.py --out .env --force   # optional local helper
sudo bash scripts/main/install-docker.sh   # if Docker is missing

bash run.sh up                             # core stack; workers still inactive
bash run.sh first-setup-omnirouter         # runs on up when Omni enabled; safe to re-run

# Install optional workers (see docs/00-workers.md):
bash run.sh install schedule media security notify message monitor
bash run.sh install list                   # all short names
bash run.sh workers                        # confirm activation
```

For Zalo:

```bash
bash scripts/main/setup-zalo.sh            # QR first, then zalo-api + adapter (not sudo)
bash scripts/main/login-zalo.sh            # re-login when stack already up
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
bash run.sh install media schedule
bash run.sh update
```

Full recreate:

```bash
bash run.sh destroy
bash run.sh up
bash run.sh install schedule media    # re-add workers you need
```

Typical source update on a deployed host:

```bash
cd /opt/assistant
git pull
bash run.sh update
```

---

## Worker changes

Workers are off until installed. Do **not** hand-edit `WORKER_*` in `.env.example` (those keys are not in the template).

```bash
bash run.sh install media
bash run.sh install schedule message zalo
bash run.sh install security monitor openbao
bash run.sh uninstall zalo
bash run.sh uninstall traefik
bash run.sh uninstall gateway
```

Runtime flags on a **running** host — `add-components` + **`--update`** (not plain `up`):

```bash
bash run.sh add-components ZALO_INBOUND_QUEUE=0 --update
bash run.sh add-components ENABLE_9ROUTER=1 --update
bash run.sh add-components ENABLE_QWEN=1 OLLAMA_BASE_URL=http://host.docker.internal:11434 OLLAMA_MODEL=qwen3:4b --update
```

Do **not** disable edge with raw flags:

```bash
# wrong — blocked by run.sh
bash run.sh add-components ENABLE_TRAEFIK=0
bash run.sh add-components ENABLE_API_GATEWAY=0
```

Every worker install/uninstall and every `add-components`/`remove-components` run **backup + verify first** and abort on failure.

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
bash run.sh install clouddrive
bash run.sh backup-sync-clouddrive
```

Stamps include `config/env.sealed` (full `.env`) and `config/profile-options.env` (non-secret runtime flags).

---

## Knowledge + maintenance

```bash
bash run.sh auto-learn
bash run.sh learn-status
```

`compact` / `optimize-memory` require the Media\|File worker (`bash run.sh install media`).

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
| `assistant-zalo-watch.timer` | when Zalo/Message worker is enabled |

---

## See also

- [02-components-and-commands.md](./02-components-and-commands.md) — components + commands  
- [00-workers.md](./00-workers.md)  
- [config/DEFAULTS.md](./config/DEFAULTS.md)  
- [architect/backup-restore/README.md](../architect/backup-restore/README.md)
