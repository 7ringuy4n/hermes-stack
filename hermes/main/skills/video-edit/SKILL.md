---
name: video-edit
description: "Edit one supplied video through OmniRoute combo video-edit. RESULT-ONLY (see media-out)."
---

# Video editing

Follow skill **`media-out`**. Require one accessible source video. Preserve timing, audio, framing, and unrequested regions unless the user explicitly asks to change them.

Call OmniRoute `POST /v1/videos/generations` with combo model `video-edit`, the source video, and the requested transformation. OmniRoute exposes generation and editing models through this single video endpoint. Run one video operation at a time, poll only the returned operation, save the completed MP4 under `/opt/data/media/out/`, and deliver it once.

Default generated test outputs to 480P. Do not overwrite the source, invent a local ffmpeg transformation as a substitute for the model edit, or expose credentials/provider details.

## Related

- `video-gen` — create a new short clip
- `image-edit` — edit a supplied still
- `media-out` — result-only delivery
