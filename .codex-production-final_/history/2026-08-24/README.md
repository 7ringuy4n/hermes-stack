# 2026-08-24

19 incident(s). Times are UTC+7.

## 07:30 — Trace LC schedule miss + durable PG/claim/context foundations

### Symptom

User asked to schedule into Zalo “LC group”; bot later claimed group missing, only “Home” connected, and a 60-minute confirmation window expired — while earlier `!zalo allow` + schedule fire had already delivered into LC.

### Root cause

1. First attempt ran before `!zalo allow` (allowlist empty) — correct miss.
2. Hermes agent path invented a confirmation wait / Home substitution instead of fail-fast allow/refresh guidance and durable thread lookup.
3. Claim stored only admin `user_id`; channel registry was JSON-primary; schedules still SQLite — incomplete SoT for identity vs delivery.

### AI decision

Backfilled from legacy log. At fix time: prioritize durable core change over VPS hotpatch; align classify/skills when intent routing was involved.

### Fix (core)

PG Zalo normalized tables + claims; zalo-context skill/API; claim persists `claimed_thread_id`; schedule-worker Postgres path with execution/correlation ids; security message-check before Hermes; scoped `run.sh update`; media conditional routing skill text.

### Todo list

- Reproduce
- Fix core
- Regression test
- Verify on lab/VPS

### Prevent recurrence

Always resolve named groups via zalo-context/PG before schedule/create; never swap `user_id`↔`thread_id`; never invent confirmation waits.

## 08:00 — Env-file probe answered with path listing

### Symptom

User asked whether the server stores environment files; bot confirmed existence and listed `.env`, `.env.openbao`, and backup `profile-options.env` paths/sizes.

### Root cause

1. Secret-probe policy did not match Vietnamese “file môi trường” existence phrasing → message reached Hermes.
2. Skills/SOUL forbade scans but not soft “does it exist / is it stored” probes; model enumerated host paths.

### AI decision

Backfilled from legacy log. At fix time: prioritize durable core change over VPS hotpatch; align classify/skills when intent routing was involved.

### Fix (core)

Expand `config/agent/secret-probe.json` (+ gateway copy) for env-file existence phrases; harden classify prompt + SOUL + zalo-channel + safety + ux refuse; remove unused compose `SQLITE_PATH`; document host timezone at first setup; clarify `.env` is gitignored (example only in source).

### Todo list

- Reproduce
- Fix core
- Regression test
- Verify on lab/VPS

### Prevent recurrence

Secret probe must block before LLM; classify/SOUL refuse with one line and no follow-up enumeration menus.

## 08:10 — Quote reply: bot cannot read old message (DM + group)

### Symptom

User replies by quoting an older Zalo message (DM or group); bot answers as if no quoted content was attached (asks what to read / ignores quote).

### Root cause

1. Bridge only forwarded `data.quote`; some reply payloads use `refMsg`/`reference`, or put `uidFrom` without `ownerId` (group reply-to-bot gate misses).
2. Hermes snip returned empty for media quotes without caption/title, and required non-empty user text before injecting `[Quoted message]`.
3. Media-from-quote only matched narrow `chat.photo` / `share.*` prefixes.

### AI decision

Backfilled from legacy log. At fix time: prioritize durable core change over VPS hotpatch; align classify/skills when intent routing was involved.

### Fix (core)

`scripts/main/zalo-bridge/zaloClient.js` quote extract/map + RAW `hasQuote` diagnostics; `attachment.quoted_context_snip` media placeholders; adapter inject + media-from-quote + address fallback.

### Todo list

- Reproduce
- Fix core
- Regression test
- Verify on lab/VPS

### Prevent recurrence

Always log hasQuote on inbound; snip must never drop a present quote object to silent empty when msgType is known.

## 08:20 — Scoped `run.sh update` fails on zalo-api (hermes scale)

### Symptom

`bash run.sh update hermes zalo-api …` stops after hermes with `no such service: hermes: disabled` on `up zalo-api`.

### Root cause

`compose()` always appended `--scale hermes=N` after scoped service names → invalid compose CLI for non-hermes updates.

### AI decision

Backfilled from legacy log. At fix time: prioritize durable core change over VPS hotpatch; align classify/skills when intent routing was involved.

