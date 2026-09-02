---
name: media-out
description: "RESULT-ONLY delivery for ALL media/files. No step chatter, no approve, no chat_id/PII. One file send per turn. Use whenever creating or sending a file."
---

# Media / file delivery (result only)

Applies to **every** create/export/send of a file or media asset: images, PDF, DOCX, XLSX, CSV, MD, TXT, PPTX, and any other attachment.

## Hard rules

1. **Do not** narrate steps (“để mình…”, “I’ll generate…”, “Now I have…”, “Let me analyze…”, “locate thread…”, “kiểm tra…”, “pip…”, “uv…”, PIL overlays).
2. **Do not** ask the user to approve anything or whether to resend the file.
3. **Do not** mention `chat_id`, `thread_id`, DM/group metadata, display names from internal context, paths, or backends.
4. Work silently with tools; user-facing text = **the result** (file and/or the asked facts). No success ack line.
5. Write under `/opt/data/media/out/<safe-name>.<ext>` only.
6. **One delivery only:** images → generate via dispatcher **without** `send_zalo`; office → one `send-file` **or** rely on autosend — never both.
7. Compound inbound (several requests in one bubble) is **split into turns** unless it is a **single schedule**. This skill applies to the **current** media item only — it does not cancel later numbered requests.
8. **Compound / parallel jobs:** send the **file only** on a media turn. Do not add a short “done” line before or after.
9. **Schedule payload:** after each file, continue remaining items in that run. Do not treat media-out as end-of-run.

## User-facing reply

**Success:** send the file (and any requested facts). No extra sentence.

**Failure (Vietnamese):** `Hiện chưa tạo được file này. Bạn thử lại sau hoặc rút gọn yêu cầu giúp mình.`  
**Failure (English):** `Couldn’t create that file. Please try again or shorten the request.`

## Never say

- dispatcher / pip / uv / root / permission / approve / dashboard  
- chat_id / thread_id / “DM with …” / internal user labels  
- Step-by-step plans, “Now I have the page…”, “Let me fetch…”, session-restored notices  
- Image API keys, `.env` missing keys, Omni auth, numbered “how should I continue?” menus
- `execute_code` or scripts that scan `.env`, `config.yaml`, or replica dirs for secrets

## Route by type

| Need | Skill / API |
|------|-------------|
| Image | `image-gen` → Omni `POST /v1/images/generations` model `image-gen` (**no** `send_zalo`) |
| Short video | **`video-gen`** — refused; use **`image-gen`** for stills or policy refuse via `/v1/video-policy-refuse` |
| Office | `file-gen` / `documents` → `POST /v1/office-file` (create+send; not Hermes pdf skill) |
| Markdown / text file | `markdown` → then `file-gen` |
| Facts printed as images on a web page | download image → vision-ocr combo (`vision_read` / router-worker) → then answer / `image-gen` |
