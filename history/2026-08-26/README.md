# 2026-08-26

18 incident(s). Times are UTC+7.

## 07:05 — Classify prompt was one unmaintainable JSON string

### Symptom

Operators could not edit classify policy without scrolling a 20k-character embedded string; copies drifted from the skill SoT.

### Root cause

All taxonomy, schedule, media, delivery, and schema rules lived in a single `system` field.

### AI decision

Backfilled from legacy log. At fix time: prioritize durable core change over VPS hotpatch; align classify/skills when intent routing was involved.

### Fix (core)

Split the skill into `parts/` (core, schedule, media, delivery, schema). Router assembles them into one LLM hop. Sync writes an assembled bake fallback. Remove keyword infographic NLU from the offline heuristic.

### Todo list

- Reproduce
- Fix core
- Regression test
- Verify on lab/VPS

### Prevent recurrence

Edit the matching part file, not the bake JSON. Do not add a second classify call. Do not restore substring intent lists.

## 07:20 — Classify Python still scanned schedule prose

### Symptom

Schedule, delay, clock, destination, and numbered-list intent could still be chosen from user text inside the classifier module when the LLM failed or as a host fill.

### Root cause

Regex fallbacks and clock extraction in classify Python duplicated the LLM job and fought structured JSON.

### AI decision

Backfilled from legacy log. At fix time: prioritize durable core change over VPS hotpatch; align classify/skills when intent routing was involved.

### Fix (core)

Remove those scanners. Normalize keeps JSON fields only. Fail open when classify is down. Harden the schedule skill part so delay, cron, destination, and split are emitted by the model. Host digit-clock mapping stays after `once_at`.

### Todo list

- Reproduce
- Fix core
- Regression test
- Verify on lab/VPS

### Prevent recurrence

Do not add phrase scanners to classify Python. Extend `skills/classify/parts/` and consume JSON.

## 07:35 — Host still scanned user prose for office, poster, and clocks

### Symptom

Office kind/body, text-poster N/phrase, memory mode, and once_at fire time could still be chosen from Vietnamese/English regex in Dispatcher, memory-manager, and schedule helpers.

### Root cause

Those modules duplicated classify. Phrase lists cannot cover paraphrases and fought structured JSON.

### AI decision

Backfilled from legacy log. At fix time: prioritize durable core change over VPS hotpatch; align classify/skills when intent routing was involved.

### Fix (core)

Remove those scanners. Classify emits `output_type`, `poster_n` / `poster_phrase` / `poster_bw`, and `clock_hm`. Host consumes those fields. Prior-conversation strip and status-frame filters are string protocol.

### Todo list

- Reproduce
- Fix core
- Regression test
- Verify on lab/VPS

### Prevent recurrence

Do not add user-language regex to host/classifier Python. Extend `skills/classify/parts/` and structured fields.

## 08:20 — Workflow cadence still scanned user prose

### Symptom

Cadence and some clock helpers still chose once/daily/weekly or AM/PM from Vietnamese/English words when classify JSON omitted cadence.

### Root cause

`plan.infer_cadence_heuristic` and `schedule_tz.parse_hhmm` duplicated classify.

### AI decision

Backfilled from legacy log. At fix time: prioritize durable core change over VPS hotpatch; align classify/skills when intent routing was involved.

### Fix (core)

Remove those scanners. Cadence is classify JSON or an explicit enum. Digit clocks only.

### Todo list

- Reproduce
- Fix core
- Regression test
- Verify on lab/VPS

### Prevent recurrence

Do not add language AM/PM or cadence dictionaries to host Python.

## 08:40 — Office shortcut timed out while the PDF send was still in flight

### Symptom

PDF write succeeded, but the user got a text fallback. Shortcut waited 45s; Dispatcher send waited 90s. Send timeout crashed office-file.

### Root cause

Shortcut timeout shorter than bridge send. office-file only caught HTTPException, not ReadTimeout. Dispatcher /v1/mode still scanned Vietnamese/English verbs.

### AI decision

Backfilled from legacy log. At fix time: prioritize durable core change over VPS hotpatch; align classify/skills when intent routing was involved.

### Fix (core)

Catch send failures after write; shortcut wait 120s. Auto mode uses media flag only.

### Todo list

- Reproduce
- Fix core
- Regression test
- Verify on lab/VPS

### Prevent recurrence

