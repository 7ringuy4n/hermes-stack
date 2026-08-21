---
name: documents
description: "MODE=documents — create/read office & text files via Dispatcher office-file. RESULT-ONLY (see media-out). Images → image-gen."
---

# Documents (md · txt · pdf · docx · xlsx · csv)

Follow skill **`media-out`**. Medium+ when `OFFICE_FILE_GEN=1`. Hard refuse music/video.
**Images** → **`image-gen`**.

## Create + send (required)

Always use Dispatcher (has reportlab/openpyxl baked in). Do **not** use Hermes
`pdf`/`docx`/`xlsx` skills (name collisions) or `pip install` inside the agent.

```bash
curl -sS -X POST http://dispatcher:8090/v1/office-file \
  -H 'Content-Type: application/json' \
  -d '{
    "prompt":"<full user request>",
    "thread_id":"<inbound thread_id>",
    "thread_type":"user",
    "filename":"<safe>.pdf",
    "caption":""
  }'
```

Examples:

| User | Call |
|------|------|
| tạo 1 file pdf và điền vào số 1 | `prompt` that text, `filename":"so_1.pdf"` |
| tạo 1 file text điền số 1 | same API (parser picks `.txt`) or `filename":"number.txt"` |

## Do not

- Narrate steps / claim success without `"ok":true`
- Ask for approval / invent “cannot send file on Zalo”
- Dump server paths
