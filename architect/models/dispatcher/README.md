# models / dispatcher

## Purpose

Central tool HTTP service: web search round-robin, optional media helpers, and routing helpers for soft modes. Container: `dispatcher`.

## Profile

Must. Web backends configured from Medium up (`WEB_BACKENDS` / SearXNG).

## Main functions

| API | Function |
|---|---|
| `POST /v1/search` | Web search (disabled/empty on Low) |
| `POST /v1/image` | Medium+: paid1 → paid2 → ComfyUI CPU (SDXL/SD1.5) → ComfyUI GPU (FLUX.2 klein) |
| `POST /v1/office-file` | Medium+: create txt/csv/md/xlsx/docx/**pdf** (`OFFICE_FILE_GEN=1`; reportlab + DejaVu) |
| `POST /v1/mode` | Soft mode suggestion from text/media flags |
| Health | `/health` for monitors |

## Related

- [../README.md](../README.md)
