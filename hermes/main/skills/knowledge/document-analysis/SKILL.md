---
name: document-analysis
description: "Analyze PDF/DOCX/XLSX and structured files. Use for extract, summarize, forms, tables — routes to document skills."
---

# Document analysis

## Route by type

| Type | Skill |
|---|---|
| PDF | `pdf`, `official/pdf` |
| Word | `docx`, `official/docx` |
| Excel | `xlsx`, `official/xlsx` |
| Mixed / create | `documents`, `file-gen` |

## Must follow

1. Use skill **scripts** under each document skill — do not guess binary formats.
2. Scanned PDFs → OCR path (dispatcher/upload), not fake text extraction.
3. Output structured results (JSON/tables) when the user needs data, not prose-only.

## Sources

Anthropic document skills (already in `hermes/main/skills/{pdf,docx,xlsx}`). Upstream: anthropics/skills.
