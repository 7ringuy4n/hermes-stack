# 02 — Components & commands

**Before anything else:** copy `.env.example` → `.env` and set every `CHANGE_ME` secret.

```bash
cd /opt/assistant
bash run.sh <command>
```

**Runtime:** Optional workers use `bash run.sh install <name>` (not keys in `.env.example`). See [00-workers.md](./00-workers.md), [config/DEFAULTS.md](./config/DEFAULTS.md), and [02-commands.md](./02-commands.md).

---

## Overview

| Item | Detail |
|------|--------|
| **Product** | Hermes Agent + Memory. Social apps (Zalo / Telegram / HTTP) are optional. |
| **Knob** | Optional workers via `bash run.sh install …` (`WORKER_*=active\|inactive`) |
| **Core** | Always on — Hermes, memory, router-worker, Omni, Traefik local, API Gateway, Valkey |
| **Auto-learn** | 00:00 → Qdrant (no approve). **Not** the same as compact. |
| **Compact** | 00:00 when **Media** worker is active — slim skills / memory |
| **Backups** | `/data/assistant/backups` · optional CloudDrive (`install clouddrive`) |

Legacy `ASSISTANT_PROFILE=low|medium|high` and `switch-profile` are removed — see [00-profiles.md](./00-profiles.md).

---

## Components by worker

| Area | Core | schedule | media | security / openbao | notify | monitor | message / zalo |
|------|:----:|:--------:|:-----:|:------------------:|:------:|:-------:|:---------------:|
| Hermes + Memory + router-worker | Yes | — | — | — | — | — | — |
| OmniRouter (default LLM) | Yes | — | — | — | — | — | — |
| 9Router | Opt (`ENABLE_9ROUTER=1`) | — | — | — | — | — | — |
| Traefik local / API Gateway | Yes | — | — | — | — | — | — |
| schedule-worker | — | Yes | — | — | — | — | — |
| Dispatcher / OCR / Jobs / SearXNG / Comfy / office | — | — | Yes | — | — | — | — |
| OpenBao / authz / SIEM / policy | — | — | — | Yes | — | — | — |
| Antivirus (ClamAV) | — | — | — | Opt (`antivirus`) | — | — | — |
| notify + alert-watch | — | — | — | — | Yes | — | — |
| Grafana / Prometheus / Loki / Alloy | — | — | — | — | — | Yes | — |
| zalo-proxy + zalo-api | — | — | — | — | — | — | Yes |
| CloudDrive mirror | — | — | — | — | — | — | Opt (`clouddrive`) |
| OpenVPN | — | — | — | — | — | — | Opt (`openvpn`) |

Full name catalog: `bash run.sh install list`.

---

## Commands (quick matrix)

| Command | What it does |
|---|---|
| `up` / `down` / `ps` / `logs` | Compose lifecycle |
| `destroy` | Backup+verify, then remove this project's containers + networks (volumes/data kept) |
| `update` | Backup+verify, rebuild stack, refresh router bootstrap, prune disk |
| `workers` / `profile` | Show worker activation + core flags |
| `install NAME…` | Short name → `.env` (backup+verify, then `up`) |
| `uninstall NAME…` | Deactivate by short name |
| `install list` | Show install name catalog |
| `add-components KEY=VAL…` | Write `.env`, then `up` (or `--update` on running host) |
| `switch-profile <…>` | Removed — fails with a worker hint |
| `backup` / `restore` / `verify` / `migrate` | DR stamp lifecycle |
| `auto-learn` / `learn-status` | Knowledge ingest |
| `compact` / `optimize-memory` | Memory housekeeping (**media** worker) |
| `check-media` | Dispatcher / OCR / Jobs / SearXNG smoke (**media**) |
| `check-security` | Security stack smoke |
| `install-timers` | systemd timers |
| `backup-sync-clouddrive` | When CloudDrive installed |
| `channel-status` | Social-app flags |
| `first-setup-omnirouter` | Omni combo wiring (safe re-run) |
| `first-setup-llm` | Only when `ENABLE_9ROUTER=1` |
| `first-setup-openbao` / `load-openbao-env` | OpenBao seed + env load |

Detail: [02-commands.md](./02-commands.md).

---

## Worker quick examples

### Core only

```bash
bash run.sh up
bash run.sh backup && bash run.sh verify
bash run.sh auto-learn
sudo bash run.sh install-timers
```

### Typical production set

```bash
bash run.sh install schedule media security notify message monitor
bash run.sh workers
bash run.sh check-media
bash run.sh check-security
```

### Media only

```bash
bash run.sh install media
bash run.sh check-media
```

### Runtime flags on a live host

```bash
bash run.sh add-components ENABLE_9ROUTER=1 --update
bash run.sh add-components ZALO_INBOUND_QUEUE=0 --update
```

Prefer `install` / `uninstall` for workers; use `add-components … --update` for core router / queue flags.

---

## I want to… → command

| Goal | Command |
|------|---------|
| Start / stop stack | `up` / `down` / `ps` / `logs` |
| Wipe containers + networks (keep data) | `destroy` then `up` |
| Save / recover / move server | `backup` → `verify` → `restore` or `migrate` |
| Index documents into knowledge | `auto-learn` (+ `learn-status`) |
| Tidy memory (media worker) | `compact` or `optimize-memory` |
| Schedule midnight jobs | `sudo bash run.sh install-timers` |
| Sync backup to Drive | `install clouddrive` then `backup-sync-clouddrive` |
| Attach Zalo | `install message` then `bash scripts/main/setup-zalo.sh` |
| See worker state | `bash run.sh workers` |

---

## Paths

| Role | Path |
|------|------|
| Code (VPS) | `/opt/assistant` |
| Code (dev) | this clone (e.g. `D:\Onedrive\Work\hermes-stack`) |
| Live data | `/data/assistant` |
| Backups | `/data/assistant/backups` |
| CloudDrive mirror | `/data/clouddrive` |

---

## Related

- [00-workers.md](./00-workers.md) — install catalog  
- [00-profiles.md](./00-profiles.md) — legacy profile note  
- [02-commands.md](./02-commands.md) — commands-only detail  
- [architect/README.md](../architect/README.md) · [hermes/README.md](../hermes/README.md)
