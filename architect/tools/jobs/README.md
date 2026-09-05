# tools / jobs

## Purpose

Async workers (RQ + Valkey) for long OCR/ingest/file tasks so the HTTP path stays fast under load.

## Profile

Media worker (`ENABLE_JOBS=active`). Core ingest does not require this worker.

## Main functions

| Function | Detail |
|---|---|
| Queue consumer | BLPOP / RQ on shared Valkey |
| Job types | OCR, ingest, future file-gen |

## Related

- [../README.md](../README.md)  
- [ingest](../ingest/README.md)
