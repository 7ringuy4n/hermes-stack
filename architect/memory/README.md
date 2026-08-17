# memory

## System architecture

| | |
|--|--|
| **Sits between** | Hermes ↔ stores |
| **Owns** | Short-term turns (session/Valkey) + durable facts (memory-manager/Postgres) |
| **Does not own** | Document RAG (`knowledge_chunks` — that is [tools/ingest](../tools/ingest/README.md)) |

<table style="width:100%;border-collapse:collapse;font-size:13px;">
  <tr>
    <td style="padding:12px;background:#f5f5f5;border:1px solid #ddd;text-align:center;width:28%;">Hermes</td>
    <td style="padding:8px;background:#eee;text-align:center;width:4%;">→</td>
    <td style="padding:14px;background:#2563eb;color:#fff;text-align:center;border:3px solid #fbbf24;width:36%;"><b>session + memory-manager</b></td>
    <td style="padding:8px;background:#eee;text-align:center;width:4%;">→</td>
    <td style="padding:12px;background:#e8f4ea;border:1px solid #c5e0c8;text-align:center;width:28%;">Valkey · Postgres</td>
  </tr>
</table>

## Purpose

Everything that makes the agent **remember** across a turn and across days: short-term chat session and long-term typed memories. Memory Manager injects into the prompt under a token budget.

## Profile

**Must (all profiles).** Always on in Low.

## Sub-packages

| Package | Store | Function |
|---------|-------|----------|
| [memory-manager/](./memory-manager/README.md) | Postgres (+ optional Qdrant index) | `/v1/context`, `/v1/remember` — assemble mode/skills/memories; **canonical LTM** |
| [session/](./session/README.md) | Valkey | Active conversation, dest thread, locks, timing helpers |

Conversational long-term memory is **Memory Manager + Postgres** only.

## How short-term and long-term work together

```text
Turn N
  1. session (Valkey) loads last messages for this thread (TTL, e.g. ~1 day)
  2. memory-manager builds context within CONTEXT_BUDGET_TOKENS
       - skills pointers
       - typed Postgres memories (+ optional Qdrant retrieval)
  3. Hermes answers
  4. Async: remember durable facts → Postgres via /v1/remember
       (never spam the user with “saved memory” bubbles)

Later day
  Valkey session may be empty (TTL expired)
  Postgres still supplies “user prefers …” facts via Memory Manager
```

**Not** the same as document RAG (`knowledge_chunks` in tools/ingest). Do not put PDF bodies into conversational memory as “preferences”.

## Related

- [tools/ingest](../tools/ingest/README.md) — document knowledge  
- [docs/01-workflow.md](../../docs/01-workflow.md)  
- [docs/03-architecture.md](../../docs/03-architecture.md)  
- [docs/MULTI_NODE.md](../../docs/MULTI_NODE.md) — Valkey/Postgres SPOFs
