---
name: web-search-strategy
description: "Search strategy and source selection for current information. Use when facts may be stale in training data or user asks for latest/news/prices."
---

# Web search

## User-facing

Send **only the final answer** (and a generated file if the user asked for one). Never send process lines (“Now I have the page…”, “Let me analyze both images…”, “Mình đang lấy…”).

## Strategy

1. **Query shaping** — keywords + site/time hints; Vietnamese and English variants if needed.
2. **Search** — always `POST http://model-router:8096/v1/search` (combo **web-search**:
   OmniRoute `/v1/search` with Tavily → Firecrawl → SearXNG, then direct adapters). Never call Omni
   chat completions or the media worker for search.
3. **Extract** — `POST http://model-router:8096/v1/extract` on the best URL (extract
   backends from config; SearXNG cannot extract). If extract fails, stop with a short failure line.
4. **Page images** — if the useful content is in **images** (tables, posted prices, charts):
   1. Download the image to `/opt/data/media/in/<safe>.jpg` (shared media volume).
   2. Read via vision-ocr combo (router-worker `POST /v1/chat/completions` model `vision-ocr`, or ingest/dispatcher `vision_read`).
   3. Use the extracted text as the source of truth.
   4. If the user asked for an **image** of that result, call skill `image-gen` (Omni `/images/generations` model `image-gen`) with the facts in the English prompt.
5. **Answer** — lead with the finding; note date/locale if relevant. No “want me to resend?”.

## Lyrics / “tìm lời bài hát”

When the user asks for lyrics and a recent audio/video attachment (or a quoted message) already names the song/artist (e.g. `Multo - Cup of Joe ….mp3`):

1. Use that title/artist as the search query immediately.
2. Do **not** ask “which song?” when the filename or quoted context is clear.
3. Search via Router Worker `/v1/search` (Omni-backed), then answer with the lyrics (or a short failure if none found).

## Note

This skill controls **behavior**; execution uses Omni search (via Router Worker) + OCR. Media generation stays on the Media/File worker. See `vendor/tavily/tavily-best-practices`.

## Confidential/internal docs (hard rule)

If the user request looks like it targets **internal technical docs / software docs** (examples: “docs”, “documentation”, “API docs”, “README”, “ADR”, “spec”, “changelog”, “tài liệu kỹ thuật/phần mềm”):
- Do **not** browse the open web.
- Instead, answer from local `knowledge_chunks` (use `knowledge-rag`) and be explicit if retrieval is empty.

## Sources

VoltAgent awesome-agent-skills (catalog).
