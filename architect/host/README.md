# host

## Purpose

Host-level setup for the assistant stack: OS prep, Docker, directories under `/data/assistant` and `/opt/assistant`, timezone, and systemd timers that call `bash run.sh` / backup-restore. This layer does **not** run inside Docker as an app service; it documents and holds scripts that prepare the machine.

## Profile

| Profile | Role |
|---|---|
| Low / Medium / High | Always needed to install and run the stack |

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
