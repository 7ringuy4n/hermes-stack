---
name: file-gen
description: Create or edit office files (xlsx, docx, txt, pdf, csv) and send them to the requester. Images use skill image-gen (media/out). No music/video.
---

# File generation → send to requester (must)

When the user asks to **create / export / edit** an **xlsx · csv · docx · txt · pdf · pptx** file:

1. **Build the file**, then **send it to the same person / thread** that is chatting.
2. **Do not** produce music or video. **Images / jpeg / png** → skill **`image-gen`** (write under `/opt/data/media/out/…`, never dump loose `/opt/data/*.png`).
3. Do not send stock manuals/library PDFs as “proof” → see `no-outbound-doc` if present.

## Bundled Hermes skills (prefer)

Use helpers already in the Hermes image (mirrored under `hermes/main/skills/`):

- xlsx — `skills/xlsx/` · https://hermes-agent.nousresearch.com/docs/user-guide/skills/bundled/productivity/productivity-xlsx  
- docx — `skills/docx/` · https://hermes-agent.nousresearch.com/docs/user-guide/skills/bundled/productivity/productivity-docx  
- pdf — `skills/pdf/` · https://hermes-agent.nousresearch.com/docs/user-guide/skills/bundled/productivity/productivity-pdf  
- md/txt — skills `markdown` / `documents`

If a helper is missing, write Python directly (`openpyxl` / `docx` / `reportlab`). Install once:

`uv pip install --target /opt/data/lazy-packages openpyxl python-docx pypdf reportlab`

## Output path

Write **`/opt/data/media/out/<safe-name>.<ext>`** (Hermes volume → bridge can read it).  
Do not write only to `/tmp` and ask the user to fetch it themselves.

## Send on Zalo (required)

Zalo **can send files**. Never claim “cannot send files / text only”.

1. Write the file to **`/opt/data/media/out/<safe-name>.<ext>`** (not `/tmp`, not workspace-only).
2. Call **immediately** (either):

```bash
curl -sS -X POST http://dispatcher:8090/v1/send-file \
  -H 'Content-Type: application/json' \
  -d '{"path":"/opt/data/media/out/<safe-name>.<ext>","thread_id":"<id>","thread_type":"user|group"}'
```

Or use the platform send-attachment path your stack exposes. One short confirmation line after send — no path dumps, no secret leakage.
