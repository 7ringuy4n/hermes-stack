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

## 2026-08-20 20:20 +07 — Legacy check-medium/high wrappers and High deploy PS1

### Symptom

`scripts/main/check-medium.sh` and `check-high.sh` still existed after workers renamed smokes to `check-media` / `check-security`. `Deploy-High.ps1` / `Deploy-V050-Test.ps1` referenced Python entrypoints that are not in `scripts/main`.

### Root cause

Compatibility aliases left after the medium/high → media/security rename; PowerShell deploy wrappers never moved with the Python helpers into `scripts/temp/`.

### Fix

Delete the wrappers and broken PS1 entrypoints. Keep only `check-media.sh` / `check-security.sh` and `run.sh` worker command names.

### Prevent recurrence

Do not add profile-tier smoke aliases. New smoke scripts must use worker names (`media`, `security`, …).

## 2026-08-20 20:10 +07 — Learn pending silent; schedule inject 404; legacy medium/high compose

### Symptom

1. Zalo file/OCR reached ingest pending but admin never got approve (`!zalo learn approve …`).
2. Saved schedules did not run; `schedule-worker` logged `inject 404` / `EOF` on `zalo-proxy:8787/inject-event`.
3. Bridge restarted on `127.0.0.1` only → Docker Hermes SSE / socat could not reach host `:8787`.
4. File pipeline: `Permission denied: /opt/data/media/inbound`.
5. Ops still referenced obsolete `docker-compose.medium.yml` / `high.yml` while runtime used workers + `media`/`security`.

### Root cause

1. Ingest notify posted only to Notification Worker; with Notify inactive, `notified=false` and no bridge fallback; admin file not wired on ingest.
2. Host `hermes-zalo-plugin` lacked `POST /inject-event`; wrong bind after restart dropped Docker reachability.
3. Shared media dirs missing / root-owned so Hermes could not stage inbound files.
4. Duplicate legacy profile overlays drifted from `run.sh` (media/security) and confused backup/stack-watch/first-setup.

### Fix

- Ingest: notify → bridge `/send` fallback to sole admin; compose wires `ZALO_BRIDGE_URL` + `ZALO_ADMIN_USERS_FILE`.
- `patch_zalo_bridge_inject.py`: keep `ZALO_PLUGIN_HOST=0.0.0.0` on restart; document firewall risk (do not publish 8787 publicly; use `ZALO_PLUGIN_TOKEN`).
- `setup-zalo.sh`: create `media/inbound` + `media/out` owned by Hermes UID.
- Remove `docker-compose.medium.yml` / `docker-compose.high.yml`; point backup, stack-watch, and first-setup at `media.yml` / `security.yml` like `run.sh`.

### Prevent recurrence

Do not reintroduce ASSISTANT_PROFILE overlays. Learn pending must never depend on Notify Worker alone. After any bridge restart, verify listen is `0.0.0.0:8787` and `/inject-event` returns `{"ok":true}` from the schedule network.

## 2026-08-20 15:45 +07 — Classify dead-end + schedule by group name

### Symptom

First Zalo message returned “Could not classify this request. Please send it again.”; later messages had no reply. Operator wanted schedules that deliver to a named Zalo group.

### Root cause

1. `model-router` `/v1/classify` returned `ok:false` (`classify_llm_failed`) while chat completions still worked — Zalo adapter **consumed** the turn with an error instead of falling through to Hermes.
2. Channel registry was never populated (`NO_CHANNELS_DIR`), so there was no durable id↔name map for “gửi vào nhóm X”.
3. Schedule `origin` always used the **current** thread, so DM-created schedules could not retarget a group.

### Fix

- Adapter: classify failure → fall through to Hermes (fail-open).
- Persist Zalo users/groups in `channels/registry.json` (inbound upsert, allowlist/admin sync, bridge contacts via `!zalo refresh`).
- On schedule create, resolve `target_channel` / “nhóm …” and rewrite `origin.thread_id` to the group id (requester stays `user_id`).

### Prevent recurrence

Keep Hermes API key + Omni/fallback healthy for classify, but never block interactive chat on classify failure. Seed group names with `!zalo allow` / `!zalo label` / `!zalo refresh` before scheduling by name.

