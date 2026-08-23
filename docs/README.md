# docs

English operations docs for the **assistant** stack.

| Doc | Contents |
|-----|----------|
| [00-workers.md](./00-workers.md) | Optional workers (`WORKER_*=active\|inactive`) |
| [00-profiles.md](./00-profiles.md) | Legacy note — profiles removed; redirects to workers |
| [HARDWARE.md](./HARDWARE.md) | Tested lab + extra RAM/disk/CPU (Grafana+Prometheus, Loki, all optionals ~5 GiB / ~40 GB / ~2 vCPU) |
| [01-workflow.md](./01-workflow.md) | Chat / request path |
| [02-components-and-commands.md](./02-components-and-commands.md) | Components + commands |
| [02-commands.md](./02-commands.md) | `run.sh` command reference |
| [03-architecture.md](./03-architecture.md) | Architecture |
| [04-component-flows.md](./04-component-flows.md) | Per-component flows |
| [05-edge-networking.md](./05-edge-networking.md) | Traefik / API Gateway / OpenVPN (optional) |
| [06-model-routing.md](./06-model-routing.md) | Model Router / OmniRouter (default) / 9Router (optional) |
| [MULTI_NODE.md](./MULTI_NODE.md) | Hermes×2 vs true HA; store SPOFs |
| [SECURITY.md](./SECURITY.md) | Isolation vs LLM heuristic; VPN-only edge |
| [AGENT_RULES.md](../AGENT_RULES.md) | Operator / agent hard rules (SoT) |
| [config/DEFAULTS.md](./config/DEFAULTS.md) | Non-secret defaults |
| [CHANGELOG.md](./CHANGELOG.md) | Change log |
| [scripts/HISTORY.md](../scripts/HISTORY.md) | Ops issue log: symptoms, root causes, fixes (timestamped) |
| [GIT.md](./GIT.md) | Git workflow: feature → develop → release → main |
| [NEXT.md](./NEXT.md) | Backlog |

## Related indexes

| Area | Path |
|------|------|
| Platform services | [architect/README.md](../architect/README.md) |
| Backup / restore | [architect/backup-restore/README.md](../architect/backup-restore/README.md) |
| Docker Compose | [docker/README.md](../docker/README.md) |
| Hermes surface | [hermes/README.md](../hermes/README.md) |
| Skills | [hermes/main/skills/README.md](../hermes/main/skills/README.md) |

Put secrets in host `.env` only (never commit).
