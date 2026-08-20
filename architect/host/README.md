# host

## System architecture

| | |
|--|--|
| **Sits between** | Operator ↔ Docker / OS |
| **Owns** | Paths (`/opt/assistant`, `/data/assistant`), install scripts, timers that call `run.sh` |
| **Does not own** | Container app logic (that is other `architect/*` layers) |

<table style="width:100%;border-collapse:collapse;font-size:13px;">
  <tr>
    <td style="padding:12px;background:#f5f5f5;border:1px solid #ddd;text-align:center;width:28%;">Operator</td>
    <td style="padding:8px;background:#eee;text-align:center;width:4%;">→</td>
    <td style="padding:14px;background:#2563eb;color:#fff;text-align:center;border:3px solid #fbbf24;width:36%;"><b>host scripts</b></td>
    <td style="padding:8px;background:#eee;text-align:center;width:4%;">→</td>
    <td style="padding:12px;background:#e8f4ea;border:1px solid #c5e0c8;text-align:center;width:28%;">Docker Compose · /data · /opt</td>
  </tr>
</table>

## Purpose

Host-level setup for the assistant stack: OS prep, Docker, directories under `/data/assistant` and `/opt/assistant`, timezone, and systemd timers that call `bash run.sh` / backup-restore. This layer does **not** run inside Docker as an app service; it documents and holds scripts that prepare the machine.

## Scope

| Scope | Role |
|---|---|
| Any worker set | Always needed to install and run the stack |

## What lives here

| Path | Function |
|---|---|
| [`scripts/main/`](../../scripts/main/) | Product host ops: Docker install, LLM first-setup (via `run.sh`) |
| [`scripts/temp/`](../../scripts/temp/) | Local-only deploy/probe/hotfix (gitignored) |

## Runtime paths (production)

| Path | Function |
|---|---|
| `/opt/assistant` | Code / compose (`STACK_ROOT`) |
| `/data/assistant` | Hermes data, media, skills mount target |
| `/data/assistant/backups` | Local DR stamps (Low/Medium) |

## How it works

1. Operator clones or syncs this repo to `/opt/assistant`.
2. Copies `.env.example` → `.env` and sets secrets.
3. Creates `/data/assistant` (and backups dir) with correct ownership for the Hermes UID.
4. Runs `bash run.sh up` which starts Must containers.
5. (Later) systemd timers for **auto-learn** and (Medium+) **compact** call ops scripts under `backup-restore/`.

## Inputs / outputs

- **In:** `.env`, Docker Engine, disk space  
- **Out:** Running compose project `assistant`, data directories ready for mounts  

## Related

- [backup-restore](../backup-restore/README.md) — timers and DR  
- [docs/00-profiles.md](../../docs/00-profiles.md)
- [docs/HARDWARE.md](../../docs/HARDWARE.md) — host sizing + extra RAM/disk/CPU when Grafana/Prometheus/Loki are on
