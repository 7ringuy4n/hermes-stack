---
name: image-gen
description: "Generate still images via OmniRouter combo image-gen. Host owns scenic-only delivery; Hermes uses this skill only when classify keeps process_original_message true (mixed deliverables)."
---

# Image generation

Follow skill **`media-out`** (result only — no step chatter, no approve, no chat_id / names / DM metadata).

The built-in Hermes `image_generation` tool is often **unavailable**. Do **not** stop. Do **not** invent local drawing scripts, ComfyUI, or new skills.

## Scenic-only (host-owned)

When classify sets **`process_original_message false`** for a pure scenic ask (SCENE: instruction, no search sibling), the **Zalo host** already calls Omni combo **`image-gen`** via internal HTTP. Do **not** shell out with `curl`, pipes, or inline `python -c` — security policy blocks that pattern.

**Never** use `execute_code`, terminal scripts, or file reads to hunt API keys in `.env`, `config.yaml`, replica directories, or `/opt/data`. Keys are injected by the stack — if diffusion still fails, send only the **media-out** failure line.

If you still need diffusion for a **mixed** turn (image + file in one bubble), call **dispatcher** `POST http://dispatcher:8090/v1/scenic-still` (JSON `prompt`, `filename`, `size`) — the worker holds Omni keys. Never bash one-liners, never secret scans, never the built-in `image_generation` tool, never `execute_code`.

## Diffusion (OmniRouter combo image-gen)

Call **OmniRouter** with combo name **`image-gen`** always (Media worker active **or** inactive; never `model=hermes` for still diffusion, never ComfyUI, never dispatcher `/v1/image`):

- Endpoint: `POST {OMNIROUTER_BASE_URL}/images/generations` (default `http://omni-router:20129/v1/images/generations`)
- Auth: `Authorization: Bearer $OPENAI_API_KEY` (same as `OMNIROUTER_API_KEY`)
- Body: `model` = `image-gen` (or `$IMAGE_GEN_COMBO` when set), English `prompt`, `n=1`, HD `size` `"1280x720"` (16:9) unless the user asks otherwise
- Decode `data[0].b64_json` (or fetch `url`) and write under `/opt/data/media/out/<safe-slug>.webp` (or `.png` / `.jpg`)

Use **urllib**, **requests**, or a short checked-in helper script — not `curl | python`. Do **not** run `execute_code` to inspect environment variables or read `.env` / replica config files for keys.

Omni may return a **top-level JSON array** of `{b64_json|url}` (not always `{"data":[...]}`). Always accept both shapes.

**Visual prompts (any user language):** Prefer the classifier's English `SCENE:` line. Preserve the user's requested subject, medium, viewpoint, mood, composition, and constraints; do not replace them with a fixed photographic style or location template. For `RENDER: composed-image`, generate only the background and reserve readable negative space. The editable prompt policy in `skills/classify/parts/image-runtime.json` supplies generic generation and composition instructions; application code must not embed replacement prompt prose.

On Omni failure: one **media-out** failure line only. When the ask was primarily a **PDF/office file**, finish via **`file-gen`**.

## Local Pillow modes (not Omni diffusion)

Exact text posters only (not scenic diffusion or labeled dashboards):

| Need | Call |
|------|------|
| Exact text poster | `POST http://dispatcher:8090/v1/text-poster` |

Grounded information images use **Omni combo image-gen** (`model=image-gen`) for the background, then the host's generic composition model and dispatcher `POST /v1/overlay`. The model chooses the content hierarchy and visual treatment; the renderer validates and executes it.

Do **not** call deprecated `POST http://dispatcher:8090/v1/image` for scenic generation. Do **not** use the built-in `image_generation` tool and never tell the user that “credentials aren’t available” — keys live on Omni/dispatcher; on failure send only the media-out failure line.

## Output

Only `/opt/data/media/out/<safe-slug>.*` (webp/png/jpg).

## Related

- `multi-purpose`, `vision-ocr`, `video-gen`, `file-gen`
