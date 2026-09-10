---
name: coding
description: "Coding and UI/UX work via Memory Manager + knowledge_chunks RAG and vendored skills. Triggers: code, implement, refactor, TypeScript, React, UI, design system, bug, TDD, architecture. No Gateway rate-limit on coding paths. Prefer local knowledge (top 5) over inventing."
---

# Coding (skills-only)

Hermes orchestrates coding with **skills** — there is **no** coding-worker container.

## Must follow

1. Use **Memory Manager** (`MEMORY_URL`, `/v1/context`, `/v1/remember`) for durable facts — Postgres SoT.
2. Use **knowledge ingest** (`INGEST_URL`, collection `knowledge_chunks`) for docs/specs: **top 5** + count of rest; empty/down → refuse, no invent, no internet on Low.
3. Prefer vendored skills under:
   - `core/*`, `knowledge/*`, `coding/*`, `communication/*` — Hermes wrappers (see `skills/README.md`)
   - `vendor/superpowers/` — systematic-debugging, verification-before-completion, TDD, git
   - `vendor/trailofbits/` — audit-context-building, differential-review, insecure-defaults
   - `vendor/mattpocock/` — implement, codebase-design, diagnosing-bugs, tdd, code-review, improve-codebase-architecture
   - `vendor/ui-ux-pro-max/` — ui-ux-pro-max, design-system, design, ui-styling
   - `vendor/anthropic/skill-creator/` — operator skill authoring only
4. Heavy OCR/image still goes through **dispatcher workers** (async) — do not block the chat turn on long jobs.
5. Do **not** add coding-specific rate limits (Gateway skips `/coding` and `X-Assistant-Skill: coding`).

## Attribution

See `vendor/mattpocock/ATTRIBUTION.md`, `vendor/ui-ux-pro-max/ATTRIBUTION.md`, `vendor/superpowers/ATTRIBUTION.md`, `vendor/trailofbits/ATTRIBUTION.md`.
