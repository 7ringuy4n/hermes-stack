---
name: documents
description: "MODE=documents — create/read/edit office & text files (md, txt, pdf, docx, xlsx, csv). Prefer official pdf|docx|xlsx skills + file-gen send path. Images → image-gen."
---

# Documents (md · txt · pdf · docx · xlsx · csv)

Medium+ only when `OFFICE_FILE_GEN=1`. Hard refuse music/video. **Generate image / wallpaper / poster** → skill **`image-gen`** (save under `/opt/data/media/out/` only).

## Official Hermes skills (bundled upstream)

Use these folders under `/opt/data/skills/` (bind-mounted from `hermes/main/skills`):

| Format | Skill folder | Upstream docs |
|---|---|---|
| PDF | `pdf/` | https://hermes-agent.nousresearch.com/docs/user-guide/skills/bundled/productivity/productivity-pdf |
| DOCX | `docx/` | https://hermes-agent.nousresearch.com/docs/user-guide/skills/bundled/productivity/productivity-docx |
| XLSX / CSV | `xlsx/` | https://hermes-agent.nousresearch.com/docs/user-guide/skills/bundled/productivity/productivity-xlsx |
| Scanned PDF / OCR | `vendor/hermes-media/ocr-and-documents/` or `ocr-deepseek` | productivity-ocr-and-documents |

Source: [NousResearch/hermes-agent](https://github.com/NousResearch/hermes-agent) `skills/productivity/{pdf,docx,xlsx}`.

## Markdown / plain text

- Write `.md` / `.txt` with the shell or Python (`pathlib`). No special library.
- Output path: **`/opt/data/media/out/<safe-name>.<ext>`** then send via `file-gen` / dispatcher.

```bash
printf '%s\n' "# Title" "" "Body…" > /opt/data/media/out/note.md
```

## Must send to requester

After creating a file, follow **`file-gen`**: `POST http://dispatcher:8090/v1/send-file` with that path + inbound `thread_id`. One short chat line only.

## Do not

- Invent “cannot send file on Zalo”
- Dump server paths to the user (except confirming `/opt/data/media/out/…` when they asked for a local file)
- Generate music / video here (images → **`image-gen`**)