# tools

## Purpose

Document and media **tooling** around Hermes: embed text, ingest into Qdrant knowledge, OCR (Medium+), and async Jobs workers (Medium+).

## Profile

| Package | Low | Medium | High |
|---|---|---|---|
| ingest, embedding | Must | Must | Must |
| ocr, jobs | Off | On | On |

## Sub-packages

| Package | Function |
|---|---|
| [ingest/](./ingest/README.md) | Learn submit, auto-learn, list/search knowledge, chunk/embed/upsert |
| [embedding/](./embedding/README.md) | Embedding HTTP facade → 9Router / upstream |
| [ocr/](./ocr/README.md) | PDF/image text extraction |
| [jobs/](./jobs/README.md) | RQ/Valkey workers for long OCR/ingest tasks |

## Knowledge vs chat memory

| Store | Collection / service | Use |
|---|---|---|
| Document RAG | Qdrant `knowledge_chunks` | Manuals, PDFs, specs |
| Chat LTM | Memory Manager / Postgres | User preferences / facts |

**List/find/cite:** top **5** results + count of the rest. If empty: say no information — **no guessing, no internet** on Low.

**Auto-learn @ 00:00:** promote eligible files into Qdrant without admin approve (`LEARN_REQUIRE_APPROVE=0`).

## Related

- [memory](../memory/README.md)  
- [models/dispatcher](../models/dispatcher/README.md)
