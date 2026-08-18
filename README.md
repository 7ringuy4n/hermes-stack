<p align="center">
  <strong>assistant</strong>
</p>

# assistant

[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](./LICENSE)
[![Profiles](https://img.shields.io/badge/profiles-low%20%7C%20medium%20%7C%20high-blue.svg)](#which-profile-should-i-use)
[![Docs](https://img.shields.io/badge/docs-index-informational.svg)](./docs/README.md)

Self-hosted **Hermes Agent** stack with memory, knowledge ingest, optional channels
(Zalo / Telegram), and ops tooling. Profiles scale from a minimal Low box to a full
High lab (OpenBao, Grafana, authz).

This repository is the **product source of truth**. Runtime data stays on the host
(`ASSISTANT_DATA_DIR`, default `/data/assistant`). Never commit `.env`.

> **Channels:** Zalo uses the upstream bridge
> [hermes-zalo-plugin](https://github.com/cuongdev/hermes-zalo-plugin)
> by **Cường Tuấn Nguyễn (cuongdev)** (MIT). See
> [hermes/main/plugins/zalo/ATTRIBUTION.md](./hermes/main/plugins/zalo/ATTRIBUTION.md).

## New here?

You need a Linux host with Docker and Compose, Git, and SSH. If that is new:

1. Install Docker with the script in [Quick start](#quick-start-low) (or your distro docs).
2. Start on **Low** only — one Hermes, no Zalo, no monitor.
3. Open the dashboard through an SSH tunnel (ports stay on localhost for safety).
4. Read [docs/00-profiles.md](./docs/00-profiles.md) before jumping to Medium/High.

Full doc map: **[docs/README.md](./docs/README.md)** · Architecture: **[docs/03-architecture.md](./docs/03-architecture.md)** · Hardware: **[docs/HARDWARE.md](./docs/HARDWARE.md)**

## Use cases

| You want… | Start with | Why |
|-----------|------------|-----|
| Private AI chat + facts that persist | **Low** | Hermes + Valkey session + Postgres memory + Qdrant knowledge |
| Chat that can search the web, OCR PDFs, queue long jobs | **Medium** | Adds dispatcher search, OCR, jobs workers, optional image path |
| Lab/enterprise controls (ACL, SIEM, secrets, dual Hermes) | **High** | Authz/policy, OpenBao, SIEM; Hermes×2 on one node; monitor optional |
| Zalo / Telegram as the front door | Any profile + channel flag | Social packs attach anytime — not a separate profile |
| Coding vs general model split | Medium/High + Model Router | [docs/06-model-routing.md](./docs/06-model-routing.md) |

## High-level architecture

<table style="width:100%;border-collapse:collapse;font-family:Segoe UI,Arial,sans-serif;font-size:13px;">
  <tr><td colspan="3" style="padding:12px;background:#1a1a1a;color:#fff;text-align:center;font-weight:700;">USERS — Console / IDE · Zalo / Telegram (optional)</td></tr>
  <tr><td colspan="3" style="padding:4px;background:#eee;text-align:center;color:#666;">▼</td></tr>
  <tr><td colspan="3" style="padding:12px;background:#0f766e;color:#fff;text-align:center;font-weight:700;">edge (default ON) — API Gateway · Traefik &nbsp;|&nbsp; Zalo bypasses edge</td></tr>
  <tr><td colspan="3" style="padding:4px;background:#eee;text-align:center;color:#666;">▼</td></tr>
  <tr><td colspan="3" style="padding:14px;background:#2563eb;color:#fff;text-align:center;font-weight:700;">hermes — Agent · skills · plugins (×1 or ×2 on one node)</td></tr>
  <tr><td colspan="3" style="padding:4px;background:#eee;text-align:center;color:#666;">▼</td></tr>
  <tr><td colspan="3" style="padding:12px;background:#4338ca;color:#fff;text-align:center;font-weight:700;">model-router — coding → 9router · general → OmniRouter (opt) / fallback</td></tr>
  <tr><td colspan="3" style="padding:4px;background:#eee;text-align:center;color:#666;">▼</td></tr>
  <tr>
    <td style="width:34%;padding:12px;background:#e8f4ea;border:1px solid #c5e0c8;vertical-align:top;"><b>Platform</b><br/>dispatcher · memory · session<br/>ingest / OCR / jobs</td>
    <td style="width:33%;padding:12px;background:#fff8e6;border:1px solid #f0e0b0;vertical-align:top;"><b>Stores (SPOFs today)</b><br/>Valkey · Postgres · Qdrant</td>
    <td style="width:33%;padding:12px;background:#fde8e8;border:1px solid #f0c0c0;vertical-align:top;"><b>Channels</b><br/>zalo-api when ENABLE_ZALO<br/>notify (High opt)</td>
  </tr>
</table>

Stores in one line: **Valkey** = short-term session / locks / queues · **Postgres** = durable facts · **Qdrant** = rebuildable knowledge. Mem0 is removed.

Component map with HTML panels: [docs/03-architecture.md](./docs/03-architecture.md) · Layer index: [architect/README.md](./architect/README.md) · Scale / SPOFs: [docs/MULTI_NODE.md](./docs/MULTI_NODE.md)

## Requirements

| Requirement | Why |
|-------------|-----|
| Linux host with Docker + Compose | runs the stack |
| Git | clone / update |
| SSH access | tunnels for dashboards / QR |

### Hardware (tested + minimums)

Lab-tested **High** (Hermes×2, monitor off, Zalo, backup/restore): **Ubuntu 24.04 · 4 vCPU · 16 GiB RAM · ~200 GB SSD** (~3 GiB idle).

| Profile | Minimum | Comfortable |
|---------|---------|-------------|
| **Low** | 2 vCPU · 4 GiB · 40 GB | 2 · 8 GiB · 80 GB |
| **Medium** | 2 vCPU · 8 GiB · 80 GB | 4 · 16 GiB · 120 GB |
| **High** (no Grafana/Loki/Prometheus) | 4 vCPU · 8 GiB · 100 GB | **4 · 16 GiB · 200 GB** |
| **High** + all optional features | 6 vCPU · 16 GiB · 140 GB | 8 · 32 GiB · 250 GB |

Add-ons (Grafana+Prometheus **or** Loki+Alloy, exporters start with their component): Grafana+Prometheus **~1.5 GiB · ~10 GB · ~0.5 vCPU** · Loki+Alloy **~1.5 GiB · ~20 GB · ~0.5 vCPU** · **all optional features ~5 GiB RAM · ~40 GB disk · ~2 vCPU**. Details: [docs/HARDWARE.md](./docs/HARDWARE.md).

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

Tunnel the Hermes dashboard (and 9Router if needed). With Hermes×1 (Low default):

```bash
ssh -L 29119:127.0.0.1:29119 -L 20128:127.0.0.1:20128 USER@HOST
```

On High with Hermes×2, host `:29119` is not published — tunnel Traefik (`8080`) and/or API Gateway (`8088`) instead ([docs/00-profiles.md](./docs/00-profiles.md)).

Update later:

```bash
cd /opt/assistant && git pull && bash run.sh update
```

Defaults (non-secret): [docs/config/DEFAULTS.md](./docs/config/DEFAULTS.md) · Commands: [docs/02-commands.md](./docs/02-commands.md)

## Which profile should I use?

| Profile | Adds | Choose when |
|---------|------|-------------|
| **low** | Hermes×1, Model Router, Traefik/Gateway, Valkey, Postgres, Qdrant, memory, ingest/embedding, 9router | Smallest useful stack |
| **medium** | + OCR, jobs, SearXNG, ComfyUI CPU, compact timer | Documents + web + async work |
| **high** | + OpenBao, authz, SIEM; zalo-api with Zalo; Hermes×2 one node; monitor optional; Zalo optional | Controls / lab / dual Hermes load |

```bash
export ASSISTANT_PROFILE=medium   # or high
bash run.sh up
# or, from a running stack (backup+verify first):
bash run.sh switch-profile medium
bash run.sh add-components ENABLE_ZALO=1
```

Traefik defaults to `TRAEFIK_MODE=local` (VPN/localhost). `public` + ACME is explicit opt-in. Compose YAML: [`docker/`](./docker/README.md). Backup/restore: [architect/backup-restore/README.md](./architect/backup-restore/README.md).

## Resilience (what is / is not HA)

Self-heal timers (`assistant-stack-watch`, `assistant-zalo-watch`) restart exited containers and reconnect Zalo SSE when the session is still logged in.

| Component | Today | Note |
|-----------|-------|------|
| Hermes | ×2 on **one** node (High) | Load only — not multi-node HA |
| Zalo SSE | **One** owner lock | Never two SSE clients; QR only if `sessionDead` |
| Valkey / Postgres / Qdrant / Traefik | Single instance | **SPOFs** — see [docs/MULTI_NODE.md](./docs/MULTI_NODE.md) |
| Jobs workers | Scale out | Shared Valkey RQ queue |

Do **not** call the stack HA until the stores are replicated.

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

## Layout

| Path | Role |
|------|------|
| [`run.sh`](./run.sh) | up / down / update / checks / timers |
| [`docker/`](./docker/README.md) | Compose overlays (`--project-directory` = repo root) |
| [`architect/`](./architect/README.md) | microservices (dispatcher, memory, ingest, backup-restore, …) |
| [`hermes/main/`](./hermes/README.md) | skills, plugins, messages |
| [`config/`](./config/) | Grafana, Alloy, Loki |
| [`docs/`](./docs/README.md) | profiles, workflow, commands, hardware, routing |
| [`scripts/main/`](./scripts/main/) | install, first-setup, Zalo, watches |

## Documentation

| Doc | Contents |
|-----|----------|
| [docs/README.md](./docs/README.md) | Full doc index |
| [docs/HARDWARE.md](./docs/HARDWARE.md) | Tested lab + extra RAM/disk/CPU when Grafana/Prometheus/Loki/OmniRouter are on |
| [docs/00-profiles.md](./docs/00-profiles.md) | Low / Medium / High + Traefik modes |
| [docs/02-commands.md](./docs/02-commands.md) | `run.sh` commands |
| [docs/03-architecture.md](./docs/03-architecture.md) | System architecture (HTML panels) |
| [docs/04-component-flows.md](./docs/04-component-flows.md) | Per-component flows |
| [docs/05-edge-networking.md](./docs/05-edge-networking.md) | Traefik / Gateway / OpenVPN |
| [docs/06-model-routing.md](./docs/06-model-routing.md) | Model Router / 9router / OmniRouter |
| [docs/MULTI_NODE.md](./docs/MULTI_NODE.md) | Hermes×2 vs true HA / SPOFs |
| [architect/README.md](./architect/README.md) | Platform layer index + design links |
| [architect/backup-restore/README.md](./architect/backup-restore/README.md) | DR commands + tested round-trip |
| [docker/README.md](./docker/README.md) | Compose file map + monitor profile |
| [docs/GIT.md](./docs/GIT.md) | Feature → develop → release → main |
| [docs/CHANGELOG.md](./docs/CHANGELOG.md) | Change history |

## Security notes

- Commit **`.env.example` only** — real secrets stay in host `.env` (gitignored).
- `scripts/temp/` is gitignored (local deploy/hotfix scripts).
- `hermes/temp/` is gitignored (local drafts).
- Dashboards and admin ports bind to localhost; use SSH tunnels.
- On clean Ubuntu internet-facing hosts, enable **fail2ban** for SSH (see [Host hardening](#host-hardening-clean-ubuntu)).

## License

MIT — see [LICENSE](./LICENSE) if present. Upstream Hermes and hermes-zalo-plugin
retain their own licenses and attribution.
