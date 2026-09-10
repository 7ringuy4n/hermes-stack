# 2026-09-10 — invented weather observation clock

## Symptom

A live Zalo weather ask (`thời tiết hcm ra sao`) answered with a fabricated
observation time (for example “khoảng 20:25”) that did not match the host
`Asia/Ho_Chi_Minh` wall clock.

## Root cause

Classify already receives host `Timezone` / `Local now`, and composed overlays
stamp from `ASSISTANT_TZ`/`TZ`. Hermes chat turns built `MessageEvent(text=…)`
from the raw user string only, so the agent invented a wall clock from search
snippets or prior turns.

## Fix

- `hermes/main/plugins/zalo/host_clock.py` — pure `with_host_clock_context`.
- `adapter.py` applies it on inbound, queue parts, compound parts, schedule fire.
- `web-search` / `core/answering` / `SOUL.md` — never invent a conflicting clock.
- Unit: `test/scripts/host_clock_context_unit.py`.

## Verification

- Unit PASS locally.
- VPS: weather reply clock must match host Local now (±1–2 min); continue case
  index from visual-weather PDF through memory-scale (former 111→132).
