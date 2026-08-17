# Case: media disabled (Medium / High)

Negative: `IMAGE_BACKENDS` empty.

- Image-gen request → short 503, no crash, no fake media.
- Empty prompt → 400 short message.
- Invalid/unsupported type recorded.
- Office/image tools do not claim success when backends are empty.
