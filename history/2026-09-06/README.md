# 2026-09-06 — scoped notes, cancellation, and HA liveness

## Direct shortcut artifact deduplication

A one-replica paired direct-message benchmark exposed an image-edit artifact
being resent by the following web-search turn. Direct shortcut delivery now
records the distributed file claim and the captured turn token, with claim
rollback on delivery failure.

## Isolated workflow final-delivery recovery

A two-replica DM probe showed that an isolated web-search job could complete
after producing its final answer without an observable Zalo delivery. Workflow
completion now requires a delivery marker. When the final assistant message is
already in shared session memory but delivery is missing, the owner retries it
once through the per-destination send lock and records whether recovery was
needed.

## Paired benchmark delivery evidence

The DM benchmark previously treated an omitted synthetic marker as a missing
Zalo response even when the timestamp-correlated self-message contained the
requested current UTC answer and sources. The harness now distinguishes
transport delivery from marker compliance and requires semantic evidence when
the marker is absent.

## Release verification summary

- The one-replica paired DM run completed in 333.44 seconds. The quote-based
  image edit and the following sourced web response were both delivered; the
  visual evaluator scored the edited image 8/10.
- The equivalent two-replica paired DM run completed in 320.20 seconds with
  the same delivery result and an 8/10 visual score. One sample is not enough
  to attribute the small difference to replica count because image-provider
  latency dominated and the same-conversation FIFO intentionally serialized
  both requests.
- Group-scoped scenarios were excluded from this release round by operator
  decision. DM and quote-reply isolation remained in scope.
- All 90 local unit scripts passed with disposable test dependencies. The live
  post-run snapshot showed an empty Zalo queue, one SSE lease owner, two
  running Hermes replicas, healthy stateful services, and zero container
  restart counts.

## Late media crossed Zalo turn boundaries

### Symptom

A plain text request could receive an artifact produced by an earlier request,
then lose its correct text response because the adapter believed media had
already completed the current request.

### Root cause

Artifact discovery had no initialized per-turn clock, so it used a broad
fallback window. The delivery marker was a set keyed only by conversation;
a cancelled late sender could restore that marker after the next inbound reset.

### Technical detail

- **Functions:** `adapter.py::_as_autosend_turn_files()`,
  `adapter.py::_as_begin_turn()`, and
  `adapter.py::_as_job_already_sent_file()` now share one captured turn token.
- **Lines:** `hermes/main/plugins/zalo/adapter.py:L3291-L3363` owns turn state;
  `L6042-L6208` captures the token before asynchronous delivery.
- **Fields:** `_as_tclock[thread_id].t0` changes from absent to the processed
  turn start; `_as_job_file_sent` changes from `set[thread_id]` to
  `dict[thread_id, turn_token]`.
- **Route:** Zalo inbound queue to Hermes response autosend; no provider or
  OmniRoute combo membership is changed.

### AI decision

The fix establishes artifact ownership at the turn boundary. Clearing a
thread-wide flag again would leave the same race, and a VPS-only cleanup would
not protect fresh installs.

### Fix (core)

Queued, direct, and workflow turns now initialize a real wall-clock boundary
and increment a destination-local token. Async media senders retain the token
captured at discovery; a completion from an older token cannot mute the current
turn.

### Todo list

- [x] Reproduce from Hermes and Zalo delivery logs.
- [x] Replace thread-scoped delivery state with turn-scoped state.
- [x] Add old-turn completion and cross-thread regression cases.
- [x] Verify sequential delivery and an intentionally stale artifact through
  the live Zalo bridge; the expected text arrived and no photo was emitted.
- [ ] Verify the two-request concurrent delivery variant through the live Zalo
  bridge.

### Prevent recurrence

`test/scripts/zalo_turn_media_isolation_unit.py` covers current-turn media,
next-turn reset, a late old-token completion, and independent destinations.

## Verified teardown after secret scrubbing

A clean-deployment gate exposed that successful runtime startup deliberately
removes transient secret exports, while the later destroy path expected those
values for both the OmniRoute inventory export and Compose parsing. Destroy now
reloads OpenBao before its backup and teardown. An enabled OmniRoute export that
is skipped or fails now fails the pre-change backup gate; the named volume is
still the recovery source of truth, while the JSON inventory is required audit
evidence.

The live media suite also uses process-unique evaluator files and removes each
host temporary file after transfer, preventing ownership collisions between
ordinary and privileged test runs.

## Task-aware proxy identity

