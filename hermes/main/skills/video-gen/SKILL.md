---
name: video-gen
description: "Refuse video, music, audio generation and YouTube/music/video transcripts. RESULT-ONLY (see media-out)."
---

# Video / music / audio / transcripts (refused)

Follow skill **`media-out`**.

**Policy:** this stack does **not** generate or fetch:

- Synthetic **video** clips
- **Music** / song generation
- **Audio** / voice / TTS generation (except stack ASR used internally when enabled)
- **YouTube / TikTok / Facebook** download, transcript, or summary
- Music lyrics transcription from URLs
- Video frame transcription pipelines (manim, ffmpeg encode loops)

Do **not** invent pipelines or call Whisper as a user-facing product.

## Required

Ask dispatcher for the refuse message (OmniRouter writes user-facing text):

```bash
curl -sS -X POST http://dispatcher:8090/v1/video-policy-refuse \
  -H 'content-type: application/json' \
  -d '{"topic":"video_generate","context":"<verbatim user request>","language":"vi"}'
```

Topics: `video_generate` | `video_summary` | `music_generate` | `audio_generate` | `transcript`

Reply with JSON **`message`** only.

## Alternatives

| Need | Route |
|------|--------|
| Still image / infographic | **`image-gen`** or **`multi-purpose`** |
| Office document | **`file-gen`** |

## Related

- `image-gen` — supported stills
- `multi-purpose` — complex still layouts
