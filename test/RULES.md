# Hermes Stack verification contract

This file is the source of truth for repository and VPS release verification.
Tests prove the live user outcome and route; an assertion alone is not proof.

## 1. Safety and test identity

- Read `AGENT_RULES.md`, `BE_RULE.md`, `HARDEN_RULE.md`, `docs/GIT.md`,
  `docs/CHANGELOG.md`, `docs/HISTORY.md`, and `history/` before a lab.
- Use only the designated test VPS and operator-authorized Zalo account.
- Supply the user identity at runtime as `ZALO_TEST_USER_ID`. Never commit a
  numeric Zalo identity or print authentication tokens.
- Back up and verify Zalo state, OpenBao, and OmniRoute configuration before
  destructive lifecycle testing. Reports record checksums/counts, not secrets.
- First setup is setup-only: no test traffic, temporary patch, or generated
  media. Tests begin after setup completes.
- Do not change AI Box accounts, provider members, combo ordering, or strategy
  during an update test. Export before/after and compare.
- Temporary artifacts go under `scripts/temp/` or the lab report directory and
  are removed when the run completes. Remove Python caches from core source.

## 2. Outcomes

| Result | Meaning |
|---|---|
| `PASS` | Route evidence, final artifact/reply, semantic evaluation, and relevant logs all satisfy the case. |
| `FAIL` | Product behavior, delivery, correctness, layout, concurrency, or stability is wrong. |
| `SKIP` | A free-provider quota/capability block is proven in logs; never use SKIP for a code/runtime defect. |
| `BLOCKED` | Required authorization or external state is unavailable. |

Never relabel a failed live test as pass. Every report includes exact timestamps,
commit SHA, replica count, correlation IDs, combo/model attribution, elapsed
time, restart deltas, and sanitized evidence.

Transport delivery evidence must be an acknowledgement-backed durable
`delivered` event. A queued `assistant_turn`, generated file, log intention, or
optional bridge self-message echo is not proof that Zalo accepted the result.

Gateway approval prompts are control-plane messages. When a gateway marks a
send with `is_approval_prompt`, the Zalo adapter must deliver it through the
normal secret and egress guards while bypassing assistant process-narration and
post-media muting. A filtered prompt reported as successfully delivered is a
failure because it leaves the tool waiting for consent the user cannot provide.

## 3. Two-phase release gate

### Phase A — local/static

1. Confirm current architecture docs agree with compose and `run.sh`.
2. Search current code/docs for retired 9Router, legacy OmniRouter, local OCR,
   ComfyUI, video-gen/video-edit, and retired secret aliases. Historical
   changelogs may retain them as dated history.
3. Run syntax, unit, classify-contract, media-policy, Zalo queue, backup,
   OpenBao, and documentation-link checks.
4. Confirm no numeric Zalo identity, secret, Python cache, or ad-hoc patch file
   is committed.

### Phase B — clean VPS deployment

1. Capture baseline services, workers, timers, restart counters, disk/memory,
   recent container logs, Zalo journal, OmniRoute logs/history, and watcher logs.
2. Run `bash run.sh backup` and `bash run.sh verify`; verify Zalo and OmniRoute
   components without exposing their contents.
3. Run `bash run.sh destroy`, then `bash run.sh up`. Volumes and
   `/data/assistant` remain. Restore enabled workers from the retained supported
   configuration and validate service-specific health.
4. Prove Zalo identity/session and OmniRoute provider/combo configuration match
   the pre-destroy backup.
5. Prove the Zalo path is bridge → proxy → Traefik → Valkey-elected Hermes
   owner. Stop the active owner and verify a standby acquires after the bounded
   lease interval without duplicate delivery or restarting every replica.
   Kill an owner after it claims a queued item and prove the promoted owner
   recovers the inflight item before later items in that conversation.
6. Execute the capability cases below through the Zalo plugin and confirm the
   operator sees every expected result in Zalo.
7. Repeat the concurrency workload with `HERMES_REPLICAS=1` and `2` using the
   same prompts/fixtures; compare latency, throughput, routing, restarts, and
   resource pressure.
8. Re-read logs and restore the requested final replica count. Clean temporary
   files and caches.

## 4. Capability cases

Fixtures come from `D:\Onedrive\Work\test docs`. Copy only the case inputs to a
sanitized VPS lab directory; do not modify the source fixture directory.

