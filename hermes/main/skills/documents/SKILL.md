---
name: documents
description: "MODE=documents — LLM authors file content; Dispatcher office-file renders. RESULT-ONLY (see media-out)."
---

# Documents (md · txt · pdf · docx · xlsx · csv)

Follow skill **`media-out`** when `OFFICE_FILE_GEN=active`. Hard refuse music/video.
**Images** → **`image-gen`**.

## Author before create (required)

**You** write the full file body: structure, headings, tables, and facts. Use `web_search`
for live data when the ask needs it. Pass your composed text as `prompt` — not the user's
bubble verbatim, and not a fixed template.

Use one clear title, concise subtitle, meaningful sections, and label/value facts
where suitable. Select hierarchy and density for the content rather than a fixed
topic template. PDF must use authored HTML/CSS; DOCX/PPTX/XLSX use structured
markdown that the renderer can turn into styled headings, cards/tables, readable
spacing, and presentation-safe pages/slides/sheets.

For HTML/PDF, keep factual content in normal flow with content-driven heights.
Never use negative margins, translated offsets, absolute/fixed positioning, or
hidden overflow on text containers. Keep icons in bounded cells, verify large
values fit with padding, maintain print-safe contrast, and balance the full page
instead of leaving an accidental empty lower third. Use one timezone notation
consistently. These are generic layout invariants, not a topic template.

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
- Claim visual quality without rendering/inspecting the result
- Silently change the requested file extension when a renderer fails
- Impose weather card, dashboard, or screen layouts unless the user asked for that style
