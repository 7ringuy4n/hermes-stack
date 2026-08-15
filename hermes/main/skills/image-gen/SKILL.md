---
name: image-gen
description: "Generate images (wallpaper, poster, txt2img). ALWAYS save under /opt/data/media/out/ — never dump loose files in /opt/data or /tmp."
---

# Image generation (must)

When the user asks to **create / draw / generate / make an image** (wallpaper, poster, PNG/JPEG, text-on-image, ComfyUI, …):

## Output path (hard rule)

1. **Only** write under **`/opt/data/media/out/`** (create dir if missing).
2. **Forbidden** destinations:
   - `/opt/data/<anything>.png` (HERMES_HOME root)
   - `/opt/data/black_wallpaper.png`, `/opt/data/hermes_*.png`, etc.
   - `/tmp/…` as the final deliverable
   - repo cwd / `./outputs` without moving into `media/out`
3. Filename: **safe slug** only — lowercase, `[a-z0-9._-]`, short. Example: `black_wallpaper.png`, `hermes_10_lines.png`.
4. Host mirror: same files appear under `/data/assistant/media/out/` (Hermes mount `/opt/data` ← data dir).

```bash
mkdir -p /opt/data/media/out
# final path MUST look like:
#   /opt/data/media/out/<safe-name>.png
```

## Preferred: dispatcher (must try first)

**Always** call this before Pollinations curl, Comfy Cloud, or freestyle Pillow:

```bash
curl -sS -X POST http://dispatcher:8090/v1/image \
  -H 'content-type: application/json' \
  -d '{"prompt":"<user request>","filename":"<safe-name>.png","refine":true}'
```

Response includes `hermes_path` like `/opt/data/media/out/<name>.jpg`. Use that path — do not re-save elsewhere.

If HTTP 503 `IMAGE_BACKENDS empty` → tell user image backends are disabled in `.env` (do not invent alternate hosts unless skill fallback below).

Optional Zalo send: `"send_zalo":true,"thread_id":"<id>","thread_type":"user|group"`.

Backends (Medium+): `IMAGE_BACKENDS` → llm → vendor → comfy-cpu → comfy-gpu. Override with `"provider":"vendor"` etc.

## ComfyUI skill

If using `comfyui` / `run_workflow.py`, **always**:

```bash
--output-dir /opt/data/media/out
```

Never `--output-dir ./outputs` or `/opt/data`.

## Pillow / Terminal (simple solid / text layouts only)

Allowed for trivial canvases (solid color, few lines of text) when dispatcher/Comfy is overkill:

```bash
mkdir -p /opt/data/media/out
# write ONLY to /opt/data/media/out/<safe-name>.png
```

Still **never** `/opt/data/<file>.png`.

## After create

- Confirm briefly; prefer stating the path as `/opt/data/media/out/<file>` (not `/opt/data/<file>`).
- Chat/Zalo send: `POST http://dispatcher:8090/v1/send-file` with that path (same as `file-gen`), or `/v1/image` with `send_zalo`.

## Related

- `comfyui` — diffusion workflows (output-dir rule above)
- `file-gen` — office docs only (xlsx/docx/pdf/txt); not images
- `media-local` — download inbound URLs into media cache
