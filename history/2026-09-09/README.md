# 2026-09-09 — scheduled composed-image execution, adaptive layout, and locale integrity

## Symptom

A composed image requested for a future time was acknowledged and stored, but
the due execution returned a text-only answer. The same execution attempted to
quote a non-existent Zalo message and received an invalid-parameter response.
A Vietnamese note request also received an English confirmation. Multi-region
composition depended on a deployment-specific token-budget environment value.

## Root cause

The classifier and schedule record were correct: the persisted plan contained
independent evidence searches, one dependent `media_generation` task, and
`schedule_delivery=process`. In the queue-enabled path,
`ZaloAdapter._as_enqueue_inbound` sent `schedule_fire` directly to
`_as_dispatch_event` (`hermes/main/plugins/zalo/adapter.py:L4083`) instead of
executing the stored plan. Generic Hermes therefore tried its own web/image
tools and could only produce text when image generation was unavailable.

The same synthetic fire was converted into a `SendMessageQuote` even though its
`schedule:<id>:<execution>` identifier is an internal correlation id rather
than a Zalo message id (`adapter.py:L5597`). Attachment delivery also omitted
the task-local schedule source fallback (`adapter.py:L8449`), weakening durable
correlation for scheduled files.

Note UX keys were absent from `hermes/main/messages/ux.json`, so the host-owned
note branch used its English fallback. Composed planning read
`OMNI_OVERLAY_PLAN_MAX_TOKENS` even though the accepted JSON structure is
already strictly bounded (`media_shortcuts.py:L303`).

A clean full-feature redeploy also exposed a restored-tree ownership gap. The
post-ready hook only repaired `docs/` recursively when the top-level directory
was not writable. A writable parent containing root-owned descendants therefore
passed the probe and failed later at recursive `chmod`.

The live DM/group concurrency gate exposed a separate context-precedence gap.
The bridge and durable queue preserved the correct quoted text and destination,
but the queue worker then hydrated an unrelated completed session before the
current reply. A direct-message model resumed the older image task instead of
following the current quoted-text instruction.

Later live tests found four additional gaps. The dispatcher scheduled path used
the environment lookup helper without importing it, and dispatcher-created
attachments did not always retain the source turn for durable delivery. A
single queued request was replaced by the classifier's normalized instruction,
so exact-response intent could be lost even though multi-part splitting was not
needed. Vietnamese semantic folding removed combining marks but did not map
`đ`, producing false evaluation failures.

Composed-image planning also conflated independently sourced subjects with
visual panel count. Requests for weather and fuel in one shared bottom or left
region were therefore split, while a legacy payload adapter silently retained
only six of the planner's validated fact lines. The visible result looked like
a hard-coded template and could omit fuel data.

Finally, the remaining live-suite harness waited on optional bridge
self-message journal echoes even after durable history proved Zalo accepted a
result. Every successful request incurred the full wait and the scheduler gate
reported a false missing acknowledgement.

The mixed DM/group capability gate then found a source-correlation race within
one DM. The next DOCX reached the correct user, but its dispatcher-generated
attachment was recorded against the preceding weather request because queue
recovery rebound only the destination before the file tool read shared session
state. The later text response used the new source, making the mismatch visible
only to exact attachment correlation.

The first complete numbered run exposed three interacting follow-up failures.
The history harness treated optional gateway text as delivery proof, created
three-hour schedules without cleanup, and let those schedules fire inside later
cases. The remaining suite correlated all replies only by thread and time, so
an unrelated schedule acknowledgement could be counted twice. Finally, an
explicit quoted reply still received the chat's recent-attachment pack before
quoted context was appended; the model could resume the old file task instead
of returning the literal quoted response.

A visual artifact supplied after the first adaptive-layout pass exposed a
renderer defect rather than a planner defect. `bottom-bar` first measured a
content-sized card, then unconditionally replaced its width with the full image
width. The resulting dark layer hid the entire lower-right scene even though
the copy occupied only the left half.

The corrected concurrency gate then caught a live-data route bypass: one of two
current-weather requests answered through `execute_code` using conversation
context instead of making a new call through the operator-owned `web-search`
combo. Its answer looked plausible, but attribution correctly rejected it.

The first clean, uninterrupted full-suite run exposed a cross-case attachment
recall defect. Every unquoted text-only turn received the last extracts even
when it was a fresh URL, image, schedule, or DOCX request. A representative
archive test also sent a list where the real adapter expects one media object
and exited after extraction without waiting for the injected chat turn. That
unrelated generic turn occupied the DM queue for minutes, delayed the following
concurrency cases, and sent document creation into Hermes-local tooling instead
of the Dispatcher. An OpenBao lifecycle case also restarted the active Zalo
owner immediately before the URL-refusal gate; the test endpoint accepted an
event before an SSE consumer was ready, so no user turn existed to answer.

