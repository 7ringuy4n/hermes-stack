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
    "prompt":"<user request, include format + body e.g. tạo file pdf điền số 1>",
    "thread_id":"<inbound thread id>",
    "thread_type":"user",
    "filename":"<safe-name.pdf>",
    "caption":""
  }'
```

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
- Ask for approval
- Dump server paths
- Generate images here → **`image-gen`**

## Related

- `media-out`, `documents`, `image-gen`
