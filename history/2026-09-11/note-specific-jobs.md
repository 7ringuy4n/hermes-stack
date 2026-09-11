# Specific job notes via skills (no host NLU)

## Symptom

Search-then-note listed/stored aggregate buckets such as role+city+count instead
of concrete openings, and host Python grew Vietnamese/request regex to filter
them.

## Root cause

Listing policy lived in host regex (forbidden). After moving to skills, VPS
smoke still failed because router-worker `normalize_plan` dropped
`persist_gathered_notes`, so deferred persist and the notes listing contract
never armed. Historical aggregate rows also polluted the smoke query.

## Fix

- Classify: `persist_gathered_notes` on search/schedule plans for gather-then-store.
- Skills: `notes/SKILL.md`, `notes/prompts/search_then_note_listing.txt`,
  `web-search/SKILL.md`, `classify/parts/notes.txt` own concrete vs aggregate
  listing and prior-note omission.
- Host: structural numbered-item split + URL citation only; inject the skill
  prompt asset with Prior notes data; no user-request Vietnamese hardcoding.

## Verification

- `python test/scripts/notes_specific_jobs_unit.py`
- `python test/scripts/notes_deferred_persist_unit.py`
- `python test/scripts/notes_atomic_cite_unit.py`
- `python test/scripts/schedule_search_note_fire_unit.py`