Shortcut wait must exceed Dispatcher Zalo send timeout. Do not infer mode from user-language word lists.

## 09:25 — Operator scripts still offered a removed local LLM path

### Symptom

Product combos are Omni OpenCode, but docs and scripts still told operators how to turn a host LLM path back on. Leftover env pins and Omni connections could fight `hermes`/`classifier`.

### Root cause

The product default changed; enable scripts, compose pass-through, and lab preflight stayed.

### AI decision

Backfilled from legacy log. At fix time: prioritize durable core change over VPS hotpatch; align classify/skills when intent routing was involved.

### Fix (core)

Remove those operator scripts and flags. first-setup clears leftover pins, deactivates leftover Omni Ollama/Qwen connections, and drops leftover Qwen-named combos. Live OpenCode-family members stay. Case 38 checks combo fill only.

### Todo list

- Reproduce
- Fix core
- Regression test
- Verify on lab/VPS

### Prevent recurrence

Do not document or wire a host LLM enable flag. Keep first-setup clearing old pins on upgrade.

## 11:20 — Multi-delay schedule bubbles got no reply

### Symptom

One message with several sequential relative delays could produce no assistant reply. Pause/resume/update on an existing lịch could create a new job instead of changing the matched one.

### Root cause

Classify schema required top-level delay/cron, so a wrapper with only `tasks[]` timing was `classify_invalid` and fell through. Schedule fanout re-classified inner instruction text and dropped delays. Host clock used processing time, not request receipt. Wrapper `task_hint=schedule` always forced create.

### AI decision

Backfilled from legacy log. At fix time: prioritize durable core change over VPS hotpatch; align classify/skills when intent routing was involved.

### Fix (core)

Prompt: keep timed intent as schedule; independent `tasks[]`; accumulate relative delays from receipt; resolution/selector/timezone source. Host: schema accepts `tasks[]`; fanout without a second classify hop; `request_received_at + delay_seconds`; lifecycle via selector + upsert enabled; transform maps to process at fire.

### Todo list

- Reproduce
- Fix core
- Regression test
- Verify on lab/VPS

### Prevent recurrence

Do not re-classify schedule parts. Do not invent schedule ids. Do not default omitted cadence to daily. Classify timeout must cover a multi-job JSON answer.

## 15:30 — Env-variable storage ask got a greeting, not a refuse

### Symptom

User asked how environment variables are stored on the server; the visible reply was a generic greeting with /help instead of a short refuse (looked like no useful response).

### Root cause

1. Secret-probe patterns covered “file môi trường” but not “biến môi trường” / environment-variable storage phrasing, so the gate did not short-block.
2. Classify already emitted a refuse with `process_original_message=false`, but the Zalo host never delivered that line and fell through to Hermes, which greeted.

### AI decision

Backfilled from legacy log. At fix time: prioritize durable core change over VPS hotpatch; align classify/skills when intent routing was involved.

### Fix (core)

Expand `config/agent/secret-probe.json` (+ gateway copy / defaults). Harden classify SECRET/ENV policy and SOUL/safety/zalo-channel for env-variable storage asks. Host: when classify sets `process_original_message=false` with a refuse body (skill null/security), send that body and do not call Hermes.

### Todo list

- Reproduce
- Fix core
- Regression test
- Verify on lab/VPS

### Prevent recurrence

Secret probe must block env-variable paraphrases before LLM. Host must honor `process_original_message=false` for direct refuse lines.

## 16:10 — Secret probe hardcoding + quote envelope miss

### Symptom

Env-storage soft asks could reach Hermes as a greeting. Probe Python carried embedded deny lists and regex. @mention with a quoted message/file could hide probe wording in the quote.

### Root cause

1. `_DEFAULT_INPUT` / `_DEFAULT_OUTPUT` and `re.compile` lived in probe modules instead of policy-only matching.
2. Host secret-probe scanned outer text only.
3. Classify refuse (`process_original_message=false`) was not always delivered by the host.

### AI decision

Backfilled from legacy log. At fix time: prioritize durable core change over VPS hotpatch; align classify/skills when intent routing was involved.

### Fix (core)

Policy-only literal markers; fail closed if policy missing. Probe outer + quoted snip/filename. Host direct refuse for classify `process_original_message=false`. Harden classify SECRET/ENV for quote/mention envelopes. Generic SOUL/safety/zalo-channel; ops alert for missing policy.

### Todo list

