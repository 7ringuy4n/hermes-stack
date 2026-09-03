---
name: file-gen
description: "Create/edit office files (xlsx, docx, txt, pdf, csv) via Dispatcher. LLM authors full file content; worker renders. RESULT-ONLY (see media-out)."
---

# File generation → send (result only)

Follow skill **`media-out`**. When the user asks to **create / export / edit** an
**xlsx · csv · docx · txt · pdf · md** file:

## LLM authors content (required)

**You** decide structure, sections, tables, tone, and language. Compose the complete
file body for `prompt` — **markdown** the worker understands:

```text
# Main title
## Subtitle or date line
IMAGE: /opt/data/media/out/hero.png
- Nhiệt độ: 31°C
- Độ ẩm: 70%
Short prose paragraph when needed.
```

Fetch live facts with `web_search` when needed, then weave them into your draft.
Never paste search-page chrome, district lists, or raw JSON into the body.

Do **not** use legacy marker schemas (`TITLE:`, `OVERVIEW:`, `SHEET:`). The worker
renders markdown + optional `IMAGE:` — not the user's raw create sentence.

## Visual PDF with city / hero photo

When the user wants an **attractive PDF with city imagery**:

1. Run **`web_search`** for live facts (keep only labeled metrics).
2. Create the hero still via **dispatcher** (has Omni keys — never the built-in
   `image_generation` tool, never `execute_code`, never read `.env`):

```bash
curl -sS -X POST http://dispatcher:8090/v1/scenic-still \
  -H 'Content-Type: application/json' \
  -d '{"prompt":"Photorealistic photograph of Ho Chi Minh City skyline, real camera photo, natural lighting, highly detailed, not cartoon, not anime","filename":"hcm-hero.jpg","size":"1280x720"}'
```

Use the JSON `hermes_path` (or `/opt/data/media/out/<file>`). If this call fails, omit IMAGE and still deliver the PDF. Never tell the user about credentials, keys, or backends.
3. Compose markdown **exactly** in this shape (no create sentence, no SERP chrome,
   no markdown tables):

```text
# Title
## Subtitle or update time
IMAGE: /opt/data/media/out/<hero>.jpg
- Label: value
- Label: value
One short prose paragraph optional.
```

4. One **`POST /v1/office-file`** with that prompt (`output_type=pdf`).

Do **not** rely on the host search→office shortcut for designed PDFs — you must compose.
Never greet, never `/help`, never narrate tools, never mention missing API keys.

## Default (must) — Dispatcher office API

Do **not** install `pypdf` / `reportlab` / `openpyxl` in Hermes. Do **not** call
`skill_view` / `skill_manage` for ambiguous names `pdf` / `docx` / `xlsx`.
Never narrate reportlab/pip/uv. Dispatcher owns PDF rendering server-side.

```bash
curl -sS -X POST http://dispatcher:8090/v1/office-file \
  -H 'Content-Type: application/json' \
  -d '{
    "prompt":"<markdown body you authored>",
    "thread_id":"<inbound thread id>",
    "thread_type":"user",
    "filename":"<safe-name.pdf>",
    "output_type":"pdf",
    "caption":""
  }'
```

Requires Media|File worker with `OFFICE_FILE_GEN=active`. Success: `"ok":true` and
Zalo receives the file (empty caption). User-facing text per **media-out**:
**file only**.

## Fallback (txt/md only)

If office-file returns 503, write plain text then `send-file` (see prior skill text).

## Do not

- Pass the user's create sentence verbatim as `prompt`
- Dump SERP titles or navigation chrome into the PDF body
- Block PDF delivery on image-backend failure — finish text layout; omit IMAGE if gen failed

## Related

- `media-out`, `documents`, `image-gen`