### C1 — image generation (`image-gen`)

Send a natural-language still-image request through Zalo. Require:

- classify selects image generation and OmniRoute records requested combo
  `image-gen`;
- one viewable image is delivered to Zalo within the image operation deadline
  (maximum five minutes);
- when text is requested, visible text follows the current message language,
  contains no profanity, and is checked by OCR plus visual inspection;
- for a multi-subject request, every independently sourced subject is present
  exactly once and every explicit spatial relationship is preserved;
- treat an explicitly requested shared region as one visual group even when it
  contains several independently sourced subjects. Subject count must not
  silently become panel count, and payload adaptation must preserve every
  validated fact rather than truncating to a legacy line limit;
- exercise both a shared bottom information bar and a shared left-side frame
  with current weather plus fuel prices. Require the complete facts in the
  requested language, the requested placement, one cohesive background, and no
  hard-coded split-panel fallback. A bottom band is content-sized by default
  and must leave meaningful scene visible beside it; it may cover the full
  width only when the request explicitly requires full width;
- exercise at least one named grid arrangement, one repeated-side arrangement,
  and one normalized custom-region arrangement. Unspecified regions must be
  distributed without overlap; no panel may cover another panel or essential
  requested scene content;
- the scene, composition, typography, contrast, and requested facts are scored,
  not merely file existence.

### C2 — vision analysis (`vision-ocr`)

Send at least one image containing text and one image without text. Ask the LLM
to analyze naturally rather than force a fixed OCR template. Require route
evidence for `vision-ocr`, accurate description/transcription where applicable,
uncertainty for unreadable content, and one user-visible answer per input.

### C3 — optimize/compact memory and knowledge

Seed a unique non-secret fact/document, invoke both supported optimization
paths, and prove embedding calls use combo `embedding`. Verify useful recall
before/after, no silent data loss, collection/schema compatibility, bounded
resource usage, and no unrelated conversation leakage.

### C4 — web search (`web-search`)

Ask a time-sensitive question whose answer can be independently checked.
Require route attribution to `web-search`, current sources/links, agreement
between cited sources and answer, and no fabricated citation. A provider quota
may be skipped only when an alternate member also cannot serve and logs prove
the external limit. Each typed current-data request must make a fresh native
search call in the same turn. Reusing a prior answer or substituting code,
shell, or direct language HTTP calls fails the route even if the prose looks
plausible.

### C5 — embedding API (`embedding`)

Submit known related/unrelated strings through the live embedding path. Require
correct vector shape, finite values, related-pair similarity above unrelated
pairs, `embedding` combo attribution, and no fallback to a chat combo.

### C6 — document and archive analysis

Use representative PDF, DOCX, PPTX, XLSX, text, image, and compressed fixtures.
Require safe extraction limits, traversal/bomb defenses, natural analysis via
`vision-ocr` where visual reading is needed, accurate file enumeration, and no
server paths or extracted secrets in the Zalo reply. Unsupported/corrupt files
must fail clearly without crashing workers.

### C7 — scheduler

Schedule one harmless result for no more than two minutes in the future. A
simple reminder must be stored and delivered as verbatim standalone content;
it must not be converted into generated work or a follow-up question. Require
exactly one acknowledgement, durable row, one execution, and one final
transport-accepted delivery whose `source_message_id` correlates to that
schedule row. Also require the correct timezone and no duplicate after a
worker or Hermes restart. Remove the test schedule and row afterward.

For scheduled image work, persist the full original intent instead of reducing
it to a text reminder. Run the same adaptive weather-and-fuel composition used
by C1 with a near-future deadline and require the scheduled artifact to retain
the shared-region placement, facts, language, single-scene requirement, and
source-correlated image delivery.

Every test-created schedule must include an opaque source marker and be deleted
in a cleanup boundary on pass, failure, or timeout. A later live case must never
observe a delayed fire left behind by an earlier harness.

### C8 — image edit, including Zalo reply quote

Send an image, then reply-quote that message with a natural edit instruction.
Require quoted attachment resolution, route attribution to `image-edit`, a
visibly edited output that preserves unrequested content, and delivery to the
same conversation. Fail if the source image is guessed from global recent
state, the original is returned unchanged, or only routing is proven.

