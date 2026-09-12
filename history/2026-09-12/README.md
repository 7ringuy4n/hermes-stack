# 2026-09-12 — titled notes, silent research schedules, and visual PPTX

## 14:10 — Note titles, clean retrieval views, and explicit bulk mutation

### Symptom

Whole-scope note deletion was rejected as an ambiguous multi-match, note counts
dumped long bodies, and saved research mixed useful findings with operational
commentary. Notes had no durable title, so list and detail views could not be
both compact and informative.

### Root cause

The note schema stored only `content`; classifier normalization discarded a
title and had no typed list/count/detail or explicit-bulk contract. The client
treated every multi-match mutation as ambiguous, including an authorized
whole-scope delete, and defaulted lookup to twenty verbose content rows.

### Technical detail

- **Functions:** `notes_client.py::execute_note_plan()` and
  `notes_client.py::_candidate_lines()` (`hermes/main/plugins/zalo/notes_client.py:L93–L248`).
- **Schema/API:** `architect/memory/memory-manager/app.py:L124–L160` and
  `app.py::query_notes()` (`L469–L533`) — `title` absent → optional persisted
  title; `limit=20`/oldest date order → default 10/newest-updated order.
- **Fields:** note item `title`; selector `view=list|detail|count`,
  `match_all`, and `bulk`.

### AI decision

Keep language understanding in classify/notes skills and make the host enforce
only typed authorization and scope. This avoids phrase-specific delete rules
while retaining the existing ambiguity safety boundary.

### Fix (core)

- Added an idempotent title-column migration, title-aware FTS, create/update
  persistence, and safe title backfill on a deduped create.
- Added compact newest-first lists, count and detail views, and explicit bulk
  range/keyword/all mutations.
- Made search-then-note output generic and structured, with concrete-job
  specificity as one domain rule and no storage/tool commentary.

### Todo list

- [x] Reproduce missing title and delete-all ambiguity in client units.
- [x] Change classifier, Memory API, host client, skills, and UX assets.
- [x] Extend the existing CRUD/citation tests instead of adding duplicate cases.
- [ ] Verify migrations and real-channel behavior on the clean VPS candidate.

### Prevent recurrence

`notes_crud_unit.py`, `notes_atomic_cite_unit.py`, and C10 now cover titles,
clean list/count/detail views, range mutation, whole-scope deletion, citations,
and ambiguity/scope boundaries.

## 14:35 — Search-only backend inherited by native page extraction

### Symptom

VPS Hermes logs showed native `web_extract` rejecting page hydration because it
inherited SearXNG, a search-only backend. Multi-source and scheduled research
could therefore stop at shallow snippets even while Router Worker had
Tavily/Firecrawl extraction available.

### Root cause

The shared Hermes config exposed the Router Worker SearXNG-compatible search
URL but did not set a separate extraction-capable provider. Upstream Hermes
strictly rejects a selected search-only provider for extraction.

### Technical detail

- **Function:** `scripts/main/patch-hermes-router-worker.py::_patch_web_routing()`
  (`L98–L119`) — missing `web.search_backend`/`web.extract_backend` → both
  `router-worker`.
- **Provider:** `RouterWorkerWebSearchProvider`
  (`hermes/main/plugins/web/router_worker/provider.py:L44–L85`) — native search
  and extract calls route to `/v1/search` and `/v1/extract`.
- **Config:** `web.extract_backend`: implicit `searxng` → `router-worker`;
  provider credentials remain in Router Worker/OpenBao.

### AI decision

Add a stack-owned Hermes web provider instead of copying provider secrets into
every Hermes replica or teaching the model to use shell/network workarounds.

### Fix (core)

The plugin normalizes Router Worker search and both Tavily/Firecrawl extraction
response shapes. The idempotent shared-config patch selects it for search and
extraction, and replica config synchronization propagates the setting.

### Todo list

- [x] Confirm the failure in prior VPS logs.
- [x] Trace strict upstream provider selection.
- [x] Add the stack provider and idempotent config patch.
- [x] Extend the existing router fallback unit.
- [ ] Prove native search + extraction after VPS deployment.

### Prevent recurrence

`router_worker_fallback_unit.py` now checks config idempotence and normalizes
both extraction-provider response shapes. C4 requires real multi-source page
hydration and honest blocked-page handling.

## 15:00 — PPTX discarded model-selected visuals

### Symptom

A requested three-slide weather presentation could arrive as plain slides or
the wrong artifact family, with no scenic image and weak visual hierarchy.

### Root cause

The file-generation skill mentioned optional images, but
`office_file.py::write_pptx_styled()` explicitly discarded every `IMAGE:` line
and exposed no validated model-selectable layout directive.

### Technical detail

- **Function:** `architect/models/dispatcher/office_file.py::write_pptx_styled()`
  (`L785–L1000`) — `IMAGE:` ignored → safe media-root resolution and embedding.
- **Fields:** PPTX body `IMAGE:` and
  `LAYOUT=full-bleed|image-left|image-right|minimal`.
- **Renderer boundary:** model owns slide story/count/layout; Dispatcher
  validates media paths and renders the selected composition.

### AI decision

Retain a deterministic safe renderer while moving content hierarchy, slide
count, image brief, and layout choice to the skill/model. Removing the renderer
would lose path, overflow, and delivery safety; keeping one fixed template would
repeat the reported failure.

### Fix (core)

PPTX generation now embeds a validated scenic still as full-bleed or split
layout, preserves exactly authored sections as slides, and never creates a
second deliverable. The flexible composed-image live test accepts the semantic
bottom region chosen by the model while retaining scene-visibility constraints.

### Todo list

- [x] Reproduce image directives being discarded.
- [x] Add model-authored PPTX layout directives and safe renderer support.
- [x] Extend the existing PPTX test to require exactly three slides and media.
- [ ] Render and inspect the VPS artifact; reject clipping or poor balance.

### Prevent recurrence

C9 now requires one three-slide PPTX, embedded scenic media, visual inspection,
no PDF substitution, and no separately delivered intermediate image.
