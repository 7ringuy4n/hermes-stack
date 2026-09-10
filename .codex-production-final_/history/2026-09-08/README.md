# 2026-09-08 — bounded queue-session recovery

## Symptom

A two-destination concurrency gate accepted both inbound events, but only one
request produced its expected response inside the test window. The other queue
claim remained active while the agent repeatedly called model fallbacks. Its
eventual outbound was a timeout notice rather than the requested answer.

## Cause

The platform handler starts agent execution in a background session task. The
durable queue coroutine waited for that session to become idle, but a failed
idle wait abandoned only the queue-side coroutine. It did not cancel the base
adapter session task. In addition, the queue wrapper caught nested
`TimeoutError` values as though its own outer deadline had expired, producing a
misleading configured-duration message.

## Decision and fix

- Cancel the base adapter session task before releasing a claim whose agent did
  not become idle.
- On the outer queue deadline, cancel the same session defensively.
- Distinguish outer cancellation from nested operation timeouts in logs.
- Keep the recovery notice duration-neutral and free of internal process data.
- Make the live two-destination gate require the expected content as well as one
  source-correlated delivery per destination.
- Reinforce the generic response policy so simple, self-contained requests do
  not invoke unrelated tools because of older context.
- Hydrate short model context from completed user/assistant exchanges only.
  User-only records remain durable but cannot repeatedly re-seed a later turn.
- Remove the older duplicate worker-routing entry and disambiguate the vendored
  code-review skill. A unit contract now rejects duplicate registry names.
- Forward the queued attachment list and attachment-kind signal through the
  early media gate. Previously an image-edit plan returned from that gate
  without its source, so the dispatcher was never called.
- End media labs on externally observable artifact and delivery evidence rather
  than an optional flow-log marker.
- Replace the PDF lab's optional missing extractor with the renderer dependency
  already shipped by the worker, then require text extraction, page rendering,
  and an independent visual evaluation.
- Crop the accidental lower-page void from sparse, text-bearing one-page PDFs.
  The operation is structural and topic-neutral; multi-page, image-only, and
  already balanced pages preserve their original geometry.
- Bind every PostgreSQL readiness probe to the configured database name. A
  role-only probe still reported ready but attempted a connection to a missing
  role-named database every five seconds, obscuring meaningful production logs.
- Regenerate the committed Router Worker classifier fallback from the canonical
  prompt parts and assert exact equivalence in the unit gate. This prevents a
  normal update from rewriting tracked source when a prompt part changes.

## Verification

Verification requires the full local unit suite, a clean VPS lifecycle check,
the two-destination real-channel test, owner failover, queue drain, and a final
log/restart audit. A release must not advance while any of those checks fail.

This release gate completed 103 unit scripts without failure, exercised direct
and quoted cancellation in private and group scopes, delivered eight ordered
messages across two concurrent destinations, retrieved exact records from a
disposable ten-million-row corpus with indexed sub-millisecond queries, and
delivered both a real quoted-image edit and a rendered single-page PDF for
independent visual review.

## Capability concurrency and scheduler startup ordering

### Symptom

A clean full-profile deployment started all requested services, but the
scheduler restarted once before becoming healthy. Its first connection attempt
failed while the internal PostgreSQL hostname was not yet resolvable. Existing
two-destination tests also concentrated on ordered text and quote isolation and
did not prove that independent conversations could run search and file
generation at the same time.

### Cause

The scheduler had a runtime database dependency but no Compose startup
dependency. Its restart policy recovered the service, masking the avoidable
startup fault. The concurrency suite verified queue mechanics without
transport-acknowledged capability artifacts or provider-side search
attribution.

### Decision and fix

- Require PostgreSQL to be healthy before Compose starts the scheduler.
- Assert that dependency in the offline defaults contract.
- Add two simultaneous private/group bursts for current-weather search and
  DOCX generation.
- Correlate each delivery to its source event, verify both generated packages,
  inspect exact document content, confirm search-combo attribution, obtain an
  independent semantic score, and require complete queue drain.
- Resolve private runtime identities from protected state and keep numeric
  identities out of source and reports.
- Normalize the example and operator documentation to the runtime queue cap.
  Environment cleanup upgrades only the exact retired default, leaving
  operator-selected capacities unchanged.

### Verification

The corrected scheduler started healthy with zero restarts and no database
resolution error. The live capability gate delivered both weather answers,
attributed both searches to the expected combo, delivered two valid and
content-isolated DOCX packages, received a perfect semantic evaluation, and
left both destination queues empty without a queue timeout.

The environment migration unit gate also proved that the retired queue cap is
upgraded and a custom cap remains byte-for-byte unchanged.

The first post-update repetition exposed a real artifact-isolation defect. Two
simultaneous office shortcuts created distinct files, but the completion path
directly delivered only image outputs and fell back to scanning the shared
output directory for documents. Each conversation could therefore claim the
other conversation's document, while a bridge-created `send-` copy used a
second fingerprint and allowed a duplicate delivery.