### Fix (core)

Only add `--scale hermes=N` when no explicit services, or `hermes` is among them.

### Todo list

- Reproduce
- Fix core
- Regression test
- Verify on lab/VPS

### Prevent recurrence

Any scoped `compose up <svc>` must not attach unrelated `--scale` targets.

## 08:35 — Restore fails: No such container: redis

### Symptom

`bash run.sh restore <stamp>` → `no such service: redis`, then valkey step `No such container: redis` / `ERROR: valkey ping after restore`. Postgres/qdrant may already have been restored.

### Root cause

Compose renamed Redis → Valkey (`container_name: valkey`). Restore still hardcoded `docker stop|start|exec redis` and `compose up … redis`.

### AI decision

Backfilled from legacy log. At fix time: prioritize durable core change over VPS hotpatch; align classify/skills when intent routing was involved.

### Fix (core)

`architect/backup-restore/lib/backup.sh`: datastore up uses `valkey`; restore resolves container via `assistant_container`; `run.sh` compact pings `valkey`.

### Todo list

- Reproduce
- Fix core
- Regression test
- Verify on lab/VPS

### Prevent recurrence

Never hardcode legacy container name `redis` for stack ops; use `assistant_container` or compose service `valkey`.

## 09:00 — Quote-reply to image: bot sees type=32 only

### Symptom

User quotes an old **photo** and asks "đọc nội dung trong ảnh"; bot says it only received `[quoted message type=32]` with no image.

### Root cause

Zalo sends numeric `msgType=32` for photos. Snip/media-from-quote only matched string types like `chat.photo`.

### AI decision

Backfilled from legacy log. At fix time: prioritize durable core change over VPS hotpatch; align classify/skills when intent routing was involved.

### Fix (core)

`normalize_zalo_msg_type` + `extract_media_from_quote` in attachment; bridge maps numeric types; adapter uses shared helper.

### Todo list

- Reproduce
- Fix core
- Regression test
- Verify on lab/VPS

### Prevent recurrence

Always normalize Zalo numeric msgType before media/quote handling.

## 09:00 — Backup missing OmniRouter combos; OpenBao KV not restored

### Symptom

After restore, OmniRouter combos empty; OpenBao -dev lost API keys (only `.env.openbao` copied back).

### Root cause

Volume backup listed `nine_router_data` but not `omni_router_data`; OpenBao -dev is ephemeral with no KV re-import on restore.

### AI decision

Backfilled from legacy log. At fix time: prioritize durable core change over VPS hotpatch; align classify/skills when intent routing was involved.

### Fix (core)

Backup/restore `omni_router_data`; `restore_openbao_kv.py` imports KV export on restore.

### Todo list

- Reproduce
- Fix core
- Regression test
- Verify on lab/VPS

## 11:20 — Quote-reply photo: only "[quoted image]", no OCR

### Symptom

After type-32 mapping, bot still says it only received `[quoted image]` and asks to send the photo directly. Hermes may also show "Recovered reply — gateway restarted".

### Root cause

Inbound Zalo `TQuote` fields are `cliMsgType` + `attach` (JSON string) + `msg` — not `content`/`href` like a normal message. Media extract looked only at `content`, so no URL → no download/OCR. Gateway watchdog restarts (event-loop hang) caused the recovered-reply banner.

### AI decision

Backfilled from legacy log. At fix time: prioritize durable core change over VPS hotpatch; align classify/skills when intent routing was involved.

### Fix (core)

Bridge merges/parses `attach` into quote content; attachment helpers read `attach`/`hdUrl`/`thumbUrl`/params; RAW logs attach preview.

### Todo list

- Reproduce
- Fix core
- Regression test
- Verify on lab/VPS

### Prevent recurrence

Treat inbound quotes as TQuote shape; never assume Message.content for quoted media.

## 11:40 — Backup should include router combos + OpenBao

### Symptom

Operators expected backup/restore to preserve OmniRouter/9Router combo configuration and OpenBao secrets as first-class components (not only buried in generic volumes / skipped KV import).

### Root cause

Router volumes were mixed into `volumes`; no human-readable combo export. OpenBao KV restore skipped when the -dev container was not yet up.

