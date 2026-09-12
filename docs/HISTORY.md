# Project history

This file is the stable navigation point for project history.

- Root-cause records are maintained by date under [`history/`](../history/README.md).
- Operational changes and incident pointers are indexed in [`scripts/HISTORY.md`](../scripts/HISTORY.md).
- Release-facing changes are recorded in [`docs/CHANGELOG.md`](./CHANGELOG.md).

History entries must describe reusable symptoms, causes, decisions, fixes,
verification, and prevention. Do not copy chat messages, credentials, host
identities, or ticket-specific wording into documentation.

## 2026-09-12 — one-pass grounded image composition

See `history/2026-09-12/README.md` for removal of the Pillow information-card
renderer after it created gray canvas bands and obscured scene content. The same
record covers the missing native web-provider registration, quiet async
workflow delivery, and human-readable security alerts.

## 2026-09-09 — scheduled composed-image execution

See `history/2026-09-09/README.md` for the queue-enabled schedule-fire gap that
discarded a valid persisted search→image graph, quoted an internal schedule id,
and omitted task-local attachment correlation. The same correction adds
same-language note UX, removes an unnecessary composed-plan environment knob,
and makes the full scheduled-image fire a mandatory release case. The live
DM/group concurrency gate also found that explicit quoted text was combined
with an unrelated completed session; quote context now takes precedence.
Follow-up gates preserved verbatim atomic prompts through the queue, repaired
dispatcher attachment correlation and scheduled environment loading, and made
shared bottom/left information regions independent of subject count. The same
record documents the retired six-line payload cap and the live harness change
from optional bridge echoes to durable acknowledged delivery evidence. A later
visual review found that the renderer still forced a model-selected bottom band
to full image width; bands are now content-sized and bounded so they preserve
the unrequested side of the scene. The record also covers stale attachment
recall in explicit replies, same-turn routed-search enforcement, and removal of
test-created schedule leakage across live cases.
The uninterrupted clean-deploy run then exposed a broader attachment-recall
boundary: old extracts were appended to every later text-only request, causing
new URL, archive, and DOCX turns to take unrelated long paths and block their
conversation queue. Recall is now conservative and explicit; the archive and
post-restart gates also wait for real terminal/bridge readiness evidence.
The resumed 131-case release gate exposed a cross-process autosend gap:
Dispatcher delivered the requested PDF and claimed it in the shared session,
then the adapter skipped that claim and fell through to an older embedded hero
image. A claimed rich document now terminates that turn's older-file scan, and
the live oracle checks acknowledged source-correlated image delivery directly.
The focused rerun then exposed a startup-order regression: Hermes' later
image-level bundled-skill sync installed a generic PDF skill even after the
entrypoint cleaned categorized clones, sending chat creation back to local
FPDF scripts. Replica startup now retains the restrictive repository wrappers,
suppresses the bundled Office skill names before that later sync, and deletes
categorized clones. The PDF oracle also uses an exact positive token, always
runs its durable delivery audit, rejects unsolicited current-only scope, and
requires an 8/10 visual result without blocking layout defects.

## 2026-09-08 — multi-domain spatial composition

See `history/2026-09-08/README.md` for the evidence-decomposition and flexible
layout correction. Composed images now retain each independently sourced
subject and support validated named or normalized regions; document authoring
uses the same compositor for text over embedded images while keeping ordinary
page regions in safe normal flow. Local rendering, VPS image/PDF inspection,
real-channel delivery, classifier contracts, and restart checks passed.
The same record documents the follow-up completion-budget correction after a
valid multi-region plan was truncated before its closing JSON delimiter.

## 2026-09-08 — bounded queue-session recovery

See `history/2026-09-08/README.md` for the production-gate failure in which a
background agent session remained active after a queue worker expected terminal
delivery. The fix fences the background task before releasing durable work,
separates nested operation timeouts from the queue deadline, and strengthens the
live concurrency test to reject semantically wrong replies.
The same gate found two additional release blockers: queued media routing
dropped the staged source arguments before the host shortcut, and document
tests accepted a PDF without proving it was readable or visually balanced.
The dated record covers the routed quoted-image edit, generic sparse-page
compaction, and render-based PDF evaluation added to prevent recurrence.

## 2026-09-07 — release queue, scheduler, and lifecycle hardening

See `history/2026-09-07/README.md` for standalone Compose secret hydration,
noninteractive post-ready knowledge synchronization, destination-safe queue
recovery, and task-local schedule delivery correlation. The release evidence
now distinguishes accepted transport delivery from generated output and proves
that simple reminders execute once with their requested content.

## 2026-09-06 — scoped notes and request control

See `history/2026-09-06/README.md` for the durable note boundary, semantic
active-turn cancellation, healthy Zalo standby behavior, and OpenBao-backed
retention defaults. The same record covers the atomic task-aware proxy rename
to Router Worker and its upgrade cleanup boundary. It also records the verified
teardown requirement: transient OpenBao values are reloaded before backup and
Compose parsing, and an incomplete OmniRoute inventory blocks destruction.
The Zalo autosender now uses a real per-turn clock and token, preventing a late
artifact from one request from leaking into or muting a later request.
The architecture record now distinguishes active-active HTTP routing from the
active-passive Zalo owner path, and Grafana provisioning has one canonical
host-mounted tree with uniqueness checks.
Outbound delivery is now a bridge-acknowledged PostgreSQL event, so HA recovery
and DM/group isolation evidence remains durable even when the bridge does not
emit self-message journal events. External fixture discovery also supports
nested release worktrees without machine-specific paths.
The Zalo owner lease has an event-loop-independent heartbeat and stale-owner
send fence, preventing synchronous model work from triggering a false takeover
or allowing a genuinely superseded owner to deliver late.
The pre-lock request-control path now reuses deterministic access and group
addressing boundaries before semantic cancellation, and its release evidence
contains no internal execution identifiers.
The same dated record follows the continuous-message production gate from its
initial timeout through the core fixes and final pass. Per-conversation SSE
sequencing and execution locks preserve FIFO without blocking an independent
DM/group stream; quote/session/delivery state is bound to the claimed source
message, and the release evaluator executes as valid nested Python.

The dated record also covers privacy-preserving provider-session correlation
and the 10-million-record memory index gate. That gate exposed and corrected an
expression-index mismatch that made full-text retrieval scan the corpus.
It additionally records the clean-deploy documentation ownership failure and
the owner-failover delivery gap. Post-ready learning now repairs only its
validated persistent mirror and propagates failure; queue recovery now retains
the terminal response, performs a fenced channel send, and acknowledges only
after delivery succeeds.

## 2026-09-05 — update isolation, routing consolidation, and Zalo HA

See `history/2026-09-05/README.md` for the update/watchdog race, transient
OpenBao secret propagation, retired routing cleanup, dependency replacement,
scheduled media plan handoff, grounded image composition, stale Zalo SSE recovery,
image-edit routing, quoted-media ownership, slow-provider resilience,
single-deliverable visual documents, and the
model-authored office-artifact release gate, and Traefik-routed Zalo ownership
with renewable Valkey failover.
