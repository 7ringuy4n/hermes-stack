# 2026-09-11 — deferred search-then-note never persisted

## Symptom

1. “Find new Java BE/fullstack jobs on Facebook then note them” returned a
   listing and claimed “Đã lưu thành ghi chú…” but Memory had no new rows.
2. “Show saved job / Java notes” → `Không tìm thấy ghi chú phù hợp.`
3. “How many notes do I have?” listed older notes only (no job listings).

## Root cause

1. Empty `notes[]` create already fell through so Hermes could gather, but the
   host never POSTed the gathered answer to Memory Manager. The agent invented
   the save confirmation; outbound filtering did not invent storage.
2. Lookup failed primarily because nothing was written. Filler-heavy queries
   (“hiển thị các tin tuyển dụng java đã lưu”) also weakened FTS/ILIKE match
   when rows eventually exist.
3. Deferred pending was keyed by the bare Zalo thread id, while Hermes final
   `send()` often uses an isolated `{thread}::job::{job}` chat id — so the
   persist hook never saw the pending gather even after host logic existed.

## Fix

- Host marks deferred note persist when classify signals empty create or
  search-then-note wording; on substantive `send()`, strip false save claims,
  split numbered items into note rows (tags/date from the ask), POST via
  `notes_client`, append real `ZALO_NOTES_SAVED_MSG`. Pending keys use
  `real_thread_id` so `::job::` session sends still match.
- Re-queue pending for gate/admin/short wait lines so status chatter does not
  consume the gather slot; clear pending on other host-owned short-circuits.
- Lookup retries with `simplify_note_query` when the first pass is empty.
- Default `MEMORY_URL` fallback aligns with compose (`http://memory:8095`).
- Classify notes skill: host persists after gather; classify never claims store.
- Unit: `test/scripts/notes_deferred_persist_unit.py`.

## Verification

- Local: `notes_deferred_persist_unit`, `notes_control_unit`.
- VPS: search-then-note reply includes host save confirm; Memory `/v1/notes`
  (or Zalo lookup for Java/tuyển dụng) returns the new rows — not fake PASS.
