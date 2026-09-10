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

## Model execution starved the HA lease heartbeat

### Symptom

Valkey remained healthy and immediately reachable from the Hermes container,
but the owner logged a renewal timeout during a long model turn. The resulting
false ownership loss cancelled queued work and allowed a standby election.

### Root cause

Lease renewal ran on the same asyncio loop as the gateway. A provider path can
perform a synchronous segment long enough to prevent that loop from scheduling
the 45-second renewal, so the lease expired despite a healthy store and host.

### Decision and core fix

An owner-token-safe daemon heartbeat now renews the lease independently of the
gateway loop. The async monitor continues checking ownership and tolerates its
own delayed connection only while that heartbeat is fresh. A send-time fence
rejects outbound work when the heartbeat observed token loss or exceeded the
lease lifetime without a successful renewal.

### Prevention

Lease units cover fresh, explicitly lost, and expired heartbeat states. Live
tests require one owner, one SSE client, no renewal-loss errors, no crossed
delivery, and recovery when the actual owner container is stopped.

Cancellation release checks also inspect the acknowledged user-facing reply.
They reject process/container identifiers, internal task or message handles,
correlation values, queue keys, and long numeric execution identifiers.

## Duplicate outbound classification silently discarded valid replies

### Symptom

Hermes completed concurrent turns and its local delivery-obligation ledger
marked both as delivered, but Zalo received neither and PostgreSQL contained no
acknowledgement-backed delivery event.

### Root cause

The adapter called the LLM-based outbound-noise classifier twice on the same
content. The first decision allowed the final answer; the second could classify
it differently and returned a successful no-op, causing the gateway ledger to
finalize an obligation that never reached the bridge.

### Decision and core fix

Outbound content is classified once, after autosend has already performed any
caption replacement. A permitted reply proceeds directly to the bridge; an
intentional protocol/status suppression remains explicit and logged.

### Prevention

The delivery unit requires exactly one outbound-noise decision in the send path
and requires durable delivery recording only after bridge acknowledgement.
Live labs use ordinary user-facing sentences and scope their durable queries to
the run start time, avoiding internal-looking markers that the privacy policy is
designed to suppress.

## 15:22 — Pre-lock cancellation preserved access boundaries

### Symptom

The active-request control hook intentionally runs before the per-conversation
lock, but it received group text before normal addressing and access gates. A
group cancellation run also lacked durable control events on its first attempt,
while the same DM variants completed.

### Root cause

The early control path called semantic classification directly from the raw SSE
payload. The ordinary inbound path applies allowed-thread, strict-user, group
mode, and addressed-message handling later, after the lock. Reaching the control
classifier early therefore bypassed those deterministic boundaries and could
classify unnormalized addressed text.

### Technical detail

- **Function:** `hermes/main/plugins/zalo/adapter.py::_on_inbound_guarded()` —
  invoked `_as_try_cancel_active_request()` before access/address normalization.
- **Function:** `hermes/main/plugins/zalo/adapter.py::_as_prelock_control_text()`
  — now applies the deterministic sender, thread, group-mode, and addressing
  checks without performing language interpretation.
- **Lines:** `hermes/main/plugins/zalo/adapter.py:L984-L1016` and
  `L1056-L1077` at fix time.
- **Fields:** inbound `threadId`, `threadType`, `senderId`, `mentions`, and
  quote ownership are validated/normalized before the text reaches the
  `cancel_task` classifier contract.
- **Route:** Zalo SSE owner → guarded inbound control path → classifier
  `task-control`; OmniRoute combo membership is unchanged.

### AI decision

Keep semantic stop-intent recognition in the classifier, while duplicating only
the minimal deterministic authorization checks required before the lock. Moving
the control hook back behind the lock would restore the original inability to
interrupt active work, and phrase matching in Python would violate the language
understanding boundary.

### Fix (core)

The pre-lock hook now declines unauthorized, disallowed, disabled, or
unaddressed control messages and passes normalized addressed text to the
existing semantic cancellation classifier. The live lab prints only boolean
outcome markers and independently rejects internal identifiers in the delivered
acknowledgement.

### Todo list

- [x] Reproduce the missing group cancellation audit.
- [x] Harden the core pre-lock authorization and addressing boundary.
- [x] Extend the cancellation contract and release rules.
- [x] Pass live plain-message and genuine quote-reply cancellation in the
  authorized group.
- [x] Verify an empty queue, one SSE owner, two running replicas, and no
  actionable Hermes/Zalo/OmniRoute/Router Worker errors after the run.
