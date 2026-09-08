# 2026-09-07

## 19:48 — standalone lifecycle and asynchronous delivery release gate

### Symptom

Standalone Compose inspection or teardown could fail after plaintext secrets
were scrubbed, cold-start knowledge synchronization could wait for an
interactive privilege prompt, and recovered or scheduled work could complete
without durable proof that the response reached its original destination.

### Root cause

Lifecycle helpers did not share the OpenBao hydration boundary used by full
startup. Post-ready synchronization assumed an interactive host session. Queue
recovery retained work content but did not rebind the original conversation,
while scheduled processing crossed an asynchronous boundary that discarded
the originating message identity. The classifier also had no explicit generic
contract separating simple reminder content from work that needs live tools.

### Technical detail

- **Function:** `run.sh::do_compose_with_openbao_env()` wraps standalone
  Compose commands with transient secret hydration and guaranteed cleanup.
- **Function:** `run.sh::do_post_ready_learn()` prepares the bind mount with a
  noninteractive privilege check and executes synchronization inside the
  running service container.
- **Function:** `adapter.py::_as_run_queued_part()` rebinds the queued
  destination before handling recovery and requires the actual delivery event
  before acknowledgement.
- **Functions:** `adapter.py::_on_inbound_guarded()`,
  `_as_schedule_fire_verbatim()`, and `send()` carry a task-local source
  identity through asynchronous schedule execution.
- **Fields:** `delivery_kind`, `source_message_id`, and `scheduleDelivery`
  distinguish queue recovery, generated results, and schedule-originated
  delivery without exposing internal execution identifiers.
- **Prompt:** `skills/classify/parts/delivery.txt` makes simple reminders
  verbatim and reserves process-mode scheduling for requests requiring live
  lookup, tools, reasoning, or generated content.

### AI decision

Transport acceptance, not content generation or a log intention, is the
terminal success boundary. Task-local context preserves the schedule source
across concurrent asynchronous work without mutable global state. Reminder
semantics remain model-driven through the shared prompt while code validates
only routing and delivery invariants.

### Fix (core)

Unified standalone lifecycle secret hydration, made post-ready synchronization
unattended-safe, fenced queue acknowledgement on confirmed delivery, rebound
recovered work to its original destination, and propagated schedule source
identity through a context-local value. Hardened the classifier prompt and
release labs to prove exact source/destination correlation.

### Todo list

- [x] Verify a clean destroy and full-feature startup.
- [x] Verify concurrent direct and threaded conversation delivery.
- [x] Verify owner failover and fenced recovery without duplicate output.
- [x] Verify image, vision, document, and web capability delivery.
- [x] Reproduce and repair schedule evidence and reminder semantics.
- [x] Verify one acknowledgement and one correlated schedule delivery.
- [x] Verify plain and quoted active-request cancellation without exposing an
      internal execution identifier.

### Prevent recurrence

Lifecycle, queue, delivery-history, classifier assembly, scheduler, continuous
message, and concurrency tests now cover these boundaries. Future live gates
must correlate schedule delivery to its durable source row and may not infer
success from generated content, logs, or a synthetic bridge echo.

## Attachment acknowledgements were absent from durable delivery history

### Symptom

Text responses acknowledged by the messaging bridge were written to the
shared delivery ledger, but successful image, document, video, and voice sends
were not. In a multi-replica deployment this prevented source-message
correlation and made attachment recovery decisions depend on process-local
logs.

### Root cause

The attachment methods returned the bridge response immediately after a
successful send. They never called the same durable history path used by text
delivery. The affected paths were `send_image_file`, `send_document`,
`send_video`, and `send_voice` in
`hermes/main/plugins/zalo/adapter.py:L8325-L8662`.

### Fix

`_as_bridge_message_id` structurally extracts the acknowledgement identifier
from supported bridge response envelopes. `_as_record_attachment_delivery`
then records a `delivered` event containing `source_message_id`,
`delivery_kind`, `attachment_kind`, `file_name`, quote state, and the bridge
message identifier (`hermes/main/plugins/zalo/adapter.py:L8257-L8323`). Each
acknowledged attachment path calls the helper; failed sends still do not create
false delivery evidence.

`test/scripts/zalo_delivery_history_unit.py` locks the helper contract and all
attachment call sites. Syntax checks plus delivery-history, inbound-queue, and
media-shortcut units passed locally. The updated adapter was applied with the
core component updater after verified backup `20260907_065600`; both replicas
returned running with zero restarts and the connector remained logged in with
one event stream.

