---
name: media-out
description: "RESULT-ONLY delivery for ALL media/files. No step chatter, no approve, no chat_id/PII. One file send per turn. Use whenever creating or sending a file."
---

# Media / file delivery (result only)

Applies to **every** create/export/send of a file or media asset: images, PDF, DOCX, XLSX, CSV, MD, TXT, PPTX, and any other attachment.

## Hard rules

1. **Do not** narrate steps (“để mình…”, “I’ll generate…”, “locate thread…”, “kiểm tra…”, “pip…”, “uv…”).
2. **Do not** ask the user to approve anything.
3. **Do not** mention `chat_id`, `thread_id`, DM/group metadata, display names from internal context, paths, or backends.
4. Work silently with tools; user-facing text = **result only**.
5. Write under `/opt/data/media/out/<safe-name>.<ext>` only.
6. **One delivery only:** images → generate via dispatcher **without** `send_zalo`; office → one `send-file` **or** rely on autosend — never both.

## User-facing reply (only this)

**Success (Vietnamese):** `Đã xong.`  
**Success (English):** `Done.`  

No “Đây là file của bạn.”, no path dumps, no “để mình gửi…”.

**Failure (Vietnamese):** `Hiện chưa tạo được file này. Bạn thử lại sau hoặc rút gọn yêu cầu giúp mình.`  
**Failure (English):** `Couldn’t create that file. Please try again or shorten the request.`

## Never say

- dispatcher / Comfy / Pollinations / pip / uv / root / permission / approve / dashboard  
- chat_id / thread_id / “DM with …” / internal user labels  
- Step-by-step plans or process narration

## Route by type

| Need | Skill / API |
|------|-------------|
| Image | `image-gen` → `POST /v1/image` (**no** `send_zalo`) |
| Office | `file-gen` / `documents` → one `POST /v1/send-file` |
| Markdown / text file | `markdown` → then `file-gen` |
| Explicit Comfy workflow | `comfyui` → `--output-dir /opt/data/media/out` |