- [ ] Run the complete release suite after work resumes.

### Prevent recurrence

`test/scripts/notes_control_unit.py` locks the pre-lock ordering and required
authorization/address normalization calls. `test/scripts/zalo_active_cancel_lab.py`
requires bridge-acknowledged cancellation without printing audit rows or
accepting any process, container, task, message, correlation, queue, or long
numeric execution identifier in the user-facing reply.

## 17:00 — Continuous-message release gate remains open

### Symptom

Two simultaneous four-message bursts reached durable admission and processing
for a direct conversation and an addressed group, but the complete set did not
reach terminal delivery inside the five-minute release deadline. The first run
also showed that capability-owned replies did not consistently persist the user
side of session history.

### Root cause found

The adapter invoked note, direct-reply, media, vision, and workflow handlers
before durable FIFO admission. Those paths could therefore overtake ordinary
Hermes turns. Session persistence was also coupled to the generic outbound send
path, so a workflow or host-owned handler could produce an assistant turn without
the corresponding admitted user turn.

### Core changes under validation

- Capability routing now begins after a durable queue item is claimed.
- Asynchronous workflow turns hold their conversation item until the workflow
  reaches a terminal state.
- Queue items retain their own user text and quote payload; dequeue binds both
  before session hydration and agent execution.
- The admitted user turn is persisted once at queue claim, while outbound sends
  append only the assistant side for that item.
- Core conversation guidance gives an explicit quoted-message block precedence
  over conflicting older history and treats recent attachments as optional.
- The live gate now uses natural consecutive prompts and an LLM semantic review
  in addition to structural delivery, FIFO, quote, history, and residue checks.

### Verification status

- Offline compilation and queue/control units: pass.
- VPS component backup, update, and two-replica recreation: pass.
- Both live destinations: four admissions and four processing events observed.
- Session-history repair: confirmed for completed items.
- Five-minute terminal-delivery gate: fail; the remaining items drained shortly
  after the deadline, with no replica restart or owner-lease failure.
- Full release suite and merge gate: not run; merge requests remain blocked.

### Resume point

Profile the queue-to-agent wait boundary for trivial consecutive turns. Separate
classifier/provider latency from local serialization, then either remove the
unnecessary wait or establish a justified operation-specific deadline. Re-run
the continuous-message semantic gate before the destructive clean-deploy suite.

## 19:00 — Continuous DM/group gate passed after scoped concurrency repair

### Symptom

Consecutive messages could be durably queued yet complete slowly, arrive at the
agent in a different order, lose DM quoted context after dequeue, duplicate a
session user turn, or have a concise valid result suppressed. Early live runs
also failed their semantic check even when the visible answers were correct.

### Root cause

Four independent boundaries interacted:

1. one owner-wide agent lock serialized unrelated conversations;
2. concurrent pre-lock cancellation classifiers could reorder SSE admission
   inside one conversation;
3. session and quote state depended on mutable owner-local maps instead of the
   claimed queue item and durable source identity;
4. outbound content was classified twice, and the test evaluator generated an
   invalid nested Python string because its newline was not escaped.

Synthetic injection identifiers also cannot prove native Zalo quote transport.
The adapter's supported plain-send fallback was correct, but its delivery
metadata remained marked as quoted after the quoted send was rejected.

### Fix (core and release gate)

- Sequence inbound SSE messages per conversation before semantic control work.
- Lock agent turns per conversation, allowing an independent DM and group to run
  concurrently.
- Route capability work only after durable claim; rebuild quote context from the
  stored quote and hydrate memory from the claimed text.
- Persist the user side once at claim, tag user/assistant/delivery history with
  the source message, and exclude queue gate notices from session memory.
- Remove the duplicate outbound classification and preserve concise completed
  answers in the file-owned outbound contract.
- Clear the quoted-delivery flag when the bridge rejects a quote and the plain
  fallback succeeds.
- Correlate live assertions by source message and escape the nested semantic
  evaluator prompt correctly. Genuine Zalo messages remain required to prove a
  native quote bubble; synthetic runs prove quote understanding and fallback.

### Verification

- Python compilation and focused queue/control/session contract tests: pass.
- Verified pre-mutation backups and two-replica plugin reconciliation: pass.
- Live two-destination burst: eight of eight terminal deliveries in FIFO order.
- Quoted context and next-turn continuity: pass in both DM and group.
- Source-scoped session pairing, conversation isolation, empty queue, and no late
  timeout: pass.
- LLM semantic review: pass.
- Observed end-to-end duration: 181.27 seconds. OmniRoute logs showed primary
  provider authorization/server errors followed by successful priority fallback;
  no Hermes or watcher restart loop was required.

