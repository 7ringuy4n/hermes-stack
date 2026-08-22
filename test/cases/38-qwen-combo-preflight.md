# Case: Qwen combo preflight (ENABLE_QWEN + OmniRouter)

Verify OmniRouter `hermes` / `classifier` combos match Qwen configuration before
Zalo reply tests (case 32) or manual chat.

## Goal

Catch silent “no response” when `ENABLE_QWEN=1` but no API key or empty combos.

## Preconditions

- Stack up with `ENABLE_OMNIROUTER=1`, `router-worker` healthy
- Optional: `QWEN_API_KEY` (or `DASHSCOPE_API_KEY` / `ALIBABA_API_KEY`) in host `.env`

## Steps

1. Run `python test/scripts/qwen_combo_preflight.py`
2. Script reads masked `.env` flags and Omni sqlite combos (no secrets in report)
3. When key is set, run `bash run.sh first-setup-omnirouter` if combos empty, re-check

## Pass criteria

| Mode | Pass |
|------|------|
| `ENABLE_QWEN=0` | PASS (Qwen optional off) |
| `ENABLE_QWEN=1` + key set + `hermes`/`classifier` each ≥1 model | PASS |
| `ENABLE_QWEN=1` + **no** key + empty combos | PASS with `QWEN_KEY_MISSING` (expected negative — explains no Zalo reply) |
| `ENABLE_QWEN=1` + key set + combos still empty after first-setup | FAIL |

## Fail events

- Omni DB missing / router-worker down
- Key present but combos empty after first-setup
- Router logs show repeated 400 for model `hermes` while combos claim non-empty

## Notes

- Lab VPS with generated `.env` has `ENABLE_QWEN=1` and empty `QWEN_API_KEY` by design until operator adds a key.
- Real Zalo messages and case 32 require a filled `hermes` combo — see `docs/QWEN_PERFORMANCE.md`.