## 2026-08-20 15:25 +07 — Zalo connected but no bot replies (claim + normal chat)

### Symptom

Bridge `loggedIn=true` and `sseClients=1`, but `!zalo claim` / normal Zalo messages got no useful reply.

### Root cause

1. `!zalo claim` had already succeeded (`zalo_admin_users.txt` had a sole admin); re-claim only returns “already has admin”.
2. Hermes `OPENAI_API_KEY` was wired only to `N9ROUTER_API_KEY` while OmniRouter is the default → empty key on Omni-only installs.
3. Model path returned `omni-router:429` (OpenCode Free rate-limit / credential exhaustion) so LLM chat could not complete.

### Fix

- Compose: Hermes `OPENAI_API_KEY=${OMNIROUTER_API_KEY:-${N9ROUTER_API_KEY:-}}`.
- `setup-zalo.sh`: use `ASSISTANT_DATA_DIR` as the host shared Hermes data dir.
- Operator: wait out Omni free-tier cooldown, or enable an alternate provider (9Router / paid fallback).

### Prevent recurrence

Keep Hermes API key wiring aligned with the default router (Omni first). First-setup docs should note OpenCode Free 429 as a no-reply cause distinct from Zalo SSE attach failures.

## 2026-08-20 15:05 +07 — clean-host Zalo bridge logged in but Hermes never attached

### Symptom

On a fresh deploy, QR login succeeded and bridge health showed `loggedIn=true`, but Zalo never interacted with Hermes and bridge health stayed `sseClients=0`.

### Root cause

1. `setup-zalo.sh` skipped plugin activation when `/data/assistant/config.yaml` did not exist yet on a clean host.
2. The old `sed` logic inserted `- zalo-platform` under the first unrelated `enabled:` key instead of the real `plugins:` block.
3. Shared `/data/assistant/.env` could remain root-owned, so Hermes replicas could not read the linked env file.
4. Restart logic targeted `hermes`, but compose used `assistant-hermes-1`.

### Fix

- Seed shared `config.yaml` from the newest live replica when the shared file is missing.
- Rewrite the config edit path to place `zalo-platform` only under the real `plugins:` block and set `gateway.platforms.zalo.enabled: true`.
- Chown shared `.env` to `HERMES_UID:HERMES_GID` before restart.
- Resolve the active Hermes container name before restart.

### Prevent recurrence

Any first-setup channel attach script must work with an empty shared data dir, not assume pre-existing shared config, and must edit structured config blocks by scope rather than matching the first same-named key in the file.

## 2026-08-20 14:20 +07 — clean Ubuntu first setup blocked

### Symptom

Fresh host: `run.sh up` failed missing secrets; `destroy` failed backup (postgres not running); `zalo-api` crash-looped; `setup-zalo` waited forever on 9Router / “Low core”.

### Root cause

1. `.env` not seeded with required `CHANGE_ME_*` / compose required vars.  
2. `do_destroy` always ran `backup_first` even with zero containers.  
3. `zalo-api` Dockerfile omitted `channels_registry.py`.  
4. `setup-zalo.sh` still branched on `ASSISTANT_PROFILE` and waited for 9Router on “low”.

### Fix

- Reorder `.env.example` (secrets first); local `scripts/temp/generate_env_secrets.py`.  
- Skip backup on destroy when no project containers.  
- COPY `channels_registry.py` in zalo-api Dockerfile.  
- `wait_core_ready`: model-router + OmniRouter + zalo-api.  
- Docs/scripts updated to workers + OmniRouter default.

### Prevent recurrence

Keep Dockerfile COPY list in sync with `app.py` imports. First-setup docs must not mention PROFILE/low/9Router-as-default.

---

## 2026-08-20 07:35 +07 — profiles mixed optional workers into core

### Symptom

A fresh Low install started schedule/media/security-shaped services, and classify sent `max_tokens` that truncated long JSON.

### Root cause

`ASSISTANT_PROFILE=low|medium|high` turned whole overlays on. Schedule worker was always-on in compose. Classify always set `max_tokens`.

### Fix