The shortcut completion path now treats its returned file path as
authoritative for every supported artifact type and sends that exact path.
Shared-directory discovery remains only for legacy shortcuts that return no
path. File claims also canonicalize bridge staging prefixes, so source and
staged copies have one identity. The live gate must be repeated unchanged;
the failed repetition is retained as regression evidence rather than accepted
as a pass.

## Prevention

Future concurrency labs must retain structured evidence for both delivery and
semantic outcome. Any asynchronous layer that waits on a lower-level task must
also define how that task is fenced or cancelled when the wait expires.
Changes to classifier prompt parts must regenerate the committed fallback in
the same change; exact bake equivalence is a release invariant.

## Multi-domain evidence and flexible spatial composition

### Symptom

A composed image with several independently sourced subjects could retain only
one subject and one placement. Layout choices were limited to corner badges,
so repeated side requests and precise in-image or embedded-document regions
could overlap or be omitted.

### Root cause

The classifier could legally emit one broad search for multiple evidence
domains, while the host executed only the first declared query. The composition
schema then exposed one top-level fact collection and one placement. The image
renderer had no normalized region contract and supported only four corners and
a bottom bar.

### Technical detail

- **Functions:** `media_shortcuts.py::_evidence_queries()`,
  `::_synthesize_overlay_plan()`, `::_overlay_panels_payload()`, and
  `::run_search_then_composed_image()` at
  `hermes/main/plugins/zalo/media_shortcuts.py:L340-L460,L654-L700,L1253-L1315`.
- **Renderer:** `overlay.py::_normalized_region()`, `::apply_overlay()`, and
  `::apply_overlay_panels()` at
  `architect/models/dispatcher/overlay.py:L182-L220,L253-L350,L352-L400`.
- **API fields:** `ImageReq.overlay_panels` and
  `overlay_design.region={x,y,width,height}` at
  `architect/models/dispatcher/app.py:L174-L194,L783-L815`; normalized values
  are clamped to the drawable image and malformed regions are ignored.
- **Contract:** `design.placement` expanded from four corners plus one bar to a
  nine-cell grid, bars, and side columns; `panels` expanded from one effective
  region to six validated regions.

### AI decision

Keep natural-language decomposition and design in English prompt assets, then
validate only structural fields in Python. A topic-specific parser or fixed
two-column template would repair one example but leave future subjects,
languages, and positions uncovered. Documents reuse the composed-image API for
copy over an embedded image and retain normal-flow tables/sections for ordinary
page layout.

### Fix (core)

- Plan up to four focused evidence searches and execute every planned query.
- Synthesize up to six independent panels while preserving requested subjects,
  language, timestamp label, and relative positions.
- Support named grid regions and arbitrary normalized rectangles, clamp them
  to safe bounds, and distribute repeated-side or automatic panels into stable
  non-overlapping slots.
- Teach the file-generation skill to preserve multi-region page relationships
  and to compose image overlays before embedding them in a document.
- Replace the classifier-only lab assertion with stronger runtime evidence:
  the live gate now requires at least two executed evidence queries in addition
  to classifier graph validity and source-correlated delivery.

### Todo list

- [x] Reproduce the missing-subject and single-placement output.
- [x] Fix evidence decomposition and multi-result composition in core source.
- [x] Add named, repeated-side, and normalized-region renderer variants.
- [x] Add the embedded-document spatial contract and regression checks.
- [x] Pass focused local compile, render, workflow, and Office structure gates.
- [x] Apply through the normal VPS updater with a verified backup.
- [x] Pass live multi-domain delivery and visually inspect the generated image.
- [x] Render and inspect a one-page PDF containing the six-region composition.
- [x] Audit container and bridge logs plus restart counts after the run.

### Verification

Local focused gates passed, including a six-region raster and three repeated
left-side panels. The VPS overlay endpoint rendered twelve lines across six
normalized regions; a one-page PDF embedded the resulting image and retained
all six regions. The real channel run decomposed one broad classifier query
into two evidence searches, delivered one source-correlated image, and passed
both immediate and scheduled classifier contracts. Visual review confirmed two
requested subjects in their requested left/right regions with localized,
legible copy and no overlap.

All observed core containers remained running with zero restart counts. Two
Traefik health warnings occurred while the recently recreated Hermes service
was handling the long media request; subsequent probes recovered without a
restart or delivery failure. This non-terminal load sensitivity remains an
operational observation rather than a release failure.

### Prevent recurrence

`composed_image_overlay_unit.py` covers malformed regions, six custom regions,
and repeated-side distribution. `media_capability_skills_unit.py` protects the
document contract, and `zalo_weather_fuel_lab.py` requires runtime evidence
decomposition instead of assuming one exact classifier graph shape. Future
capability gates must continue visual inspection; file existence alone is not
sufficient.

