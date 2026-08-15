# architect

Platform layers around Hermes. Each subfolder has a detailed README.

**Diagrams:** [docs/03-architecture.md](../docs/03-architecture.md) (whole system) · [docs/04-component-flows.md](../docs/04-component-flows.md) (per layer)

| Layer | Doc | Profile |
|---|---|---|
| host | [host/README.md](./host/README.md) | all |
| social-app | [social-app/README.md](./social-app/README.md) | attach |
| authentication | [authentication/README.md](./authentication/README.md) | High |
| security | [security/README.md](./security/README.md) | High |
| memory | [memory/README.md](./memory/README.md) | Must |
| tools | [tools/README.md](./tools/README.md) | Must (+ OCR/Jobs Med+) |
| models | [models/README.md](./models/README.md) | Must |
| notification | [notification/README.md](./notification/README.md) | High |
| admin-api | [admin-api/README.md](./admin-api/README.md) | High / channel |
| backup-restore | [backup-restore/README.md](./backup-restore/README.md) | Must |
| monitor | [monitor/README.md](./monitor/README.md) | High |

Hermes product surface (skills, messages, plugins): [../hermes/README.md](../hermes/README.md).
