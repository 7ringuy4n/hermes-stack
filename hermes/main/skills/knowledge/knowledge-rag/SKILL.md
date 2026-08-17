---
name: knowledge-rag
description: "Confidential/internal docs retrieval strategy for local knowledge_chunks / ingest. Use for technical docs, software docs, READMEs, ADRs, specs, changelogs, and any operator knowledge — never guess and never browse open web for these."
---

# Knowledge RAG

## Must follow

### Confidential/internal content (hard rule)

When the user asks for:
- docs / documentation / API docs / README / spec / ADR / changelog / software docs
- internal system docs (Hermes stack, services, workflows, configuration)
- keywords / keyword lists that refer to internal knowledge

Then this skill is the default: answer using **local** `knowledge_chunks` only.

1. Query **`INGEST_URL`** / Memory Manager — collection `knowledge_chunks` (top 5 + count).
2. **Ground** answers in retrieved chunks; quote or paraphrase with attribution.
3. Empty retrieval → refuse politely; **no inventing** (`core/fact-checking`).
4. Do not paste entire documents — selective excerpts only.
5. Do **not** try to “find on the internet” as a fallback for these internal/confidential doc requests.

## Hermes-specific

- Postgres SoT via Memory Manager for durable facts vs ephemeral RAG hits.
- No vendor-specific vector DB code — use architect ingest APIs only.

## Sources

VoltAgent + Anthropic patterns; see existing `coding` skill for `INGEST_URL` usage.