### Prevent recurrence

`inbound_queue_unit.py` locks per-conversation serialization and independent
conversation concurrency. `notes_control_unit.py` locks durable source metadata,
claim-time quote reconstruction, gate-memory exclusion, plain-fallback metadata,
and evaluator escaping. `zalo_continuous_messages_lab.py` requires acknowledged
source-correlated delivery plus LLM semantic evaluation and never treats a
synthetic message identifier as native quote-transport proof.

## 19:30 — Provider session correlation and indexed memory at scale

### Symptom

Python provider requests did not carry a stable conversation header. During
the corresponding production gate, exact knowledge retrieval from a
10,000,000-row corpus was accurate but required 6.729 seconds and did not use
the full-text index. The first Router Worker rebuild also entered a restart
loop.

### Root cause

Router Worker rebuilt authorization headers at each egress path without a
conversation identity. Memory queries used `to_tsvector(content)`, while the
GIN index covered `to_tsvector(coalesce(content, ''))`; PostgreSQL expression
indexes require the query expression to match. The Router Worker Dockerfile
also enumerated Python modules explicitly and omitted the new helper.

### Technical detail

- **Functions:** `session_headers.py::opencode_session()` and
  `app.py::proxy()` / `classify_endpoint()` add the header at all provider
  egress boundaries.
- **Lines:** `architect/models/router-worker/session_headers.py:L53-L58`,
  `app.py:L373-L431` and `L437-L550`; image ownership is
  `architect/models/router-worker/Dockerfile:L5`.
- **Field:** `x-opencode-session` is a namespaced SHA-256 digest; raw
  `conversation_id`, `session_id`, `thread_id`, or `chat_id` never leaves the
  stack in that header.
- **Function:** `architect/memory/memory-manager/app.py::recall()` at
  `L653-L730` now separates indexed full-text retrieval from the substring
  compatibility fallback.
- **Indexes:** `memories_session_idx` and
  `memories_thread_session_created_idx` at `app.py:L108-L110`; full-text query
  expression now matches `memories_fts_idx` exactly.

### AI decision

Hash the best stable conversation discriminator rather than forwarding private
channel identifiers. Keep substring matching only as a second query after the
indexed search returns nothing. Use one disposable generated corpus for both
knowledge and historical-session needles so the benchmark measures the real
index families without retaining test data.

### Fix (core)

The channel classifier propagates its conversation identity to Router Worker,
which digests and attaches it to proxy, classify, and outbound requests. The
memory API accepts optional session/time constraints, returns session identity,
and uses matching indexes. The Router Worker image includes the new module.

### Todo list

- [x] Reproduce the missing provider header in the Python egress source.
- [x] Add opaque stable correlation and regression coverage.
- [x] Reproduce full-text latency over exactly 10,000,000 rows.
- [x] Fix the expression mismatch and add session/time indexes.
- [x] Rebuild the live services and clear the packaging restart loop.
- [x] Pass the rerun and remove the disposable table.
- [ ] Complete the remaining destructive clean-deploy release suite.

### Prevent recurrence

`router_worker_session_header_unit.py` checks stability, privacy, all egress
hooks, and Docker packaging. `memory_recall_index_unit.py` locks the query/index
contract. `memory_scale_10m_lab.py` requires exact answers, indexed plans,
measured per-query latency, and unconditional table cleanup.

## 20:00 — Clean deployment could leave the learned document mirror unwritable

### Symptom

A destructive clean deployment restored the documentation dataset successfully,
but the post-ready synchronization failed with a permission error. Services were
healthy, so the old workflow reported the deployment as usable even though its
knowledge-refresh stage had not completed.

### Root cause

The restored persistent documentation directory could remain owned by the
privileged backup process. The post-ready learner runs as the deployment user,
and the lifecycle wrapper treated its failure as a warning instead of a failed
deployment.

### Technical detail

- **Function:** `run.sh::do_post_ready_learn()` resolves the configured data
  root, rejects an unsafe root path, and repairs only its `docs` child.
- **Ownership:** privileged deployments use `HERMES_UID:HERMES_GID`; ordinary
  deployments use the invoking user's numeric identity.
- **Failure boundary:** directory creation, ownership repair, synchronization,
  and learning must all succeed or the lifecycle command returns failure.

### Fix and verification

The core lifecycle now creates the mirror, applies recursive ownership and
user read/write traversal permissions, then propagates synchronization failure.
`post_ready_learn_permissions_unit.py` locks the scoped-path and error-propagation
contract. Two clean lifecycle runs completed the post-ready sync and scan with
no manual repair and no container restart.

