---
name: web-search
description: "Search strategy and source selection for current information. Use when facts may be stale in training data or user asks for latest/news/prices."
---

# Web search

## Strategy

1. **Query shaping** — keywords + site/time hints; Vietnamese and English variants if needed.
2. **Source quality** — prefer official docs, primary publishers; deprioritize SEO farms.
3. **Extract** — follow search with extract/read on best URLs (dispatcher or Firecrawl).
4. **Answer** — lead with finding; note date/locale if relevant.

## Note

This skill controls **behavior**; execution uses Hermes tools/MCP (`tavily`, `firecrawl`, `searxng`, dispatcher). See `vendor/tavily/tavily-best-practices`.

## Confidential/internal docs (hard rule)

If the user request looks like it targets **internal technical docs / software docs** (examples: “docs”, “documentation”, “API docs”, “README”, “ADR”, “spec”, “changelog”, “tài liệu kỹ thuật/phần mềm”):
- Do **not** browse the open web.
- Instead, answer from local `knowledge_chunks` (use `knowledge-rag`) and be explicit if retrieval is empty.

## Sources

VoltAgent awesome-agent-skills (catalog).
