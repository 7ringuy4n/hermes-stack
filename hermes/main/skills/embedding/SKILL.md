---
name: embedding
description: "Embeddings for memory/knowledge compact via embedding service using combo embedding (Omni /embeddings, then OmniRoute)."
---

# Embedding

Used by ingest, memory compact, and knowledge optimize — not a user-facing chat skill.

**Stack path:** `POST http://embedding:8094/v1/embeddings` (or `/embeddings`)

Upstream:

1. OmniRouter `POST /v1/embeddings` with `model=embedding` (`EMBED_MODEL`)
2. OmniRoute OpenAI-compatible embeddings when Omni unavailable and OmniRoute is enabled
3. Local ONNX fallback only when `EMBED_LOCAL_FALLBACK=1`

Hermes must **not** invent embedding vectors, call external embed HTTP, or ask the user for OpenAI embed keys. Operators fill combo **`embedding`** members in OmniRouter / OmniRoute UI.

## Related

- Memory / knowledge workers use this service automatically on compact/optimize
