# 02b — Commands by profile (detail)

> **Prefer the combined page:** [02-components-and-commands.md](./02-components-and-commands.md) (components + commands).

All commands go through the repo root:

```bash
cd /opt/assistant   # or D:\Onedrive\Work\assistant on Windows via Git Bash / WSL
export ASSISTANT_PROFILE=low   # or medium|high
bash run.sh <command> [args…]
```

Set secrets in `.env` **before** `up`. Use `sudo` on the VPS when writing under `/data/assistant` or installing systemd timers.

**Legend:** ✅ available · ⬜ not in this profile (command refuses with a short hint) · ◐ optional if you attach a social-app / override flag

---

## Quick matrix

| Command | Low | Medium | High | What it does |
|---|---|---|---|---|
| `up` / `down` / `ps` / `logs` | ✅ | ✅ | ✅ | Compose lifecycle |
| `destroy` | ✅ | ✅ | ✅ | Remove this project's containers + networks (volumes/data kept) |
| `update` | ✅ | ✅ | ✅ | After `git pull`: rebuild stack, refresh LLM wiring, prune disk |
| `profile` | ✅ | ✅ | ✅ | Show `ASSISTANT_PROFILE` + optional flags |
| `backup` | ✅ | ✅ | ✅ | DR stamp → `/data/assistant/backups` |
| `restore [stamp]` | ✅ | ✅ | ✅ | Restore LATEST or stamp |
| `verify [stamp]` | ✅ | ✅ | ✅ | Check backup manifest + live pings |
| `migrate` | ✅ | ✅ | ✅ | Pack stamp tarball for a new host |
| `auto-learn` | ✅ | ✅ | ✅ | Index eligible docs → Qdrant (**no approve**) |
| `learn-status` | ✅ | ✅ | ✅ | Health + document count hint from ingest |
| `compact` | ⬜ | ✅ | ✅ | Slim skills / memory drafts (silent) |
| `optimize-memory` | ⬜ | ✅ | ✅ | Alias: Mem0/memory compact hooks + Valkey ping |
| `install-timers` | ✅* | ✅† | ✅† | Systemd: auto-learn 00:00; +compact 00:00 on Med+; backup 00:30 |
| `backup-sync-clouddrive` | ⬜ | ⬜ | ✅ | Copy latest stamp to CloudDrive mirror |
| `channel-status` | ◐ | ◐ | ◐ | Show attached social-app flags (Zalo/Telegram) |

\* Low timers: **auto-learn + backup** only (no compact) — run manually.  
† Medium/High: installed automatically by `run.sh up` / `update` (compact included).

---

## Stack lifecycle (all profiles)

```bash
bash run.sh up              # start Must (+ profile optionals when compose overlays exist)
bash run.sh down
bash run.sh destroy         # remove project containers + networks (volumes/data kept)
bash run.sh ps
bash run.sh logs [service]  # e.g. bash run.sh logs ingest
bash run.sh profile         # ASSISTANT_PROFILE=low|medium|high
bash run.sh update          # after git pull: rebuild + LLM refresh + disk prune
```

Full recreate (containers/networks only; keeps `/data/assistant` and named volumes):

```bash
bash run.sh destroy
bash run.sh up
```

Typical source update on a deployed host:

```bash
cd /opt/assistant   # git clone of this repo
git pull
bash run.sh update
```

---

## Backup / restore / migrate (Must — all profiles)

Stamps land in `BACKUP_DIR` (default **`/data/assistant/backups`**). High may also sync to CloudDrive (separate command).

```bash
bash run.sh backup                    # create stamp + LATEST
bash run.sh verify                    # verify LATEST
bash run.sh verify 20260815_003000    # verify one stamp
bash run.sh restore                   # restore LATEST
bash run.sh restore 20260815_003000
bash run.sh migrate                   # tarball of LATEST for a new server
```

| Profile | Extra |
|---------|-------|
| Low / Medium | Local disk only |
| High | After backup: `bash run.sh backup-sync-clouddrive` (needs `ENABLE_CLOUDDRIVE=1`) |