### Prevent recurrence

Every externally acknowledged delivery type must write one shared durable
record keyed to its source message. Live media tests must require the matching
attachment kind in that record and must not treat a text acknowledgement as
proof that a requested file was sent.

## Production composed-image gate remains blocked by intermittent classification

### Observation

The corrected live gate injected the real request before any diagnostic model
calls. Durable queue events advanced through enqueue, processing, user turn,
assistant turn, and a text delivery with the same source identifier. The
required `search_composed_image_shortcut` and attachment-send events did not
occur within six minutes, so the case failed. An immediate post-run classifier
probe returned the required `search,media_generation` dependency graph; the
daily wrapper probe returned `unknown`.

### Test correction

`test/scripts/zalo_weather_fuel_lab.py:L61-L257` now separates live execution
from post-run classifier contract probes. It requires the production host
shortcut, an acknowledged media send, and a durable `delivered` row whose
`source_message_id` matches the injected request and whose
`attachment_kind=image`. Diagnostic classifier calls run only after delivery
observation, so the gate cannot starve the request it measures.

### Resume checkpoint

The release gate is not passed and no merge request is authorized yet. Resume
by diagnosing the Router Worker/classifier response associated with the failed
source turn, then fix the core classification path without weakening the gate.
After that, rerun the focused live case and the remaining release checks. The
requested large-scale comparative benchmark remains skipped.

## Client library replacement review

No production-safe drop-in replacement for the audited vendored client was
found. The closest actively published alternative has a smaller API surface,
retains deprecated native/cryptographic dependencies already removed from the
vendored fork, and lacks equivalent provenance metadata. Another fork is
older and retains the same dependencies; the Python alternative is archived;
the official SDK targets a different account/API surface.

For this release, retain the audited vendored client and its native Node crypto
implementation. Revisit migration only after an alternative proves maintained
provenance, required personal/group API coverage, dependency parity, and the
full bridge integration suite.

## 07:36 — Dependent execution graph was split into synthetic queue turns

### Symptom

The production composed-image case generated and delivered an image, but the
strict source-correlation gate failed. The original request first produced a
text response, while the attachment delivery was recorded against a synthetic
`:part2` source identifier instead of the original inbound identifier.

### Root cause

`multi_request.py::split_compound_requests()` treated every classifier
`instructions` entry as an independent user request. A single deliverable may
legitimately contain several execution nodes, such as search followed by a
dependent media-generation node. The queue split that dependency graph into
separate turns and classified the resulting parts again, allowing routing
variance between admission and execution.

### Technical detail

- **Functions:** `multi_request.py::parts_from_plan()` and
  `classify_compound_request()` preserve dependent graphs and return the
  reusable plan (`hermes/main/plugins/zalo/multi_request.py:L29-L64`).
- **Queue site:** `_as_drain_queue()` stores the successful atomic plan on the
  existing queue item and clears it only when independent parts are created
  (`hermes/main/plugins/zalo/adapter.py:L4126-L4198`).
- **Fields:** `task_details[].depends_on`: non-empty dependency edge previously
  produced separate `message_id:partN` turns; fixed behavior retains one
  original `message_id` and one plan.
- **Classifier protocol:** `retry=1` was incorrectly interpreted as one total
  request. It now means one bounded repair after the initial request, using the
  versioned `repair_template` (`architect/models/router-worker/classify.py:L1212-L1321`).

### AI decision

The queue cannot infer natural-language intent. It can, however, enforce the
classifier's typed dependency graph. Keeping any graph with a dependency edge
atomic is generic, preserves the model-owned intent boundary, and avoids an
input-specific exception. Reusing that same plan also removes a redundant
model call. A bounded protocol repair was chosen over an arbitrary retry: it
only follows a successful but structurally unusable response and supplies a
generic versioned correction instruction.

### Fix (core)

- Added dependency-aware split planning and atomic-plan reuse.
- Corrected `retry` semantics and added one schema-repair prompt asset.
- Added structural classifier diagnostics without logging user content.
- Kept the audited vendored client and existing OmniRoute combo membership.

The queue and classifier regression units passed locally. On the VPS, the
strict pre-fix gate correctly failed even though the image was sent, because
the attachment belonged to `:part2`. After the core update, the strict gate
recorded the image against the original unsuffixed source identifier and both
immediate and scheduled classifier contracts passed.

