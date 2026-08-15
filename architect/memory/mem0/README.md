# memory / mem0

## Purpose

Long-term **conversational** memory service (Mem0-compatible). Stores user facts in a Qdrant collection such as `conversational_memory`, separate from document `knowledge_chunks`.

## Profile

Must — container `mem0`.

## Main functions

| Function | Detail |
|---|---|
| Add memory | After a turn, store durable facts |
| Search | Retrieve facts relevant to the current question |
| Compact | Optional High/Medium maintenance |

## Related

- [../README.md](../README.md)  
- [tools/ingest](../../tools/ingest/README.md) — do not mix with RAG docs
