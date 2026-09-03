# 2026-08-25

11 incident(s). Times are UTC+7.

## 07:45 — Relative schedule wrong clock; image+txt collapsed

### Symptom

Relative one-shot group delivery confirmed at the wrong local clock; list did not show the new job. Compound image+text-file asks lost the image deliverable; some PDF creates bypassed Dispatcher.

### Root cause

1. Classify guided the model to compute absolute fire times into cron / next_run_at.
2. Schema rejected delay-only plans.
3. Host preferred model timestamps over runtime delay resolution.
4. Office shortcut treated mixed image+file bubbles as a single file create.

### AI decision

Backfilled from legacy log. At fix time: prioritize durable core change over VPS hotpatch; align classify/skills when intent routing was involved.

### Fix (core)

- Harden classify for once_after + delay_seconds and multi-deliverable splits.
- Accept delay-only schedules; host owns fire instant.
- Skip office shortcut when image and file are requested together.

### Todo list

- Reproduce
- Fix core
- Regression test
- Verify on lab/VPS

### Prevent recurrence

Classifier never resolves wall-clock for relative delays. Confirmations must come from schedule-worker/tool responses, not model prose.

## 07:55 — Classify still taught one-shot cron

### Symptom

Weak classify models could still emit invented `cron_expr` for one-shot schedules despite relative-delay harden rules.

### Root cause

Prompt contradictions: intent/keys/examples still implied cadence+cron for every schedule, including once_at / once_after.

### AI decision

Backfilled from legacy log. At fix time: prioritize durable core change over VPS hotpatch; align classify/skills when intent routing was involved.

### Fix (core)

Harden `classify.json` so only recurring schedules emit `cron_expr`. One-shot forms leave cron null; host resolves timing.

### Todo list

- Reproduce
- Fix core
- Regression test
- Verify on lab/VPS

### Prevent recurrence

Any new schedule guidance in classify must name `schedule_form` and must not teach one-shot → cron.

## 08:05 — Phrase scanners stole mixed jobs from classify

### Symptom

Mixed image+file bubbles could produce only a text file. Relative one-shot schedules and cross-thread sends depended on incomplete word lists, so paraphrases missed the intended path.

### Root cause

Dispatcher shortcuts and host extractors classified intent with phrase dictionaries before (or instead of) model-router JSON.

### AI decision

Backfilled from legacy log. At fix time: prioritize durable core change over VPS hotpatch; align classify/skills when intent routing was involved.

### Fix (core)

Harden classify so it owns paraphrases, mixed deliverables, immediate adapter deliver, and delay_seconds. Host consumes those fields; office shortcut runs only for a single classified file job.

### Todo list

- Reproduce
- Fix core
- Regression test
- Verify on lab/VPS

### Prevent recurrence

Do not add natural-language dictionaries for schedule/media/destination. Extend `classify.json` and structured plan fields instead.

## 18:40 — Dictated schedule body fired as process; gateway crash-loop

### Symptom

Relative one-shot send-later jobs saved, then never delivered. API gateway restarted on classify client import.

### Root cause

1. Classify treated any `nội dung:` containing describe-like words as assistant task-work (`process`), so fire went through Hermes and hung.
2. Gateway `classify_client.py` compiled a regex without importing `re`.

### AI decision

Backfilled from legacy log. At fix time: prioritize durable core change over VPS hotpatch; align classify/skills when intent routing was involved.

### Fix (core)

Harden `classify.json` so dictated send-bodies are `verbatim` and skill-lists stay `process`. Host consumes `schedule_delivery`. Heuristic fallback only treats lead describe-verbs as generate-jobs. Add the missing gateway import.

### Todo list

- Reproduce
- Fix core
- Regression test
- Verify on lab/VPS

### Prevent recurrence

Do not keyword-spot payload words to choose process vs verbatim. Classifier JSON owns that decision.

## 19:10 — Verbatim fire stored then silently dropped

### Symptom

Relative send-later lịch saved and fired; no Zalo message arrived.

### Root cause

Classify and host stored `schedule_delivery=verbatim`. At fire the adapter called send, then `/v1/outbound` treated the dictated body as process chatter and dropped it (`drop approval/resume chatter`).

### AI decision

Backfilled from legacy log. At fix time: prioritize durable core change over VPS hotpatch; align classify/skills when intent routing was involved.

### Fix (core)

Verbatim scheduleFire metadata skips the outbound noise filter. That filter stays for Hermes-generated lines only.

### Todo list

- Reproduce
- Fix core
- Regression test
- Verify on lab/VPS

### Prevent recurrence

Do not run `/v1/outbound` on a payload the host already committed to deliver as-is.

## 19:45 — Group describe fire echoed the schedule ask

### Symptom

One-shot “send into named group + describe …” saved, then the group received the original schedule sentence instead of a description.

### Root cause

Classifier treated “gửi vào [group]” as dictated send (`verbatim`) and left timing/destination in `message`/`fire_text`. Host fell back to the create ask when no `nội dung:` marker existed.