### C9 — professional office artifacts

Generate one PDF, DOCX, PPTX, and XLSX from the same small content brief.
Require accurate content plus visual QA from rendered pages/slides/sheets:
hierarchy, margins, alignment, contrast, readable typography, tables/charts,
page breaks, clipping/overflow, localization, and consistent style. “File
opens” is insufficient. Use the repository document skills and their
render-and-inspect workflow.

External design references must be reviewed for license before reuse. Research
may use high-signal repositories such as `anthropics/skills` and
`hugohe3/ppt-master`; learn from their workflows, but do not vendor unlicensed
or incompatible code/assets.

Repeat the PDF case with several explicitly positioned subjects. Ordinary
document content must preserve the requested row/column/edge relationships in
safe normal flow. When the request explicitly requires copy over an embedded
image, require one dispatcher-composed image with all requested regions, embed
only that final image, and reject overlap, missing regions, risky absolute CSS,
or separately delivered intermediate images.

When Dispatcher has already delivered and claimed a final PDF or Office file,
adapter late-autosend must stop at that claimed document and must not expose an
older embedded image as another attachment. Filesystem sidecars are diagnostic;
the release oracle fails on an acknowledgement-backed image delivery correlated
to the document-only source request.

Replica startup must retain the repository root `pdf`, `docx`, and `xlsx`
wrapper directories and add the bundled names to `.curator_suppressed` before
image-level skill sync. Their frontmatter names remain distinct and route chat
creation to `file-gen`; categorized and official clones are removed. The live
oracle must match the positive `NEW_PDF` line exactly, never treat `NO_NEW_PDF`
as success, query durable image delivery even when no document appears before
the deadline, and fail closed if that audit is unavailable. For a current-only
request, it must reject forecast, probability, or advice sections. Its rendered
page judge must report at least 8/10 and no blocking overlap, clipping,
unreadable text, broken hierarchy, or materially wasted space.

For composed images with several information regions, also reject an empty or
truncated structured composition plan. The live gate must observe a complete
planner response before accepting generated-file and delivery evidence.

### C10 — multipurpose notes, session history, RAG, and cancellation

Create dated and undated notes for at least three unrelated subjects (for
example a plan, an idea, and a personal checklist). Require DM/user and group
scopes to remain isolated, exact-date lookup to use the indexed note date,
topic lookup to return the correct stored content, duplicate create to dedupe,
and update/delete to write an audit version. An ambiguous mutation must ask for
selection and must not change data.

Verify short-term session history survives a Hermes replica replacement and
that durable RAG recall remains grounded after compact/embedding reindex. Reset
the session and prove archived history is traceable without leaking another
thread's content.

During a deliberately long request, send an explicit stop message and repeat
with a quote-reply in both an authorized DM and group. The control request must
bypass rate/FIFO admission, cancel only the active turn in that thread, record
`cancel_requested` then `cancelled`, suppress late delivery, release ownership,
and allow the next queued request to complete. If no work is active, require an
accurate no-active response rather than a false success.
The user-facing stop acknowledgement must not expose a process/container ID,
task or message identifier, correlation value, queue key, or other internal
execution handle.
An unauthorized sender, disallowed group, unaddressed group message, or group
with control disabled must not reach semantic cancellation or stop another
user's active turn.

### C11 — continuous-message ordering and conversational continuity

Send at least four natural messages consecutively to one DM without waiting for
the previous response. Include one direct request, one reply quoting the bot's
answer, one short contextual follow-up that omits an entity already established
by the quoted/prior turn, and one unrelated request. Repeat the sequence in an
authorized group while correctly addressing the bot.

Require every accepted message to produce exactly one terminal outcome in FIFO
order. Each response must remain correlated with its own source queue item,
retain the correct source-tagged user text in session history, use quoted and
recent context without an unnecessary clarification, and keep unrelated
requests independent. Native quote transport must be verified with genuine
Zalo message identifiers; an injection lab may verify quoted-context semantics
and successful plain fallback but must not claim native quote-bubble proof.
Fail on crossed sources, duplicate or missing replies, context taken from a
later message, a timeout notice after a valid result, late output from an
earlier turn, queue residue, or leakage between DM and group scopes.