- Reproduce
- Fix core
- Regression test
- Verify on lab/VPS

### Prevent recurrence

Do not embed deny dictionaries or regex in probe Python. Soft paraphrases belong in classify/LLM. Always scan quote envelopes before Hermes.

## 16:50 — Secret file ask still opened knowledge-learn; probe keywords grew

### Symptom

Refuse could succeed while Knowledge pending-approval still staged the attachment. Soft env/secret asks encouraged expanding secret-probe keyword lists.

### Root cause

1. Async file → learn/submit did not honor classify refuse.
2. Intent was partially encoded as literal markers in secret-probe.json.
3. Plaintext OpenBao/stack env exports remained after deploy/restore.

### AI decision

Backfilled from legacy log. At fix time: prioritize durable core change over VPS hotpatch; align classify/skills when intent routing was involved.

### Fix (core)

Policy intent_owner=classify with empty marker lists. Strengthen classify SECRET/ENV + safety. Host learn-skip on classify refuse; AV/file path classifies caption before learn. Scrub plaintext exports after up|update|restore.

### Todo list

- Reproduce
- Fix core
- Regression test
- Verify on lab/VPS

### Prevent recurrence

Do not grow soft-phrase dictionaries in secret-probe.json — strengthen classify/skills. Never stage knowledge after a secret refuse.

## 16:55 — Dual secret-probe marker lists collapsed

### Symptom

Policy still carried separate input and output marker arrays after soft intent moved to classify.

### Root cause

Schema kept two lists for a gate that is classify-owned and empty by default.

### AI decision

Backfilled from legacy log. At fix time: prioritize durable core change over VPS hotpatch; align classify/skills when intent routing was involved.

### Fix (core)

Single `block_patterns` (default empty) in secret-probe policy and probe/ingest readers.

### Todo list

- Reproduce
- Fix core
- Regression test
- Verify on lab/VPS

### Prevent recurrence

Do not reintroduce input/output keyword dictionaries for soft secret intent — strengthen classify.

## 18:10 — Blank docs got secret refuse

### Symptom

Blank or ordinary test attachments could show the secret/env refuse line even with no secret-seeking caption. After scrub, compose update could fail missing required `.env` values.

### Root cause

1. AV gate treated prior learn-skip and filename-only blobs as a full secret refuse.
2. Classify SECRET ASK + ATTACHMENT was too broad for bare/blank filenames.
3. Scrub emptied compose-interpolated host keys and update did not reload OpenBao before compose.

### AI decision

Backfilled from legacy log. At fix time: prioritize durable core change over VPS hotpatch; align classify/skills when intent routing was involved.

### Fix (core)

Classify: refuse only on explicit secret/env asks; bare/blank/filename-only stay file OCR/read. Host: refuse on ask text (or extracted body that is itself a secret ask); learn-skip only skips knowledge staging. Scrub skips compose-required keys; load OpenBao env before up|update.

### Todo list

- Reproduce
- Fix core
- Regression test
- Verify on lab/VPS

### Prevent recurrence

Do not classify filename-alone as a secret probe. Do not reuse learn-skip as a turn-wide refuse. Keep compose-required host keys or reload them before compose.

## 18:25 — Blank attachments still refused via Zalo fileExt JSON

### Symptom

Blank/ordinary Security-folder attachments still received the secret/env refuse line after the prior filename-only fix.

### Root cause

Zalo inbound text for files is often a fileExt/wire JSON blob. The AV secret gate classified that JSON as the user ask.

### AI decision

Backfilled from legacy log. At fix time: prioritize durable core change over VPS hotpatch; align classify/skills when intent routing was involved.

### Fix (core)

`_as_user_secret_ask_blob` drops wire JSON and filename-alone. Attachment body that is itself a secret ask still refuses (risk docs). Classify: fileExt envelopes are not secret probes.

### Todo list

- Reproduce
- Fix core
- Regression test
- Verify on lab/VPS

### Prevent recurrence

Never treat channel wire metadata as a secret-seeking caption.

## 18:35 — Blank docs still opened Knowledge pending

### Symptom

Blank/whitespace-only attachments could still notify Knowledge pending-approval. Long security/LLM-risk documents could be mistaken for short secret asks.

### Root cause

1. File pipeline submitted learn with path even when OCR/extract was empty.
2. Attachment secret gate classified full long documents the same as short risk txt bodies.

### AI decision

