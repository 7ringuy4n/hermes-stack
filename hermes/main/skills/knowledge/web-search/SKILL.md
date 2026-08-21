---
name: web-search
description: "Search strategy and source selection for current information. Use when facts may be stale in training data or user asks for latest/news/prices."
---

# Web search

## User-facing

Send **only the final answer** (and a generated file if the user asked for one). Never send process lines (“Now I have the page…”, “Let me analyze both images…”, “Mình đang lấy…”).

## Strategy

1. **Query shaping** — keywords + site/time hints; Vietnamese and English variants if needed.
2. **Search** — Router Worker combo `POST http://model-router:8096/v1/search` (combo order Tavily → SearXNG; SearXNG is the local last resort). Never call the media worker for search.
3. **Extract** — `POST http://model-router:8096/v1/extract` on the best URL. Do **not** use SearXNG for extract (it cannot). If extract fails, stop with a short failure line.
4. **Page images** — if the useful content is in **images** (tables, posted prices, charts):
   1. Download the image to `/opt/data/media/in/<safe>.jpg` (same volume as OCR).
   2. `POST http://ocr:8091/v1/ocr` with `{ "path": "/data/media/in/<safe>.jpg" }`.
   3. Use the OCR text as the source of truth.
   4. If the user asked for an **image** of that result, call `image-gen` / dispatcher `POST /v1/image` with the OCR facts in the prompt. Do not overlay with local PIL/pip in the chat turn.
5. **Answer** — lead with the finding; note date/locale if relevant. No “want me to resend?”.

## Lyrics / “tìm lời bài hát”

When the user asks for lyrics and a recent audio/video attachment (or a quoted message) already names the song/artist (e.g. `Multo - Cup of Joe ….mp3`):

1. Use that title/artist as the search query immediately.
2. Do **not** ask “which song?” when the filename or quoted context is clear.
3. Search via Router Worker `/v1/search`, then answer with the lyrics (or a short failure if none found).

## Note

This skill controls **behavior**; execution uses Router Worker search + OCR. Media generation stays on the Media/File worker. See `vendor/tavily/tavily-best-practices`.

## Confidential/internal docs (hard rule)

If the user request looks like it targets **internal technical docs / software docs** (examples: “docs”, “documentation”, “API docs”, “README”, “ADR”, “spec”, “changelog”, “tài liệu kỹ thuật/phần mềm”):
- Do **not** browse the open web.
- Instead, answer from local `knowledge_chunks` (use `knowledge-rag`) and be explicit if retrieval is empty.

## Sources

VoltAgent awesome-agent-skills (catalog).