### AI decision

Backfilled from legacy log. At fix time: prioritize durable core change over VPS hotpatch; align classify/skills when intent routing was involved.

### Fix (core)

Harden `classify.json` so destination + work verb is `process` with inner-work only. Heuristic strips destination before delivery choice. Host never fires a create-schedule shell as `fire_text`.

### Todo list

- Reproduce
- Fix core
- Regression test
- Verify on lab/VPS

### Prevent recurrence

`message`/`instructions` must never contain relative-delay or “gửi vào [group]” wrappers; destination stays in `target_channel`.

## 19:50 — Verb regex was fake NLU on the host

### Symptom

Fixes kept adding Vietnamese/English verb lists in host and heuristic to choose verbatim vs process.

### Root cause

Classify owns paraphrases; host dictionaries cannot and must not.

### AI decision

Backfilled from legacy log. At fix time: prioritize durable core change over VPS hotpatch; align classify/skills when intent routing was involved.

### Fix (core)

Remove lead-verb / schedule-shell regex from host. Trust `schedule_delivery` and plan fields. Heuristic uses only the `nội dung:` protocol marker (verbatim once_after) vs default process. Refuse fire_text identical to the full inbound ask.

### Todo list

- Reproduce
- Fix core
- Regression test
- Verify on lab/VPS

### Prevent recurrence

Do not grow natural-language dictionaries for schedule delivery. Harden `classify.json` instead.

## 20:20 — Zalo still phrase-scanned Vietnamese for intent

### Symptom

Office/poster/schedule/destination/search paths could still be chosen by host regex and keyword lists even after classify owned delivery mode.

### Root cause

`plugins/zalo` kept semantic scanners (`looks_*`, group-name extractors, topic wraps, lyric keywords) that inferred task_hint / routing from user prose.

### AI decision

Backfilled from legacy log. At fix time: prioritize durable core change over VPS hotpatch; align classify/skills when intent routing was involved.

### Fix (core)

Remove those scanners. Host consumes classify JSON only. Harden `classify.json` for ownership, live-data files, destination, and lyric/search families. Units assert plan gates.

### Todo list

- Reproduce
- Fix core
- Regression test
- Verify on lab/VPS

### Prevent recurrence

Do not add Vietnamese natural-language dictionaries under `plugins/zalo`. Extend `classify.json` and structured fields instead.

## 20:55 — List ask deleted a schedule

### Symptom

Users asking where a reminder was (often while quoting the create message) got “Đã xóa 1 lịch” instead of a list. Bare list phrasing stayed chat.

### Root cause

Classify had no strong list/inspect family; quoted create context was treated as delete. Host normalize forced non-delete schedules to create_schedule, so list could not survive schema.

### AI decision

Backfilled from legacy log. At fix time: prioritize durable core change over VPS hotpatch; align classify/skills when intent routing was involved.

### Fix (core)

Harden `classify.json` for list vs delete and process-group `target_channel`. Accept `list_schedule` in classify clients; adapter lists via schedule-worker when `skill_action=list`.

### Todo list

- Reproduce
- Fix core
- Regression test
- Verify on lab/VPS

### Prevent recurrence

Never map where/list/show/inspect to delete. Quotes do not change the current ask’s action.

## 21:05 — Classify prompt lived in three places

### Symptom

Prompt hardenings were re-applied under model-router/config while Zalo/gateway clients and docs pointed at different paths, so behavior drifted after updates.

### Root cause

`classify.json` was treated as a model-router-only file instead of the inbound Zalo classify skill contract.

### AI decision

Backfilled from legacy log. At fix time: prioritize durable core change over VPS hotpatch; align classify/skills when intent routing was involved.

### Fix (core)

Move SoT to `hermes/main/skills/classify/`. Router mounts skills and reads that file. Sync bake fallback on update. Document that every Zalo message classifies purpose via this skill.

### Todo list

- Reproduce
- Fix core
- Regression test
- Verify on lab/VPS

### Prevent recurrence

Edit only the skill `classify.json`. Do not hand-edit the bake copy.

## 21:10 — Model-router config folder was a second SoT

### Symptom

Operators edited `architect/models/model-router/config/*.json` while skills/docs pointed elsewhere; classify/outbound/web-search combo drifted after updates.

### Root cause

Router prompts lived under model-router bake config instead of Hermes skills.

### AI decision

Backfilled from legacy log. At fix time: prioritize durable core change over VPS hotpatch; align classify/skills when intent routing was involved.

### Fix (core)

SoT: `skills/classify`, `skills/outbound`, `skills/web-search/web-search-combo.json`. Sync bake on update. Drop unused `heuristic.json` (never loaded).

### Todo list

- Reproduce
- Fix core
- Regression test
- Verify on lab/VPS

### Prevent recurrence

Edit skill JSON only; never hand-edit bake copies. Do not reintroduce keyword NLU files.
