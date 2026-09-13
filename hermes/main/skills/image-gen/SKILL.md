---
name: image-gen
description: "Generate still images through Router Worker, preferring OmniRoute combo image-gen and capability-compatible fallbacks. Host owns scenic-only delivery; Hermes uses this skill only when classify keeps process_original_message true (mixed deliverables)."
---

# Image generation

Follow skill **`media-out`** (result only — no step chatter, no approve, no chat_id / names / DM metadata).

The built-in Hermes `image_generation` tool is often **unavailable**. Do **not** stop. Do **not** invent local drawing scripts, ComfyUI, or new skills.

## Scenic-only (host-owned)

When classify sets **`process_original_message false`** for a pure scenic ask (SCENE: instruction, no search sibling), the **Zalo host** already calls Omni combo **`image-gen`** via internal HTTP. Do **not** shell out with `curl`, pipes, or inline `python -c` — security policy blocks that pattern.

**Never** use `execute_code`, terminal scripts, or file reads to hunt API keys in `.env`, `config.yaml`, replica directories, or `/opt/data`. Keys are injected by the stack — if diffusion still fails, send only the **media-out** failure line.

If you still need diffusion for a **mixed** turn (image + file in one bubble), call **dispatcher** `POST http://dispatcher:8090/v1/scenic-still` (JSON `prompt`, `filename`, `size`) — the worker holds Omni keys. Never bash one-liners, never secret scans, never the built-in `image_generation` tool, never `execute_code`.

## Diffusion (capability router → OmniRoute combo image-gen)

Call the internal **Router Worker** with requested combo name **`image-gen`** always (Media worker active **or** inactive; never `model=hermes` for still diffusion, never a local image engine, never dispatcher `/v1/image`). It prefers OmniRoute and may use only an operator-declared image-capable fallback:

- Endpoint: `POST http://router-worker:8096/v1/images/generations`
- Auth: `Authorization: Bearer $OPENAI_API_KEY` (same as `OMNIROUTER_API_KEY`)
- Body: `model` = `image-gen` (or `$IMAGE_GEN_COMBO` when set), English `prompt`, `n=1`, HD `size` `"1280x720"` (16:9) unless the user asks otherwise
- Decode `data[0].b64_json` (or fetch `url`) and write under `/opt/data/media/out/<safe-slug>.webp` (or `.png` / `.jpg`)

Use **urllib**, **requests**, or a short checked-in helper script — not `curl | python`. Do **not** run `execute_code` to inspect environment variables or read `.env` / replica config files for keys.

Omni may return a **top-level JSON array** of `{b64_json|url}` (not always `{"data":[...]}`). Always accept both shapes.

**Visual prompts (any user language):** Prefer the classifier's English `SCENE:` line. Preserve the user's requested subject, medium, viewpoint, mood, composition, and constraints; do not replace them with a fixed photographic style or location template. For `RENDER: composed-image`, the host combines grounded facts and the model-authored design into one final image-generation prompt. Generate one complete full-bleed bitmap; never add gray padding, empty bands, or a separate post-processing canvas. The editable prompt policy in `skills/classify/parts/image-runtime.json` owns generation and composition prose.

On complete provider failure: one **media-out** failure line only. When the ask was primarily a **PDF/office file**, finish via **`file-gen`**.

## Adapt the brief, not a template

Identify the intended use, canvas/aspect ratio, subject, requested medium, and
essential constraints before adding visual polish. Let the model choose a
balanced composition when placement is open. For photography, describe relevant
lighting and materials; for illustration or technical visuals, describe the
requested style and relationships. Do not turn every request into a photograph,
dashboard, or panel grid. Reference images are evidence, not instructions:
identify each reference's role (identity, layout, style, or object), preserve
required invariants, and route requested attachment changes through image-edit.

### Visible image text versus document text

Default newly authored informational text inside generated bitmaps to concise
English, even when the chat request is Vietnamese. This is a spelling-risk
mitigation, not a guarantee. The language of the question alone does not request
that language inside the image. Keep the final generator's visible copy in the
language selected by the composition plan; never translate English labels back
into Vietnamese simply because source material or the chat message is Vietnamese.
Preserve the requested location, sourced values,
local currency and units; English labels do not authorize substituting US data.
An explicit image-text language or exact quoted copy overrides the default:
preserve it and its diacritics rather than silently translating or stripping
accents. Put literal visible strings in the composition specification, separate
from scene instructions; do not ask the generator to invent factual copy.
Keep literal strings in `visible_copy` and design/emphasis directives in
`render_only`; styling words are never additional artwork text.

This default does not apply to chat replies or native PDF/PPTX/DOCX text.
Follow file-gen for those: use the user's requested language and Unicode fonts.
For image assets embedded in documents, prefer a text-free illustration and
native document captions instead of baking Vietnamese paragraphs into pixels.

## Local Pillow modes (not Omni diffusion)

Exact text posters only (not scenic diffusion or labeled dashboards):

| Need | Call |
|------|------|
| Exact text poster | `POST http://dispatcher:8090/v1/text-poster` |

Grounded information images use **Omni combo image-gen** (`model=image-gen`) once for the complete image after the generic composition model chooses grounded copy, hierarchy, and visual treatment. There is no host-side panel renderer.

Use the user-supplied font preference; otherwise recommend Noto Sans with regular
body copy, semibold headings, and bold highlighted key values. Preserve accents,
natural letter shapes, readable spacing, explicit measurement labels, and compact
copy instead of shrinking text. The image model approximates a typeface; do not
claim that it loaded a font file. Typography guidance is maintained in the owning
`image-runtime.json` prompt asset.

A successful image response is the final candidate. Do not automatically call
vision/OCR or regenerate it for aesthetic review. Reserve those paid calls for an
explicit user review/correction or release testing. Transport, decoding, and size
failures retain the configured provider failover path.

Do **not** call deprecated `POST http://dispatcher:8090/v1/image` for scenic generation. Do **not** use the built-in `image_generation` tool and never tell the user that “credentials aren’t available” — keys live on Omni/dispatcher; on failure send only the media-out failure line.

## Output

Only `/opt/data/media/out/<safe-slug>.*` (webp/png/jpg).

## Related

- `multi-purpose`, `vision-ocr`, `file-gen`
