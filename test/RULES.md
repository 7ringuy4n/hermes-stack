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
the external limit.

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

Schedule one harmless Zalo result for no more than two minutes in the future.
Require exactly one acknowledgement, durable row, one execution, one final
delivery, correct timezone, and no duplicate after worker/Hermes restart.
Remove the test schedule and row afterward.

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

## 6. Stability observation

Before and after every live set, capture:

```bash
docker compose ps
docker compose logs --since 15m hermes model-router omni-router
journalctl --user -u com.hermes.zaloplugin --since '15 minutes ago'
systemctl --user status com.hermes.zaloplugin
systemctl list-timers 'assistant-*'
```

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
