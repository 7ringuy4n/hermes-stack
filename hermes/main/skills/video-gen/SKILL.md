---
name: video-gen
description: "Generate a short H.264 video via dispatcher POST /v1/video. Default stack path — do not invent matplotlib/manim/ascii. RESULT-ONLY (see media-out)."
---

# Video generation

Follow skill **`media-out`** (result only — no step chatter).

Do **not** write Python/matplotlib/manim/PIL frame loops. Do **not** create new skills. Do **not** install manim or mention pangocairo. Native Hermes video tools are often missing — use dispatcher.

**ComfyUI** is still the diffusion backend **inside dispatcher** (`IMAGE_BACKENDS` includes `comfy-cpu`). You do not run `comfy` CLI unless the user named a Comfy/Wan/Hunyuan workflow. Default video = `POST /v1/video` (still → H.264). Default image = `POST /v1/image` (llm → vendor → comfy-cpu).

## Default (must)

1. One short web search only if the user asked for **live** weather/facts.
2. `POST http://dispatcher:8090/v1/video` with a scene prompt and optional `overlay` lines (facts already fetched — do not put the whole user paragraph in overlay).
3. Write under `/opt/data/media/out/<safe-slug>.mp4` (dispatcher does this).
4. Do **not** `send_zalo` / `/v1/send-file` — Zalo autosend delivers the file.

```bash
mkdir -p /opt/data/media/out && curl -sS -X POST http://dispatcher:8090/v1/video \
  -H 'content-type: application/json' \
  -d '{"prompt":"<scene>","filename":"<safe-slug>.mp4","seconds":4,"refine":false,"overlay":["<fact1>","<fact2>"]}'
```

Success: `"ok":true`, `"backend":"ffmpeg-still"`. Autosend sends the mp4. No extra chat line.

If dispatcher returns 503/502: one failure line from **media-out**, then stop.

## Related

- `image-gen` — still images (`POST /v1/image`)
- `media-out` — result-only delivery
- `comfyui` — only when the user named a Comfy/Wan/Hunyuan workflow