Search-backed schedule creation had a separate evidence mismatch: the runtime
current-search contract was appended before persistence. The schedule executed
correctly, but `context.original_request` no longer matched the user's text and
the strict gate could not find the pending record.

## Technical detail

- `architect/models/dispatcher/image_backends.py:L20` imports the shared
  `env_active` helper used by the generated-image backend; dispatcher delivery
  correlation is resolved and persisted by
  `architect/models/dispatcher/app.py:L509-L704`.
- `hermes/main/plugins/zalo/multi_request.py:L62` returns raw text for a single
  atomic item, and `hermes/main/plugins/zalo/adapter.py:L4259` applies that rule
  before durable admission.
- `hermes/main/plugins/zalo/adapter.py:L4415-L4430` now passes the claimed
  queue item's `message_id` into `_as_autosend_remember_turn` before handlers
  execute; this atomically refreshes the per-conversation source key read by
  dispatcher attachment delivery.
- `hermes/main/plugins/zalo/media_shortcuts.py:L186-L638` keeps eight bounded
  facts and authors one shared overlay payload; opaque layout telemetry at
  `media_shortcuts.py:L1332` exposes panel/fact counts and normalized placement.
  `architect/models/dispatcher/overlay.py:L12-L45` enforces the same eight-line
  renderer bound.
- `scripts/main/sync-router-worker-skills.sh:L42-L62` installs through a staged
  writable file and repairs bounded destination ownership before replacing the
  baked classifier.
- `test/scripts/zalo_tn_remaining_suite_remote.py:L98-L148` reads acknowledged
  `delivered` rows, while `L336-L365` counts scheduler acknowledgements whose
  `meta.delivery_kind` is `gate`.

## Decision and fix

- Execute a schedule's creation-time plan through `_as_try_workflow_submit`
  before generic fallback, while retaining the deliberate queue bypass for due
  work.
- Clear quote state for synthetic schedule events and never synthesize a Zalo
  quote from their internal message ids.
- Use the task-local schedule source id when recording acknowledged attachment
  delivery.
- Add locale-aware note success, empty, ambiguous, and failure copy.
- Make the validated composition-plan completion budget a fixed protocol bound,
  removing the operator environment knob.
- Keep visual design model-authored, but require a requested visual subject to
  remain recognizable instead of degenerating into an abstract gradient.
- Probe recursive docs-tree access before learning and fall back to the bounded
  sudo/container ownership repair when any restored descendant is inaccessible.
- Persist whether a queue item contains an explicit inbound quote and suppress
  unrelated session hydration for that turn. The quoted text remains visible,
  while ordinary unquoted follow-ups retain durable conversation continuity.
- Import runtime environment lookup on every dispatcher execution path and
  propagate the active Zalo source correlation into dispatcher attachment
  sends.
- Keep raw text for an atomic queue item; use classifier-normalized parts only
  when the request was actually decomposed. Normalize Vietnamese `đ` explicitly
  in language-agnostic semantic checks.
- Rebind both destination and source from the durable queue claim before
  beginning a recovered turn; never infer a new file's source from the previous
  per-conversation session value.
- Treat a user-requested shared region as one group regardless of source-subject
  count. Carry eight bounded facts consistently through planner, validator,
  payload adapter, and overlay renderer, with opaque layout diagnostics.
- Recursively repair and verify the Router Worker skill bundle before baking a
  restored read-only tree.
- Use acknowledged `zalo_message_history` delivery rows for reply and schedule
  acknowledgement evidence; retain journal echoes as diagnostics only.
- Suppress recent-attachment recall when the inbound turn contains an explicit
  quote; quoted context is already the authoritative reference.
- Keep named top/bottom bands content-sized and capped at 72% image width by
  default. A normalized region can still request full width explicitly.
- Re-correlate every remaining-suite delivery and schedule acknowledgement by
  its unique source message. The history harness now proves the exact durable
  result and deletes its tagged schedule in a `finally` cleanup boundary.
- When a typed plan requires live search, replace unrelated attachment recall
  with the current request plus a trusted execution contract: call native
  `web_search` now, do not reuse prior results, and do not bypass routing with
  code, shell, or direct HTTP libraries.
- Apply that current-search contract only to an executing immediate or fired
  turn. Preserve schedule-create text byte-for-byte in `original_request`.
- Append recalled attachment extracts only when the new text explicitly refers
  to an earlier file, sheet, image, archive, or short elliptical follow-up.
  Output filenames in fresh create requests and remote URLs are not references.
- Exercise archive chat delivery with the adapter's real single-media object
  and wait for a non-busy source-correlated terminal response before the next
  case. Wait for a logged-in bridge with an SSE owner after lifecycle restarts,
  and use per-run refusal evidence files so repeated privileged runs cannot
  collide in `/tmp`.

## Prevention