### AI decision

Backfilled from legacy log. At fix time: prioritize durable core change over VPS hotpatch; align classify/skills when intent routing was involved.

### Fix (core)

Component `routers` (volumes + env.router + combo JSON export); OpenBao restore brings container up then imports KV.

### Todo list

- Reproduce
- Fix core
- Regression test
- Verify on lab/VPS

### Prevent recurrence

Treat routers and OpenBao as named backup components with verify-friendly artifacts.

## 12:05 — Quote fix shipped; zalo-api 500 / missing tables

### Symptom

After quote-photo fix, zalo-api returned 500 on `/v1/zalo/claims/active` (`relation "zalo_claims" does not exist`); Hermes also 404 on invented `/threads/search`, `/context/current`. Quote OCR path itself could extract `params.rawUrl`, but context/claim calls failed.

### Root cause

`zalo_store._ensure()` ran the full multi-statement `SCHEMA` via a single `psycopg` `Connection.execute()` (one command only). Process marked ready while DB still only had legacy tables from restore (`zalo_entities`, `zalo_settings`, `zalo_message_history`) — never creating `zalo_users` / `zalo_threads` / `zalo_group_members` / `zalo_claims`.

### AI decision

Backfilled from legacy log. At fix time: prioritize durable core change over VPS hotpatch; align classify/skills when intent routing was involved.

### Fix (core)

Statement-by-statement SCHEMA apply + required-table verification; startup `ensure_schema(force=True)`; route aliases for common wrong paths; skill documents allowed endpoints only.

### Todo list

- Reproduce
- Fix core
- Regression test
- Verify on lab/VPS

### Prevent recurrence

Never apply multi-statement DDL with one `execute()`; always verify required tables after ensure; re-run schema on every zalo-api startup.

## 13:00 — !zalo list shows LC group but find_thread not_found

### Symptom

`!zalo list` shows allowed group "LC group", but bot/Hermes says "Không tìm thấy nhóm LC Group" and asks for `!zalo allow`/`refresh`. PG had the row in both `zalo_entities` and `zalo_threads`.

### Root cause

`find_thread` appended the same thread twice (normalized table + legacy entities mirror). `len(exact)==2` so it returned `None` instead of the single group.

### AI decision

Backfilled from legacy log. At fix time: prioritize durable core change over VPS hotpatch; align classify/skills when intent routing was involved.

### Fix (core)

Superseded by normalized SoT sync (see 13:05 entry).

### Todo list

- Reproduce
- Fix core
- Regression test
- Verify on lab/VPS

### Prevent recurrence

Any name search merging two stores must dedupe before uniqueness checks.

## 13:05 — find_thread SoT: sync entities → normalized, no dual search

### Symptom

`!zalo list` shows "LC group" but `threads/find` returned not_found.

### Root cause

Dual search in `find_thread` (zalo_threads + zalo_entities) produced duplicate exact matches. Dedupe at search time was a bypass, not a data fix.

### AI decision

Backfilled from legacy log. At fix time: prioritize durable core change over VPS hotpatch; align classify/skills when intent routing was involved.

### Fix (core)

- `sync_normalized_from_entities()` at startup: one-way backfill entities → `zalo_users`/`zalo_threads`; prune denied rows from threads.
- `find_thread` / `get_current_context` query normalized tables only.

### Todo list

- Reproduce
- Fix core
- Regression test
- Verify on lab/VPS

### Prevent recurrence

Compat mirror (`zalo_entities`) feeds normalized SoT on startup; routing APIs never merge two stores at query time.

## 14:30 — SOUL blocked + schedule-worker missing public schema

### Symptom

SOUL.md blocked every turn (`deception_hide`). Schedule-worker PG loop errors every 2s (`relation "schedules" does not exist`). Hermes fell back to inventing outbound endpoint `/v1/zalo/send`.

### Root cause

1. SOUL queue-state rule: "Do not tell the user that a request is queued…" triggered the Hermes `do_not…tell…user` deception scan.
2. SOUL language section missing Spanish/Japanese/English examples; `soul_deception_unit.py` did not cover the 8-word window pattern.
3. `store_pg.go` used unqualified `schedules` table name; after restore, workflow schema `wf.schedules` also present but this worker needs `public.schedules`.

