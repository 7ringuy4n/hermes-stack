# tools / embedding

## Purpose

Thin HTTP service that turns text into vectors for ingest and search.

## Profile

Must — container `embedding`.

## Main functions

| Function | Detail |
|---|---|
| Embed batch | Used by ingest upsert and `/v1/search` |
| Upstream | OpenAI-compatible 9Router when `EMBED_API_KEY` / `N9ROUTER_API_KEY` is set |
| Local fallback | ONNX `BAAI/bge-small-en-v1.5` when upstream has no embedding credentials/models (`EMBED_LOCAL_FALLBACK=1`, default) |

## Env

| Variable | Default | Meaning |
|---|---|---|
| `EMBED_UPSTREAM` | `http://9router:20128/v1` | OpenAI-compatible embeddings URL |
| `EMBED_API_KEY` | `N9ROUTER_API_KEY` | Bearer for upstream |
| `EMBED_MODEL` | `openai/text-embedding-3-small` | Preferred upstream model id |
| `EMBED_BACKEND` | `auto` | `auto` / `upstream` / `local` |
| `EMBED_LOCAL_FALLBACK` | `1` | Use local ONNX after upstream failure |
| `EMBED_LOCAL_MODEL` | `BAAI/bge-small-en-v1.5` | fastembed model id |

## Related

- [ingest](../ingest/README.md)  
- [models](../../models/README.md)
