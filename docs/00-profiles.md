# Profiles (legacy)

**Product tiers `ASSISTANT_PROFILE=low|medium|high` are removed from runtime.**

Use **optional workers** instead:

| Doc | Contents |
|-----|----------|
| [00-workers.md](./00-workers.md) | Worker activation (`WORKER_*=active\|inactive`) |
| [config/DEFAULTS.md](./config/DEFAULTS.md) | Non-secret defaults |
| [02-commands.md](./02-commands.md) | `run.sh add-components`, `workers`, `up` |

```bash
# Example: Schedule + Media|File + Notify + Message (Zalo)
# Edit .env then:
bash run.sh up
# Or:
bash run.sh add-components \
  WORKER_SCHEDULE=active \
  WORKER_MEDIA_FILE=active \
  WORKER_NOTIFY=active \
  WORKER_MESSAGE=active
```

`bash run.sh switch-profile …` is disabled (returns usage pointing at `add-components`).

## Routers

| Router | Default |
|--------|---------|
| **OmniRouter** | On (`ENABLE_OMNIROUTER=1`) — general / classify / outbound |
| **9Router** | Off (`ENABLE_9ROUTER=0`) — optional coding path |

First-setup LLM wiring: `bash run.sh first-setup-omnirouter` (and `first-setup-llm` only when 9Router is enabled).