Core is Hermes + Memory + Router Worker + Traefik local + watchdog. Other workers are `ENABLE_*=0` / compose profiles. Lab host `.env` can still turn Zalo/schedule/media on for tests. Classify omits `max_tokens` unless configured.

### Prevent recurrence

Do not map a profile name to a secret bundle of workers. Do not `depends_on` optional workers from Hermes.

---

## 2026-08-20 07:10 +07 — classify hit 9router; workflow owned cron ticks

### Symptom

Numbered once-lịch still classified slowly or failed closed. Schedules could re-enter classify as “đặt lịch” and create another lịch.

### Root cause

Classify/outbound preferred 9router (`prefer_omni=False`) and `model=hermes` chat skipped Omni even when Omni was healthy. Workflow `fire_due` executed cron inside Hermes/workflow instead of a dedicated worker, and fired the wrapper text.

### Fix

OmniRouter is the default general router. A Go SQLite schedule worker stores when-to-run and injects inner `fire_text` back into Hermes. Workflow tick is disabled when `SCHEDULE_URL` is set.

### Prevent recurrence

Do not put a cron ticker in Hermes. Do not fire the original “đặt lịch lúc HH:MM” wrapper. Do not force classify onto 9router when Omni is the default.

---

## 2026-08-19 21:25 +07 — once lịch still classify.failed at 21:21

### Symptom

The same numbered once lịch (21:21) still got the classify.failed Zalo line.

### Root cause

Length-based timeouts were a heuristic, not a fix. Both LLM attempts still ReadTimeout at 14s because the classify system prompt and required task_details JSON were too large for the first provider. Zalo then treated ok=false as “did not understand.”

### Fix

One classify timeout from `classify.json` (no character-count routing). Compact JSON contract; task_details optional. Fail over to the next model-router provider on timeout. Zalo HTTP classify wait is 70s. Workflows remain sequential=false.

### Prevent recurrence

Do not branch classify wait on message length. Make the LLM contract small enough to finish, and fail over providers.

---


### Symptom

A once lịch at 21:13 with four numbered tasks got “please send again” and was not stored.

### Root cause

Classify fail-closed on timeout. The payload was shorter than 400 characters so the LLM hop used the 3s hello budget. Two ReadTimeouts plus a 5s Zalo HTTP client timeout never returned JSON. Workflow then 503’d if anything reached `/v1/schedules`.

### Fix

Length-based classify budget (medium ≥120 chars → 14s, long ≥400 → 18s). HTTP client waits budget + 8s. Hello stays 3s. Workflows remain sequential=false.

### Prevent recurrence

Do not reuse the hello classify timeout for a multi-instruction lịch JSON payload.

---


### Symptom

Numbered cron jobs were forced sequential. Classify timeout was treated as a normal interactive plan. Multi-task schedules had no per-task execution class or dependencies.

### Root cause

Workflow create defaulted sequential=true (and fire_due used sequential when N>1). `/v1/classify` fail-opened to `task_hint=normal`. Schema had only a wrapper `execution_class`.

### Fix

LLM returns `task_details` + 0-based `depends_on`. Schema validation + retry, then unknown/confirm. Workflows stay async; DAG only when depends_on is set. Zalo/gateway announce classify failure instead of running the user text as chat.

### Prevent recurrence

Do not fail-open classify. Do not set sequential=true unless an operator/data dependency requires it. Keep `classify_outbound` on the shared classify_client copies. Never restart hermes-zalo-plugin as uid 0.

---

## 2026-08-19 20:50 +07 — cron briefing returned only one picture

### Symptom

A once lịch at 20:35 asked for a greeting, fuel summary, weather summary, and an HCMC weather image. Zalo received only the picture.

### Root cause

The job stayed on Hermes native cron (`jobs.json` `run_at`, no 5-field `expr`) so migrate skipped it. One agent turn ran the whole prompt and mostly produced media. Classify timeout on long text also fail-opened. Overlay-merge wording in classify.json encouraged collapsing text+image. Root-owned `hcm_weather.jpg` failed chmod for the bridge.

### Fix

Keep numbered text tasks separate from a later draw. Re-classify at tick when stored instructions are a single blob. Sequential workflow jobs. Migrate once `run_at`. Copy media when chmod is denied. Longer classify timeout for long payloads.