**Symptom:** one service had a generic model-routing name even though its role
is an execution worker between callers and the OmniRoute provider plane. Its
old identity was duplicated across container DNS, environment variables,
health metadata, scripts, monitoring, and tests.

**Cause:** earlier naming changes were partial, allowing runtime and
documentation terminology to diverge.

**Decision and fix:** use `router-worker`, Router Worker, and
`ROUTER_WORKER_*` as one atomic contract. Rename the source and operational
entry points together. During an upgrade, remove only the retired container
owned by the active Compose project, delete retired environment keys, and
migrate only exact stack-default URLs; preserve custom operator endpoints.

**Prevention:** configuration, health, routing, and clean-upgrade tests reject
the retired live identity while historical incident records remain immutable.

## Durable notes

**Symptom:** general conversational memory could retain facts but did not offer
traceable, dated CRUD for explicit user notes.

**Cause:** the memory API had no scoped note entity or mutation audit, and the
classifier schema had no note action contract.

**Decision and fix:** add per-DM/per-group PostgreSQL notes with optional dates,
full-text/date indexes, deduplication, versions, and audit rows. Keep semantic
interpretation in English classify prompt parts; host code validates and
executes structured plans. Ambiguous updates and deletes never choose a row.

**Prevention:** contract and live tests cover unrelated note subjects, date and
topic lookup, isolation, dedupe, audit, and ambiguous mutation refusal.

A live multilingual lookup showed that classifier-produced semantic tags can
use a different language from tags saved earlier. The fallback now removes
query wording and tags only inside the already-enforced scope/date window, so a
dated plan remains discoverable without widening identity or time boundaries.

A repeated live create also showed that model-added category prefixes can make
otherwise identical note bodies differ. The classify note contract now
preserves the user-authored semantic payload without labels or decorative
prefixes, keeping deterministic content deduplication stable without moving
semantic comparison into application code.

## Active request control

**Symptom:** a follow-up stop instruction entered the same queue as the long
request and could not interrupt it.

**Cause:** no control-plane classification occurred before rate limiting/FIFO
admission, and cancelling the work task also risked cancelling its queue drain.

**Decision and fix:** classify stop intent only while a thread has active work,
cancel the tracked task, preserve the drain, clear late adapter delivery, and
record both request and completion events. Office generation can write without
direct Dispatcher delivery so the cancellable adapter task remains the sender.

**Prevention:** test message and quote-reply control in DM and group, validate
no-active honesty, late-send suppression, scope isolation, and next-item
progress.

## Standby and retention

**Symptom:** a legitimate non-owner Zalo replica remained inside `connect()`
until the gateway's reconnect watchdog timed out. A watcher error path also
referenced an unset shell variable.

**Cause:** lease contention was treated as incomplete connection rather than a
healthy HA state, and the watcher log retained an obsolete field.

**Decision and fix:** return healthy standby promptly, contend for the lease in
a background task, remove the unset watcher field, and anchor the watcher's
first systemd run to timer activation rather than an already-past boot offset.
Initialize seven-day
backup and staged-memory retention in OpenBao and load it for lifecycle/timer
commands.

**Prevention:** monitor lease acquisition, SSE client count, reconnect logs,
timer results, restart deltas, and verified backup pruning without treating
provider latency as a container failure.

The retired web-extraction environment route was already scrubbed, but its old
name remained in the routing worker health output. The health surface now reports
only supported search routing fields.

## 09:15 — Note mutation confirmation isolation

### Symptom

A successful structured note mutation stored the right rows but could echo the
entire source request as its user-visible confirmation.

### Root cause

The adapter trusted the classifier's free-form `message` field for successful
note mutations even though that field is not the persisted operation result.

### Technical detail

- **Function:** `hermes/main/plugins/zalo/adapter.py::_as_run_host_media_shortcut()` — selected `plan.message` after `execute_note_plan_async()` succeeded.
- **Lines:** `hermes/main/plugins/zalo/adapter.py:L2364–L2372` — success now always uses the localized note-result message contract.
- **Field:** classify `message` — untrusted explanatory text → ignored for note mutation confirmation; `result.count` remains the validated result input.

### AI decision

Keep classification responsible for semantic intent and keep the adapter
responsible for deterministic operation-result messaging. A prompt exception
would not protect against future models returning source text in `message`.

### Fix (core)

Successful create, update, and delete operations now render the configured
`ZALO_NOTES_SAVED_MSG` result using the validated item count.

### Todo list

- [x] Reproduce through the live Zalo delivery path.
- [x] Confirm stored note scope, dates, and contents independently.
- [x] Fix the core adapter result boundary.
- [x] Add and pass a regression assertion.
- [x] Re-run the live mutation and lookup cases after deployment.

