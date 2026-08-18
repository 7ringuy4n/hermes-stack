# Ops history — issues and fixes

English log of **problems we actually hit** (lab and product) and **how they were fixed**. Newest first.

This is the operator-facing companion to [`docs/CHANGELOG.md`](../docs/CHANGELOG.md). Changelog answers “what changed.” This file answers “what broke, why, and how to stop it happening again.”

**Do not put hostnames, IPs, accounts, or secrets here.**

---

## How to add an entry

When you hit a real failure (deploy, cron, Zalo, routers, permissions):

1. Add a section at the **top** with timestamp `YYYY-MM-DD HH:MM +07`.
2. Fill **Symptom**, **Root cause**, **Fix**, **Prevent recurrence**.
3. Mirror a short bullet in `docs/CHANGELOG.md`.
4. Prefer a reusable config/skill/queue fix over a one-off keyword patch.

---

## 2026-08-18 19:14 +07 — promote v0.5.7 via MR (not develop→main)

### Symptom

Need the lịch/cadence/media-ack work on both integration and production branches without a direct develop→main merge.

### Root cause

Repo rule is feature → develop → release/* → main, each via GitHub PR.

### Fix

MR #42 `fix/zalo/workflow-wait-turn` → `develop`, then `release/v0.5.7` cherry-pick → MR #43 → `main`, then sync `main` back into `develop`.

### Prevent recurrence

Do not merge `develop` straight into `main`. Empty leftover lab lịch before rolling deploy so migrate does not recreate them.

---

## 2026-08-18 18:57 +07 — leftover daily lịch would have been re-imported by migrate

### Symptom

Lab clock-only lịch kept firing every day. A rolling deploy runs `migrate_jobs_to_workflow.py`, which upserts every `jobs.json` user row back into workflow.

### Root cause

Emptying Postgres schedules alone is not enough if `jobs.json` still holds the 17:24 Hermes cron.

### Fix

Delete workflow schedule rows **and** set `jobs.json` jobs to `[]` before migrate. Confirm `schedules_left=0` and `cron_n=0` after deploy.

### Prevent recurrence

Do not leave lab lịch enabled. After a lab, delete workflow rows and empty `jobs.json` before the next rolling deploy.

---

## 2026-08-18 18:45 +07 — lịch web-search dumped process text; fuel “images” with no OCR

### Symptom

Zalo received step chatter (“Now I have the Petrolimex page…”, “Let me get a Python environment with PIL”, session-restored, “Đã xong”, “Mình đang lấy giá xăng…”). Fuel/weather image jobs still hit `web_extract` on SearXNG. Dispatcher `keys.tavily` was false.

### Root cause

- Tavily key was empty, so extract could not use Tavily and Hermes fell back to SearXNG extract (unsupported).
- Skills told the model to send `Đã xong.` / `Done.` after files; adapter also announced that line.
- Clock-only `đặt lịch lúc HH:MM` was stored as a **daily** cron, so leftover lists kept firing.
- Agent narrated scrape/OCR/PIL instead of OCR service + dispatcher image.

### Fix (source)

- Cadence: once / daily / weekly / monthly / yearly; once deletes after fire.
- Remove media done-ack (ux.json, adapter, skills, SOUL).
- web-search: dispatcher extract + OCR on page images; drop process narration on Zalo.

### Prevent recurrence

Clock-only lịch must not become daily. Image facts on a web page → OCR, then generate — never PIL overlay chatter. `keys.tavily` on dispatcher health must be true when WEB_BACKENDS includes tavily.

---

## 2026-08-18 18:28 +07 — Traefik 503 during Hermes restart (false deploy fail)

### Symptom

Rolling feature deploy marked Hermes→9router fail because Traefik `/health` returned 503 while replicas had been up only a few seconds.

### Root cause

Traefik still had Hermes backends draining. 9router itself was up (`/` 307, `/v1/models` 401 without a key). A second probe ~1 minute later: Traefik 200, gateway 200, Hermes models 200, Zalo SSE connected.

### Fix

Retry Traefik health after Hermes restart. Overlay repo skills onto replica copies so image-gen updates are live.

### Prevent recurrence

Do not treat a 503 in the first seconds after `docker restart` Hermes as a downed edge. Do not run bare `compose up` (that still strips host ports / scale).

---

## 2026-08-18 18:22 +07 — skill updates did not reach Hermes replicas

### Symptom

Repo `image-gen/SKILL.md` was synced, but the live job still used `web_extract` and sent scrape chatter.

### Root cause

Each replica uses a writable **copy** of skills (the bind mount is `:ro`). The entrypoint merged with `cp -n`, so existing `SKILL.md` files were never overwritten.

### Fix

Overlay repo skills onto the replica copy (`cp -a` without `-n`). Keep replica-only skills. Rolling deploy also copies before restart and verifies the no-scrape wording.

### Prevent recurrence

After a skill edit, confirm the replica path `replicas/<id>/skills/<name>/SKILL.md` matches the repo, not only `/opt/assistant/hermes/main/skills`.

---

## 2026-08-18 18:16 +07 — lịch “vẽ hình” replied with a release-page scrape, no image

### Symptom

A 4-item lịch (hello, HCMC weather image, fuel, current weather) sent text like “The latest release is dated 13/8/2026. Let me fetch the page and extract image URLs” and **no image file**.

### Root cause

The image job called `web_extract` (SearXNG cannot extract). Native `image_generation` was off. The model treated “vẽ hình” as “find pictures on the web” instead of dispatcher `/v1/image`. Step chatter leaked to Zalo (`media-out` was ignored).

Same run: leftover daily lịch still enabled; Hermes cron `2864b2a9c2b4` (`no_agent=false`, isolated `::job::` origin) still scheduled for 17:24 tomorrow.

### Fix (source)

- `image-gen` skill: never search/extract image URLs; generate via dispatcher.
- Session-interrupt user line → `ux.json` `session.interrupted`.

### Prevent recurrence

If an image job’s Hermes log has `web_extract` and no `POST /v1/image`, it is this class of bug. Do not scrape GitHub/news “latest release” pages for drawings.

---

## 2026-08-18 18:10 +07 — hardcoded Vietnamese “Đã lưu lịch” on schedule save

### Symptom

Confirming a lịch always sent one Vietnamese sentence, even when the user wrote English (or another language).

### Root cause

The adapter hardcoded the announce string in Python.

### Fix

- Copy in `hermes/main/messages/ux.json` → `schedule.saved` as a locale map.
- `ux_copy.reply_lang` picks `vi` / `en` / … from Unicode script in the user text.
- Env `ZALO_SCHEDULE_SAVED_MSG` forces one string if an operator wants that.

### Prevent recurrence

Do not put user-facing sentences in `adapter.py`. Add locales in `ux.json`. Python fallback must stay **English**.

---

## 2026-08-18 16:50 +07 — lab: English four-item lịch (hello + image + fuel + video)

### Symptom

Need a repeatable lab for one English schedule with **four independent jobs** (hello, HCMC weather image, Vietnamese fuel prices, HCMC weather video). Earlier numbered lịch often delivered fewer Zalo messages than jobs.

### Root cause

Same engine as the 15:23 / 15:50 misses: numbered items must become **N jobs** and **N deliveries**, not one LLM prompt.

### Fix

- Case `test/cases/25-zalo-special-four.md`.
- Lab upserts the lịch for the current Zalo login thread a few minutes ahead and watches the plugin for four replies.
- Units: `plan_instructions` splits the English list; ingest keeps the daily English list whole.

### Prevent recurrence

Run case 25 as its **own process**. Do not mix with cases 12–14 (quota) in the same runner.

---

## 2026-08-18 16:40 +07 — parallel numbered jobs still merged on one Hermes session

### Symptom

Policy required **N jobs, N Zalo replies**. Sequential wait helped, but a same-thread burst still **pending-merged** parallel `handle_message` calls. A four-item list could still collapse to two replies.

### Root cause

Hermes sessions are per chat. Two workers calling `handle_message` on the same `thread_id` share one gateway session, so later jobs look like follow-ups of the first turn.

### Fix

- Numbered Zalo lists (immediate and lịch) create **independent** jobs (`sequential=false`).
- Worker claims up to `ZALO_WORKFLOW_PARALLEL` (default **4**) at once.
- Each job uses an isolated Hermes session `{thread}::job::{job_id}`. Sends remap to the real thread under a per-thread lock.
- Job waits until **its** session is idle before complete (`ZALO_WORKFLOW_TURN_TIMEOUT_S`).
- Image-gen skill: native Hermes `image_generation` may be off (no cloud key). Always use dispatcher `POST /v1/image`.

### Prevent recurrence

Do not call `handle_message` in parallel on the **same** Hermes session. Isolation is mandatory for parallel Zalo jobs.

---

## 2026-08-18 16:25 +07 — policy: numbered list must be N jobs and N deliveries

### Symptom

Operators expected four numbered tasks to produce four Zalo messages. The old “one cron payload, one LLM turn” design produced one (or two) combined replies.

### Root cause

A lịch is only a **clock**. The body is a list of instructions. Delivery must not wait for an aggregator.

### Fix

- Immediate and scheduled numbered lists share the same job engine.
- At tick time: **one job per item**.
- Each job may send its own reply (text and/or file). No aggregator bubble.

### Prevent recurrence

Documented in `architect/workflow/README.md`. If a lab sees “4 jobs, 1 message,” treat it as a delivery/session bug, not “the model summarized.”

---

## 2026-08-18 16:20 +07 — sequential schedule jobs completed before Hermes finished the turn

### Symptom

A 4-item lịch often delivered **only the first one or two** Zalo replies. Later items looked queued then vanished. Overlapping empty turns poisoned the transcript.

### Root cause

Hermes `handle_message` **returns immediately** while the agent keeps running in the background. The Zalo workflow worker marked the job complete after the ~8s late-file grace, then claimed the next item. Those later items became pending follow-ups on the **same** session.

The late-file waiter also marked a part “delivered” when **no file** was sent, so the next item started on a false signal.

### Fix

- Worker waits until that thread’s gateway session is **idle** (and heartbeats the job lease) before late-file sweep and `complete`.
- Timeout: `ZALO_WORKFLOW_TURN_TIMEOUT_S` (default **420** seconds).
- A timed-out item is still completed-with-error so the rest of the list can run.
- Late-file wait no longer marks delivered when nothing was sent.
- Unit: `test/scripts/workflow_turn_wait_unit.py`.

### Prevent recurrence

Never `complete_job` on a Zalo `execute=hermes` turn until the session is idle or the timeout fires. Do not treat “no file after 8s” as success for the next numbered item.

---

## 2026-08-18 15:27 +07 — one numbered job exception blocked the rest of the lịch

### Symptom

Cron at **15:23** (hello + HCMC weather image + fuel prices + current weather) sent **only the first message**. Items 2–4 never arrived.

### Root cause

Workflow jobs for a numbered list were **sequential** (job N depends on job N−1 completing). The Zalo worker called `fail_job(...)` when `handle_message` threw. Failed jobs do **not** unlock children, so the chain stopped after item 1.

Typical triggers: image-gen / media-out error, 9router stream abort, read-only skills/media, or a timeout inside item 2.

### Fix

- On worker exception: send the short user line `Phiên làm việc bị gián đạn…` (best effort), then `complete_job` with `{ok: false, error: …}` so dependents unlock.
- Fall back to `fail_job` only if complete itself fails.
- File: `hermes/main/plugins/zalo/adapter.py` (`_as_workflow_worker`).

### Prevent recurrence

Sequential lists must treat “this item failed” as **done for dependency purposes**, unless you intentionally want a hard stop. Prefer isolated parallel jobs (16:40 entry) so one crash cannot stall the others.

---

## 2026-08-18 15:07 +07 — `deploy_high.py` crashed locally before any remote destroy

### Symptom

Lab High destroy/redeploy aborted immediately with:

```text
NameError: name 'n' is not defined
```

at `print(f"HERMES_JOBS_BEFORE={n}")` / `HERMES_JOBS_AFTER={n}` inside `test/scripts/deploy_high.py`.

### Root cause

The remote bash script is built with a Python **f-string**. `{n}` in the embedded `python3 - <<'PY'` heredoc was interpolated **locally** (where `n` does not exist), not on the VPS.

### Fix

Print with concatenation:

```python
print("HERMES_JOBS_BEFORE=" + str(n))
print("HERMES_JOBS_AFTER=" + str(n))
```

### Prevent recurrence

Inside `rf""" ... """` remote scripts, never write `{var}` unless it is a **local** format field (`{REMOTE}`, `{zalo}`, …). Remote Python braces must be doubled (`{{` / `}}`) or avoided.

---

## 2026-08-18 15:05 +07 — Hermes cron “readonly database” + skills copy `[Errno 30]`

### Symptom

- Hermes cron could not `INSERT INTO executions` → `sqlite3.OperationalError: attempt to write a readonly database`.
- Replica startup: `Failed to copy … [Errno 30] Read-only file system: '.../replicas/<id>/skills/creative'`.
- Scheduled image jobs could not write `media/out`.
- User-facing: lịch confirmed, then no dispatch / no media.

### Root cause

1. **`executions.db`** on the shared cron dir was owned by **root** `644`. The scheduler runs as Hermes uid **1000**.
2. **`replicas/<id>/skills`** was a **symlink** to `/opt/data/skills`, which is a **`:ro` bind mount** from the repo. Writes follow the symlink → read-only FS.
3. **`media/out`** was not group-writable by uid 1000.

`/opt/data` itself is `rw`. The trap is the extra `:ro` mounts and the symlink.

### Fix

- `chown 1000:1000` + `chmod 664` on `executions.db*` (and sibling cron files).
- `hermes-replica-entry.sh`: **copy** skills into the replica home instead of `ln -s` (merge with `cp -a -n` on later boots). Remove stale skill symlinks before restart.
- `chown -R 1000:1000` + `chmod -R 775` on `media/out`.
- Verify from inside a replica: SQLite write test + `mkdir` under replica `skills/` + `touch` under `media/out`.

### Prevent recurrence

- After any destroy/recreate, check cron file **owner**, not only that the file exists.
- Never symlink replica-writable trees onto `:ro` binds (`skills`, `plugins`, `messages`).
- Compose warnings “refusing chown through symlinked path” are a hint this class of bug is back.

---

## 2026-08-18 15:00 +07 — 9router `ResponseAborted` / Zalo `[response interrupted]`

### Symptom

Zalo showed `[response interrupted]` even when schedule **detection** succeeded (`Đã lưu lịch`). 9router logs: many `DISCONNECT: ResponseAborted` on free OpenCode models (5–13s each), then fallback to the next model.

### Root cause

Hermes **client** aborts the stream and tries the next combo member. That is the designed fallback loop. When **all** members abort, the user sees interrupt copy.

Contributing factors:

- User sending a new message before the previous turn finished (busy/interrupt path).
- Upstream free-model latency / provider drops (not a local 9router crash; process stayed `running`, restart count 0).
- Parallel numbered jobs colliding on one session (see 16:20 / 16:40).

This is **not** the same bug as “cron did not tick.” Workflow logs still showed jobs created.

### Fix

- Restart 9router only to clear stale sockets (does not fix provider aborts).
- Isolate jobs + wait for turn idle so Hermes does not abort because a second job started mid-stream.
- Do not treat 9router UI `/health` 404 as down; `/` 307 and `/v1/models` 401 still mean the process is up.

### Prevent recurrence

If interrupt copy appears **and** `workflow job done` is missing, inspect session isolation first. If jobs complete but the model stream dies, it is upstream quota/latency — recreate router keys when the lab hits quota (cases 12–14).

---

## 2026-08-18 13:55 +07 — daily lịch at 13:54 GMT+7 did not fire the same minute it was saved

### Symptom

User saved `13:54 GMT+7` at about `13:54:20`. Confirmation returned, but **today’s** run never happened. Next fire jumped to **tomorrow**.

### Root cause

`next_daily_cron` used `if candidate <= local: +1 day`. Same-minute create is already “past” by a few seconds, so `next_run_at` skipped today.

A second bug: `claim(execute=…)` returned empty when the **first** dequeued job had a different execute type, so Zalo `hermes` and Hermes `hermes_http` **starved** each other on one Valkey list.

A third bug: clock extract preferred `6:00 AM` **inside item 1** of the payload over `lúc 13:54`.

### Fix

- `next_daily_cron(..., grace_s=120)`: if now is 0–120s after the clock, keep **today**.
- Re-upsert of the same clock keeps a **past** `next_run_at` so catch-up still fires.
- Ticker catch-up: if `next_run_at` already jumped to tomorrow and today has not fired, still fire today’s slot (within grace).
- `claim`: skip non-matching execute types and re-enqueue; do not return empty.
- Clock extract prefers `lúc` / `at` / `vào` + `HH:MM`.

### Prevent recurrence

Units in `workflow_schedule_concurrency_unit.py` and `workflow_unit.py` (`test_same_minute_grace_1354`). Never take the first `HH:MM` in the body as the schedule clock.

---

## 2026-08-18 13:10 +07 — multi-request and cron depended on one LLM turn

### Symptom

A numbered list in one Zalo bubble (or one lịch payload) was one Hermes prompt. The model typically answered **only the last item** (fuel) or **only the first**. Restart/crash lost in-flight work.

### Root cause

No durable job graph. Cron in Hermes `jobs.json` ran **one agent prompt**. Immediate lists were split in-process only.

### Fix

- New **workflow** service (`:8108`): Postgres canonical state, Valkey delivery, outbox, leases, idempotency.
- At ingest: schedule-shaped text stays **one schedule**. At **tick**: explode into jobs (`plan_instructions`).
- Hermes user lịch is `no_agent` so the old ticker does not double-run the same prompt.
- Zalo adapter submits compound lists and schedule text; workers claim `execute=hermes`.

### Prevent recurrence

Do not add new “one prompt does the whole list” paths. Lists go through workflow jobs.

---

## 2026-08-18 12:45 +07 — one-line `1. 2. 3.` only ran the last item

### Symptom

`Thực hiện: 1. … 2. … 3. …` flattened onto one line by Zalo. Only the last item (xăng) ran.

### Root cause

Splitter only matched **line-start** indexes (`^1.`), not inline `1. … 2. …`.

### Fix

- `_inline_numbered_bodies` in `multi_request.py`.
- Wrap each part: “chỉ làm đúng việc này.” Unique part message ids (`:part2`, …).

### Prevent recurrence

Unit fixture: newline list **and** one-line list in `multi_request_unit.py`.

---

## 2026-08-18 12:40 +07 — `--timer` vs `--time`; list showed raw cron objects

### Symptom

`--timer 12:35` was ignored or treated unlike `--time`. Admin list dumped a Hermes schedule dict instead of `name @ HH:MM`. A payload that was only `timer HH:MM` was stored as if it were a real task.

### Fix

- `--timer` alias of `--time`.
- Human label `buoi-sang-hcm @ 12:35`.
- Clock-only prompt is not a task; hint to set nội dung with `update … :`.
- Clock change clears `next_run_at` so Hermes recomputes.

---

## 2026-08-18 12:05 +07 — compound autosend window too short; `jobs.json` unreadable by Hermes

### Symptom

Image arrived after text send; next compound part started too early or waited 180s. Hermes ticker could not update `last_run` because zalo-api wrote `jobs.json` as **root `0600`**.

### Fix

- Autosend window = **whole compound sequence**.
- After each turn, short late sweep for a file that landed as the model finished.
- `jobs.json` `0664`, owner uid 1000. Replica empty file also `0664`.

### Prevent recurrence

After any zalo-api write of cron files, assert mode and uid (deploy scripts already chmod/chown).

---

## 2026-08-18 11:20 +07 — `hằng ngày` list split into parallel crons; colon update dropped the numbered body

### Symptom

`hằng ngày` + `06:00 GMT+7` numbered list became **several** schedules at the same clock → busy-interrupt and dropped items. `!zalo schedule update Tên : 1. … 2. …` did not keep the list whole.

### Fix

- Keep-whole markers include `hằng ngày`, `thức dậy`, `GMT+7`, `đặt lịch`, …
- Numbered list + clock hint also stays one lịch even if a spelling is missing.
- Update parser: index / name / `:` / `--` payload.
- `deliver: origin` so results go to the chat that asked.

---

## 2026-08-18 10:45 +07 — destroy profile wiped lịch

### Symptom

After `run.sh destroy` + High up, user schedules were gone. `hermes cron list` looked empty.

### Root cause

Jobs lived in `replicas/<container-id>/cron/jobs.json`. Destroy creates **new** container ids. Backup excluded `./replicas`. Restore never re-applied jobs. Compose `HERMES_HOME=/opt/data` pointed at an empty tree.

### Fix

- Shared store: `$HERMES_DATA_DIR/cron/jobs.json`.
- `hermes-cron-share.sh` promotes the newest replica copy.
- Zalo-owner replica ticks the shared dir; other replicas keep an empty local file (no double-run).
- Backup: `hermes-jobs.json` + `hermes-cron.tgz`.
- `deploy_high.py` snapshots cron **before** destroy and verifies job count after up.

### Prevent recurrence

Never store durable lịch only under `replicas/<id>/`. Always snapshot cron before destroy. Verify `HERMES_JOBS_AFTER` ≠ empty when `HERMES_JOBS_BEFORE` > 0.

---

## 2026-08-18 10:15 +07 — Notify alerts logged `zalo: false` with no thread env

### Symptom

`ENABLE_NOTIFY=1` and a sole Zalo admin existed, but alerts never reached Zalo unless `NOTIFY_ZALO_THREAD` was set.

### Fix

Dest order: request thread → optional `NOTIFY_ZALO_THREAD` → admin file → `ZALO_ADMIN_USERS`. Re-read the admin file on each send.

---

## 2026-08-18 09:10 +07 — `Đã xong.` between compound parts

### Symptom

Image part sent the file **and** `Đã xong.`, then the text part ran. Users thought the sequence was finished.

### Fix

Media-out success line is **deferred until after the last queued part**. Copy: `messages/ux.json` → `media.done`.

---

## 2026-08-18 08:45 +07 — overlapping Zalo turns injected busy / interrupt UX

### Symptom

Users saw:

```text
⚡ Interrupting current task. I'll respond to your message shortly.
💡 First-time tip — … /busy queue …
```

Rate-limited follow-ups were **dropped**.

### Root cause

Upstream Hermes injects interrupt copy when a new turn starts mid-run. Compound `handle_message` without waiting (or several crons at the same clock) triggered it. Rate-limit path discarded the extra message.

### Fix

- Drop busy/interrupt `/busy` copy on Zalo (`gateway_noise.py`).
- Valkey inbound FIFO per thread; drain **one** Hermes turn at a time.
- Rate-limit: tell the user **once**, **keep** the message, process later.
- Cap `ZALO_INBOUND_QUEUE_MAX` (later default **3**).
- Valkey down → fail-open sequential in-process turns.

### Prevent recurrence

Do not start a second `handle_message` on a thread that is still running unless jobs use isolated sessions (16:40).

---

## 2026-08-18 08:10 +07 — numbered style `1 vẽ` / `2.Sau đó` plus media-out dropped request 2

### Symptom

Live Zalo: `yêu cầu:` + `1 vẽ…` + `2.Sau đó …` ran **image + fuel in one turn**. After the file, media-out “one short line, no recap” dropped request 2. This was **not** the summarization skill.

### Fix

Splitter accepts `1 task` / `2.Sau đó` (indexes 1–20, must include 1 and 2). Media-out applies **per turn after split**.

---

## 2026-08-18 07:15 +07 — daily 06:00 scheduled for tomorrow when created at 05:58

### Symptom

At 05:58 local, “daily 06:00” confirmed as **tomorrow**.

### Root cause

Comparison used UTC or already-passed logic without “still ahead today.”

### Fix

`architect/tools/schedule_tz.py` — `next_daily_run(hour, minute)`: if the local clock is still ahead, schedule **today**. Skill `core/scheduling` + zalo-api policy. Later reused by workflow `next_daily_cron` grace.

---

## 2026-08-17 17:55 +07 — destroy / profile switch without a verified backup

### Symptom

A failed destroy left the lab with no rollback stamp.

### Fix

`run.sh destroy`, `switch-profile`, `add-components`, and `update` run `backup` then `verify` and **abort** if either fails. Lab deploy scripts must not swallow destroy failure with `|| true`.

---

## 2026-08-17 12:05 +07 — post-ready-learn probed missing Hermes dashboard port on High

### Symptom

Hermes×2 has **no** host `:29119`. post-ready-learn and stack-watch treated Hermes as down.

### Fix

When `HERMES_REPLICAS ≠ 1`, probe **Traefik / API Gateway** `/health` (root `/` is 404 by design).

---

## 2026-08-16 19:40 +07 — stack-watch collapsed Hermes×2 → ×1 every ~2 minutes

### Symptom

Dashboard: “Chat connection interrupted. Reconnecting…”. Zalo SSE dropped. Hermes host ports (`:29119` / `:28642`) vanished on a timer.

### Root cause

`stack-watch` ran `docker compose up` **without** hostports/edge overlays and **without** `--scale hermes=$HERMES_REPLICAS`, so every ~2 minutes it stripped scaled Hermes and edge.

### Fix

- `compose up` keeps `--scale hermes=$HERMES_REPLICAS`.
- Skip Grafana probe when monitor is off; skip host `:29119` when replicas ≠ 1.
- Default `STACK_WATCH_RESTART_HERMES=0` so probe-fail does not bounce healthy replicas.
- Boot grace + exponential backoff (later 90s→3600s) so a bad probe cannot restart-storm.

### Prevent recurrence

Any host `compose up` from watch/heal **must** pass the same `-f` overlays and `--profile` flags as `run.sh`. Caution in operator rules: full PowerShell deploy can buffer-hang; prefer Python SSH helpers.

---

## 2026-08-16 19:50 +07 — two Hermes replicas both attached Zalo SSE

### Symptom

`sseClients=0` or duplicate sessions after scale-up / restore. Bot silent after DR.

### Root cause

Bare Compose DNS `hermes` matched every replica. Empty `ZALO_PLUGIN_URL` fell back to a default bridge URL. Stale `zalo_owner` file blocked reclaim when the previous container id was gone. s6 restored env after the entrypoint cleared it.

### Fix

- Only the elected owner replica keeps Zalo URL; others clear it.
- Adapter connects only if hostname matches `zalo_owner`.
- Explicit empty env does **not** default to a bridge URL.
- Entrypoint scrubs unreachable owners; adapter can reclaim when owner DNS is gone.
- Restore clears the lock and runs `heal-zalo-sse.sh`. Backup excludes `zalo_owner*`.

---

## 2026-08-16 08:15 +07 — zalo-watch + stack-watch Hermes restart storm

### Symptom

Hours of Hermes restart loops. Zalo SSE never stable.

### Root cause

`zalo-watch` restarted Hermes when `sseClients==0` (miss limit too low). `stack-watch` also bounced Hermes on probe fail / post-boot flicker.

### Fix

- Default `ZALO_WATCH_RESTART_HERMES=0` (bridge-only on sse=0).
- SSE miss ≥ 15; cooldown 1800s.
- `STACK_WATCH_RESTART_HERMES=0`; boot grace 600s; heal 9router/dispatcher without thrashing Hermes.

---

## 2026-08-15 16:50 +07 — skill learn failed when 9router had no embedding models

### Symptom

Cases 12–14: learn/scan produced 0 vectors or quota errors.

### Fix

Embedding service uses local ONNX `BAAI/bge-small-en-v1.5` (fastembed) when 9Router has no embedding credentials. Ingest recreates `knowledge_chunks` if vector size changes. If the lab still hits **chat** quota, recreate router keys (operator caution).

---

## 2026-08-15 14:20 +07 — first Low deploy: disk full blocked Hermes extract

### Symptom

Hermes image extract failed on a small root volume.

### Fix

Extend the data LV before extract; prune builder/image after first-setup. See `docs/HARDWARE.md`.

---

## Windows / PowerShell pitfalls (recurring)

These are **local runner** issues, not product bugs. They waste deploy time if forgotten.

| When | What happens | What to do |
|------|----------------|------------|
| 2026-08-18 (repeated) | PowerShell treats `&&` / `||` as parse errors | Use `;` between commands, or put `|| true` **inside** the remote bash script only |
| 2026-08-18 | `interrupt` in a double-quoted `grep -iE` string is parsed as a cmdlet | Put the SSH/Python in a `.py` file; do not embed bash `grep` in PowerShell `-c` strings |
| 2026-08-18 | `python3 - <<'PY'` heredoc in an f-string interpolates `{n}` | Concatenate prints; double `{{` `}}` for Docker Go templates in the same f-string (`{{{{.Names}}}}`) |
| Operator caution | Full deploy via a huge PowerShell script **buffer-hangs** | Use `test/scripts/deploy_high.py` / `deploy_feature_vps.py` (Paramiko + streamed PTY) |
| Git commit from PowerShell | `$(cat <<'EOF'` is not valid | Write the message to a UTF-8 temp file and `git commit -F` |

---

## Git promote (2026-08-18 15:54 +07)

### Symptom

Request “create MR then merge to develop **and** main” while sitting on `develop` with mixed temp files.

### Root cause

[`docs/GIT.md`](../docs/GIT.md): **never** merge `develop` straight into `main`. Feature/fix → `develop`; `release/*` → `main`. Temp reports / `_tmp_*` probes must not ship.

### Fix

1. Branch `fix/zalo/workflow-schedule-reliability` from current work.
2. Stage product files only (workflow service, Zalo adapter, compose, docs, unit/VPS scripts). Leave `test/reports/**` and `test/scripts/_tmp_*`.
3. Fetch + rebase onto `origin/develop`.
4. PR [#40](https://github.com/7ringuy4n/hermes-stack/pull/40) → merge into `develop`.
5. `release/v0.5.6` from `origin/main`, cherry-pick the fix commit, PR [#41](https://github.com/7ringuy4n/hermes-stack/pull/41) → merge into `main`.
6. Fast-forward local `develop` / `main`; delete local fix/release branches.

### Prevent recurrence

Do not `gh pr create --base main` from `develop`. Do not commit `_tmp_` probes.

---

## Quick index (symptom → section)

| You saw | Go to |
|---------|--------|
| Lịch saved, no run today (same minute) | 13:55 same-minute grace |
| Lịch saved, only first Zalo message | 15:27 fail_job; 16:20 turn wait; 16:40 session isolation |
| `[response interrupted]` | 15:00 9router abort |
| `readonly database` / Errno 30 skills | 15:05 permissions |
| `NameError: n` in deploy_high | 15:07 f-string |
| Schedules gone after destroy | 10:45 shared cron |
| Busy / `/busy` tip on Zalo | 08:45 FIFO + noise filter |
| Only last numbered item answered | 12:45 inline split |
| Hermes ports vanish every ~2 min | 16 Aug stack-watch scale |
| Dual Zalo SSE / silent bot after restore | 16 Aug Zalo owner lock |
| Skill learn empty / embedding | 15 Aug ONNX fallback |
