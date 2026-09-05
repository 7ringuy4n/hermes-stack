# Case: Omni combo preflight (hermes + classifier)

Verify OmniRouter `hermes` / `classifier` combos have members before Zalo
reply tests (case 32) or manual chat.

## Goal

Catch silent “no response” when chat/classify combo aliases are empty.

## Preconditions

- Stack up with `ENABLE_OMNIROUTER=1`, `model-router` healthy
- first-setup-omnirouter has filled both combos with OpenCode `oc/*`

## Steps

1. Run `python test/scripts/omni_combo_preflight.py`
2. Script reads Omni sqlite combos (no secrets in report)
3. If combos are empty, run `bash run.sh first-setup-omnirouter`, then re-check

## Pass criteria

| Mode | Pass |
|------|------|
| `hermes` and `classifier` each ≥1 model | PASS |
| Missing Omni DB or either combo empty | FAIL |

## Fail events

- Omni DB missing / model-router down
- Combos still empty after first-setup
- Router logs show repeated 400 for model `hermes` while combos claim non-empty

## Notes

- Real Zalo messages and case 32 require a filled `hermes` combo.
