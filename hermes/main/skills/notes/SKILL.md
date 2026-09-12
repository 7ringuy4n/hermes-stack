---
name: notes
description: Save, find, revise, or remove durable personal and group notes, including dated plans and later questions about them. Use for explicit note-taking and recall; do not treat ordinary conversation as a note request.
---

# Durable notes

Use the Memory service notes API through the host-owned Zalo route. Notes are
general-purpose: plans, lists, decisions, ideas, references, preferences, and
other material the user explicitly asks to retain.

## Contract

- Preserve the user's meaning and language. Do not invent missing details.
- A date belongs to the record only when supplied or unambiguously resolved from
  the current-turn time context. Store it as `YYYY-MM-DD`.
- Keep distinct dated items as distinct records so date lookup remains useful.
- Give every new note a concise model-authored title, including content-only
  notes. Keep operational commentary out of both title and content.
- DM notes are private to that user scope. Group notes belong to that group
  scope. Never move or reveal notes across scopes.
- Creation, lookup, update, and deletion are different actions. Do not claim an
  action succeeded until the host API confirms it.
- When a non-bulk update or deletion matches several notes, present the
  candidates and ask which one; never guess. Apply multiple matches only when
  classify explicitly authorizes `bulk=true`; require `match_all=true` for a
  whole-scope delete.
- Answer questions from returned note contents. Date and full-text indexes are
  authoritative; semantic retrieval is supplementary.
- Do not write note content into repository files, `MEMORY.md`, prompts, or
  environment variables.

## Search then note

When the user asks to find live information and then note it:

1. Classify/runtime use a single search gather with `persist_gathered_notes=true`.
2. Follow `prompts/search_then_note_listing.txt` for the listing shape.
3. List only concrete findings. Each numbered record begins with a concise
   title, followed by useful details and an https source URL. This first line
   becomes the durable note title.
4. Never emit aggregate search-result buckets as noteable items. For job
   research specifically, use `Title (stack) — Employer` and one real opening
   per record rather than role/location/count summaries.
5. Prefer findings not already present in Prior notes when the host supplies them.
6. Never claim storage succeeded; the host persists numbered items after gather.

## Classifier plan

The classifier supplies `task_hint=note`, `task_type=note`, `skill=notes`, one
of `skill_action=create|lookup|update|delete`, and structured `notes` or
`note_selector` fields. For live gather-then-store, classify emits
`task_hint=search` with `persist_gathered_notes=true`. The Zalo host validates
and executes that plan against Memory service `/v1/notes*`; do not substitute
terminal SQL or filesystem scratch notes.

## Retrieval and mutation views

- Default/list lookup: the ten newest matches, date + title only.
- Count lookup: a compact count, without dumping note bodies.
- Detail lookup: one selected note with title, full content, and citations.
- Query and mutation selectors may combine a keyword with `date_from` and
  `date_to`. A bulk mutation must be explicit; an unqualified multi-match stays
  ambiguous.
