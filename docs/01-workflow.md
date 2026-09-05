# 01 — Core chat workflow

**As of:** 2026-08-23  
**Scope:** Core stack (workers inactive). Optional workers: [00-workers.md](./00-workers.md).  
**Full architecture + HTML flows:** [03-architecture.md](./03-architecture.md) · [04-component-flows.md](./04-component-flows.md).

## Product

Hermes Agent + Memory. Without a social app you chat through the Hermes console, IDE, or another HTTP client. Attach Message worker (`install message` / `zalo`) for Zalo.

## Core path

```text
Console / IDE / optional social-app
        │
        ▼
    Hermes Agent
        ├─ Memory Manager
        │     • Valkey — short-term session (TTL), rate-limit, small queues
        │     • Postgres (Memory Manager) — long-term conversational facts
        │     • Qdrant conversational_memory — optional vector recall
        ├─ Knowledge — Ingest + Embedding → Qdrant knowledge_chunks
        │     auto-learn 00:00 (no approve); list/find top 5 + rest count
        ├─ Session
        ├─ Model Router (model-router) → OmniRouter (default) · OmniRoute optional
        └─ Tool bus only when Media worker is active (dispatcher / OCR / Jobs / SearXNG)
        │
        ▼
   One short reply (no progress spam, no server paths)
```

### Memory in plain language

1. **While you chat**, recent messages live in **Valkey** (fast, expires).
2. **Important facts** are written asynchronously into **Postgres** via Memory Manager (optional Qdrant index) so later sessions can recall them — not every joke or "ok".
3. **Documents** go through **ingest** into **`knowledge_chunks`**. At midnight **auto-learn** indexes eligible files from `/data/assistant` media (and inbound when a social app is attached). Empty search → say there is no information; **do not guess**. Web search requires the Media worker.

### Off until you install workers

| Capability | Install |
|------------|---------|
| Schedule / timed send | `schedule` |
| OCR, Jobs, SearXNG, Comfy, office file-gen, compact | `media` |
| Authz, SIEM, policy, OpenBao, AV path | `security` / `openbao` / `antivirus` |
| Notify / alert-watch | `notify` |
| Zalo / Telegram | `message` or `zalo` |
| Grafana, Prometheus, Loki, Alloy | `monitor` |

Traefik local + API Gateway are **core defaults** (`ENABLE_TRAEFIK=active`, `ENABLE_API_GATEWAY=active`).

### Editable UX strings

User-facing copy lives under `hermes/main/messages/` (e.g. `learn-notify.json`). Prefer skills + editable lists for cite/secret triggers instead of huge hardcoded adapter regexes.

### Paths

| Role | Path |
|---|---|
| Code | `/opt/assistant` or this clone |
| Data | `/data/assistant` |
| Backups | `/data/assistant/backups` |
| Skills | `hermes/main/skills` → mounted into Hermes data |
