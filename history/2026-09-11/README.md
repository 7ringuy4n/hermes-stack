# 2026-09-11 — schedule quote-delete silent + search-then-note failed UX

## Symptom

1. After `!zalo schedule list`, quote-reply `xoá số 2` / `xoá lịch thứ 2`
   produced no host reply.
2. “Find live job listings then note them” answered with
   `Không thể hoàn tất thao tác ghi chú` (`notes.failed`) instead of searching.

## Root cause

1. Queue/host classify for quote-replies often saw bare user text only, so
   `delete_schedule` missed `list_index`. Host delete either wiped the whole
   thread or never selected an ordinal; when classify missed schedule entirely,
   Hermes took a short ambiguous turn and stayed silent.
2. Host `plan_is_note` short-circuited `skill_action=create` with an empty
   `notes[]` into Memory Manager → `missing_notes` → failed UX, before any
   live search could gather content to note.
3. `schedules_for_thread` called `list_schedules()` but that helper was missing
   (dead code left after `upsert_schedule_from_row`'s return). Host delete then
   raised `NameError` and produced no Zalo reply — the silent quote-delete
   failure observed on VPS.
4. Queue path imported `quoted_context_snip` again inside `_run_turn`, which made
   the name local and raised `UnboundLocalError` before host delete could run.

## Fix

- Pass quoted schedule-list snip into classify on the queue path.
- Honor `schedule_selector.list_index` (1-based) in matching and host delete.
- Host-parse ordinals (`xoá số 2`, …) into `list_index` during normalize and
  coerce quote-reply ordinal deletes onto the schedule delete path.
- Restore missing `list_schedules()` so host list/delete no longer NameError.
- Empty note create falls through to Hermes for live gather instead of
  announcing `notes.failed`.
- Classify skill parts: schedule list_index + notes search-then-note guidance.
- Unit: `test/scripts/schedule_delete_list_index_unit.py`.

## Verification

- Local units: schedule_delete_list_index, schedule_list_classify, notes_control.
- VPS smoke: quote-delete item 2; search-then-note without notes.failed.
