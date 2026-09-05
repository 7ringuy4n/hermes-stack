# Profiles (legacy)

**Product tiers `ASSISTANT_PROFILE=low|medium|high` are removed from runtime.**

Use **optional workers** instead:

| Doc | Contents |
|-----|----------|
| [00-workers.md](./00-workers.md) | `bash run.sh install <worker>` |
| [config/DEFAULTS.md](./config/DEFAULTS.md) | Non-secret defaults |
| [02-commands.md](./02-commands.md) | `run.sh install`, `workers`, `up` |

```bash
bash run.sh up
bash run.sh install schedule media notify message
bash run.sh workers
```

`bash run.sh switch-profile …` is disabled (returns usage pointing at `install` / `add-components`).

## Routers

| Router | Default |
|--------|---------|
| **OmniRouter** | On (`ENABLE_OMNIROUTER=active`) — general / classify / outbound |
| **OmniRoute** | Off (`ENABLE_OMNIROUTER=inactive`) — optional coding path |

First-setup LLM wiring: `bash run.sh first-setup-omnirouter` (and `first-setup-llm` only when OmniRoute is enabled).