## 20:30 — Promoted message owner acknowledged an undelivered terminal result

### Symptom

The owner-failover gate promoted the standby, recovered the in-flight item, and
completed its model turn, but no channel delivery was recorded. The recovered
queue item was nevertheless acknowledged and removed.

### Root cause

The base gateway runs the message handler in the background. Its streaming
fallback can return a terminal string after ownership changes without invoking
the adapter's send path. Queue completion waited for the session to become idle
but did not retain that returned value, so it had nothing to recover before
acknowledging the item.

### Technical detail

- **Functions:** `ZaloPlatformAdapter.set_message_handler()` captures the
  terminal handler value on the individual inbound event;
  `_run_claimed_queue_item()` checks delivery history and media ownership after
  session idle, then invokes the serialized sender with
  `delivery_kind=queue_recovery` when required.
- **Safety:** the response is stored per event rather than in shared adapter
  state; the existing owner-token fence and destination lock still protect the
  send.
- **Acknowledgement:** a failed recovery send raises an error, leaving the raw
  item in shared in-flight state for another elected owner.

### Fix and verification

The adapter now retains non-empty terminal text and performs exactly one guarded
recovery delivery only when neither delivery history nor owned media proves a
prior send. Static queue coverage and syntax checks passed. The live two-replica
gate then promoted the standby, delivered the recovered response, drained all
pending/in-flight/active state, restored two replicas, and reported zero
failures.

### Prevent recurrence

`inbound_queue_unit.py` locks terminal capture, delivery-ledger inspection,
recovery-send labeling, and no-ack-on-send-failure. The live failover gate must
prove both channel acknowledgement and queue cleanup; promotion alone is never
a pass.

## 22:35 — Production-final work paused and preserved

### Completed before the pause

- The live media-URL refusal path now intercepts policy refusals before an
  asynchronous workflow is created. A durable delivered response, absence of
  an unintended image, and an independent semantic evaluation all passed.
- The media classifier instructions now keep designed visual requests on the
  image path and require current or external facts to use one search followed
  by one dependent media-generation step. Schedule instructions preserve that
  inner dependency graph under the outer schedule.
- The router validates the composed-image protocol emitted by the model: one
  search must precede one media-generation task and the latter must depend on
  the former. This is protocol validation rather than user-text classification.
- Focused classifier, media shortcut, and prompt assembly unit tests passed.
  Repeated live immediate and scheduled classification probes also produced the
  required graph.
- Earlier gates in this round passed clean deployment, 10-million-record indexed
  recall, continuous-message correlation, active cancellation, concurrent
  direct/group delivery, owner failover with delivery recovery, image and
  document paths, web search, scheduling, environment cleanup, and restart
  monitoring.

### Latest finding

The weather-and-fuel live gate was stale because it submitted a workflow
directly and bypassed the real inbound host shortcut. Its direct workflow
completed but produced text/failure delivery instead of the required composed
image, so it was correctly recorded as a failure. The gate has been rewritten
to inject through the production messaging path and to require the classifier
graphs, the composed-image host flow, an acknowledged attachment send, and
durable marker events. The rewritten gate compiles but has not yet been run.

### Resume checklist

1. Run the rewritten weather-and-fuel messaging-path gate.
2. Run the complete offline suite after the latest classifier and adapter
   changes.
3. Run focused live regressions for service health, media refusal,
   weather-and-fuel composition, queue failover, concurrent direct/group
   delivery, cancellation, and continuous messages. The requested comparative
   benchmark remains intentionally skipped.
4. Inspect container logs, assistant logs, the host plugin journal, OmniRouter,
   and Router Worker for queue residue, abnormal delivery, and restart churn.
5. Finish the architecture/documentation legacy audit and record the final root
   cause analysis.
6. Remove generated reports, temporary bundles, and caches; review the final
   diff and repository status.
7. Only if every required gate passes: commit and push, merge through develop,
   merge through main, reconcile other open merge requests using the newest
   compatible change, and provide the main-branch update procedure.

### Operational state at pause

- The last observed deployment was healthy with two assistant replicas, one
  event-stream consumer, and no restart increase in the key services.
- The most recent verified server restore point is `20260906_222707`.
- Router Worker contains direct-provider fallback logic and unit coverage, but
  live direct-provider credentials are not installed; a complete OmniRouter
  outage therefore remains a model-call availability risk.
- No merge request was opened during this production-final round.
