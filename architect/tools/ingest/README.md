# tools / ingest

## Purpose

Document ingestion and knowledge API: accept text/files, chunk, embed, upsert into Qdrant `knowledge_chunks`, and serve list/search for cite skills. Container name: `ingest`.

## Profile

Must (all profiles).

## Main functions

| Endpoint / job | Function |
|---|---|
| `POST /v1/learn/submit` | Always stage **pending**; notify sole Zalo admin (notify worker or bridge `/send` fallback). Admin: `!zalo learn approve` |
| `GET /v1/learn/list` | Catalog documents; `?q=&limit=5` |
| `POST /v1/search` | Vector search over chunks (`top_k` default 5) |
| `POST /v1/ingest` | Break-glass sync ingest |
| Midnight auto-learn | Scan media / docs roots → Qdrant |
| Notify templates | `hermes/main/messages/learn-notify.json` (editable) |

## Pipeline

```text
File or text
  → (High: security-manager isolation — YARA/static/limits; AV if ENABLE_ANTIVIRUS=1)
  → extract text (OCR on Medium+ if needed)
  → chunk → embedding → Qdrant knowledge_chunks
  → later: list/search → Hermes skill answers
```

## Titles in chat

Public list/cite uses short **titles** (content/product label), never `inbound/…` server paths.

## Env

`REDIS_URL` (Valkey; env name kept for RQ compatibility), `QDRANT_URL`, `EMBED_URL`, `LEARN_LIST_LIMIT`, `LEARN_REQUIRE_APPROVE` (scan/midnight auto-ingest when `0`; Zalo file submit always pending), `LEARN_NOTIFY_PATH`, `NOTIFY_URL`, `ZALO_BRIDGE_URL`, `ZALO_ADMIN_USERS_FILE`, media roots under `/data/assistant`.

Pending learn notify order: Notification Worker → bridge DM to sole admin (`zalo_admin_users.txt`). Do not leave pending silent when Notify Worker is inactive.

## Related

- [embedding](../embedding/README.md)  
- [ocr](../ocr/README.md)  
- [hermes/main/skills/knowledge-learn](../../../hermes/main/skills/knowledge-learn/SKILL.md)
