# tools

## System architecture

| | |
|--|--|
| **Sits between** | Hermes / timers ↔ Qdrant (+ OCR/jobs workers) |
| **Owns** | Document ingest, embeddings, OCR (Med+), RQ jobs (Med+) |
| **Does not own** | Conversational LTM (that is [memory](../memory/README.md)) |

<table style="width:100%;border-collapse:collapse;font-size:13px;">
  <tr>
    <td style="padding:12px;background:#f5f5f5;border:1px solid #ddd;text-align:center;width:28%;">Files / Hermes / jobs</td>
    <td style="padding:8px;background:#eee;text-align:center;width:4%;">→</td>
    <td style="padding:14px;background:#2563eb;color:#fff;text-align:center;border:3px solid #fbbf24;width:36%;"><b>ingest · OCR · embedding</b></td>
    <td style="padding:8px;background:#eee;text-align:center;width:4%;">→</td>
    <td style="padding:12px;background:#e8f4ea;border:1px solid #c5e0c8;text-align:center;width:28%;">Qdrant knowledge_chunks</td>
  </tr>
</table>

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
| [embedding/](./embedding/README.md) | Embedding HTTP facade → OmniRoute / upstream |
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
- [docs/03-architecture.md](../../docs/03-architecture.md)
