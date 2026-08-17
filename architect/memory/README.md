# memory

## Purpose

Everything that makes the agent **remember** across a turn and across days: short-term chat session and long-term typed memories. Memory Manager injects into the prompt under a token budget.

## Profile

**Must (all profiles).** Always on in Low.

## Sub-packages

| Package | Store | Function |
|---------|-------|----------|
| [memory-manager/](./memory-manager/README.md) | Postgres (+ optional Qdrant index) | `/v1/context`, `/v1/remember` — assemble mode/skills/memories; **canonical LTM** |
| [session/](./session/README.md) | Valkey | Active conversation, dest thread, timing helpers |

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
