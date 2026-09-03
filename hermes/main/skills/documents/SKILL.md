---
name: documents
description: "MODE=documents — LLM authors file content; Dispatcher office-file renders. RESULT-ONLY (see media-out)."
---

# Documents (md · txt · pdf · docx · xlsx · csv)

Follow skill **`media-out`**. Medium+ when `OFFICE_FILE_GEN=active`. Hard refuse music/video.
**Images** → **`image-gen`**.

## Author before create (required)

**You** write the full file body: structure, headings, tables, and facts. Use `web_search`
for live data when the ask needs it. Pass your composed text as `prompt` — not the user's
bubble verbatim, and not a fixed template.

## Create + send (required)

Always use Dispatcher (has reportlab/openpyxl baked in). Do **not** use Hermes
`pdf`/`docx`/`xlsx` skills (name collisions) or `pip install` inside the agent.

```bash
curl -sS -X POST http://dispatcher:8090/v1/office-file \
  -H 'Content-Type: application/json' \
  -d '{
    "prompt":"<full content you authored>",
    "thread_id":"<inbound thread_id>",
    "thread_type":"user",
    "filename":"<safe>.pdf",
    "caption":""
  }'
```

Examples:

| User | Call |
|------|------|
| tạo 1 file pdf và điền vào số 1 | `prompt` with your layout (e.g. a line containing `1`), `filename":"so_1.pdf"` |
| tạo 1 file text điền số 1 | same API (parser picks `.txt`) or `filename":"number.txt"` |

## Do not

- Narrate steps / claim success without `"ok":true`
- Ask for approval / invent “cannot send file on Zalo”
- Dump server paths
- Impose weather card, dashboard, or screen layouts unless the user asked for that style
