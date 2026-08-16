---
name: image-gen
description: "Generate images via dispatcher. RESULT-ONLY (see media-out). One call, no send_zalo (autosend delivers once), one short result line."
---

# Image generation

Follow skill **`media-out`** (result only — no step chatter, no approve, no chat_id / names / DM metadata).

## Output path

Only `/opt/data/media/out/<safe-slug>.png` (or `.jpg`). Never `/opt/data/<file>.png` or `/tmp`.

## Generate (must)

**Do not** set `send_zalo:true` and **do not** call `/v1/send-file` for the same image — Zalo autosend delivers **one** file from `/opt/data/media/out/`. Double-send causes duplicates.

```bash
mkdir -p /opt/data/media/out && curl -sS -X POST http://dispatcher:8090/v1/image \
  -H 'content-type: application/json' \
  -d '{"prompt":"<user request>","filename":"<safe-slug>.png","refine":false}'
```

Do not install Pillow/pip/uv unless dispatcher fails twice.

## User-facing reply (only this)

After `ok:true`: reply exactly `Đã xong.` (or `Done.`). Nothing else — no “I’ll generate…”, no thread/chat_id, no “Đây là file của bạn.”

## Related

- `media-out` — result-only rules for all media
- `comfyui` — only if user explicitly asks for a Comfy workflow; still `--output-dir /opt/data/media/out`
- `file-gen` — office docs only, not images