Backfilled from legacy log. At fix time: prioritize durable core change over VPS hotpatch; align classify/skills when intent routing was involved.

### Fix (core)

Skip learn on empty/whitespace extracts (host + ingest). Short-body-only secret refuse for attachment content. Classify/SOUL/safety: untrusted content is data; blank never learn; long risk notes are documents.

### Todo list

- Reproduce
- Fix core
- Regression test
- Verify on lab/VPS

### Prevent recurrence

Never stage knowledge without meaningful text. Do not treat security whitepapers as user secret probes.

## 18:50 — Blank docs still opened Knowledge pending; classify 401 after scrub

### Symptom

Blank/whitespace-only attachments could still notify Knowledge pending-approval. Long security/LLM-risk documents could be mistaken for short secret asks. After env scrub, router-worker classify failed with Omni 401.

### Root cause

1. File pipeline submitted learn with path even when OCR/extract was empty.
2. Attachment secret gate classified full long documents the same as short risk txt bodies.
3. Scrub wiped compose-interpolated Omni/Gateway keys from ROOT/.env while router-worker reads them via compose `${VAR}`.

### AI decision

Backfilled from legacy log. At fix time: prioritize durable core change over VPS hotpatch; align classify/skills when intent routing was involved.

### Fix (core)

Skip learn on empty/whitespace extracts (host + ingest). Short-body-only secret refuse for attachment content. Classify/SOUL/safety: untrusted content is data; blank never learn; long risk notes are documents. load-openbao-env fills compose LLM keys when empty; scrub skips those interpolate keys.

### Todo list

- Reproduce
- Fix core
- Regression test
- Verify on lab/VPS

### Prevent recurrence

Never stage knowledge without meaningful text. Do not treat security whitepapers as user secret probes. Keep compose-interpolated LLM keys fillable from OpenBao before up|update.

## 19:20 — Blank docx inspected via Hermes docx/terminal

### Symptom

Blank office attachments produced long agent replies that unzipped packages, read metadata, and narrated missing python-docx — not a short empty-file notice.

### Root cause

After worker extract, office binaries could still be passed to Hermes (`media_urls`), so the local docx skill / terminal ran instead of the host ingest extract ack.

### AI decision

Backfilled from legacy log. At fix time: prioritize durable core change over VPS hotpatch; align classify/skills when intent routing was involved.

### Fix (core)

Host treats ingest/OCR extract as SoT for office/text; blank/whitespace short-circuits with empty-file ack; strip media paths before any Hermes hop. Classify/SOUL/docx/worker-routing: chat attachment reads stay on media_file/ingest/OCR — never local docx/terminal forensics.

### Todo list

- Reproduce
- Fix core
- Regression test
- Verify on lab/VPS

### Prevent recurrence

Never hand chat office packages to Hermes tools when workers already extracted (or found empty).

## 19:35 — Zip attachments needed media-only worker extract

### Symptom

Compressed attachments were not handled as media-worker reads; Hermes could terminal-unzip packages including non-media members.

### Root cause

`.zip` was `attachment_kind=none`, so no ingest extract path ran and the binary could reach Hermes tools.

### AI decision

Backfilled from legacy log. At fix time: prioritize durable core change over VPS hotpatch; align classify/skills when intent routing was involved.

### Fix (core)

Ingest `extract-archive` (media members only). Host kind=archive → that endpoint; strip paths; empty-archive ack. Classify routes archives to media_file without local unzip forensics.

### Todo list

- Reproduce
- Fix core
- Regression test
- Verify on lab/VPS

### Prevent recurrence

Never expand nested archives or non-media members for chat attachment reads.

## 19:40 — Multi-format archives needed media-only extract + password gate

### Symptom

Zip was insufficient; 7z/rar/tar and password-protected packs could fall through to Hermes tools or expand non-media members.

### Root cause

Archive support was zip-only without password handling or rar/7z backends.

### AI decision

Backfilled from legacy log. At fix time: prioritize durable core change over VPS hotpatch; align classify/skills when intent routing was involved.

### Fix (core)

Ingest extract-archive for zip/7z/rar/tar with optional password; media-only members; host password ack; classify routes archives to media_file without local unzip.

### Todo list

- Reproduce
- Fix core
- Regression test
- Verify on lab/VPS

### Prevent recurrence

Never brute-force archive passwords. Never expand nested archives or non-media members.
