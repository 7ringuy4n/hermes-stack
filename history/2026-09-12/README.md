# 2026-09-12 — titled notes, silent research schedules, and visual PPTX

## 20:20 — Gray image bands, unregistered web search, and noisy status output

### Symptoms

Generated information images contained large gray side or bottom bands and
opaque cards that hid the scene. A concurrent current-weather gate delivered
two plausible answers but only one attributed routed search. Async workflows
sent a visible processing placeholder, while critical file alerts exposed a
raw nested scanner dictionary.

### Root causes

- The image path generated a text-free background and then resized/painted it
  through `dispatcher/overlay.py`; this deterministic canvas step could not
  adapt to scene saliency or arbitrary user-requested placement.
- The stack web plugin declared `router-worker` in `plugin.yaml` but its
  `__init__.py` had no `register(ctx)` call, so Hermes rejected the configured
  native provider and the model could answer without a fresh tool result.
- After registration was added, live deployment still skipped the provider:
  Hermes user plugins are opt-in, the preserved enabled list contained only
  the Zalo plugin, and the post-start config patch did not reload replicas.
  The dynamic plugin also needs a package-relative provider import.
- Workflow submission unconditionally announced a localized started message,
  and Security Manager interpolated its internal `layers` object into alerts.
- The concurrent DM/group burst delivered every answer but retained one queue
  claim past the gate deadline. Session-idle detection used substring matching;
  because a group session key ends with its sender id, that key was mistaken
  for the same sender's DM destination and coupled otherwise isolated queues.

### Decisions and fixes

- Keep evidence planning and copy validation, then send the complete scene,
  exact grounded copy, grouping, and spatial constraints to `image-gen` in one
  prompt. The model owns typography and composition. Remove `overlay.py`, the
  dispatcher endpoint, related request fields, and renderer-specific tests.
- Require a full-bleed result in the image prompt and live gate; forbid gray or
  blank padding, split canvases, and large opaque panels that conceal the scene.
- Register `RouterWorkerWebSearchProvider`, enable its path-derived
  `web/router_worker` key without replacing operator entries, use a relative
  package import, sync it with every replica, and reload running Hermes
  containers after setup/update applies the shared config.
- Keep durable internal queue processing records, but remove the visible async
  workflow placeholder. Format critical alerts as filename, concise blocking
  reason, and quarantine outcome only.
- Pass the typed destination into session-idle waits and match the exact DM
  payload or group destination prefix. Never infer queue ownership from an id
  occurring anywhere in another session key.

### Verification and prevention

- Focused composition, skill, provider-registration, workflow, and security
  units pass locally.
- The provider unit now covers preserved/idempotent enabled-list mutation and
  requires the setup/update reload hook, preventing a discovered-but-skipped
  plugin from passing deployment tests again.
- The turn-wait unit reproduces a group key ending in the concurrent DM user's
  id and requires it not to hold the DM queue; delivery/timeout queue contracts
  remain covered by their existing units.
- The release gate retains concurrent DM/group attributed search and terminal
  source correlation; the flexible image gate now requires model-rendered
  full-bleed composition and rejects any legacy endpoint call.
- VPS deployment, focused live reruns, and the complete numbered gate remain
  required before merge.

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

## 18:45 — Extraction still unavailable without optional provider keys

### Symptom

After the clean VPS deployment selected the correct Router Worker provider,
`POST /v1/extract` still returned a controlled 502 whenever both optional
Tavily and Firecrawl extraction keys were absent.

### Root cause

Router Worker had only credentialed extraction adapters. Its local SearXNG
fallback intentionally supports search only, and there was no safe bounded
reader for ordinary public result pages.

### AI decision

Keep credentialed extraction first for richer parsing, then use a narrow
public-page reader as the final adapter. Validate every initial and redirect
URL, reject URL credentials/non-standard ports/non-global addresses, disable
environment proxies, accept only textual content, and enforce byte/character
limits.

### Fix (core)

- Added the `direct` extraction adapter after Tavily and Firecrawl.
- Added DNS/address and redirect validation plus a 2 MiB response bound.
- Added conservative HTML text/title extraction and normalized its response in
  the stack-owned Hermes provider.
- Extended the existing Router Worker fallback unit with direct-response,
  HTML-cleaning, and private-destination rejection cases.

### Todo list

- [x] Reproduce the keyless 502 on the deployed candidate.
- [x] Add and unit-test the safe direct adapter.
- [ ] Redeploy and prove extraction against a public page.
- [ ] Run the full numbered and real-channel suites.

### Prevent recurrence

The Router Worker fallback test now requires credential-free direct extraction
to remain last in the adapter order and verifies that non-public targets are
blocked before any fetch.

## 19:05 — Empty legacy schedule title broke compact listing

### Symptom and root cause

The production-image matrix found that a legacy schedule row with no `name`,
`fire_text`, or `text` raised `IndexError`: the compact formatter indexed the
first line of an empty list while deriving a fallback title.

### Fix

Use the first body line only when it exists; otherwise retain the existing id
fallback. The classifier-repair fixture now emits the required explicit
`persist_gathered_notes: false`, and the permission fixture recognizes the
newer per-file writability guard in addition to the directory guard.

### Prevent recurrence

`schedule_list_classify_unit.py` retains the empty-row case and must render the
schedule id without raising.

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
