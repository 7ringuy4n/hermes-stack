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

- dispatcher / Comfy / Pollinations / pip / uv / root / permission / approve / dashboard  
- chat_id / thread_id / “DM with …” / internal user labels  
- Step-by-step plans, “Now I have the page…”, “Let me fetch…”, session-restored notices

## Route by type

| Need | Skill / API |
|------|-------------|
| Image | `image-gen` → `POST /v1/image` (**no** `send_zalo`; use `overlay` for on-image facts) |
| Short video | `video-gen` → `POST /v1/video` (**no** matplotlib / manim) |
| Office | `file-gen` / `documents` → one `POST /v1/send-file` |
| Markdown / text file | `markdown` → then `file-gen` |
| Explicit Comfy workflow | `comfyui` → `--output-dir /opt/data/media/out` |
| Facts printed as images on a web page | download image → `POST http://ocr:8091/v1/ocr` → then answer / `image-gen` |