### AI decision

Backfilled from legacy log. At fix time: prioritize durable core change over VPS hotpatch; align classify/skills when intent routing was involved.

### Fix (core)

- SOUL.md queue-state line reworded; language examples added.
- `soul_deception_unit.py` extended with broad window pattern.
- `store_pg.go`: `applyPgSchema()` splits DDL statements, forces `search_path=public`, verifies tables; all DML qualified with `public.` prefix.

### Todo list

- Reproduce
- Fix core
- Regression test
- Verify on lab/VPS

### Prevent recurrence

Any PG-backed worker sharing a DB must qualify schema; SOUL edits must pass `soul_deception_unit.py` before merge.

## 15:00 — Schedule not triggered: relative-time next_run_at + fire_text verbatim

### Symptom

User issued "2 phút nữa gửi vào LC group nội dung: xuân chưa tới…". Bot replied "Đã lưu lịch!" but message never fired. DB row showed `next_run_at = 2026-08-25 14:01` (next day) and `fire_text = "sẽ gửi tin nhắn vào nhóm LC group"` (paraphrase).

### Root cause

1. Classify returned `cron_expr "1 14 * * *"` only, no `next_run_at`. The 14:38 retry stored the row after 14:01; `nextDaily()` in the worker rolled it to next day.
2. Classify paraphrased `instructions[0]` as "sẽ gửi tin nhắn vào nhóm LC group" instead of copying poem verbatim; `fire_text_from_plan` fell back to that paraphrase.

### AI decision

Backfilled from legacy log. At fix time: prioritize durable core change over VPS hotpatch; align classify/skills when intent routing was involved.

### Fix (core)

- `classify.json`: relative-time rule → emit `cron_expr` + `next_run_at` (RFC3339 UTC). Verbatim rule hardened for `nội dung:` body.
- `schedule_client.py`: `next_run_at_from_relative()` parses N phút/giây/giờ offset; used as adapter safety-net.
- `adapter.py`: compute and pass `next_run_at` to worker on schedule create.
- `workflow_client.py`: `create_schedule` accepts `next_run_at`.

### Todo list

- Reproduce
- Fix core
- Regression test
- Verify on lab/VPS

### Prevent recurrence

Any schedule with relative-time ("N phút nữa") must carry explicit `next_run_at`; worker only computes from cron when field absent.

## 15:25 — Cannot delete schedules of other groups from DM

### Symptom

`!zalo schedule list` in DM: empty. `list all` showed jobs. `!zalo schedule delete 1 2 3…` → “Không có lịch số 1 (đang có 0).” Relative create could still fire into LC group while admin could not clear those rows from DM.

### Root cause

1. `jobs_for_thread` only matched `origin.chat_id`/`thread_id` (destination group), not `requester_id`.
2. Admin list merged workflow schedules only — not Go `schedule-worker` (adapter SoT).
3. Digit remove did not fall back to the full visible pool after `list all`.
4. Postgres DELETE still used unqualified `schedules`.

### AI decision

Backfilled from legacy log. At fix time: prioritize durable core change over VPS hotpatch; align classify/skills when intent routing was involved.

### Fix (core)

- Expand thread matching; merge schedule-worker into list; dual-delete worker+workflow; PG-qualified DELETE; classify+adapter delete with `target_channel`; repair classify.json JSON.

### Todo list

- Reproduce
- Fix core
- Regression test
- Verify on lab/VPS

### Prevent recurrence

Any schedule created for a named group must remain listable/deletable from the requester chat and via `remove group <name>`.

## 16:30 — Schedule fire paraphrased; target/list UX unclear

### Symptom

`2 phút nữa gửi vào zalo lc group nội dung: <poem>` saved OK and fired into LC group, but Hermes rewrote the poem. Save ack was only `Đã lưu lịch!` with no `→ nhóm`. List said `lịch chat này` without destination. Classify emitted `target_channel: "zalo lc group"`.

### Root cause

1. Every `scheduleFire` inject was treated as inbound chat → LLM paraphrase.
2. UX/list did not surface destination when requester DM ≠ delivery group.
3. Classify target_channel kept platform noise (`zalo …`).

