# tools / embedding

## Purpose

Thin HTTP service that turns text into vectors for ingest and search. Forwards to an OpenAI-compatible upstream (usually 9Router).

## Profile

Must — container `embedding`.

## Main functions

| Function | Detail |
|---|---|
| Embed batch | Used by ingest upsert and `/v1/search` |
| Model id | From env (`EMBED_MODEL`) |

## Related

- [ingest](../ingest/README.md)  
- [models](../../models/README.md)
