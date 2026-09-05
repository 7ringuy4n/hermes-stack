# models / dispatcher

## System architecture

| | |
|--|--|
| **Sits between** | Hermes / skills ↔ media backends |
| **Owns** | image, office-file, media helpers, mode suggestion |
| **Does not own** | LLM completions (Model Router) or web search (Model Router `/v1/search`) |

<table style="width:100%;border-collapse:collapse;font-size:13px;">
  <tr>
    <td style="padding:12px;background:#f5f5f5;border:1px solid #ddd;text-align:center;width:28%;">Hermes / skills</td>
    <td style="padding:8px;background:#eee;text-align:center;width:4%;">→</td>
    <td style="padding:14px;background:#2563eb;color:#fff;text-align:center;border:3px solid #fbbf24;width:36%;"><b>dispatcher</b></td>
    <td style="padding:8px;background:#eee;text-align:center;width:4%;">→</td>
    <td style="padding:12px;background:#e8f4ea;border:1px solid #c5e0c8;text-align:center;width:28%;">image · office · media</td>
  </tr>
</table>

## Purpose

Media/File worker HTTP service: image generation, office-file create, media download/convert helpers, and soft mode suggestions. Web search is on the Model Router (`model-router`), not here. Container: `dispatcher`.

## Main functions

| API | Function |
|---|---|
| `POST /v1/scenic-still` | Generate a still through the configured image combo |
| `POST /v1/overlay` | Apply a validated adaptive information design to an existing image |
| `POST /v1/text-poster` | Render exact requested glyphs deterministically |
| `POST /v1/office-file` | Create txt/csv/md/xlsx/docx/**pdf**/pptx when `OFFICE_FILE_GEN=active` (LLM HTML or raw PDF → WeasyPrint/PyMuPDF) |
| `POST /v1/media` | Media download / convert helpers |
| `POST /v1/mode` | Soft mode suggestion from text/media flags |
| Health | `/health` for monitors |

## Related

- [../README.md](../README.md)
- [../model-router/README.md](../model-router/README.md) — web search (`/v1/search`)
