# memory / memory-manager

## Purpose

Central Memory Manager Hermes calls instead of growing a giant `MEMORY.md`. Postgres is the source of truth for typed memories; optional Qdrant index helps retrieval. Exposes context assembly and remember APIs.

## Profile

Must — container `memory`.

## Main functions

| API / job | Function |
|---|---|
| `POST /v1/context` | Given user text (+ flags), return mode hints, skills list, budgeted memories |
| `POST /v1/remember` | Persist a durable fact/event (async from agent) |
| Compact hook | Medium+ midnight compact may slim stale rows (silent) |

## Memory kinds (conceptual)

| Kind | Meaning |
|---|---|
| Working | Ephemeral turn hints (not long-lived here) |
| Episodic | Events / interactions |
| Semantic | Facts, preferences, decisions |
| Procedural | Pointers to skills on disk (`hermes/main/skills`) |

## Env (typical)

`DATABASE_URL`, `REDIS_URL` (Valkey; env name kept for clients), `QDRANT_URL`, `CONTEXT_BUDGET_TOKENS`, `TZ`

## Related

- [../README.md](../README.md)  
- [session](../session/README.md)
