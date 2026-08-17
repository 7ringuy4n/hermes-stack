# 01 — Low profile workflow

**As of:** 2026-08-15  
**Scope:** Low only. Profiles: [00-profiles.md](./00-profiles.md).  
**Full architecture + HTML flows:** [03-architecture.md](./03-architecture.md) · [04-component-flows.md](./04-component-flows.md).

## Product

Hermes Agent + Memory. Without a social app you chat through the Hermes console, IDE, or another HTTP client.

## Must turn

```text
Console / IDE / optional social-app
        │
        ▼
    Hermes Agent
        ├─ Memory Manager
        │     • Valkey — short-term session (TTL), rate-limit, small queues
        │     • Postgres (Memory Manager) — long-term conversational facts
        │     • Postgres — typed metadata Memory Manager budgets into context
        ├─ Knowledge — Ingest + Embedding → Qdrant knowledge_chunks
        │     auto-learn 00:00 (no approve); list/find top 5 + rest count
        ├─ Session
        ├─ Dispatcher (tool bus; no web backends in Low)
        └─ 9Router → LLM
        │
        ▼
   One short reply (no progress spam, no server paths)
```

### Memory in plain language

1. **While you chat**, recent messages live in **Valkey** (fast, expires).
2. **Important facts** are written asynchronously into **Postgres** via Memory Manager (optional Qdrant index) so later sessions can recall them — not every joke or "ok".
3. **Documents** go through **ingest** into **`knowledge_chunks`**. At midnight **auto-learn** indexes eligible files from `/data/assistant` media (and inbound when a social app is attached). Empty search → say there is no information; **do not guess**; **do not use the internet** in Low.

### Off in Low

OCR, web search, file-gen, compact, Jobs, Grafana/Loki/Prom, AV, secret-probe, OpenBao, CloudDrive, Traefik, OpenVPN, Zalo unless attached.

### Editable UX strings

User-facing copy lives under `hermes/main/messages/` (e.g. `learn-notify.json`). Prefer skills + editable lists for cite/secret triggers instead of huge hardcoded adapter regexes.

### Paths

| Role | Path |
|---|---|
| Code | `/opt/assistant` or this clone |
| Data | `/data/assistant` |
| Backups | `/data/assistant/backups` |
| Skills | `hermes/main/skills` → mounted into Hermes data |
