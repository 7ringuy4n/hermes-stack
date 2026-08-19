# secret-probe

Security gate **independent from** `task_hint`. Model Router never classifies `SECRET`.

## Statuses

| Status | Meaning |
|--------|---------|
| `SAFE` | Continue (task hint / pipelines) |
| `BLOCKED` | Stop. No LLM, schedule, tool, memory, or queue. |
| `REVIEW` | Policy fallback (fail closed if unsure) |

Contract:

```json
{ "status": "BLOCKED", "reason": "SECRET_POLICY" }
```

Do not put matched secrets in the JSON, logs, notify body, or schedules.

## Where it runs

```text
User → Hermes / gateway
         → INPUT Secret Probe
              BLOCK → stop
              SAFE  → task_hint (NORMAL / SCHEDULE / CODING / TOOL / SEARCH / FILE / UNKNOWN)
         → pipelines
         → OUTPUT Secret Probe
              BLOCK → refuse copy (ux.json secret_probe.refuse)
              SAFE  → user
```

Policy file: [`config/agent/secret-probe.json`](../../config/agent/secret-probe.json) (`SECRET_PROBE_POLICY`). Patterns are admin-editable — not adapter keyword tables.

## Callers

- Zalo adapter (before Hermes / workflow)
- API Gateway (before schedule create / Hermes proxy)
- Outbound Zalo `send()` after path redaction
