---
name: documents
description: "MODE=documents — LLM composes layout; Dispatcher office-file renders. RESULT-ONLY (see media-out)."
---

# Documents (md · txt · pdf · docx · xlsx · csv)

Follow skill **`media-out`**. Medium+ when `OFFICE_FILE_GEN=active`. Hard refuse music/video.
**Images** → **`image-gen`**.

## Layout before create (required)

Read **`file-gen/LAYOUT.md`**. The LLM must turn the user request into a structured
`prompt` (TITLE, OVERVIEW, `- facts`, SHEET tables) **before** calling office-file.
Never pass the user's bubble verbatim as `prompt`.

## Create + send (required)

Always use Dispatcher (has reportlab/openpyxl baked in). Do **not** use Hermes
`pdf`/`docx`/`xlsx` skills (name collisions) or `pip install` inside the agent.

```bash
curl -sS -X POST http://dispatcher:8090/v1/office-file \
  -H 'Content-Type: application/json' \
  -d '{
    "prompt":"<structured layout per file-gen/LAYOUT.md>",
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