### Prevent recurrence

Do not run a numbered briefing as one Hermes cron agent turn. Explode at tick through workflow.

## 2026-08-19 20:25 +07 — hi >15s; cron TypeError vars() on Zalo

### Symptom

A short Zalo ping still took more than 15s. A lịch job posted a Python `vars() argument must have __dict__` crash to the user.

### Root cause

Classify tried every model-router candidate (8s ReadTimeout each). Cron chat completions from 9router were not valid OpenAI message objects, so the Hermes OpenAI client raised TypeError (HTTP None).

### Fix

One classify/outbound provider then fail-open. 3s classify budget. Normalize/sanitize chat JSON in model-router. Rewrite the Python exception protocol line via `ux.json` `schedule.job_failed`. Restart the host bridge with `node server.js` after inject-event is patched — `hermes-zalo-plugin start` overwrites `server.js` and drops the route. Do not restart the bridge as root (cookies live in uid 1000’s home).

### Prevent recurrence

Do not loop every LLM provider on the Fast Dispatcher hop. Do not pass through non-ChatCompletion JSON as HTTP 200. Rolling apply must wait until the bridge is logged in before recreating Hermes, and must not call the plugin CLI `start` after a file patch.

## 2026-08-19 16:55 +07 — hi still 413; Hermes config.yaml still pointed at 9router

### Symptom

After the previous apply, a short Zalo ping still compacted/413'd. Hermes logs showed `base_url=http://9router:20128/v1` even though the container env was model-router.

### Root cause

Shared `/data/assistant/config.yaml` `model.base_url` overrides `OPENAI_BASE_URL`. 9router mapped `hermes` to `gpt-oss-120b` which rejects the tool-heavy payload.

### Fix

Hermes `POST /send` shared the aiohttp session with `GET /events`, so the reply often failed with Server disconnected (~30s after inject). Outbound `_post` now uses its own short-lived session.

### Prevent recurrence

Do not treat compose env as the Hermes LLM URL when `config.yaml` also sets `base_url`.

## 2026-08-19 16:40 +07 — Zalo ping waited on compaction then 413 leak

### Symptom

A short Zalo message waited more than 15s. The user received Hermes compaction / HTTP 413 / session auto-reset text instead of a greeting.

### Root cause

The same Zalo thread reused a huge Hermes `sessions/sessions.json` (Valkey `conversation_active` was empty). Hermes compacted; 9router (Hermes was calling it directly, not model-router) returned 413 from `gpt-oss-120b`. Outbound classify fail-opens to send, so protocol chatter reached Zalo. 9router 429 retries also added seconds.

### Fix

Drop known protocol markers from `ux.json` before classify. Cap Valkey history (`SESSION_MAX_MESSAGES=16`). Delete replica `sessions/sessions.json`. Recreate Hermes so chat uses model-router. Recreate session and reset-all. Overlay `messages/` onto the shared data dir.

### Prevent recurrence

Do not let one social thread accumulate unbounded turns. Protocol status lines stay in editable config, not adapter keyword tables.

## 2026-08-19 16:22 +07 — leftover lab cache key in classify.json

### Symptom

`prompt_rev` was left in product classify config after the High latency lab.

### Root cause

A Docker layer cache-bust was committed as if it were a product field.

### Fix

Removed `prompt_rev`. Rule 41 now in AGENT_RULES / test RULES / agent-ops hard gates.

### Prevent recurrence

After a lab run, strip test-only keys before calling the tree production-ready.

## 2026-08-19 16:00 +07 — classify stuck on 9router; chat >3s

### Symptom

Simple chat p50 ~14s. Classify timed out on 9router while Omni was enabled for general proxy traffic.

### Root cause

`/v1/classify` always posted to 9router. Nvidia 502 overload blocked Fast Dispatcher. Classify also waited 20s before fail-open.

### Fix

Classify/outbound use the same Omni-first candidate list as chat. Classify timeout 8s.

### Prevent recurrence

Case 17 records classify vs text separately. Omni on High lab for general chat.

## 2026-08-19 15:35 +07 — clip capped at 12s; chat waited on classify

### Symptom

Video length was clamped to 12 seconds. Simple Zalo/chat turns waited on classify (90s timeout, 32k max tokens).

