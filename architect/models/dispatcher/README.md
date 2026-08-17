# models / dispatcher

## System architecture

| | |
|--|--|
| **Sits between** | Hermes / skills ↔ web & media backends |
| **Owns** | `/v1/search`, image, office-file, mode helpers |
| **Does not own** | LLM completions (Model Router) or knowledge ingest |

<table style="width:100%;border-collapse:collapse;font-size:13px;">
  <tr>
    <td style="padding:12px;background:#f5f5f5;border:1px solid #ddd;text-align:center;width:28%;">Hermes / skills</td>
    <td style="padding:8px;background:#eee;text-align:center;width:4%;">→</td>
    <td style="padding:14px;background:#2563eb;color:#fff;text-align:center;border:3px solid #fbbf24;width:36%;"><b>dispatcher</b></td>
    <td style="padding:8px;background:#eee;text-align:center;width:4%;">→</td>
    <td style="padding:12px;background:#e8f4ea;border:1px solid #c5e0c8;text-align:center;width:28%;">search · image · office</td>
  </tr>
</table>

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
