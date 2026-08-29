---
name: file-gen
description: "Create/edit office files (xlsx, docx, txt, pdf, csv) via Dispatcher and deliver on Zalo. RESULT-ONLY (see media-out). Images → image-gen."
---

# File generation → send (result only)

Follow skill **`media-out`**. When the user asks to **create / export / edit** an
**xlsx · csv · docx · txt · pdf · md** file:

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
    "prompt":"<structured body>",
    "thread_id":"<inbound thread id>",
    "thread_type":"user",
    "filename":"<safe-name.pdf>",
    "output_type":"pdf",
    "caption":""
  }'
```

### Visual / attractive PDF body (required shape)

When the user wants an attractive PDF (icons, layout, designed look — any topic), put
**live facts already fetched** into the `prompt` like:

```text
TITLE: <topic or place>
SUBTITLE: <optional context>
ICON: <optional short motif token>
- <label>: <value>
- <label>: <value>
```

Dispatcher styles the sheet (Unicode-safe fonts, icons when motif/facts fit). Do not
call diffusion `/v1/image` to paint labels onto a PDF. Scenic LLM/diffusion images
are optional decoration only and must never block PDF delivery.

In-document visuals stay on **one** `office-file` PDF. Optionally also send a
standalone `info-card` PNG via **`image-gen`** if they clearly want a separate
picture; never fail the PDF on image-backend 502.

Requires Media|File worker with `OFFICE_FILE_GEN=1`. Success: `"ok":true` and
Zalo receives the file (empty caption). User-facing text per **media-out**:
**file only** — no “Đã tạo file…” sentence.

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
- Generate decorative images here → only **`image-gen`** when the user asked for a **standalone** picture

## Related

- `media-out`, `documents`, `image-gen`
