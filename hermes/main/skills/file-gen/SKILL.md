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
body{font-family:sans-serif;margin:0;background:#f4f7fb;color:#142033}
main{padding:28px}
.hero{width:100%;max-height:280px;object-fit:cover;border-radius:12px}
.cards{display:grid;grid-template-columns:1fr 1fr;gap:12px}
.card{background:#fff;border:1px solid #d9e6f5;border-radius:12px;padding:12px}
.k{font-size:12px;color:#2a6ebd}.v{font-size:18px}
</style></head><body><main>
<img class="hero" src="/opt/data/media/out/hcm-hero.jpg" alt=""/>
<h1>Thời tiết TP. Hồ Chí Minh</h1>
<h2>Cập nhật hiện tại</h2>
<div class="cards">
  <div class="card"><div class="k">Nhiệt độ</div><div class="v">31°C</div></div>
  <div class="card"><div class="k">Độ ẩm</div><div class="v">70%</div></div>
</div>
<p>Trời nắng nhẹ, oi bức.</p>
</main></body></html>
```

Never emit placeholders like `<value after search>`. Spell Vietnamese labels correctly (Nhiệt độ, Thời tiết, Độ ẩm, Gió).

### PPTX / other office

For pptx/xlsx/docx/txt/md: compose markdown or plain lines the worker understands (`#` title, `##` subtitle, `- Label: value`).

Fetch live facts with `web_search` when needed. Never paste search-page chrome into the body.

## Visual PDF with city / hero photo

1. **`web_search`** for live facts (labeled metrics only).
2. Hero still via dispatcher (Omni keys on the worker — never built-in `image_generation`, never `execute_code`, never read `.env`):

```bash
curl -sS -X POST http://dispatcher:8090/v1/scenic-still \
  -H 'Content-Type: application/json' \
  -d '{"prompt":"Photorealistic photograph of Ho Chi Minh City skyline, real camera photo, natural lighting, highly detailed, not cartoon, not anime","filename":"hcm-hero.jpg","size":"1280x720"}'
```

Use `hermes_path` / `/opt/data/media/out/<file>` in an HTML `<img src="…">`. If scenic-still fails, omit the image and still deliver the PDF. Never mention credentials.
3. Compose the **HTML document** (filled values only).
4. One **`POST /v1/office-file`** with that HTML as `prompt` (`output_type=pdf`).

Do **not** rely on the host search→office shortcut for designed PDFs — you must compose.
Never greet, never `/help`, never narrate tools, never mention missing API keys.

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
