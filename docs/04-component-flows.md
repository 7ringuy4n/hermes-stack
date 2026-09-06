# 04 — Component flows

## Interactive chat

```text
edge/Zalo → queue → Hermes → session + memory context
                           → model-router → OmniRoute `hermes`
                           → final reply → session/memory append
```

## Classification and dispatch

```text
current user message + attachment metadata
        → assembled classify prompt
        → model-router → OmniRoute `classifier`
        → schema validation
        → deterministic skill/workflow selection
```

Classification never sends the user response and application code does not
recreate the prompt with regex or keyword maps.

## Knowledge

```text
document → optional AV/policy → safe extraction
         → ingest chunks → embedding service → OmniRoute `embedding`
         → Qdrant knowledge_chunks

question → knowledge search → top supported context → Hermes answer
```

Memory optimization/compact uses the same embedding capability and must retain
useful facts. PostgreSQL remains the durable memory source; vectors are indexes.

## Multipurpose notes

```text
explicit save/find/change/remove intent → classify `notes` plan
                                     → conversation scope (DM user or group)
                                     → PostgreSQL notes + date/full-text indexes
                                     → immutable create/update/delete audit rows
```

Notes may contain any user-defined subject and may be dated or undated. The
host refuses ambiguous mutations instead of choosing a record. Notes and RAG
memory are separate contracts: vectors can improve retrieval but never replace
the scoped PostgreSQL source of truth.

## Active request cancellation

```text
stop message or quote reply → classify control intent (before rate/FIFO gate)
                            → cancel active task in the same conversation
                            → suppress adapter-owned late delivery
                            → release inflight/compound state → continue queue
```

A healthy no-active response is required when no turn is running. Schedule and
note lifecycle actions remain distinct from active-work cancellation.

## Web search

```text
web-search intent → skill/dispatcher → OmniRoute `web-search`
                  → normalized results → sourced final answer
```

SearXNG may be a media-worker backend/member. Search order is operator-managed
in OmniRoute, not hardcoded in application code.

## Still-image generation

```text
image request → classify → image-gen skill
              → OmniRoute `image-gen` → image artifact
              → OCR/visual self-evaluation → Zalo delivery
```

Requested text uses the current message language and safety constraints. Image
operations have a five-minute deadline independent of chat queue saturation.

## Image edit and quote reply

```text
Zalo reply quote → bridge quote metadata → attachment resolver/staging
                 → classify → image-edit skill
                 → OmniRoute `image-edit` → edited artifact
                 → compare with source → delivery to original conversation
```

The quoted message is the source of truth. Global “most recent image” state is
not a valid substitute.

## Office artifacts

```text
brief → documents/file tooling → PDF/DOCX/PPTX/XLSX
      → render pages/slides/sheets → visual QA → final file delivery
```

QA checks content, hierarchy, typography, alignment, spacing, overflow,
contrast, localization, and opening/rendering. File existence alone is not pass.

## Schedule

```text
request → classify schedule plan → schedule-worker → PostgreSQL
        → acknowledgement
due row → queue injection → verbatim or process execution → one delivery
```

Relative release tests use at most two minutes and remove test state afterward.

## Security and secrets

```text
bootstrap env → OpenBao import → scrub plaintext/retired keys
inbound file → size/archive controls → optional AV/policy → capability flow
```

OpenBao and OmniRoute are separate backup components. Reports never expose
secret values. Daily backup and memory compaction load their operational values
from OpenBao; backup and stale staged-memory retention default to seven days.

## Monitoring and recovery

```text
service metrics → Prometheus → Grafana
container logs  → Alloy → Loki
health checks   → stack/alert watcher → scoped recovery only
```

Provider quota, OmniRoute queue saturation, and long media latency are not
container failures. Watchers must not restart healthy services for those
conditions. A non-owner Zalo replica reports healthy standby immediately and
contends for the expiring lease in the background, avoiding periodic gateway
reconnect timeouts. See [test/RULES.md](../test/RULES.md).
