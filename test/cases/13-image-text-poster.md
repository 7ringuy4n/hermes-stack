# Case: exact text poster (dispatcher text-poster backend)

Diffusion + LLM refine must **not** run when the user wants N lines of exact quoted text (black and white typography).

## Goal

- `POST /v1/image` with a fill-in-N-lines prompt returns `backend: text-poster`, correct `n` and `phrase`.
- PNG written under `/data/media/out/` (or dispatcher media root).
- Empty prompt returns HTTP 400 (fail event).

## Preconditions

- Medium+ with dispatcher running (Pillow + DejaVu in dispatcher image).
- `text_poster.py` deployed in dispatcher container.

## Steps

1. **Happy path:**

```bash
curl -sS -X POST http://127.0.0.1:8090/v1/image \
  -H 'content-type: application/json' \
  -d '{"prompt":"create a black and white image, fill in 10 lines \"SAMPLE TEXT\"","filename":"lab-text-poster.png","refine":false}'
```

Expect: `"ok":true`, `"backend":"text-poster"`, `"n":10`, `"phrase":"SAMPLE TEXT"`, file exists.

2. **Explicit mode:** same with `"mode":"text"` (optional).

3. **Fail event:** `{"prompt":"","refine":false}` → HTTP 400, no file written.

4. **Regression guard:** response must **not** contain diffusion backend names as success for the happy path.

## Pass criteria

- Happy path JSON fields match; PNG size > 1 KB.
- Fail event short error, no stack trace in user channel.
- Hermes skill `image-gen/SKILL.md` present on mount (manual or case 12).

## Fixtures

- Phrase: `SAMPLE TEXT`, N=10, B&W English prompt (per skill doc).
