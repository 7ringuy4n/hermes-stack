---
name: markdown
description: Create or edit Markdown (.md) and plain text (.txt) notes/docs, then send via file-gen.
---

# Markdown / text

When the user wants a **`.md`** or **`.txt`** file:

1. Write UTF-8 content to `/opt/data/media/out/<safe-name>.md` (or `.txt`).
2. Send with `file-gen` / `POST http://dispatcher:8090/v1/send-file`.
3. Chat: one short ack only.

For **PDF / DOCX / XLSX** → use `documents` + official `pdf` / `docx` / `xlsx` skills.
