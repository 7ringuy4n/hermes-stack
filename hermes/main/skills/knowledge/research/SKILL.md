---
name: research
description: "Research workflow: compare sources, synthesize evidence. Use for tin tức, lookup, compare options, or 'tìm hiểu' — not for pure chat opinion."
---

# Research

## Must follow

1. State **question** and **success criteria** in one line.
2. Gather **multiple sources** when profile allows (`tavily`, `firecrawl`, `searxng`, dispatcher search).
3. **Synthesize** — agree/disagree across sources; cite titles/URLs briefly (no dump).
4. Mark gaps and recency limits.

## Tools

- Prefer `http://model-router:8096/v1/search|extract` and vendored `vendor/tavily/*`, `vendor/firecrawl/*`.
- Low profile: local knowledge only unless operator enables web.

## Confidential/internal technical docs

If the user request is about internal technical documentation (Hermes stack, software docs, configuration, READMEs, ADRs, specs/changelogs) treat it as *confidential/internal*:
- prefer **local** `knowledge_chunks` first (no browsing as a fallback)
- do not guess when retrieval is empty
- only use web research when the user explicitly asks for public, external references that are not in your local knowledge

## Sources

VoltAgent + Anthropic catalog patterns.