### Root cause

Encoder treated a lab-era 12s ceiling as the product max. Classify completion budget was sized like a full chat turn.

### Fix

Caller `seconds` up to 120s. Classify timeout 20s / 1024 tokens / one attempt. Outbound filter 2s then send.

### Prevent recurrence

`video_clip_unit` asserts 45s allowed and 200s capped. Case 17 records classify p50 separately.

---

## 2026-08-19 15:20 +07 — video attach invalid param; overlay clip; lab watch loop

### Symptom

Generated mp4 was on disk; Zalo returned `Tham số không hợp lệ`. Overlay text ran past the image edge. Case 25 watch reprinted the same fail until the SSH wait expired.

### Root cause

zca-js `sendVideo` needs `videoUrl` + `thumbnailUrl` + duration. `sendMessage` attachments do not fill those fields. Encode used jpeg-range `yuvj420p` and `-an`. Overlay drew full-width strings without wrapping. Watch required `attach_mp4>=1` before break.

### Fix

Remux with AAC/yuv420p. Adapter `send_video` uploads thumb + clip then `/api/sendVideo`. Overlay wrap-to-width. Watch exits after four jobs plus four extra polls.

### Prevent recurrence

`overlay_unit` long-line wrap. Case 25 prints `VIDEO_MISSING` and stops.

---

## 2026-08-19 14:45 +07 — replica ImportError + video sent before remux

### Symptom

Hermes replica inbound: `ModuleNotFoundError: gateway_noise`. Case 25 wrote `.zalo.mp4` after Zalo rejected the original mp4.

### Root cause

Hermes loads the adapter as `hermes_plugins.zalo_platform.adapter`; relative imports do not see files in `/opt/data/plugins/zalo`. Autosend attached the encoder mp4 before remux finished.

### Fix

Insert plugin dirs on `sys.path`. Prefer/send remuxed video; remux in the autosend path before `send_video`.

### Prevent recurrence

Rolling apply checks `import classify_client, gateway_noise`. Autosend unit covers `foo.mp4` vs `foo.zalo.mp4`.

---

## 2026-08-19 14:10 +07 — interactive chat waited on media; video send invalid param

### Symptom

Hello and simple chat shared the heavy path. Case 25 wrote `.zalo.mp4` but Zalo rejected the attachment. Replica missing `gateway_noise`.

### Root cause

No Fast Dispatcher lane. Video files could go through `send_image`. Replica `plugins/` dirs were stale.

### Fix

LLM classify returns `execution_class`. Async ACK then workflow. Remux mp4 before send; overlay plugins on rolling apply.

### Prevent recurrence

`llm_classify_unit` asserts hello is interactive and media is async. Lab cases 25/28 require `send-attachment path …mp4`.

---

## 2026-08-19 14:05 +07 — High lab: video not sent; leftover job schedule; replica plugin ImportError

### Symptom

Case 25 four jobs COMPLETED; `.zalo.mp4` written; Zalo invalid-parameter on attach; no `send-attachment path …mp4`. Leftover 07:00 schedule used `thread_id=…::job::…`. hermes-2 logged `No module named 'gateway_noise'`.

### Root cause

Remux retry did not log a successful mp4 send. Destroy restore reapplied an isolated-job schedule. Replica `plugins/` was an old directory, so `link_shared` skipped new modules.

### Fix

Delete leftover `::job::` schedules before later labs. Overlay shared plugins onto replica dirs in `hermes-replica-entry.sh`. Video send still FAIL for case 25/28 this run.

### Prevent recurrence

Entrypoint plugin overlay. Lab cleanup of `::job::` origins after restore. Do not count leftover mp4 as a send.

---

## 2026-08-19 13:25 +07 — workflow_vps schedule POST timed out at 8s

### Symptom

Case 24 VPS probe hung on `POST /v1/schedules` after health/create/plan passed.

### Root cause

Schedule upsert waits for live LLM classify; the probe used an 8s HTTP timeout.

### Fix

`workflow_vps.py` uses a 120s request timeout, matching other live classify labs.

### Prevent recurrence

Do not use short localhost timeouts for classify-backed schedule upserts on a live host.

