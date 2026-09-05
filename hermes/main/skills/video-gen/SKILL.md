---
name: video-gen
description: "Generate one short video through OmniRoute combo video-gen. RESULT-ONLY (see media-out)."
---

# Short video generation

Follow skill **`media-out`**.

Generate exactly one clip with OmniRoute `POST /v1/videos/generations`, model `video-gen`. Preserve the user's subject, motion, framing, style, and safety constraints. Default production requests to 480P and 3 seconds unless the user asks for another supported value. Run one video generation at a time.

## Required

Send JSON with `model`, `prompt`, `resolution`, and `duration`. Poll only the operation URL/id returned by the API, honor terminal failure states, download the completed MP4 to `/opt/data/media/out/`, then deliver it once.

For cost-controlled lab tests only, override to 480P and 1 second. Never bake a temporary provider model into source or rewrite operator-owned combo members.

## Alternatives

Do not use this skill for image edits, video edits, media downloads, URL transcripts, music generation, or audio generation. Do not substitute a still image when video generation fails.

## Related

- `image-edit` — edit a supplied still image
- `video-edit` — edit a supplied video
- `media-out` — result-only delivery