### Todo list

- [x] Reproduce classifier instability and dependent-graph splitting.
- [x] Implement bounded protocol repair and dependency-aware queue planning.
- [x] Add focused local regression coverage.
- [x] Run the current strict VPS case without weakening its assertions.
- [x] Apply the atomic queue fix through the core component updater.
- [x] Rerun the strict case and verify the attachment uses the original source
  identifier.
- [x] Run the complete local unit inventory and production health/log checks.
- [ ] Complete the merge-request release workflow.

### Prevent recurrence

`inbound_queue_unit.py` now proves that dependency graphs stay atomic while
independent roots still split. `router_worker_classify_repair_unit.py` proves
that `retry=1` performs exactly one repair using the prompt asset. The live gate
requires the host shortcut, attachment acknowledgement, and an image delivery
row correlated to the unsuffixed source identifier.

## 08:04 — Stateless provider calls shared one anonymous session

### Symptom

An immediate classifier contract returned a scheduled plan after a previous
scheduled probe, even though the same request classified correctly with an
explicit conversation identity.

### Root cause

Provider session correlation used one constant fallback when callers omitted
conversation metadata. Unrelated stateless requests could therefore share
provider-side conversational affinity.

### Technical detail

- **Function:** `session_headers.py::_request_content()` supplies a stable
  content discriminator after explicit header, conversation, user, and chat
  message identities are exhausted
  (`architect/models/router-worker/session_headers.py:L32-L48`).
- **Call site:** `conversation_seed()` hashes that discriminator instead of
  returning the shared `anonymous` seed
  (`architect/models/router-worker/session_headers.py:L51-L70`).
- **Fields:** body `text`, `prompt`, or `input` are serialized deterministically
  and then one-way hashed; raw content is never placed in the provider header.

### AI decision

Stateless calls still require stable correlation, but a global identifier
violates isolation. Content-derived opaque correlation preserves stability for
identical retries while separating unrelated requests without adding an
application-language intent rule.

### Fix (core)

Added deterministic request-content fallback correlation and unit coverage for
string and structured payloads. Immediate and scheduled VPS classifier probes
then remained isolated and returned their respective typed graphs.

### Todo list

- [x] Reproduce the cross-request contamination boundary.
- [x] Add a privacy-preserving stateless fallback.
- [x] Verify raw request content is absent from the header.
- [x] Rebuild Router Worker and rerun both classifier contracts.

### Prevent recurrence

`router_worker_session_header_unit.py` proves identical stateless payloads are
stable, different payloads do not collide, and plaintext content is not exposed.

## 08:06 — Classifier repair feedback hid the violated contract

### Symptom

A scheduled classifier request exhausted its one repair attempt on both model
combos and returned `unknown`, although every upstream request completed with
HTTP 200.

### Root cause

The structural validator returned only a boolean. Repair feedback therefore
said `invalid_schema` without identifying the missing timing-or-uncertainty
contract, so a weak model could repeat the same invalid structure.

### Technical detail

- **Function:** `classify.py::plan_schema_failure()` returns generic structural
  failure codes for composed-image dependencies and schedule timing
  (`architect/models/router-worker/classify.py:L396-L457`).
- **Repair site:** `classify_with_llm()` passes the exact failure code into the
  existing versioned repair template and logs only that code
  (`architect/models/router-worker/classify.py:L1318-L1330`).
- **Config:** `retry=1` remains one bounded repair; no wait, retry count, combo
  membership, or operator-owned model configuration changed.

### AI decision

Adding retries would increase load without explaining the defect. Precise
schema feedback improves the already-authorized repair turn while keeping
semantic interpretation in the model and deterministic validation in code.

### Fix (core)

Replaced boolean-only validation internals with failure codes while preserving
the public boolean wrapper. Added a missing-schedule-timing repair regression.
The final strict VPS case passed artifact delivery, source correlation, and
both immediate and scheduled classifier contracts.

### Todo list

- [x] Distinguish provider failure from schema failure in live logs.
- [x] Implement structural failure codes without user-text logging.
- [x] Verify the bounded repair unit and the full local unit inventory.
- [x] Rebuild Router Worker and pass the strict production gate.

### Prevent recurrence

`router_worker_classify_repair_unit.py` now requires the repair prompt to name
`schedule_requires_timing_or_explicit_uncertainty`. The live gate continues to
require both classifier variants after successful media delivery.