## 19:12 — Structured composition output exhausted its completion budget

### Symptom

A request with two independently sourced image regions completed classification
and both searches but returned no artifact. The user received the generic
artifact failure response while all services remained healthy.

### Root cause

The structured composition call allowed only 720 completion tokens. The active
reasoning model used part of that budget internally and emitted a detailed but
unfinished JSON object with `finish_reason=length`. Structural parsing correctly
rejected the incomplete object, leaving no composition to render.

The follow-up consistency gate exposed a second contract mismatch. Classifier
prompting now permits one focused search per evidence domain, but Router Worker
validation still required exactly one search. Valid two-search plans were
rejected through every repair attempt and surfaced as an `unknown` plan.

Visual review of the first successfully delivered artifact exposed a third,
non-terminal presentation defect: the model placed a source timestamp inside
`timestamp_label`, then the renderer appended its authoritative current time.
The resulting line contained two dates even though the factual panels and
requested positions were correct.

### Technical detail

- **Functions:** `media_shortcuts.py::_omni_json_plan()` and
  `::_synthesize_overlay_plan()` at
  `hermes/main/plugins/zalo/media_shortcuts.py:L321-L380,L410-L435`.
- **Key:** `OMNI_OVERLAY_PLAN_MAX_TOKENS` — absent/implicit `720` → bounded,
  operator-configurable default `4096` with accepted range `1024..8192`.
- **Fields:** chat request `max_tokens=720` → `4096`; provider response
  `finish_reason=length` and incomplete `message.content` → diagnostic rejection
  with model, finish reason, content length, and budget only.
- **Prompt asset:**
  `hermes/main/skills/classify/parts/image-runtime.json:5` now requests compact
  minified JSON, bounded fact rows, a bounded scene brief, and omission of
  non-material optional design fields.
- **Validator:** `architect/models/router-worker/classify.py::plan_schema_failure()`
  at `architect/models/router-worker/classify.py:L396-L432` — exactly one search
  → one or more searches, all preceding and linked to exactly one media task.
- **Timestamp ownership:** composition prompt asset — a loosely described short
  label → a localized words-only label with date, time, number, and source
  freshness values explicitly reserved for the renderer.

### AI decision

Retain strict JSON validation and the LLM-owned visual plan. Repairing an
unfinished object in host code could accept missing subjects or unsupported
facts, while topic-specific fallback panels would violate the generalization
contract. A configurable adequate budget plus compact schema guidance addresses
the failure class without interpreting user language in Python.

### Fix (core)

- Add a bounded planning-budget helper and use it for the complete composition
  call.
- Preserve the shorter evidence-query budget because that schema contains only
  one small string array.
- Add safe diagnostics when a provider returns no parseable object.
- Require the live multi-region gate to observe a complete planner response.
- Accept the intended per-domain search graph while continuing to reject missing,
  reversed, or partially linked dependencies.
- Keep timestamp formatting under renderer ownership while leaving language and
  visual-copy selection with the composition model.

### Todo list

- [x] Correlate the failed delivery with classifier, search, and planner logs.
- [x] Capture the provider finish reason and confirm truncated JSON.
- [x] Correct the source-owned planning budget and compact-output prompt.
- [x] Add unit and live-gate regression coverage.
- [x] Align Router Worker validation with the multi-domain classifier contract.
- [x] Deploy the focused fix through the normal updater and repeat the real request.
- [x] Inspect the first delivered artifact and reject its duplicate timestamp.
- [x] Repeat the live request with the timestamp-label contract and inspect it.
- [x] Audit service restarts/errors.

### Verification

The exact multi-source request completed twice after the structured-output fix.
Both runs executed two evidence queries, produced a source-correlated artifact,
and recorded successful delivery without an empty or truncated planner response.
The immediate and scheduled classifier contracts both returned the intended
two-search graph followed by one dependent media task. Visual review rejected
the first artifact's duplicate timestamp, then confirmed the corrected artifact
had localized, legible left/right panels and one renderer-owned current stamp.

Focused compile, overlay, media-skill, workflow, multi-request, planner-budget,
and Router Worker repair gates passed. The service audit found zero container
restart counts and no post-test application errors in either Hermes replica,
the bridge, Router Worker, or OmniRoute. Traefik logged a brief connection refusal
only while the explicitly requested plugin synchronization restarted Hermes;
subsequent health probes and both attachment deliveries returned HTTP 200.

### Prevent recurrence

`media_shortcuts_omni_unit.py` asserts both the configurable bound and that
composition synthesis invokes the full budget. `composed_image_overlay_unit.py`
protects the compact prompt contract. `zalo_weather_fuel_lab.py` rejects a run
that logs invalid structured planning, even if later file or delivery evidence
were otherwise present.
