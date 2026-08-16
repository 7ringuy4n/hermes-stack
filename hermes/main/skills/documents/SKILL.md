---
name: documents
description: "MODE=documents — create/read/edit office & text files. RESULT-ONLY (see media-out). Prefer pdf|docx|xlsx + file-gen. Images → image-gen."
---

# Documents (md · txt · pdf · docx · xlsx · csv)

Follow skill **`media-out`** (result only). Medium+ when `OFFICE_FILE_GEN=1`. Hard refuse music/video. **Images** → **`image-gen`**.

## Official Hermes skills

| Format | Skill folder |
|---|---|
| PDF | `pdf/` |
| DOCX | `docx/` |
| XLSX / CSV | `xlsx/` |
| Scanned PDF / OCR | `vendor/hermes-media/ocr-and-documents/` or `ocr-deepseek` |

## Markdown / plain text

Write `.md` / `.txt` to **`/opt/data/media/out/<safe-name>.<ext>`**, then send via `file-gen`.

```bash
printf '%s\n' "# Title" "" "Body…" > /opt/data/media/out/note.md
```

## Must send

After creating a file: `POST http://dispatcher:8090/v1/send-file` with path + inbound `thread_id`. Reply per **`media-out`**.

## Do not

- Narrate steps / ask for approval / invent “cannot send file on Zalo”
- Dump server paths
- Generate music / video (images → **`image-gen`**)
