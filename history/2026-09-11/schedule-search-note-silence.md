# 2026-09-11 — scheduled search-then-note silent fire

## Symptom

Ask like “5 phút nữa … tìm tin tuyển dụng Java … và ghi chú lại” produced no
usable schedule response / fire outcome (silence after the delay, or empty
`fire_text` create failure).

## Root cause

1. Schedule fires keep `task_hint=schedule`. `keep_search_then_note_atomic`
   correctly skips workflow, but Hermes fallthrough never coerced the plan into
   executable search work, never armed deferred note persist for schedule
   hints, and skipped the live-search contract (queue-only).
2. When classify put the full inbound bubble into `instructions`,
   `fire_text_from_plan` rejected it as equal to the create ask → empty
   `fire_text` → schedule-worker refuse / failed create.

## Fix

- `coerce_schedule_fire_plan_for_search_note` + defer for `schedule`/`tool`
  hints when text is search-then-note.
- Schedule-fire Hermes path applies the live-search contract.
- `fire_text_from_plan` falls back to timing-stripped original for
  search-then-note process schedules.
- Unit: `schedule_search_note_fire_unit.py`; smoke: once_after ~70s.

## Verification

- Local unit PASS.
- VPS: inject once_after search-then-note → ack, one fire listing, no
  「Đang xử lý」, notes present when gather succeeds.
