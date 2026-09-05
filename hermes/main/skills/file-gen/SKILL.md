---
name: file-gen
description: "Create/edit office files (xlsx, docx, txt, pdf, csv, pptx, md) via Dispatcher. LLM authors full file content; worker renders. RESULT-ONLY (see media-out)."
---

# File generation → send (result only)

Follow skill **`media-out`**. When the user asks to **create / export / edit** an
**xlsx · csv · docx · txt · pdf · md · pptx** file:

## LLM authors content (required)

**You** decide structure, sections, tables, tone, and language.

### PDF (required format)

For `output_type=pdf`, the office-file `prompt` MUST be one of:

1. A complete **HTML document** (`<!DOCTYPE html>…`) with inline CSS — preferred for attractive layouts.
2. Raw PDF bytes starting with `%PDF`, or `PDF_BASE64:<base64>`.

Dispatcher converts HTML→PDF (WeasyPrint). Do **not** send markdown card templates, `IMAGE:` markers, `TITLE:` / `OVERVIEW:` schemas, or expect ReportLab layout.

Example HTML body:

```html
<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8"/>
<title>City briefing</title>
<style>
body{font-family:'Noto Sans',DejaVu Sans,Arial,sans-serif;margin:0;background:#e8eef5;color:#142033}
@page{size:A4;margin:14mm}
main{padding:0 2pt}
.accent{height:5pt;background:linear-gradient(90deg,#1a3a66,#2a6ebd 55%,#5eb0e0);margin:0 0 12pt;border-radius:2pt}
.hero{width:100%;max-height:280px;object-fit:cover;display:block;border-radius:10pt}
.band{background:#1a3a66;color:#fff;padding:16pt 18pt;margin:12pt 0 14pt;border-radius:10pt}
.band h1{font-size:22pt;margin:0 0 6pt;color:#fff}
.band h2{font-size:11pt;margin:0;color:#c5d6ea;font-weight:500}
.cards{display:table;width:100%;border-collapse:separate;border-spacing:8pt;margin:0 0 14pt}
.card{display:table-cell;width:50%;background:#fff;border:1pt solid #c8d6e8;border-radius:8pt;padding:12pt 14pt;vertical-align:top}
.k{font-size:8.5pt;color:#2a6ebd;text-transform:uppercase;letter-spacing:.05em}
.v{font-size:16pt;margin-top:5pt;font-weight:700;color:#0f1a28}
p{line-height:1.55;font-size:11pt;orphans:3;widows:3}
</style></head><body><main>
<div class="accent"></div>
<img class="hero" src="/opt/data/media/out/city-hero.jpg" alt=""/>
<div class="band"><h1>City briefing</h1><h2>Live snapshot</h2></div>
<div class="cards">
  <div class="card"><div class="k">Metric A</div><div class="v">…</div></div>
  <div class="card"><div class="k">Metric B</div><div class="v">…</div></div>
</div>
<p>Short supporting prose in the user's language.</p>
</main></body></html>
```

Never emit placeholders like `<value after search>`. Choose labels and language from the user ask (not a fixed weather schema).

Use one visible document title. Do not repeat a location, subject, or short heading as a standalone line above a hero/title band that already names it. The HTML `<title>` metadata does not count as a visible heading.

### PPTX / DOCX / XLSX / MD (presentation-ready)

For pptx/docx/md: compose markdown the worker understands (`#` title, `##` subtitle, `- Label: value`, short prose). Decks and reports must look presentation-ready — title, metrics, sections — not a chat dump.
For xlsx: labeled header row + metric rows with filled values only.

Fetch live facts with `web_search` when needed. Never paste search-page chrome into the body.

## Optional embedded visual (pdf|pptx|docx|xlsx|md)

Use a generated visual only when the user explicitly requests an image/photo inside the document. An attractive interface, polished layout, or a verb such as draw/render does not by itself request a separate image artifact.

1. **`web_search`** for live facts (labeled metrics only).
2. When explicitly requested, create one embeddable still via dispatcher (Omni keys on the worker — never built-in `image_generation`, never `execute_code`, never read `.env`):

```bash
curl -sS -X POST http://dispatcher:8090/v1/scenic-still \
  -H 'Content-Type: application/json' \
  -d '{"prompt":"Photorealistic photograph of Ho Chi Minh City skyline, real camera photo, natural lighting, highly detailed, not cartoon, not anime","filename":"hcm-hero.jpg","size":"1280x720"}'
```

Use `hermes_path` / `/opt/data/media/out/<file>` in PDF HTML `<img src="…">` (and note the path in pptx/docx bodies when useful). If scenic-still fails, omit the image and still deliver the file. Never mention credentials.
The still is an internal document asset. Do not send it separately; deliver only the requested office file.
3. Compose the **kind-specific body** (filled values only):
   - **pdf** — full HTML; WeasyPrint-safe CSS (`@page`, `display:table` metric rows — avoid Grid/Flex-only layouts).
   - **pptx|docx|md** — structured markdown slides/sections with metric bullets.
   - **xlsx** — clear metric sheet.
4. One **`POST /v1/office-file`** with that body and the exact `output_type` / filename extension.

Never `write_file` draft HTML/markdown under `/tmp` (outside `HERMES_WRITE_SAFE_ROOT`). Compose the body in the tool call JSON only and POST office-file so the worker writes `/opt/data/media/out/<file>`.

Do **not** rely on the host search→office shortcut for designed presentation docs — you must compose.
Never greet, never `/help`, never narrate tools, never mention missing API keys.
Never silently remap pptx/docx/xlsx → pdf.

## Default (must) — Dispatcher office API

Do **not** install `pypdf` / `weasyprint` / `openpyxl` / `python-pptx` in Hermes. Do **not** call
`skill_view` / `skill_manage` for ambiguous names `pdf` / `docx` / `xlsx` / `pptx`.
Never narrate library installs. Dispatcher owns PDF/PPTX rendering server-side.

```bash
curl -sS -X POST http://dispatcher:8090/v1/office-file \
  -H 'Content-Type: application/json' \
  -d '{
    "prompt":"<html document or pptx markdown you authored>",
    "thread_id":"<inbound thread id>",
    "thread_type":"user",
    "filename":"<safe-name.pdf|safe-name.pptx>",
    "output_type":"pdf",
    "caption":""
  }'
```

For PPTX: markdown body, `output_type=pptx`, filename ending `.pptx`.

Requires Media|File worker with `OFFICE_FILE_GEN=active`. Success: `"ok":true` and
Zalo receives the file (empty caption). User-facing text per **media-out**:
**file only**.

## Fallback (txt/md only)

If office-file returns 503, write plain text then `send-file` (see prior skill text).

## Do not

- Pass the user's create sentence verbatim as `prompt`
- Dump SERP titles or navigation chrome into the PDF body
- Block PDF delivery on image-backend failure — finish HTML layout; omit `<img>` if gen failed
- Use ReportLab / markdown-card layouts for PDF

## Related

- `media-out`, `documents`, `image-gen`
