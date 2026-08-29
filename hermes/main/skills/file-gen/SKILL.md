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

### Visual / weather / info PDF body (required shape)

When the user wants an attractive PDF (icons, layout, weather/fuel facts), put
**live facts already fetched** into the `prompt` like:

```text
TITLE: Thời tiết TP. Hồ Chí Minh
SUBTITLE: Cập nhật hiện tại
ICON: sun
- Nhiệt độ: 31°C (cảm giác 36°C)
- Độ ẩm: 70%
- Điều kiện: Nắng
```

`ICON` is one of: `sun` | `cloud` | `rain` | `storm`. Dispatcher draws a vector
icon + colored card layout with **Unicode fonts (Noto Sans)** — Vietnamese
diacritics must render correctly. **Do not** call `image-gen` / `/v1/image`
diffusion to decorate a PDF (diffusion bakes broken Vietnamese glyphs).

For a **standalone weather/info picture** (not a PDF), use
`POST /v1/image` with `"mode":"info-card"` and the same TITLE/ICON/fact body
(styles: `midnight` | `daylight` | `emerald` via `STYLE:` line).

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