### Prevent recurrence

`test/scripts/notes_control_unit.py` rejects any return to classifier-authored
mutation confirmations inside the note execution branch.

## 09:25 — Preserve scaled Compose replicas during cleanup

### Symptom

A component-scoped update removed one healthy Hermes replica even though the
configured scale remained two.

### Root cause

The pre-update orphan cleanup treated every second container sharing a Compose
project/service label as a duplicate. Compose intentionally gives scaled
replicas the same service label and distinguishes them by container-number.

### Technical detail

- **Function:** `architect/backup-restore/lib/workers.sh::assistant_rm_compose_recreate_orphans()` — collapsed a service to one container.
- **Lines:** `architect/backup-restore/lib/workers.sh:L300–L340` — duplicate identity now includes `service:container-number`.
- **Label:** `com.docker.compose.container-number` — ignored → preserved as the scale-slot boundary.
- **Service:** `hermes` — configured replicas `2` → one replica was removed during an unrelated Router Worker update.

### AI decision

Use Compose's stable scale-slot label rather than special-casing Hermes or
disabling orphan cleanup. This preserves any intentionally scaled service while
still removing repeated occupants of the same slot and anonymous rename debris.

### Fix (core)

Cleanup tracks one container per project service and container-number slot.
Only a second occupant of the same slot is removed.

### Todo list

- [x] Reproduce through a component-scoped update with two replicas.
- [x] Identify the shared service label and distinct slot labels.
- [x] Fix the shared worker lifecycle library.
- [x] Add a regression contract.
- [x] Verify the component update retains two live replicas on the VPS.

### Prevent recurrence

`test/scripts/compose_scaled_cleanup_unit.py` requires slot-aware duplicate
identity and rejects the former service-wide singleton state.

## 09:40 — Cancellation waited behind the request it targeted

### Symptom and cause

A live stop message arrived while image generation was active, but the image
completed before the control response. The SSE reader dispatched both events,
yet the second handler waited on the same per-conversation inbound lock. Its
cancellation classifier was therefore unreachable until the first handler
released the lock.

### Fix and prevention

When a local active turn exists, the guarded inbound handler now performs the
semantic cancellation check before acquiring the conversation lock. Ordinary
messages still take the lock and preserve FIFO behavior. The unit contract
requires the cancellation call to occur before `async with lock`.

The active registry covers the guarded handler from before lock acquisition
through classification, media staging, workflow submission, and queue handoff.
This also gives fail-open execution a cancellable owner and records its terminal
`cancelled` event. A transient Valkey gate initialization failure is retried
after a bounded backoff rather than disabling queues for the replica lifetime.

### Verification

- [x] Reproduce with a live long-running request followed by a stop message.
- [x] Identify the lock ordering from logs and message-history evidence.
- [x] Move the existing semantic control check before the lock.
- [x] Re-run message and quote-reply cancellation in the authorized DM.
- [ ] Run the same cancellation cases in an authorized group.

## 10:05 — Remove ambiguous Grafana provisioning and document routing ownership

### Symptom

Grafana dashboards existed in two byte-identical repository trees, while
architecture summaries disagreed about whether the Zalo path used Traefik and
did not explain which replica drained or returned a queued request.

### Root cause

The mounted runtime configuration was copied into an architecture package and
both copies were retained. Older documentation used “edge” to mean the API
Gateway in some places and Traefik in others.

### Decision and fix

Keep the Compose-mounted `config/monitor/grafana` tree as the only provisioning
source. Document the actual hybrid model: Traefik load-balances HTTP, a Valkey
lease elects one Zalo SSE owner, and that owner drains each conversation FIFO
and sends its result to the original thread through the bridge route.

The canonical tree also retains empty `alerting` and `plugins` directories so
Grafana does not report missing standard provisioning paths at startup.

### Verification

- [x] Confirm Compose mounts the canonical config tree.
- [x] Confirm all dashboard UIDs and titles are unique.
- [x] Remove the unused mirrored provisioning tree.
- [x] Add a regression that rejects duplicate identities and source trees.
- [x] Run the monitor integration after deployment.

## 10:35 — Require a genuine quote identity in image-edit verification

### Gap

The earlier reply-image-edit probe staged a valid source image but supplied a
synthetic quote identifier. That exercised media inheritance and generation,
not the full bridge send-to-quote contract.

### Fix and prevention

The lab now sends the source photo through the live bridge first, extracts the
real returned message identifier, then injects the reply with that identifier
and the exact shared source path. It only passes after the edited artifact is
created and delivered to the authorized DM.