Case 27 now includes a mandatory two-minute full-fire gate. It verifies the
stored evidence dependency graph, execution through the composed-image shortcut,
one source-correlated acknowledged image, absence of planner truncation, and no
synthetic quote attempt. The case-index runner prints `running test case N/T`
before every unit and VPS gate so long production runs have auditable progress.
The Router Worker classifier bundle is regenerated from the authoritative skill
parts, and the assembly contract checks the current per-domain search invariant
instead of a retired wording fragment.
The live-test harness also has an explicit VPS-local mode, allowing the numbered
gates to run on the target without placing SSH credentials in command arguments
or installing Paramiko on the production host.
The latency and file-security matrices use that same shared transport instead
of maintaining private Paramiko-only executors, so the complete case index can
run under one audited execution mode.
The latency matrix also reads its API credential from an active Hermes process
when the production host deliberately keeps runtime OpenBao values out of the
on-disk environment; the value remains inside the test process and report
sanitization boundary.
Latency sampling uses Python's monotonic nanosecond clock converted to
milliseconds rather than implementation-specific `date %3N` formatting, which
uutils can emit at an unexpected width and corrupt duration arithmetic.
The numbered case index now invokes the documented bridge/SSE latency test;
the direct Traefik sampler remains an optional diagnostic and cannot substitute
for end-to-end Zalo delivery evidence. Grafana and router-default gates also
honor VPS-local mode instead of silently skipping it.
The scheduled-image gate correlates flow telemetry from the active replicas'
`agent.log` files as well as Docker stdout because the production Hermes image
persists info-level plugin events to per-replica logs.
Case 44 now includes a live Vietnamese note-locale gate so a classifier-correct
note cannot regress to an English host confirmation unnoticed.
The concurrency gate requires exact source-correlated responses in both a DM
and a three-member group, preserving the explicit-quote flag through the durable
FIFO so stale session context cannot silently override either reply.
The flexible-composition gate now sends both a near-future shared-bottom request
and an immediate shared-left request. It requires one cohesive scene, the
requested placement, all weather/fuel facts, source-correlated image delivery,
and planner diagnostics that do not derive panel count from subject count.
The remaining-suite oracle has a focused unit test that fails if journal echoes
again replace acknowledged durable delivery or schedule-gate evidence.
The case-index summary records a validated candidate revision, so an overlaid
VPS test tree cannot silently attribute results to its older checkout HEAD.
The DM/group capability gate additionally requires each DOCX attachment's
durable source ID to equal its own queue item, so correct destination alone can
no longer hide a crossed correlation.
Renderer coverage now asserts the actual band bounds on a 1280×720 image and
fails unless more than 200 pixels of right-side scene remain uncovered. The
live exact Da Nang gate produced a bounded lower-left card and a separate
bounded left-frame artifact; both preserved one cohesive scene.
History greeting, schedule, mixed schedule, PDF, and English cases passed with
durable source correlation and no leftover tagged schedule. The repaired
remaining suite passed image generation, two vision inputs, PDF/text extract,
web search, exactly one schedule acknowledgement/fire, automatic row removal,
and restart checks. Focused DM/group runs then passed exact quote responses,
two attributable weather searches, two isolated DOCX packages, semantic score
10, eight-message FIFO continuity, empty queues, and honest remote-video refusal.

## Verification

- Focused local contracts passed: composed-image planning/rendering, media
  shortcut gating, notes/control localization, Zalo delivery history, and case
  index progress.
- A pre-deployment backup was created and verified with all required components
  healthy. The runtime-only three-member test group included the requesting
  account, and the router export retained seven operator-owned combos and its
  AI-box configuration.
- Full unit, clean-deploy, live scheduled-image, concurrency, failover, and
  stability results are recorded in the release report generated by this round.

## PDF-only turn exposed an embedded hero image as a second attachment

### Symptom

The resumed 131-case VPS matrix passed 130 cases. The visual-weather PDF case
created and delivered a valid, readable, visually evaluated PDF, then also sent
the older `danang-hero.jpg` that had been used while composing the document.

### Root cause

Dispatcher sent the final PDF directly and claimed its stable file identity in
the shared session service. Adapter late-autosend scanned the same turn's output
window newest-first. When the PDF claim correctly returned `first=false`, the
loop continued to the older unclaimed image and treated that supporting asset
as another final result.

### Fix

Treat an already-claimed rich document (PDF, Office, or OpenDocument) as the
terminal artifact for that autosend scan. Do not fall through to older image
sidecars. The pure autosend contract and adapter wiring are covered locally.
The live PDF oracle still records newly created raster files for diagnostics,
but release failure is based on an acknowledged image delivery correlated to
the PDF request, not mere workspace existence.

### Prevention

- A direct Dispatcher delivery and adapter late-autosend must share one terminal
  artifact decision through the existing session claim.
- PDF-only reports must contain no source-correlated image delivery.
- Test reports identify only the authorized runtime target class; they do not
  persist the numeric Zalo identity.