---

## 2026-08-19 12:30 +07 — keyword cite/noise lists; Hermes cron skill stole lịch

### Symptom

Once-lịch with “không trích dẫn nguồn” was refused as knowledge cite. Gateway noise used a growing English/Vietnamese needle list. Hermes `jobs.json` still held a paraphrased tomorrow 11:25 once.

### Root cause

Application code classified user and outbound text with keyword dictionaries (rule 36). The scheduling skill told Hermes to persist CLI cron jobs, which rewrote numbered tasks into one wrapper prompt.

### Fix

Inbound: `task_hint=knowledge` from LLM classify. Outbound: `POST /v1/outbound`. Bridge errors in editable JSON. Scheduling skill executes due jobs only and does not persist cron.

### Prevent recurrence

`knowledge_cite_unit.py` fails if the once-lịch fixture is `knowledge`. `gateway_noise_unit.py` uses an injected outbound planner, not production needles.

---

## 2026-08-19 12:15 +07 — once-lịch refused as knowledge cite; tick ran one wrapper job

### Symptom

Zalo 11:22 GMT+7: numbered once-lịch at 11:24 (greeting, fuel E5/E10, HCMC weather, “không trích dẫn nguồn”) got `Không thấy kiến thức khớp «…»`. A 11:25 tick ran **one** English job (“Schedule a one-time task… greet and send weather and gasoline…”) instead of three tasks.

### Root cause

1. Knowledge-cite intercept matched substring `trích dẫn` anywhere, so ingest listed docs and bypassed Hermes classify (rule 15).
2. Classify sometimes stored the schedule wrapper as a single paraphrased instruction and rounded the clock (`11:24` → `25 11 * * *`). Tick explodes stored `instructions[]` only.

### Fix

Cite intercept: explicit `cite`/`find`/catalog-list commands only. Classify `schedule` or `instructions.length >= 2` skips cite. Prompt: numbered deliverables stay separate, wrapper is cadence/cron only, keep the user’s language, exact clock. Case 29.

### Prevent recurrence

`knowledge_cite_unit.py` fails if the live fixture is treated as cite. Mock classify for that fixture must be `once` + `24 11 * * *` + three instructions.

---

## 2026-08-19 12:10 +07 — dispatcher video used; Zalo still rejects mp4 attachments

### Symptom

Manim/pangocairo chatter on Zalo. Case 25 wrote a new mp4 then `send-attachment` failed (invalid parameter).

### Root cause

Hermes invented manim/matplotlib instead of dispatcher. After the skill/job hint it did `POST /v1/video`. zca-js `sendMessage` still rejects these clips. ComfyUI CPU is up as a dispatcher backend, not removed.

### Fix

Dispatcher `/v1/video`, isolated-job dispatcher hint, drop manim lines. Video delivery still needs zca-js `sendVideo` + thumbnail (not sendMessage attachments).

### Prevent recurrence

Case 25 fails without `send-attachment` of a new mp4. Case 26 requires the infographic file sent.

---

## 2026-08-19 10:40 +07 — video on disk, requester got nothing; leftover job stole the next image

### Symptom

Case 25 wrote `hcmc_weather.mp4` then Zalo `send-attachment` failed (invalid parameter). The isolated video job stayed active and later sent case 26’s infographic. Users saw many mid-generation messages. Images did not match weather/fuel overlay.

### Root cause

1. Matplotlib/odd-codec mp4 is rejected by zca-js `sendMessage` attachments.
2. Isolated sessions spawned `_as_kick_late_autosend` that outlived `workflow job done` and claimed newer files in the shared `media/out` folder.
3. Empty `IMAGE_BACKENDS=` (variable set but blank) skipped the Medium/High default, so Hermes invented its own tools.
4. Native `image_generation` is off (`check_image_generation_requirements` false).

### Fix

H.264 remux before send; job file ceiling; no late autosend on isolated jobs; dispatcher `/v1/video` + `overlay` on `/v1/image`; pin `IMAGE_BACKENDS`; result-only after a file send. Case 28.

### Prevent recurrence

Case 25 fails without `send-attachment` of a **new** mp4 in the fire window. Case 26 fails on leftover-job send. Units cover ceiling + overlay + process-narration drop.