### First genuine run and root cause

The genuine probe obtained both live values, but the edited artifact did not
use the image-edit shortcut. The workflow preflight classified the request
while its call boundary discarded the staged media path; its missing-source
guard then fell through to a generic agent turn.

### Core fix

Carry staged media paths into workflow preflight and execute an explicit
image-edit plan before the generic attached-image fallthrough. The regression
contract requires this handoff and its ordering. The lab also asks the
`vision-ocr` combo for a natural-language quality assessment of the edited
result before accepting the run.

A repeated run also exposed inconsistent decisions because image vision,
workflow preflight, and dequeue each independently called the classifier. The
adapter now classifies an attached-image turn once, passes that plan to both
pre-queue decisions, stores it in the Valkey FIFO item, and reuses it after
dequeue. The five-minute media test ceiling is enforced by default.

### Live verification

- [x] Real outbound Zalo photo and returned message identifier.
- [x] Quoted source resolved to the shared media path.
- [x] One image-edit plan reused through routing.
- [x] OmniRoute image-edit request returned successfully.
- [x] Edited PNG delivered to the authorized DM.
- [x] Independent `vision-ocr` review rated the coherent watercolor result
  8/10, confirmed the house, tree, and sun were retained, and found no visible
  unsafe text.

## Current documentation terminology audit

The final current-document scan found one configuration heading that still used
the retired Router Worker service name. The heading now uses the active name.
Compatibility cleanup code, regression fixtures, and dated reports keep the old
term only where it is necessary to detect or explain legacy state.

## Component changes reload secrets before backup

A repeated component change correctly stopped before scaling because its
mandatory backup could not export OmniRoute after the preceding update scrubbed
the transient OpenBao environment. Component add/remove now reloads OpenBao
before backup and scrubs the export afterward on both success and failure. A
source-order regression prevents backup from moving outside that protected
lifecycle.

The first retry then showed that a component option was persisted but not
exported into the already-running command. The nested update consequently used
the previous replica count. Add/remove now updates the process environment at
the same time as `.env`; the regression checks that persistence and export both
precede the apply step.

## Reliable Zalo queue ownership across replica loss

### Symptom

A Zalo event was removed from the shared FIFO before its Hermes turn finished.
If the elected SSE owner stopped in that interval, the event disappeared. A
second gap left pending queues dormant after promotion unless a later inbound
event happened to kick that same conversation.

### Root cause

`GateStore.queue_pop()` used destructive `LPOP`, while queue tasks and the list
of active destinations lived only in one process. Lease loss closed the bridge
session but did not cancel all owner-local inbound and turn tasks.

### Technical detail

- `gate_valkey.py::queue_claim()` moves `q:<destination>` to
  `qinflight:<destination>` atomically with `LMOVE`; `queue_ack()` removes the
  exact payload only after terminal processing.
- `gate_valkey.py::queue_active_ids()` stores active destinations in `qactive`;
  `queue_recover()` moves abandoned claims back to the FIFO head in order.
- `adapter.py::_as_queue_recovery_loop()` scans the registry on the elected
  owner; `_as_cancel_owner_work()` cancels local inbound, queue-drain, and turn
  tasks when renewal fails so a promoted replica owns recovery.
- The per-conversation worker lease now exceeds the maximum queued-turn
  deadline, preventing a routine recovery scan from reclaiming a legitimate
  slow turn. A newly elected owner explicitly fences stale worker locks before
  it recovers inflight items, so failover still follows the owner lease bound.
- Malformed claimed payloads are acknowledged and discarded rather than
  becoming permanent poison items.

### Decision and core fix

Use a shared claim/inflight/ack protocol with a durable active-destination
registry. Keep one worker lease per conversation so ordering is preserved,
while different DM and group destinations can drain concurrently.

### Prevention

Unit coverage proves claim recovery and destination isolation. The live release
gate stages a claimed request, stops the current owner, requires a standby to
acquire the lease and deliver the recovered request, then verifies both queue
lists and the registry are empty.

## Complete Zalo disaster-recovery state

### Symptom

A verified full backup contained the Zalo systemd unit but omitted the logged-in
bridge session and identity policy files. A clean host restore could therefore
require a new QR login or lose the authorization boundary despite a passing
manifest.

### Root cause

`assistant_backup_zalo()` captured service configuration only. The separate
session helper was not part of the atomic backup stamp.

### Technical detail

- `assistant_backup_zalo()` now requires and stores `credentials.json`, plus
  administrator, allowed-user, allowed-thread, and denied-thread policy files.