After an attachment case, send an unrelated URL, image-generation, schedule,
or document-creation request in the same conversation. The fresh request must
not inherit the old extract. A text-only attachment follow-up must contain an
explicit file/sheet/image/archive back-reference (or be a short unambiguous
elliptical follow-up) before recall is hydrated. Archive injection must use the
real single-media shape and its case must wait for a non-busy, exact-source
terminal reply before later concurrency cases begin.

Run a second burst while the first item is intentionally slow. Verify queue
depth grows within its configured bound, the elected owner renews its lease,
later items remain durable, and completion or cancellation of the first item
allows the remaining items to drain in order. Record admission-to-delivery
latency for every item rather than reporting only total runtime.

### C12 — ten-million-record memory scale

Generate an isolated, disposable corpus of exactly 10,000,000 records on the
production PostgreSQL engine. Do not commit or retain the generated data. Use
the same full-text, conversation, session, and time predicates/index families
as Memory Manager.

Measure two independently marked needles: one knowledge/RAG fact and one task
from a specifically named old session. Require exact content and scope matches,
an indexed query plan, individual execution latency within the configured
production budget, and zero cross-session substitution. Report corpus size and
both measured latencies. Always drop the lab table in cleanup, including after
a failed assertion.

## 5. Two-request concurrency and quote isolation

Run exactly two concurrent Zalo requests for the designated test identity:

1. reply-quoted image edit using a known source image;
2. a different capability from C1–C7 with a unique marker.

Both requests must retain their own correlation ID, quoted/source attachment,
acknowledgement, final result, and ordering. Fail on swapped media, cross-talk,
duplicate sends, missing final delivery, shared temporary filenames, or one
request blocking the other beyond its operation deadline.

Record wall-clock completion for the pair with one and two Hermes replicas.
Report median/tail latency only from observed samples; do not claim scaling
benefit when provider latency dominates or the sample is too small.

Also run one DM request and one request in the named three-member test group at
the same instant. Resolve the group by display name at runtime, verify its
membership through durable channel state, and require each result to return to
its originating conversation. Numeric identities must remain runtime-only.
The elected owner serializes gateway agent execution per conversation while
allowing independent conversations to run concurrently. It must retain both
durable claims, pulse worker ownership while waiting, acknowledge only after
terminal session completion, and deliver both within their operation deadlines.

Run two additional capability bursts with
`test/scripts/zalo_dm_group_capability_concurrency_lab.py`. Each burst admits
exactly one DM and one addressed group request simultaneously:

1. current-weather searches for different cities, with independent
   source-message correlations, current-condition semantics, independent
   evaluation, and `web-search` combo attribution;
2. DOCX creation with distinct titles and exact body markers, followed by
   acknowledged attachment correlation and package-content inspection.

These bursts must not use quote replies as a substitute for executing the real
search and file-generation paths. See
`test/cases/76-zalo-dm-group-capability-concurrency.md`.

## 6. Stability observation

Before and after every live set, capture:

```bash
docker compose ps
docker compose logs --since 15m hermes router-worker omni-router
journalctl --user -u com.hermes.zaloplugin --since '15 minutes ago'
systemctl --user status com.hermes.zaloplugin
systemctl list-timers 'assistant-*'
```

After any lifecycle test that restarts the active Zalo owner, wait until bridge
health reports both a logged-in session and at least one SSE consumer before
injecting the next test event. HTTP acceptance without a live consumer is not
message-delivery evidence.

Include dispatcher/jobs, schedule-worker, Valkey/PostgreSQL/Qdrant, and stack/
alert watchers when used. Distinguish:

- provider quota, queue saturation, or slow generation;
- deadlocked/blocked local request handling;
- health-check mismatch;
- memory/CPU/disk pressure;
- restart-policy/watchdog loops;
- Zalo session loss, duplicate ownership, or send failure.

Any unexpected restart, unbounded queue growth, missed reply, wrong quote, or
continuous watcher recovery blocks release until its core cause is fixed and
the full affected case is rerun.

## 7. Merge gate

Open/merge release requests only when explicitly authorized and every required
case is PASS or an evidenced provider-only SKIP accepted by the decision. Use a
feature branch into `develop`; then create a release branch from current
`main`, bring only the verified changes, and merge its request into `main`.
Inspect other open requests, keep the newest compatible fix when changes
conflict, and never merge stale superseded behavior.
