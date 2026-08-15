# hermes

Hermes is the **product surface**: agent skills, channel plugins, editable messages, and config snippets. Platform services live under `architect/`.

## Default: `main/`

Same pattern as [`scripts/`](../scripts/README.md) — **ops and compose always use `main/`**:

| Folder | Purpose | Git |
|---|---|---|
| [`main/`](./main/) | **Default** — skills, plugins, messages, config, setup | **commit** |
| [`temp/`](./temp/) | Live-server / WIP skills & local notes | **ignored** |
| `data/` | Local stub — production uses `/data/assistant` | ignored |

```text
hermes/
├── main/          ← DEFAULT (compose + run.sh + post-ready-learn)
│   ├── skills/    ← product skills (ship)
│   ├── plugins/
│   ├── messages/
│   ├── config/
│   ├── setup/
│   └── docs/
├── temp/          ← live-server skills parked here (not mounted by default)
│   └── skills/
└── data/
```

Env overrides (optional):

```bash
export HERMES_DIR=hermes/main          # default
export SCRIPTS_DIR=scripts/main        # default (see run.sh)
```

## Related

- [main/README.md](./main/README.md)  
- [temp/skills](./temp/skills/README.md)  
- [docs/01-workflow.md](../docs/01-workflow.md)