### AI decision

Backfilled from legacy log. At fix time: prioritize durable core change over VPS hotpatch; align classify/skills when intent routing was involved.

### Fix (core)

- `schedule_delivery` verbatim vs process; adapter verbatim send; worker passes `scheduleDelivery`.
- Classify + `_clean_group_ref` harden display-name targets; save/list show `→ nhóm …`.

### Todo list

- Reproduce
- Fix core
- Regression test
- Verify on lab/VPS

### Prevent recurrence

Send-body schedules must set/store `schedule_delivery=verbatim` and never re-enter Hermes chat on fire.

## 18:15 — Daily 06:00 LC group: no image/skills, !zalo hung

### Symptom

`đặt lịch chạy hằng ngày lúc 06:00 vào Zalo LC Group nội dung: mô tả thơ 4 dòng…, giá xăng E5/E10, thời tiết HCM` → DM photo in 2s, no save ack, `!zalo schedule list all` no reply. Image and admin CLI “not work”.

### Root cause

1. Classify `target_channel` null; `nội dung:` host defaulted **verbatim** on a **task** body.
2. Skills not split (one blob); leftover autosend flushed an old image to DM.
3. Per-thread inbound lock blocked `!zalo` while media/LLM turn was stuck.

### AI decision

Backfilled from legacy log. At fix time: prioritize durable core change over VPS hotpatch; align classify/skills when intent routing was involved.

### Fix (core)

Classify process + split skills + “vào Zalo LC Group”; host never verbatim on task work; admin bypasses inbound lock; cancel late autosend on new user text.

### Todo list

- Reproduce
- Fix core
- Regression test
- Verify on lab/VPS

### Prevent recurrence

Task `nội dung:` (mô tả/cập nhật/dự báo/search/image) must be `schedule_delivery=process` with per-skill instructions. Admin CLI must not share the media-turn lock.

## 19:00 — Daily schedule → poster / no save (heuristic bypass)

### Symptom

`đặt lịch chạy hằng ngày lúc 06:00 vào Zalo LC Group nội dung: mô tả thơ 4 dòng về trời xanh…, giá xăng, thời tiết` → DM photo or silence; schedules table empty.

### Root cause

1. Text-poster shortcut matched before schedule create (`4 dòng` + `anh` substring of `xanh`).
2. Classify early-returned `schedule_heuristic_plan` before LLM — no `target_channel` / `process` / skill split from classify.json.

### AI decision

Backfilled from legacy log. At fix time: prioritize durable core change over VPS hotpatch; align classify/skills when intent routing was involved.

### Fix (core)

- Skip office/poster shortcuts when `looks_schedule_create`; harden `_DRAW` word boundaries.
- Prefer LLM classify; enrich schedule heuristic only as post-LLM fallback; preserve split instructions in `force_timed`; extract `vào Zalo LC Group`.

### Todo list

- Reproduce
- Fix core
- Regression test
- Verify on lab/VPS

### Prevent recurrence

Schedule-create prose must never take Dispatcher media shortcuts. Timed schedules with task `nội dung:` must hit classify.json (or enriched heuristic fallback), not a bare clock stub.

## 19:55 — One schedule became many jobs; LC Group lost; 19:30 weather-only

### Symptom

Daily 06:00 LC Group and once 19:30 (poem + fuel + weather) saved, but list showed several rows at wrong clocks into DM. 19:30 fired weather only.

### Root cause

`hydrate_user_text` prepended prior turns with old HH:MM. `split_compound_requests` counted those clocks and zipped them onto skill instructions, dropping `vào Zalo LC Group`.

### AI decision

Backfilled from legacy log. At fix time: prioritize durable core change over VPS hotpatch; align classify/skills when intent routing was involved.

### Fix (core)

Clock-split and target extract use `strip_prior` current text only. Fan-out requires 2+ run-at clocks on the current bubble. Same clock + several skills = one schedule.

### Todo list

- Reproduce
- Fix core
- Regression test
- Verify on lab/VPS

### Prevent recurrence

Never scan `[Prior conversation]` for schedule clocks or destination. Incidental times in a skill body (`6:00 AM` wakeup text) are not extra jobs.
