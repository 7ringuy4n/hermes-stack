# docs

English operations docs for the **assistant** stack.

| Doc | Contents |
|-----|----------|
| [00-profiles.md](./00-profiles.md) | Low / Medium / High |
| [HARDWARE.md](./HARDWARE.md) | Tested lab hardware + recommended minimums |
| [01-workflow.md](./01-workflow.md) | Chat / request path |
| [02-components-and-commands.md](./02-components-and-commands.md) | Components + commands by profile |
| [02-commands.md](./02-commands.md) | `run.sh` command reference |
| [03-architecture.md](./03-architecture.md) | Architecture |
| [04-component-flows.md](./04-component-flows.md) | Per-component flows |
| [05-edge-networking.md](./05-edge-networking.md) | Traefik / API Gateway / OpenVPN (optional) |
| [06-model-routing.md](./06-model-routing.md) | Model Router / 9router / OmniRouter |
| [MULTI_NODE.md](./MULTI_NODE.md) | Hermes×2 vs true HA; store SPOFs |
| [SECURITY.md](./SECURITY.md) | P0 hardening notes / residual risks |
| [AGENT_RULES.md](./AGENT_RULES.md) | Operator / agent hard rules (SoT) |
| [config/DEFAULTS.md](./config/DEFAULTS.md) | Non-secret defaults |
| [CHANGELOG.md](./CHANGELOG.md) | Change log |
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
