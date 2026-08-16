<p align="center">
  <strong>assistant</strong>
</p>

# assistant

[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](./LICENSE)
[![Profiles](https://img.shields.io/badge/profiles-low%20%7C%20medium%20%7C%20high-blue.svg)](#profiles)

Self-hosted **Hermes Agent** stack with memory, knowledge ingest, optional channels
(Zalo / Telegram), and ops tooling. Profiles scale from a minimal Low box to a full
High lab (OpenBao, Grafana, authz).

```
Chat apps (optional)  →  Hermes gateway  →  dispatcher / 9Router  →  models
                              ↓
                     memory · knowledge · skills
```

This repository is the **product source of truth**. Runtime data stays on the host
(`ASSISTANT_DATA_DIR`, default `/data/assistant`). Never commit `.env`.

> **Channels:** Zalo uses the upstream bridge
> [hermes-zalo-plugin](https://github.com/cuongdev/hermes-zalo-plugin)
> by **Cường Tuấn Nguyễn (cuongdev)** (MIT). See
> [hermes/main/plugins/zalo/ATTRIBUTION.md](hermes/main/plugins/zalo/ATTRIBUTION.md).

## Requirements

| Requirement | Why |
|-------------|-----|
| Linux host with Docker + Compose | runs the stack |
| Git | clone / update |
| SSH access | tunnels for dashboards / QR |

### Hardware (tested + minimums)

Lab-tested **High** (Hermes×2, monitor off, Zalo, backup/restore): **Ubuntu 24.04 · 4 vCPU · 16 GiB RAM · ~200 GB SSD**.

| Profile | Minimum | Comfortable |
|---------|---------|-------------|
| **Low** | 2 vCPU · 4 GiB · 40 GB | 2 · 8 GiB · 80 GB |
| **Medium** | 2 vCPU · 8 GiB · 80 GB | 4 · 16 GiB · 120 GB |
| **High** (no Grafana/Loki/Prometheus) | 4 vCPU · 8 GiB · 100 GB | **4 · 16 GiB · 200 GB** |
| **High** + monitor stack | 4 vCPU · 16 GiB · 150 GB | 8 · 32 GiB · 250 GB |

Full sizing notes: [docs/HARDWARE.md](docs/HARDWARE.md).

### Host hardening (clean Ubuntu)

On a **fresh Ubuntu** VPS (SSH exposed to the internet), install **fail2ban** before or right after Docker so repeated failed SSH logins are banned:

```bash
sudo apt update
sudo apt install -y fail2ban
sudo systemctl enable --now fail2ban
sudo fail2ban-client status sshd   # confirm the jail is active
```

Keep SSH key-based auth where possible; fail2ban complements (does not replace) firewall rules (`ufw` / security groups).

## Quick start (Low)

```bash
git clone <your-repo-url> /opt/assistant
cd /opt/assistant

cp -n .env.example .env
# Edit every CHANGE_ME value (Hermes dashboard, 9Router, memory DB, …)

sudo bash scripts/main/install-docker.sh   # skip if Docker already works
# On clean Ubuntu: install fail2ban (see Host hardening above)
export ASSISTANT_PROFILE=low
bash run.sh up
bash run.sh first-setup-llm
bash run.sh ps
```

Tunnel the Hermes dashboard (and 9Router if needed):

```bash
ssh -L 29119:127.0.0.1:29119 -L 20128:127.0.0.1:20128 USER@HOST
```

Update later:

```bash
cd /opt/assistant && git pull && bash run.sh update
```

Defaults (non-secret): [docs/config/DEFAULTS.md](docs/config/DEFAULTS.md).

## Profiles

| Profile | Adds |
|---------|------|
| **low** | Hermes, 9Router, memory, redis, ingest/embedding core |
| **medium** | Web search, OCR, jobs, ComfyUI CPU image path, compact timer |
| **high** | OpenBao, authz, admin-api, SIEM; optional Grafana/Loki/Prometheus (`monitor`); optional Zalo |

```bash
export ASSISTANT_PROFILE=medium   # or high
bash run.sh up
```

Compose YAML lives under [`docker/`](docker/README.md). Hardware sizing: [docs/HARDWARE.md](docs/HARDWARE.md). Backup/restore: [architect/backup-restore/README.md](architect/backup-restore/README.md).

## Zalo (optional)

```bash
# in .env
ENABLE_ZALO=1

bash run.sh up
bash scripts/main/setup-zalo.sh    # after stack healthy — install only, no QR
bash scripts/main/login-zalo.sh    # manual QR (last step)
```

Admin (exactly one user): after login, DM the bot `!zalo claim`, then
`!zalo admin transfer @user` when needed.

Self-heal timers (`assistant-stack-watch`, `assistant-zalo-watch`) restart down
services / reconnect SSE without user-visible backend noise.

## Layout

| Path | Role |
|------|------|
| `run.sh` | up / down / update / checks / timers |
| `docker/` | Compose overlays (`--project-directory` = repo root) |
| `architect/` | microservices (dispatcher, memory, ingest, backup-restore, …) |
| `hermes/main/` | skills, plugins, messages |
| `config/` | Grafana, Alloy, Loki |
| `docs/` | profiles, workflow, commands, hardware |
| `scripts/main/` | install, first-setup, Zalo, watches, Deploy-High |

## Documentation

| Doc | Contents |
|-----|----------|
| [docs/README.md](docs/README.md) | Doc index |
| [docs/HARDWARE.md](docs/HARDWARE.md) | Tested lab + minimum / comfortable specs |
| [docs/00-profiles.md](docs/00-profiles.md) | Low / Medium / High |
| [docs/02-commands.md](docs/02-commands.md) | `run.sh` commands |
| [docs/03-architecture.md](docs/03-architecture.md) | Component map |
| [architect/backup-restore/README.md](architect/backup-restore/README.md) | DR commands + tested round-trip |
| [docker/README.md](docker/README.md) | Compose file map + monitor profile |

## Security notes

- Commit **`.env.example` only** — real secrets stay in host `.env` (gitignored).
- `scripts/temp/` is gitignored (local deploy/hotfix scripts).
- `hermes/temp/` is gitignored (local drafts).
- Dashboards and admin ports bind to localhost; use SSH tunnels.
- On clean Ubuntu internet-facing hosts, enable **fail2ban** for SSH (see [Host hardening](#host-hardening-clean-ubuntu)).

## License

MIT — see [LICENSE](LICENSE) if present. Upstream Hermes and hermes-zalo-plugin
retain their own licenses and attribution.