**Restore** uses Compose under `docker/` (not full `run.sh up` / first-setup). Postgres skips DROP/CREATE ROLE for the session user; Qdrant restores per-collection snapshots (storage HTTP recover N/A on Qdrant 1.13+).

**Lab-tested (2026-08-16):** High · Hermes×2 · monitor off · stamp `20260816_195940` — backup, verify, restore + canary, gateway/Zalo/DB healthy. Details: [architect/backup-restore/README.md](../architect/backup-restore/README.md). Hardware: [HARDWARE.md](./HARDWARE.md).

---

## Knowledge: auto-learn (Must — all profiles)

**Auto-learn ≠ compact.** Auto-learn writes **documents** into Qdrant `knowledge_chunks`. No admin approve (`LEARN_REQUIRE_APPROVE=0`).

```bash
bash run.sh auto-learn        # one-shot: scan media/docs (+ CloudDrive on High) → ingest
bash run.sh learn-status      # ingest /health and short catalog hint
```

Sources:

| Profile | Sources |
|---|---|
| Low / Medium | `/data/assistant` media + docs; channel inbound if social-app attached |
| High | Above + CloudDrive mirror |

Scheduled: **00:00** via `install-timers`.

Cite/list from chat still uses skills → ingest `list`/`search` (top 5 + rest count). That is not a `run.sh` command.

---

## Memory compact / optimize (Medium + High only)

```bash
bash run.sh compact              # slim skill drafts / memory housekeeping (silent)
bash run.sh optimize-memory      # Mem0/memory compact endpoints + Valkey ping
```

On **Low**, these print: `compact/optimize-memory require ASSISTANT_PROFILE=medium|high`.

Scheduled compact: **00:00** on Medium/High (second midnight job next to auto-learn).

---

## Timers

```bash
sudo bash run.sh install-timers
```

| Timer | Low | Medium / High |
|---|---|---|
| `assistant-auto-learn.timer` 00:00 | ✅ | ✅ |
| `assistant-compact.timer` 00:00 | — | ✅ |
| `assistant-backup.timer` 00:30 | ✅ | ✅ |

---

## High-only / attachable

```bash
bash run.sh backup-sync-clouddrive   # High + CloudDrive
bash run.sh channel-status       # ENABLE_ZALO / TELEGRAM / HTTP
```

Social-app **admin chat commands** (e.g. Zalo `!zalo …`) are documented inside `architect/social-app/<app>/` — they are not `run.sh` verbs and disappear when the pack is detached.

---

## Profile cheat-sheet

### Low

```bash
export ASSISTANT_PROFILE=low
bash run.sh up
bash run.sh backup && bash run.sh verify
bash run.sh auto-learn
sudo bash run.sh install-timers   # auto-learn + backup only
```

### Medium

```bash
export ASSISTANT_PROFILE=medium
bash run.sh up                # also installs timers (auto-learn + compact + backup)
bash run.sh check-medium
bash run.sh compact           # optional manual run
bash run.sh auto-learn
bash run.sh backup
```

### High

```bash
export ASSISTANT_PROFILE=high
# .env: OPENBAO_DEV_ROOT_TOKEN, GRAFANA_ADMIN_PASSWORD, ADMIN_API_TOKEN
bash run.sh up                # medium+high overlays, timers, seed OpenBao
bash run.sh first-setup-llm   # if needed
bash run.sh check-high
bash run.sh backup && bash run.sh backup-sync-clouddrive   # CloudDrive when rclone ready
# optional notify:
#   ENABLE_NOTIFY=1 bash run.sh up
```

---

## See also

- [02-components-and-commands.md](./02-components-and-commands.md) — components + commands  
- [00-profiles.md](./00-profiles.md)  
- [architect/backup-restore/README.md](../architect/backup-restore/README.md)  
- [01-workflow.md](./01-workflow.md) — Low chat path (not ops)
