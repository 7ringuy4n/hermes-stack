---
name: markdown
description: "Create/edit Markdown (.md) and plain text (.txt), then send via file-gen. RESULT-ONLY (see media-out)."
---

# Markdown / text

Follow skill **`media-out`**. When the user wants a **`.md`** or **`.txt`** file:

1. Write UTF-8 to `/opt/data/media/out/<safe-name>.md` (or `.txt`).
2. Send with `file-gen` / `POST http://dispatcher:8090/v1/send-file`.
3. Reply: `Đã xong.` / `Done.` only (or short failure).

For **PDF / DOCX / XLSX** → `documents` + official `pdf` / `docx` / `xlsx` skills.
