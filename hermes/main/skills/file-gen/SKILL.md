---
name: file-gen
description: "Create/edit office files (xlsx, docx, txt, pdf, csv) via Dispatcher. LLM authors full file content; worker renders. RESULT-ONLY (see media-out)."
---

# File generation → send (result only)

Follow skill **`media-out`**. When the user asks to **create / export / edit** an
**xlsx · csv · docx · txt · pdf · md** file:

## LLM authors content (required)

**You** decide structure, sections, tables, tone, and language. Compose the complete
file body for `prompt` — prose, markdown, bullet lists, tables, or any layout that fits
the ask. Fetch live facts with `web_search` when needed, then weave them into your draft.

Do **not** use a fixed marker schema (`TITLE:`, `OVERVIEW:`, `SHEET:`, etc.). The worker
renders what you write; it does not impose a weather card or dashboard template.

## Default (must) — Dispatcher office API

Do **not** install `pypdf` / `reportlab` / `openpyxl` in Hermes. Do **not** call
`skill_view` / `skill_manage` for ambiguous names `pdf` / `docx` / `xlsx` (name
collisions refuse to load — that path fails and leaves the user with no file).
Never narrate reportlab/pip/uv. Dispatcher owns PDF rendering server-side.

Create **and** deliver in one call:

```bash
curl -sS -X POST http://dispatcher:8090/v1/office-file \
  -H 'Content-Type: application/json' \
  -d '{
    "prompt":"<full file body you authored>",
    "thread_id":"<inbound thread id>",
    "thread_type":"user",
    "filename":"<safe-name.pdf>",
    "output_type":"pdf",
    "caption":""
  }'
```

Requires Media|File worker with `OFFICE_FILE_GEN=active`. Success: `"ok":true` and
Zalo receives the file (empty caption). User-facing text per **media-out**:
**file only** — no “Đã tạo file…” sentence.

Standalone scenic images (not inside the PDF) → **`image-gen`** only when the user
clearly wants a separate picture; never block PDF delivery on image-backend failure.

## Fallback (txt/md only)

If office-file returns 503, write a plain text file then send:

```bash
printf '%s\n' "1" > /opt/data/media/out/number.txt
curl -sS -X POST http://dispatcher:8090/v1/send-file \
  -H 'Content-Type: application/json' \
  -d '{"path":"/opt/data/media/out/number.txt","thread_id":"<id>","thread_type":"user","caption":""}'
```

Autosend may also pick up a new file under `/opt/data/media/out/` — never both
office-file **and** a second send for the same file.

## Do not

- Narrate pip/uv install failures or invent “file created” when tools failed
- Ask for approval or for API keys / backend config
- Dump server paths
- Block a PDF deliverable on image-backend failures — finish the PDF via office-file
- Force weather/dashboard/screen templates — layout is your choice per the user ask

## Related

- `media-out`, `documents`, `image-gen`
