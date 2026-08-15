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

## Quick start (Low)

```bash
git clone <your-repo-url> /opt/assistant
cd /opt/assistant

cp -n .env.example .env
# Edit every CHANGE_ME value (Hermes dashboard, 9Router, memory DB, …)

sudo bash scripts/main/install-docker.sh   # skip if Docker already works
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
| **high** | OpenBao, Grafana/Loki/Prometheus, authz, admin-api, SIEM, optional Zalo |

```bash
export ASSISTANT_PROFILE=medium   # or high
bash run.sh up
```

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
| `architect/` | microservices (dispatcher, memory, ingest, …) |
| `hermes/main/` | skills, plugins, messages |
| `config/` | Grafana, Alloy, Loki |
| `docs/` | profiles, workflow, commands |
| `scripts/main/` | install, first-setup, Zalo, watches |

## Documentation

| Doc | Contents |
|-----|----------|
| [docs/README.md](docs/README.md) | Doc index |
| [docs/00-profiles.md](docs/00-profiles.md) | Low / Medium / High |
| [docs/02-commands.md](docs/02-commands.md) | `run.sh` commands |
| [docs/03-architecture.md](docs/03-architecture.md) | Component map |

## Security notes

- Commit **`.env.example` only** — real secrets stay in host `.env` (gitignored).
- `scripts/temp/` is gitignored (local deploy/hotfix scripts).
- `hermes/temp/` is gitignored (local drafts).
- Dashboards and admin ports bind to localhost; use SSH tunnels.

## License

MIT — see [LICENSE](LICENSE) if present. Upstream Hermes and hermes-zalo-plugin
retain their own licenses and attribution.
