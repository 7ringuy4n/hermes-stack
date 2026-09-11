# 2026-09-11 — search-then-note duplicated + notes missing citations

## Symptom

1. “Find Java BE/fullstack jobs then note” produced listing + save, then
   「Đang xử lý…」, then a second search listing.
2. “How many notes today” showed job lines without source URLs; some rows still
   carried agent “cannot self-save note” disclaimer text.
3. Need RULES coverage for schedule-for-note and note CRUD.

## Root cause

1. Classify often emitted a multi-instruction search+note plan. FIFO compound
   split ran each instruction as its own turn; the first gather persisted notes
   while a later part started a workflow (「Đang xử lý…」) and gathered again.
2. `notes_from_assistant_body` stored plain title chunks only — no URL scrape /
   citation attachment — and disclaimer tails could remain inside items.

## Fix

- Keep search-then-note atomic in `parts_from_plan` and skip workflow creation
  when `keep_search_then_note_atomic` (single Hermes gather + host persist).
- Arm deferred persist for schedule fires as well as live turns.
- Attach `https` citations into note content/metadata; broaden disclaimer strip.
- Classify notes skill: one search instruction + require source URLs.
- RULES C7/C10: atomic search-then-note, citation URLs, schedule-for-note, CRUD.
- Units: `notes_atomic_cite_unit.py`, `notes_crud_unit.py`; smoke lab.

## Verification

- Local units: atomic/cite, CRUD, deferred persist, notes_control.
- VPS: one listing per inject (no workflow ack duplicate), Memory rows with
  `http` citations, Memory CRUD round-trip; schedule-for-note best-effort.