---

## 2026-08-19 09:45 +07 — need tests that match one infographic sentence

### Symptom

Users ask for one picture (HCMC weather + fuel overlay in Vietnamese). Existing cases were four numbered jobs (25) or image-then-fuel text (16).

### Root cause

Lab coverage did not include that one-task phrasing. Classify could split overlay facts into extra jobs.

### Fix

Cases 26–27 + fixtures. Classify system rule: one image/video with overlay facts is one instruction.

### Prevent recurrence

`zalo_weather_fuel_lab.py` fails if live classify is not `PLAN_N 1`.

---

## 2026-08-19 09:20 +07 — lịch created media, plugin “ok”, user still got no file

### Symptom

Case 25 jobs completed. `media/out` had a weather png/jpg. Hermes `[flow] zalo_send_file` ran. Admin DM did not receive the image/video. Lab `attach=0` because it grepped `logger.info`.

### Root cause

1. `_post` ignored HTTP status, so a missing host file (`400 file not found`) or a body without `success: true` still looked like a send.
2. Isolated jobs marked idle in ~1.5s; late autosend was skipped while `hold_inflight` was set; the 8s/30s cap ended before dispatcher files landed.
3. Claim-before-send stuck a failed file. Empty caption can make zca-js skip attachments.

### Fix

Require plugin `success: true`. Print `[zalo] send-attachment path` only after that ack. Watch `media/out` for the whole isolated job and drain remaining files. Resolve png/jpg siblings. Caption fallback. Claim after a real send.

### Prevent recurrence

Case 25 counts print-line `send-attachment path` after plugin success. Autosend unit covers `bridge_response_ok` and sibling paths.

---

## 2026-08-19 08:55 +07 — lịch media created, user got no file

### Symptom

Schedule jobs completed. Files appeared under `media/out`. Zalo user received text (or nothing extra) and no image/video.

### Root cause

Autosend compared isolated session id `{thread}::job::{id}` to the last inbound dest `{thread}` and skipped. `send_document` could also post the isolated id as `threadId`. Parallel jobs also raced on the newest file claim.

### Fix

Treat isolated and real ids as the same dest. Remap attachments with `real_thread_id`. Bind dest/t0 per job. Skip claimed files and send the next unclaimed one. Include video extensions.

### Prevent recurrence

Case 25 requires `send-attachment` (`MEDIA_SENT`), not only four job-done lines.

---

## 2026-08-19 08:45 +07 — Zalo up but zalo-api not treated as required

### Symptom

Host bridge / plugin can be logged in while operators expect zalo-api (allowlists, `!zalo`, admin DM). Rolling compose without profile `zalo` can leave the API behind.

### Root cause

zalo-proxy and zalo-api share profile `zalo`, but health/heal did not require the API container to exist.

### Fix

Proxy `depends_on` zalo-api. stack-watch starts the combo if `zalo-api` is missing. check-high fails when ENABLE_ZALO=1 and the container is absent. Case 25 uses the sole admin DM from `zalo_admin_users.txt`.

### Prevent recurrence

Rule 38. Do not recreate Hermes/Zalo without `--profile zalo`.

---

## 2026-08-19 08:30 +07 — case 25 watch saw old completed jobs

### Symptom

Lab upsert stored 4 instructions, but watch showed 4 COMPLETED jobs and zero `[zalo] workflow job done` lines.

### Root cause

Same schedule id fired earlier the same day. Fire reused `{id}:{date}` idempotency and deleted the once row. No new jobs.

### Fix

Once cadence uses `{id}:{timestamp}` idempotency. Lab watch filters workflows created at/after the fire clock.

### Prevent recurrence

Do not treat a COMPLETED workflow from earlier the same day as a new once-fire.

---

## 2026-08-19 08:15 +07 — classify timeout stored one fake job

### Symptom

Case 25 upsert stored `PLAN_N 1` / `task_hint unknown` even though a later classify probe returned 4 instructions.

### Root cause

9router ReadTimeout. Classifier still returned `ok: true` with the original blob as the only instruction. Workflow persisted that plan.

### Fix

