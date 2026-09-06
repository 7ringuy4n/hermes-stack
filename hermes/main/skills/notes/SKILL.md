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
- DM notes are private to that user scope. Group notes belong to that group
  scope. Never move or reveal notes across scopes.
- Creation, lookup, update, and deletion are different actions. Do not claim an
  action succeeded until the host API confirms it.
- When an update or deletion matches several notes, present the candidates and
  ask which one; never guess.
- Answer questions from returned note contents. Date and full-text indexes are
  authoritative; semantic retrieval is supplementary.
- Do not write note content into repository files, `MEMORY.md`, prompts, or
  environment variables.

## Classifier plan

The classifier supplies `task_hint=note`, `task_type=note`, `skill=notes`, one
of `skill_action=create|lookup|update|delete`, and structured `notes` or
`note_selector` fields. The Zalo host validates and executes that plan against
Memory service `/v1/notes*`; do not substitute terminal SQL or filesystem
scratch notes.

