# File layout contract (LLM → Hermes → worker)

When the user asks to **create** a file (pdf, docx, xlsx, csv, txt, md), the **LLM must first
produce a structured layout body** in the chat turn. Hermes passes that body unchanged to the
office worker — the worker renders bytes; it does not invent structure from raw user prose.

## Required flow

1. **Understand** user intent (topic, language, metrics, sheets, tone).
2. **Fetch live facts** when needed (`web_search`) — never bake stale guesses into layout.
3. **Compose layout** using the markers below (complete sentences in labels; UTF-8 Vietnamese OK).
4. **Call** `POST http://dispatcher:8090/v1/office-file` with `prompt` = the layout body only.
5. **Deliver** per **`media-out`** (file only, no success narration).

## Layout markers

### PDF / designed office (weather, report, dashboard)

```text
TITLE: <subject or place — official spelling>
SUBTITLE: <optional context line>
ICON: <short motif: sun | rain | cloud | wind | chart | doc>
OVERVIEW: <1–2 sentences intro when TITLE is a place/topic>
BACKGROUND: <atmosphere / setting when visual PDF>
- <Label>: <value>
- <Label>: <value>
```

Place/city subjects: `OVERVIEW` and `BACKGROUND` are required when TITLE names a location.

### DOCX / letter / memo

```text
TITLE: <document title>
- Section: <heading>
- Body: <paragraph text>
- Section: <next heading>
- Body: <paragraph text>
```

### XLSX / CSV

```text
TITLE: <workbook title>
SHEET: <sheet name>
| Col A | Col B | Col C |
| val   | val   | val   |
SHEET: <optional second sheet>
| ... |
```

Use `|` rows for tables; worker maps to sheets.

### TXT / MD

```text
TITLE: <optional title line>
<file body — markdown or plain paragraphs>
```

Or write directly to `/opt/data/media/out/<name>.md` then `send-file` when office-file returns 503.

## LLM must not

- Send raw user message as `prompt` without structuring layout first.
- Skip markers for “simple” PDFs — minimal layout is still `TITLE:` + bullet facts.
- Ask Hermes to `pip install` reportlab/openpyxl or use colliding `pdf`/`docx` skills.
- Narrate steps; output is the file (see **`media-out`**).

## Related

- `file-gen`, `documents`, `media-out`, `web-search`