Retry classify. On LLM failure return `ok: false` and empty instructions. Schedule upsert fails closed (503) instead of saving one merged job. Longer timeout (90s LLM / 100s client).

### Prevent recurrence

Lab fail-fast on `PLAN_N != 4`. Do not treat classify fallback as a successful multi-task plan.

---

## 2026-08-19 07:55 +07 — classify empty JSON from reasoning models

### Symptom

`POST /v1/classify` returned one instruction (the whole blob) instead of four numbered tasks.

### Root cause

The default combo model writes JSON in `reasoning_content` and leaves `content` empty. `max_tokens` 256/400 also hit `finish_reason=length`.

### Fix

Read `content` or `reasoning_content`, raise `max_tokens` to 2048, parse the first JSON object from the model text.

### Prevent recurrence

Classify config `max_tokens`/`timeout_s` live in `classify.json`. Probe classify `n` after model-router recreate.

---

## 2026-08-19 07:40 +07 — numbered lists classified in app code

### Symptom

Task routing and “1. 2. 3.” job splits used regex/keyword/split in gateway, Zalo, and workflow. That drifted from the architect (LLM owns understanding) and broke when phrasing changed.

### Root cause

`plan_instructions`, `looks_like_schedule`, and model-router substring heuristics interpreted user prose in application code.

### Fix

`POST /v1/classify` (LLM JSON). Callers validate cron tokens and enums, persist `context.plan`, execute jobs. No split/join NLU in product code.

### Prevent recurrence

Operator rule 36. New classify behavior needs a prompt/config change, not a new regex.

---

## 2026-08-19 07:10 +07 — notify alerted node-exporter while monitor was off

### Symptom

With High + Notify and Grafana/Prometheus off, Zalo received `[WARNING] node-exporter unreachable` (DNS name resolution failure). CPU/RAM/disk alerts were paused even though host metrics were never enabled.

### Root cause

alert-watch always scraped `http://node-exporter:9100`. The prometheus profile (which starts node-exporter) was off. Python defaults also listed optional services (AV, Zalo) that compose may not run.

### Fix

Gate scrapes on `ENABLE_*`. Empty `NODE_EXPORTER_URL` and monitor-off → skip, no alert. Skip optional health targets and DNS failures for disabled hosts. Same filter in stack-exporter.

### Prevent recurrence

Do not default scrape URLs to containers that only exist under optional compose profiles. Pass ENABLE flags into alert-watch/stack-exporter.

---

## 2026-08-18 19:45 +07 — lab SSH host and account in product scripts

### Symptom

Committed High deploy helpers defaulted SSH host and login name, so clones of `develop`/`main` contained lab identity.

### Root cause

Product entrypoints used fallback literals instead of requiring `ASSISTANT_SSH_*`. Comment examples repeated the same account. OpenVPN export defaulted the chown user to a named login.

### Fix

Require env/flags with no host or account defaults. Placeholders only (`USER@HOST`, `<user>`). VPS probes stay in gitignored `scripts/temp/`.

### Prevent recurrence

Before merging to `develop` or `main`, grep product trees for IPv4 literals and `ASSISTANT_SSH_HOST` defaults. Do not copy temp-folder credentials into `scripts/main/` or committed `test/`.

---

## 2026-08-18 19:39 +07 — stack-watch treated 9router 401 as down

### Symptom

After High up, 9router (and sometimes dispatcher) showed a start time of only a few seconds even though the rest of the stack was minutes old. Dashboard/gateway stayed up, but the router was bouncing.

### Root cause

`stack-watch` probed `GET /v1/models` with `curl -f`. Without an API key that URL returns **401** while 9router is healthy, so every 2-minute tick counted as DOWN and ran `docker restart 9router`. Compose heal was also missing `--profile notify` / `--profile sandbox`, so `--remove-orphans` could drop those services.

### Fix

- Probe 9router as up on HTTP 200/401/307.
- Align stack-watch compose profiles with `run.sh` (zalo, notify, antivirus, sandbox, omni, traefik/gateway, monitor pairing).

### Prevent recurrence

Do not use `curl -f` on 9router `/v1/models`. Confirm a heal pass does not change `9router` `StartedAt`. Keep notify/sandbox in the heal compose file list whenever those flags are on.

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
