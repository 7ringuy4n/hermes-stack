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
<html lang="vi"><head><meta charset="utf-8"/>
<title>Thời tiết TP.HCM</title>
<style>
body{font-family:'Noto Sans',DejaVu Sans,Arial,sans-serif;margin:0;background:#eef3f8;color:#142033}
@page{size:A4;margin:18mm 16mm}
main{padding:0}
.hero{width:100%;max-height:260px;object-fit:cover;display:block;border-radius:10pt}
.band{background:#1a3a66;color:#fff;padding:14pt 16pt;margin:12pt 0 14pt;border-radius:8pt}
.band h1{font-size:20pt;margin:0 0 4pt;color:#fff}
.band h2{font-size:11pt;margin:0;color:#cfe0f5;font-weight:600}
.cards{display:table;width:100%;border-collapse:separate;border-spacing:8pt;margin:0 0 14pt}
.card{display:table-cell;width:50%;background:#fff;border:1pt solid #d0deed;border-radius:8pt;padding:10pt 12pt;vertical-align:top}
.k{font-size:9pt;color:#2a6ebd;text-transform:uppercase;letter-spacing:.04em}
.v{font-size:16pt;margin-top:4pt;font-weight:700}
p{line-height:1.5;font-size:11pt;orphans:3;widows:3}
</style></head><body><main>
<img class="hero" src="/opt/data/media/out/hcm-hero.jpg" alt=""/>
<div class="band"><h1>Thời tiết TP. Hồ Chí Minh</h1><h2>Cập nhật hiện tại</h2></div>
<div class="cards">
  <div class="card"><div class="k">Nhiệt độ</div><div class="v">31°C</div></div>
  <div class="card"><div class="k">Độ ẩm</div><div class="v">70%</div></div>
</div>
<div class="cards">
  <div class="card"><div class="k">Thời tiết</div><div class="v">Nắng nhẹ</div></div>
  <div class="card"><div class="k">Gió</div><div class="v">12 km/h</div></div>
</div>
<p>Trời nắng nhẹ, oi bức.</p>
</main></body></html>
```

Never emit placeholders like `<value after search>`. Spell Vietnamese labels correctly (Nhiệt độ, Thời tiết, Độ ẩm, Gió).

### PPTX / DOCX / XLSX / MD (presentation-ready)

For pptx/docx/md: compose markdown the worker understands (`#` title, `##` subtitle, `- Label: value`, short prose). Decks and reports must look presentation-ready — title, metrics, sections — not a chat dump.
For xlsx: labeled header row + metric rows with filled values only.

Fetch live facts with `web_search` when needed. Never paste search-page chrome into the body.

## Visual presentation docs with city / hero photo (pdf|pptx|docx|xlsx|md)

Applies to **every** presentation-capable office kind the user named — not PDF-only.

1. **`web_search`** for live facts (labeled metrics only).
2. Hero still via dispatcher (Omni keys on the worker — never built-in `image_generation`, never `execute_code`, never read `.env`):

```bash
curl -sS -X POST http://dispatcher:8090/v1/scenic-still \
  -H 'Content-Type: application/json' \
  -d '{"prompt":"Photorealistic photograph of Ho Chi Minh City skyline, real camera photo, natural lighting, highly detailed, not cartoon, not anime","filename":"hcm-hero.jpg","size":"1280x720"}'
```

Use `hermes_path` / `/opt/data/media/out/<file>` in PDF HTML `<img src="…">` (and note the path in pptx/docx bodies when useful). If scenic-still fails, omit the image and still deliver the file. Never mention credentials.
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
