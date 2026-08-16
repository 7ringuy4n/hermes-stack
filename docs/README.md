# docs

English operations docs for the **assistant** stack.

| Doc | Contents |
|-----|----------|
| [00-profiles.md](./00-profiles.md) | Low / Medium / High |
| [01-workflow.md](./01-workflow.md) | Chat / request path |
| [02-components-and-commands.md](./02-components-and-commands.md) | Components + commands by profile |
| [02-commands.md](./02-commands.md) | `run.sh` command reference |
| [03-architecture.md](./03-architecture.md) | Architecture |
| [04-component-flows.md](./04-component-flows.md) | Per-component flows |
| [05-edge-networking.md](./05-edge-networking.md) | Traefik / API Gateway / OpenVPN (optional) |
| [config/DEFAULTS.md](./config/DEFAULTS.md) | Non-secret defaults |
| [CHANGELOG.md](./CHANGELOG.md) | Change log |
| [NEXT.md](./NEXT.md) | Backlog |

## Related indexes

| Area | Path |
|------|------|
| Platform services | [architect/README.md](../architect/README.md) |
| Hermes surface | [hermes/README.md](../hermes/README.md) |
| Skills | [hermes/main/skills/README.md](../hermes/main/skills/README.md) |

Put secrets in host `.env` only (never commit).
