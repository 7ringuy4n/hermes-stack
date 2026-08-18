---
name: file-gen
description: "Create/edit office files (xlsx, docx, txt, pdf, csv, pptx) and send them. RESULT-ONLY (see media-out). Images → image-gen. No music/video."
---

# File generation → send (result only)

Follow skill **`media-out`** for all replies. When the user asks to **create / export / edit** an **xlsx · csv · docx · txt · pdf · pptx** file:

1. Build the file under `/opt/data/media/out/<safe-name>.<ext>`.
2. Send to the same thread. No process chatter, no approve prompts.
3. **Images** → skill **`image-gen`**. Do not produce music/video here.

## Bundled Hermes skills (prefer)

- xlsx — `skills/xlsx/`
- docx — `skills/docx/`
- pdf — `skills/pdf/`
- md/txt — `markdown` / `documents`

If a helper is missing, write Python (`openpyxl` / `docx` / `reportlab`). Install once only if needed:

`uv pip install --target /opt/data/lazy-packages openpyxl python-docx pypdf reportlab`

(Do not narrate the install to the user.)

## Send on Zalo (required)

```bash
curl -sS -X POST http://dispatcher:8090/v1/send-file \
  -H 'Content-Type: application/json' \
  -d '{"path":"/opt/data/media/out/<safe-name>.<ext>","thread_id":"<id>","thread_type":"user|group"}'
```

User-facing text per **`media-out`**: file only on success (or short failure). No path dumps.
