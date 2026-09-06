# 2026-09-06 — scoped notes, cancellation, and HA liveness

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
