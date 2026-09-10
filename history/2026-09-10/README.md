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

A second gap: the live-search queue path replaced `event.text` with
`bare_q` + `[Current lookup execution contract]`, wiping any host clock prefix
just before `handle_message`.

A third gap (release-gate regression): stamping host clock onto the queue
`MessageEvent` **before** `_as_try_workflow_submit` polluted classify and
`original_request`, so schedule labs failed exact match (`FAIL_SCHEDULE_NOT_STORED`)
and PDF asks could be mis-routed to composed-image.

## Fix

- `hermes/main/plugins/zalo/host_clock.py` — `with_host_clock_context` +
  `strip_host_clock_context`.
- Queue path: classify/workflow/storage use **bare** user text; Hermes
  `handle_message` receives the stamped text only after routing.
- `strip_prior_for_classify` (plugin + router-worker) strips the host-clock
  wrapper as defense-in-depth.
- `web-search` / `core/answering` / `SOUL.md` — never invent a conflicting clock.
- Unit: `test/scripts/host_clock_context_unit.py`.

## Verification

- Unit PASS locally.
- VPS: weather reply clock must match host Local now (±1–2 min); continue case
  index from visual-weather PDF through memory-scale (former 111→132).