- `assistant_restore_zalo()` restores the session before starting the user
  service and restores identity files with the data-directory owner and mode
  `0600`.
- The backup contract fails when credentials are absent, so `destroy` and
  `update` stop before changing the stack.

### Decision and core fix

Make Zalo session and identity policy part of the same verified recovery stamp
as OpenBao, stores, schedules, and OmniRoute. Evidence records only component
status, counts, and checksums; it never prints identities or secrets.

### Prevention

The static backup contract and destructive VPS gate require session and policy
artifacts before teardown, then compare login, authorized group membership,
one-SSE ownership, and router inventory after clean deployment.

## Group membership was absent from durable recovery state

### Symptom

The authorized named group and its display name existed after backup, but its
PostgreSQL member snapshot was empty. A clean restore could therefore pass a
group-name check without proving the authorization roster or DM/group test
identity relationship.

### Root cause

The bridge contact refresh synchronized group and user names only. Its
`getGroupInfo` response exposes the complete roster through versioned member
entries, but no core path parsed and persisted those entries.

### Decision and core fix

An authenticated group-membership refresh now parses documented structural
fields, validates numeric identities, deduplicates entries, and requires the
parsed count to equal the provider's total. A valid roster replaces one
group's PostgreSQL snapshot in a transaction. Partial, paginated, malformed,
empty, and count-mismatched responses are rejected without deleting the last
valid state. The ordinary authorized Zalo refresh updates these snapshots as
well as names.

### Prevention

The offline parser unit covers versioned and direct member shapes, roles,
metadata, incomplete results, malformed entries, and pagination. The live
DM/group lab explicitly refreshes the named group's durable snapshot before it
requires the expected count and designated test member. Numeric identities are
kept out of source and reports.

## Media smoke still required the retired OCR container

### Symptom

A clean deployment brought every supported media service up, but
`run.sh check-media` failed by probing localhost port 8091.

### Root cause

The standalone OCR container had been fully replaced by the `vision-ocr`
combo through Router Worker, while the supported smoke script and two retained
lab paths still referenced the removed service.

### Decision and core fix

The media smoke now checks Router Worker as the live vision route alongside
dispatcher, jobs, and SearXNG. Retained security/matrix labs use the same
current endpoint and explicitly require the retired container to be absent.

### Prevention

The vision policy unit now rejects port 8091, `OCR_PORT`, and the old check
name in the supported media smoke while requiring the Router Worker endpoint.

## Delivery verification depended on optional bridge echoes

### Symptom

Concurrent DM/group and owner-failover requests produced final Hermes replies,
but the release labs could not prove delivery after the host bridge stopped
echoing outbound self-message events to its journal.

### Root cause

Session memory stored an assistant turn before transport completion, while the
durable PostgreSQL history ended at `processing`. The labs treated an optional
bridge journal echo as the transport acknowledgement.

### Decision and core fix

After each successful bridge send, the adapter records a `delivered` event with
the destination type, acknowledged message identifier, final chunk, and quote
usage. Send failures never create this event. HA labs query the durable event
and require exactly one matching delivery in the originating conversation and
none in the other conversation.

External test fixtures are now located by walking repository ancestors for the
nearest sibling `test docs` directory. This supports both a normal checkout and
a nested release worktree without embedding a workstation path.

### Prevention

Offline contracts lock acknowledgement ordering and nested-worktree fixture
resolution. Live concurrency and failover gates require the durable delivery
row, queue drainage, restored replica count, and one elected SSE owner.

## Queue acknowledgement preceded background agent completion

### Symptom

Two simultaneous conversations were admitted and one reply was delivered, but
the other ended at `processing`. The queue appeared empty even though Hermes
logged a later final response, and the elected owner missed a lease renewal
during the overlap.

### Root cause

The gateway's `handle_message` method launches agent work in the background and
returns immediately. The adapter treated that return plus a short file grace
period as completion, acknowledged the inflight row, and allowed another
conversation to overlap shared gateway execution state.

### Decision and core fix

The elected Zalo owner now serializes agent execution while retaining separate
durable per-conversation FIFO queues. After launch, it waits for the matching
gateway session to become idle, pulses the queue-worker lease during the wait,
performs late-file delivery, and only then acknowledges the claimed row. A
bounded turn timeout still releases failed work with explicit user feedback.

### Prevention

The delivery contract requires the owner execution lock and terminal session
wait to occur before queue acknowledgement. The live DM/group test injects both
requests together and requires one acknowledged result in each original
conversation with no crossed content.
