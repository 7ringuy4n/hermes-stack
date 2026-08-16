# memory / mem0 — REMOVED from stack

This service is **no longer started** by `docker-compose.yml` (decision 2026-08-16).

Long-term conversational memory is owned by **Memory Manager** + **Postgres** (optional Qdrant index). Short-term session stays on **Valkey** (`session` service).

Source files here are retained only for reference / migration archaeology. Do not re-enable without an explicit product decision and MR.
