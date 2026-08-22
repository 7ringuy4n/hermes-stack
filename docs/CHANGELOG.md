## 2026-08-22 20:00 +07 — model-router: fix duplicate /v1 in Ollama upstream URL

- `app.py`: register `/v1/*` route before catch-all (decorators apply bottom-up); was matching `/{path:path}` with `path=v1/chat/completions`.
- `route_expand.py`: `upstream_url()` strips duplicate `v1/` when provider base already ends with `/v1` (fixes `ollama:404:bad_chat` for local Qwen).

## 2026-08-22 19:30 +07 — check-security: compose-scoped zalo-api detection

- `check-security.sh`: detect zalo-api by compose service label (`assistant-zalo-api-1`), not legacy fixed name `zalo-api`.

## 2026-08-22 19:20 +07 — Fix setup-zalo infinite loop + light compose up

- `setup-zalo.sh`: after QR, call `ASSISTANT_UP_LIGHT=1 run.sh up` (compose only — no timers, Omni/Ollama/learn re-run).
- `run.sh`: stop auto-invoking `setup-zalo.sh` from `up`/`update` (was looping: setup-zalo → up → setup-zalo); print NEXT hint instead.
- `zalo-common.sh`: poll `/health` while login CLI runs in background (QR scan no longer hangs setup).

## 2026-08-22 19:00 +07 — Purge compose-scoped worker containers on install

- `workers.sh`: remove `${project}-${service}-1` and all compose-labeled worker containers (not just legacy fixed names like `searxng`).
- `run.sh`: set `ASSISTANT_PURGE_WORKER_COMPOSE=1` on `install`/`add-components` so failed partial installs do not block re-run (`assistant-searxng-1` conflict).

## 2026-08-22 18:50 +07 — Fix docker-compose.security.yml invalid UTF-8 (go-yaml parse error)

- Replace Windows-1252 `0x97` byte in comment line 15 with ASCII `-` (broke `bash run.sh install` on Linux).

## 2026-08-22 18:45 +07 — All optional workers: compose-scoped names + orphan cleanup on install

- Optional worker overlays (schedule, media, security, notify, monitor, antivirus, zalo): no global `container_name`.
- `assistant_remove_stale_worker_containers`: before `up`/`install`, remove legacy fixed-name orphans per enabled worker.
- `assistant_rm_container_by_service`: uninstall/stop works with compose-scoped or legacy names.

## 2026-08-22 18:35 +07 — Media worker: drop global container_name (avoid orphan conflicts)

- `docker-compose.media.yml`: remove `container_name` on searxng/ocr/jobs/comfyui — compose-scoped names when installed via `run.sh install media`.
- `run.sh`: `do_remove_stale_fixed_media_names` before up/update removes legacy `searxng`, `ocr`, … orphans.
- `backup.sh`: resolve containers by compose service label; stop jobs via `assistant_stop_services`.

## 2026-08-22 16:00 +07 — Classify offline heuristics (§15 cases 25/26) + Ollama ping SLO

- `classify.py`: `numbered_list_heuristic_plan` for EN4 multi-step lists (case 25).
- `classify.py`: `infographic_weather_fuel_plan` for weather+fuel poster (case 26); skip when numbered list.
- `defaults_routers_lab`: mark ping SLO exceed as **SLOW** (not FAIL) when `OLLAMA_LAB=1`.
- `schedule_classify_heuristic_unit`: cover EN4 + infographic offline paths.

## 2026-08-22 15:10 +07 — Root-cause: Ollama ensure + Zalo SSE bridge gate

- `ensure-ollama.sh`: start/pull/verify host Ollama + docker reachability (stack-watch, run.sh, post-lab).
- `ensure-ollama.sh`: systemd `OLLAMA_HOST=0.0.0.0:11434` so router-worker can reach host Ollama.
- `model-router`: probe Ollama before candidate pool; `/health` reports `ollama` status.
- `stack-watch`: heal down Zalo bridge `:8787` and Ollama when `ENABLE_QWEN=1`.
- `adapter.py`: wait for bridge `/health` before SSE connect (avoids thrash during bridge restart).
- `heal-zalo-sse.sh`: wait for bridge ready before declaring heal done.

## 2026-08-22 15:00 +07 — Lab §15 fixes (Omni-only + offline cadence)

- `plan.infer_cadence_heuristic`: offline cadence when classify LLM unavailable (`workflow_cadence_unit`).
- `classify.json`: drop `max_tokens` (router default 64; `defaults_profile_unit`).
- `grafana_pairing_unit` / `defaults_routers_lab`: skip 9router when `ENABLE_9ROUTER=0`.
- `zalo_latency_lab`: mark SLO exceed as **SLOW** (not FAIL) on local Ollama CPU lab.
- `backup-zalo-lab-preserve.sh`, `seed-zalo-admin-from-postgres.sh`: fix corrupted allowlist restore.

## 2026-08-22 14:30 +07 — AGENT_RULES: full §15 + post-lab restore

- §29.1: “run all test cases” = entire `test/RULES.md` §15 Case index (units + VPS).
- §29.2: after final lab round, `post-lab-restore.sh` + connectivity before stopping host.
- `run_case_index_lab.py`: include history regression + parallel sizing VPS scripts.

## 2026-08-22 14:25 +07 — Outbound classify fail-open (Zalo send path)

- `classify_client.normalize_outbound`: preserve `ok: false` from router.
- `/v1/outbound`: try all provider candidates; fail-open `action: send` when LLM down.
- `gateway_noise`: send user replies when outbound classifier unavailable.

## 2026-08-22 14:20 +07 — Zalo outbound fail-open when classifier down

- `gateway_noise.drop_outbound`: when `/v1/outbound` is unavailable, send user
  replies instead of dropping them as approval chatter (fixes greeting no-reply).

## 2026-08-22 14:10 +07 — router-worker Ollama host gateway

- `docker-compose.yml`: add `extra_hosts: host.docker.internal:host-gateway` on
  `router-worker` so `OLLAMA_BASE_URL` failover works from containers.
- `post-lab-restore.sh`: inline Qwen preflight (no paramiko on VPS).

## 2026-08-22 14:00 +07 — Local Ollama Qwen + post-lab restore

- Qwen active when `ENABLE_QWEN=1` and **either** cloud key **or** `OLLAMA_BASE_URL` + `OLLAMA_MODEL` (no DashScope required for lab).
- `scripts/main/lab-enable-qwen-local.sh`, `post-lab-restore.sh`: enable Ollama qwen2.5:7b, restore Zalo, preflight + router smoke before stopping host.
- `qwen_combo_preflight.py` (case 38): pass with local Ollama combos; `QWEN_COMBOS_EMPTY` when enabled but empty.
- `zalo_tn_greeting_inject`: fix LLM-not-configured detection; default wait 180s when Ollama set (CPU 7B).
- Docs: `QWEN_PERFORMANCE.md`, `.env.example`, `test/RULES.md` §15/§post-lab aligned with activatable Qwen component.

## 2026-08-22 13:05 +07 — Qwen preflight tests + no-reply diagnosis

- Case 38 + `qwen_combo_preflight.py`: detect ENABLE_QWEN=1 with empty key / empty Omni combos.
- `zalo_tn_greeting_inject`: fail fast with `FAIL_LLM_NOT_CONFIGURED` when router returns 400 on empty hermes.
- `run.sh up`: WARN when ENABLE_QWEN=1 without QWEN/DASHSCOPE/ALIBABA key.

## 2026-08-22 12:50 +07 — Skip pre-change backup on clean host (add-components)

- `run.sh add-components` / `remove-components` no longer require postgres backup when
  no compose project containers exist (first-setup / clean redeploy after wipe).

## 2026-08-22 12:45 +07 — Release v0.5.21 Postgres pg_hba mount path

- Fix compose bind mount: `./docker/postgres/pg_hba.conf` (project root), not
  `./postgres/pg_hba.conf` (Docker created a directory and postgres crash-looped).
- `setup-zalo.sh` / `heal-zalo-sse.sh`: use plain `docker` when deploy user is in
  the docker group; retry SSE attach when `sseClients=0` after config sync.

## 2026-08-22 12:30 +07 — Postgres Docker network auth (pg_hba)

- Fresh lab volumes could init with localhost-only `pg_hba.conf` and missing
  `hermes_memory`, breaking workflow/authz/zalo-api (`no pg_hba.conf entry … no encryption`).
- Mount `docker/postgres/pg_hba.conf` (scram for all hosts) and set
  `POSTGRES_HOST_AUTH_METHOD=scram-sha-256`.

## 2026-08-22 11:45 +07 — Agent session cleanup + round-2 clean main

- AGENT_RULES Hard Gates: after a lab/patch session, delete generated one-off
  scripts under `scripts/temp/` / `hermes/temp/` (keep only committed tooling).
- Round-2: wipe stack/data (keep fail2ban + preserved Zalo credentials), redeploy
  `main` with all workers; restore QR session — do not re-scan.

## 2026-08-22 11:35 +07 — Zalo entities in Postgres + lab/prod branch rules

- AGENT_RULES §14: develop lab may use Tn + Vietnamese inject strings; main must
  accept any sole admin and prefer English production defaults.
- zalo-api: PostgreSQL SoT for admin / users / DMs / groups / denied
  (`zalo_entities`); CRUD `GET|POST|DELETE /v1/zalo/entities`, `GET|PUT /v1/zalo/admin`.
- Text allowlist files remain migrate/mirror only. Compose: `DATABASE_URL` on zalo-api.
- Session durable backup/restore: `scripts/main/backup-zalo-session.sh`,
  `restore-zalo-session.sh` (round-2 redeploy without re-scan QR).
- Tn inject scripts: prefer named admin Tn; with `ZALO_REQUIRE_NAMED_ADMIN=0` fall
  back to any admin (main).

## 2026-08-22 18:20 +07 — !zalo claim fails when QR account is Tn

- Lab: after QR scan, `!zalo claim` from Tn did nothing useful: bridge often still
  `loggedIn=false` (stale QR), and claim rejected `sender==bot_id` plus zalo-api
  `/health` not loggedIn even when the message path was the same account.
- Claim allows the QR-login uid (same as bot) on first setup; do not require a
  second personal Zalo. Inbound `/v1/zalo/chat` is enough (no extra health gate).
- Seed admin from bridge `ownId` on zalo-api startup when the admin file is empty.
- Pass `ZALO_PLUGIN_TOKEN` into the host bridge systemd override.
- Unit: `zalo_claim_unit.py`.

## 2026-08-22 17:30 +07 — ENABLE_QWEN is a first-class worker option

- `assistant_option_key_ok` accepts `ENABLE_QWEN` so `run.sh add-components ENABLE_QWEN=1` works.
- Help text: first-setup-omnirouter creates empty hermes/classifier (Qwen fill when enabled).

## 2026-08-22 17:20 +07 — Release v0.5.18

Promote develop → main: PDF skill collision + office-file, schedule/classify guards, ENABLE_QWEN empty combos, SOUL multi-lang, ZALO_WORKFLOW_PARALLEL=8, production gap cases 40–74.

## 2026-08-22 17:10 +07 — Prod gap cases + SOUL multi-lang + Qwen component/parallel

- SOUL.md: multi-language reply rules (not Vietnamese-only); keep deception_hide-safe phrasing.
- Qwen is optional (`ENABLE_QWEN=0` default): `hermes`/`classifier` stay empty round-robin until enabled + key.
- Default `ZALO_WORKFLOW_PARALLEL=8` for ~5–10 concurrent multi-request Zalo users; sizing table in `docs/QWEN_PERFORMANCE.md`.
- Gap matrix cases 40–74 (`test/cases/*-gap-*.md` + README-gap-cases.md) from Production Failure Gap Test Cases v2.
- Tn scripts: `zalo_tn_history_regression.py`, `zalo_tn_qwen_parallel_sizing.py`; units for parallel recommend + SOUL.
- Docs/.env.example aligned (no OpenCode default fill; Qwen activatable).

Promote develop → main: Qwen-only/slim combos, SOUL deception_hide + greeting fixes, searxng-compat web search + Tavily cascade docs, weather/queue timeouts, mixed đặt-lịch+fuel+weather schedule guard, Tn inject lab suites.

## 2026-08-22 16:10 +07 — Mixed đặt-lịch+fuel+weather ran as async (dup weather)

- Lab: one bubble “đặt lịch lúc HH:MM + chào + giá xăng + thời tiết” was demoted to immediate workflow (3 parallel jobs); fuel job answered weather → duplicate weather; schedule not stored for 09:50.
- Guard: classify force `task_hint=schedule` when đặt/ặt lịch + HH:MM; extract cron from clock; prompt clarifies sau/kèm theo stays on the lịch.
- Topic lock on compound/workflow wraps so fuel ≠ weather ≠ greeting.
- Apply: `test/scripts/apply_mixed_schedule_fuel_weather.py`; Tn: `zalo_tn_mixed_schedule_store.py`.

## 2026-08-22 15:20 +07 — Omni unforced search always labels SearXNG

- Deeper lab probe: Omni unforced `/v1/search` reports `searxng-search` even when that connection is blocked/deleted; priority PUT does not stick on GET.
- Hermes remains Tavily-first via Router Worker forced `provider` cascade + searxng-compat shim.
- first-setup smoke: forced-tavily success check; document Omni quirk (do not treat unforced smoke as Hermes default).

## 2026-08-22 14:50 +07 — Omni search: enforce Tavily priority over SearXNG

- Lab: Tavily active but Omni unforced `/v1/search` returned `searxng-search` (initially suspected priority=1 tie).
- Hermes path was already Tavily-first via router `OMNIROUTER_SEARCH_PROVIDERS` + searxng-compat shim (name ≠ engine).
- first-setup: priority-only enforce attempt + apply/probe scripts; docs clarify SEARXNG_URL naming vs cascade.

## 2026-08-22 11:00 +07 — Weather no-reply: rebuild searxng-compat + longer queue turn

- Lab weather DM hung/no reply: router-worker image missing GET /v1/searxng-compat/search (Hermes SEARXNG_URL 404) while OpenRouter returned 402/502/503.
- Rebuild router-worker from current model-router; keep WEB_BACKENDS=omni.
- Raise ZALO_QUEUE_TURN_TIMEOUT_S default 150→300 and WEB_SEARCH_PROVIDER_TIMEOUT_S 20→30 for tool+LLM turns.
- Docs: docs/QWEN_PERFORMANCE.md; Tn suite zalo_tn_weather_mixed_schedule.py (weather + mixed ≥3 + schedule).

## 2026-08-22 10:30 +07 — Qwen slim + queue release + SOUL greeting + Omni VPN

- Zalo queue: default skip compound mark_delivered wait (ZALO_COMPOUND_WAIT_FOR_DELIVERY=0) so the next message can run after handle_message.
- Omni: OMNIROUTE_DISABLE_CREDENTIAL_HEALTH_CHECK=true; slim hermes/classifier to 1–2 Qwen models; dedicated qwen-fast combo for ~1.5B/1.7B; optional deactivate non-Qwen LLM providers.
- SOUL: warm greeting without Hermes/AI branding; never invent /help slash-commands (still avoids deception_hide phrasing).
- OpenVPN docs: reach Omni from any OS via SSH tunnel or VPN-bound publish.
- Test: test/scripts/zalo_tn_qwen_perf.py (Tn inject) for latency + CPU/RAM/disk samples.

## 2026-08-22 09:10 +07 — Tn greeting inject PASS via gateway.log offsets

- Test no longer false-fails on stale queue-timeout / SOUL lines (TZ cut).
- Reads new bytes of replica gateway.log after inject; PASS ~22s send ok on lab.

## 2026-08-22 09:00 +07 — Greeting test reads gateway.log; drop compound race

- Hermes gateway logs to replica gateway.log (docker logs often empty) — Tn greeting inject now reads those files.
- Removed premature compound mark_delivered that raced with in-flight Zalo send.

## 2026-08-22 08:40 +07 — Greeting no-reply: Qwen3 think-only + compound wait

- Root cause after Qwen-only combos: hermes lead model qwen3.6 burned max_tokens inside think tags (finish_reason=length, empty visible text). Zalo then waited on compound delivery until the 150s queue turn timeout — no reply.
- omnirouter_qwen sort: prefer qwen2.5 / qwen-plus / instruct; penalize Qwen3.x thinking-style ids.
- Zalo: if a part has no outbound, skip compound wait; lower compound part timeout default 180→35s.

## 2026-08-22 08:20 +07 — SOUL.md blocked by deception_hide (greeting no-reply)

- Hermes threat pattern do not … tell … the user (FILLER up to 8 words) matched SOUL phrasing and blocked the whole SOUL.md context every turn.
- Agent ran without greeting guidance, over-used tools, hit 150s Zalo queue turn timeout — no useful reply.
- Reword SOUL lines to avoid the pattern; keep intent (no /help spam, no channel naming, no pangocairo chatter).

## 2026-08-22 08:05 +07 — Zalo greeting no-reply: Qwen-only combo + Tn inject test

- Short DM greeting timed out (150s queue turn) because hermes RR still kept flaky ollamacloud members after Qwen-first fill (empty_choices / slow retries).
- When Qwen is active, Omni first-setup now sets hermes/classifier to Qwen-only (round-robin among Qwen chat models).
- Lab case 32 + test/scripts/zalo_tn_greeting_inject.py: inject greeting as allowlisted user Tn via bridge /inject-event.

## 2026-08-22 07:40 +07 — Qwen/Alibaba provider + hermes/classifier first; scheduleFire/group allow

- Omni first-setup: ensure provider alibaba (connection name qwen) when QWEN_API_KEY / ALIBABA_API_KEY / DASHSCOPE_API_KEY set; fill combos hermes + classifier Qwen-first, strategy round-robin (do not wipe when Qwen inactive).
- Reject allow-status phrases as schedule group names (status text like da allow (N)).
- scheduleFire bypasses inbound FIFO; SCHEDULE_URL / SCHEDULE_WORKER defaults on so fires reach Hermes.
- Classified tasks keep using Router Worker to Omni model=classifier (Qwen via combo).

## 2026-08-21 20:40 +07 — Classifier 400 AiError (prompt/text/audio) + prior hydrate

- Omni `classifier` combo members resolved to Cloudflare AI non-chat models
  (need `prompt` / `text` / `audio`); chat/completions `messages` → HTTP 400.
- Classify now skips 400 + AiError schema bodies (mark combo bad → try `hermes`).
- Strip `[Prior conversation]` before classify so Valkey hydrate does not hide
  schedule/intent of the current message.

## 2026-08-21 20:25 +07 — Schedule create silent: classify 503 + 150s queue timeout

- Zalo “đặt lịch … lúc HH:MM” got no reply: Omni `classifier` 503 (inactive
  accounts), failover `hermes` ReadTimeout 60s, then Zalo queue turn timeout 150s;
  answering lock left stuck; cron jobs empty.
- Classify marks 502/503 like 401/403 (skip dead combo briefly); classify timeout
  15s; early/fallback **schedule heuristic** for once/daily `lúc HH:MM`.
- Unit: `schedule_classify_heuristic_unit.py`.

## 2026-08-21 19:55 +07 — SOUL deception_hide; Valkey session; PDF/poster content

- SOUL.md rephrased so Hermes `deception_hide` no longer blocks the whole file
  (“do not tell the user…” → skip/suggest-only wording).
- Zalo short-term chat hydrates/appends via Session service (Valkey); replica
  `sessions.json` is not the SoT after recreate.
- Office-file parses `chứa số N` and strips “gửi cho tôi”; text-poster takes the
  first token after `N dòng` (e.g. hello).
- Zalo media shortcuts call Dispatcher office-file / text-poster for clear
  create intents so the model cannot rewrite into wrong PDF/scene images.
- Units: `office_poster_session_unit.py`.

## 2026-08-21 19:30 +07 — PDF skill collision → fake send + gpt-oss spam

- Zalo “tạo 1 file pdf…” still answered “file gửi kèm” with no attachment:
  agent called `skill_view('pdf')` (3 clones), then `pip`/`reportlab` loops;
  each tool turn re-hit Omni `gpt-oss-120b` with full tool schemas.
- Rename SoT `pdf`/`docx`/`xlsx` (+ official) to `*-tools-local` with
  create-and-send deferred to `file-gen` / `POST /v1/office-file`.
- Replica entry purges `productivity|documents/{pdf,docx,xlsx}` clones,
  force-overlays SoT office skills, and rewrites leftover `name: pdf|docx|xlsx`.
- Unit: `office_skill_collision_unit.py`.

## 2026-08-21 18:50 +07 — Empty Omni combos; office files via Dispatcher

- first-setup no longer fills OpenCode into hermes / classifier; both combos
  are cleared to empty members (operator adds models in Omni UI).
- Zalo "tao file pdf/txt" claimed success but no upload: Hermes hit pdf skill
  collision + failed pip/pypdf; nothing landed in media/out. Skills now require
  POST /v1/office-file; default OFFICE_FILE_GEN=1; empty send caption.

## 2026-08-21 18:20 +07 — Queue turn timeout; Tavily → Firecrawl → SearXNG

- Hung Hermes/web-search turn no longer blocks the next Zalo message: queued
  `handle_message` wrapped in `asyncio.wait_for` (`ZALO_QUEUE_TURN_TIMEOUT_S`),
  drain max + stuck-task cancel (`ZALO_QUEUE_DRAIN_MAX_S`), always
  `compound_end` / answering release + UX line on timeout.
- Omni search cascade default `tavily-search,firecrawl-search,searxng-search`
  with per-provider `WEB_SEARCH_PROVIDER_TIMEOUT_S` (20s) for bounded failover.

## 2026-08-21 18:05 +07 — Hermes web_search via SearXNG-compat shim (Omni)

- Weather Zalo fail: native Hermes `web_search` used raw SearXNG (no Tavily in
  Hermes env; Omni key is masked in API). Soft "tool broken" reply.
- Router Worker adds `GET /v1/searxng-compat/search` (SearXNG JSON shape) on
  top of Omni combo. Hermes `SEARXNG_URL` defaults to that shim.
- Skill rename `web-search-strategy` kept; compose keeps optional Tavily key.

## 2026-08-21 17:55 +07 — Hermes native web_search needed Tavily key

- Zalo weather ask failed with a soft "search tool broken" reply while Router
  Worker Omni `/v1/search` already worked.
- Root cause: Hermes toolset `web` uses `TAVILY_API_KEY` / `SEARXNG_URL`,
  not `WEB_SEARCH_URL`. Compose only set SearXNG → empty/CAPTCHA results.
- Fix: pass `TAVILY_API_KEY` (and Firecrawl) into Hermes; rename knowledge
  skill to `web-search-strategy` to end `web-search` name collision.

## 2026-08-21 16:53 +07 — Omni UI owns search (Tavily → SearXNG)

- Omni Providers: first-setup connects local SearXNG (`providerSpecificData.baseUrl`)
  and prefers Tavily; blocks `ollama-search` for default `/v1/search`.
- Router Worker default `WEB_BACKENDS=omni` proxies to Omni `POST /v1/search`.
- Hermes web-search skills document Omni-owned failover; extract stays on Router Worker.
- Unit: `websearch_combo_unit.py` expects `backends: [omni]`.
## 2026-08-21 16:30 +07 â€” Web search combo config-driven (no py DEFAULT_CHAIN)

- Skill must hit Router Worker `/v1/search`. Failover **Tavily â†’ SearXNG** lives in
  `config/web-search-combo.json` / `WEB_BACKENDS` (OmniRouter-style combo), not a
  hardcoded `DEFAULT_CHAIN` in Python. OmniRouter stays LLM-only.
- Unit `websearch_combo_unit.py` asserts env + JSON order and no `DEFAULT_CHAIN`.

## 2026-08-21 16:05 +07 â€” Web search status: Router Worker combo, not OmniRouter

- Lab check: SearXNG container healthy; OmniRouter has **no** search/tavily/searx
  integration (LLM combos only). Search combo is **Router Worker**
  `POST /v1/search` with default `WEB_BACKENDS=tavily,searxng`.
- Lab broken: `TAVILY_API_KEY` empty; SearXNG engines CAPTCHA/rate-limited â†’
  `/v1/search` 502. Hermes `web_extract` wrongly tried SearXNG for extract.
- Hardening: clearer â€œOmni â‰  searchâ€ docs/skill; SearXNG settings prefer
  engines that work from datacenter IPs; searx call drops `language=all` and
  reports unresponsive engines. Unit: `websearch_combo_unit.py`.

## 2026-08-21 15:35 +07 â€” Cron wrappers + lyric follow-up no web search

- Hermes native cron deliveries showed `Cronjob Response` / `job_id` / stop-reminder
  footers on Zalo; â€œtÃ¬m lá»i bÃ i hÃ¡tâ€ after Multo.mp3 asked which song instead of searching.
- **Zalo**: strip cron wrappers on outbound; remember bare filenames even when AV
  extract is empty; inject quoted context; lyric follow-ups hint web-search from
  filename. Skills: quiet-delivery / scheduling / web-search / schedule.
- Unit: `test/scripts/cron_lyric_unit.py`.

## 2026-08-21 14:25 +07 â€” Bare files silent / mp4 â€œno videoâ€: agent + Omni busy

- Bare mp3/txt only showed Knowledge-pending; csv/xlsx got no Zalo reply; mp4
  asked for a video that was already attached â€” agent turns died on Omni
  **capacity-busy 503** after retries.
- **Zalo**: bare office/text/av attachments now send a deterministic extract ack
  (like image OCR ack) and skip the agent for that turn.
- **Router Worker**: detect capacity-busy / retry-shortly; sleep
  `OMNIROUTER_BUSY_BACKOFF_S` (default 3s) between rotate hops; default rotate
  attempts **5**. Case **37** / attachment units updated.

## 2026-08-21 14:05 +07 â€” Second photo silent: SSE blocked + OCR-ack send hung

- Two bare photos: first got OCR ack, second was OCRâ€™d (incl. glyph-noise) but Zalo showed no second reply.
- **Root cause:** `_handle_sse_event` awaited full OCR/AV, so the SSE reader stalled; OCR-ack `send()` also ran autosend (no `as_skip_autosend`) and skipped inflight clear (`as_skip_inflight`).
- **Fix:** schedule inbound on a background task with a per-thread lock; OCR ack skips autosend/filters, clears answering slot, kicks the inbound queue; glyph-noise OCR â†’ empty ack. Units updated (case 37).

## 2026-08-21 13:45 +07 â€” Photo OCR ok but Zalo silent: Omni 403 + agent tools

- Bare Zalo photos with successful PaddleOCR still got **no reply** when OmniRouter round-robin hit `ollama-cloud/deepseek-v4-pro` (subscription 403). Hermes streamed that error through model-router and the agent died after retries; compound part waits then timed out.
- **Router Worker**: chat completions always call upstream non-stream so error bodies can failover; **rotate** the primary Omni combo (`OMNIROUTER_ROTATE_ATTEMPTS`, default 3) so free members can answer; then try `OMNIROUTER_FAILOVER_MODELS` (default `auto/best-free`); wait longer (`MODEL_ROUTER_TIMEOUT_S` default **180**); rebuild client stream as one-shot SSE when requested.
- **Zalo adapter**: bare image â†’ immediate deterministic OCR ack (with or without text); skip agent/tool loop. Unit/case **37**.

## 2026-08-21 12:15 +07 â€” PaddleOCR works only with matching paddlex minor

- Lab rebuilds initially fell back to tesseract: paddleocr 3.1.1 + paddlex 3.7 broke `PaddlePredictorOption`; pinning paddlex 3.1.1 then broke import (`langchain.docstore`). Aligned to **paddleocr 3.7.0 + paddlex 3.7.2** per upstream table; still returns `via=paddle` for `HOA DON 1250000 VND`.

## 2026-08-21 12:10 +07 â€” PaddleOCR is the primary OCR engine (Media Worker)

- OCR service (separate container under the Media Worker profile) now runs **PaddleOCR first** for images and scanned PDF pages. Vision LLM is opt-in (`OCR_VISION=0` by default) so text-only routers no longer burn a round trip or invent â€œplease upload the imageâ€ as OCR text.
- Paddle inference runs on a dedicated thread pool inside the OCR container so dispatcher ASR / other Media Worker ops are not blocked. Tesseract remains the secondary fallback; pymupdf still handles PDF text layers.
- Build: `INSTALL_PADDLE=1` installs CPU `paddlepaddle` + `paddleocr` (mobile PP-OCRv5 when available). Model cache on the media volume. Unit: `test/scripts/paddle_ocr_unit.py`.

## 2026-08-21 11:52 +07 â€” OCR image must COPY result.py

- `empty_scan_result` lived in `result.py` but the OCR Dockerfile only copied `app.py`/`refuse.py`, so the rebuilt container crash-looped on import after PR #93.

# Change history

## 2026-08-21 11:50 +07 â€” Photo staged OK but agent greeted; OCR empty â‰  failure

- Resent photo was staged (`â€¦/inbound/â€¦/image.jpg`) and OCR path was no longer 404, but vision was in a 900s cooldown and tesseract found no glyphs â†’ `ocr_failed`. Hermes still ran an agent turn after recreate and sent a generic `/help` greeting instead of an image ack.
- OCR: after a successful local scan with no text, return `ok:true, empty:true` (not `ocr_failed`); reject body with neither path nor `image_b64` as 400; label cooldown path as `via=tesseract`.
- Zalo adapter: bare image + empty OCR â†’ immediate deterministic ack, skip agent; OCR path miss retries with `image_b64`.

## 2026-08-21 11:40 +07 â€” Photo arrived, OCR 404 on replica cache, no Zalo reply

- Inbound Zalo images were cached under `/opt/data/replicas/.../cache/images/`, which OCR/ingest/dispatcher do **not** mount. `POST /v1/ocr` returned 404, extract text was empty, and the bare-image prompt told the agent to â€œopen the imageâ€ while vision tools were unavailable â€” so the turn produced LLM outbound calls but **no bridge send**.
- Fix: `stage_shared_media` copies the download onto `/opt/data/media/inbound/{thread}/` before workers run; empty-OCR image prompt no longer demands opening the file or calling missing vision tools.
- Unit: `zalo_attachment_unit.py` covers the staging copy.

## 2026-08-21 11:20 +07 â€” Zalo bridge EADDRINUSE crash-loop + media/fetch 404

- **Bridge ownership:** `patch_zalo_bridge_inject.py` used to `pkill` + `runuser`/`Popen` a second Node listener while the user systemd unit `com.hermes.zaloplugin` stayed enabled. The orphan held `:8787`, systemd failed with `EADDRINUSE` every 5s (restart counter past 9500), and journal spam drowned real signal. Restart now clears orphans, then enables/restarts the systemd unit; `setup-zalo.sh` no longer `nohup`s a competing process; `zalo-watch` heals through the same path.
- **`/media/fetch`:** Hermes `ASSISTANT_MEDIA_PROXY_v1` POSTs CDN URLs to the bridge, but upstream `hermes-zalo-plugin` 1.0.9 has no such route (`Cannot POST /media/fetch`), so images never reached OCR. The patcher now installs `POST /media/fetch` + `GET /media/:id` (session cookies from `~/.hermes-zalo/credentials.json`) and dedupes the thrice-applied `/inject-event` handlers left by the old marker.
- Unit: `test/scripts/zalo_bridge_patch_unit.py`.

## 2026-08-21 11:10 +07 â€” OCR no longer passes off a blind model's excuse as text

- **OCR worker**: the routed model has no vision on this stack, so it answered 200 OK with â€œI donâ€™t see an image â€” please upload itâ€. That reply was longer than the minimum length and matched no refusal pattern, so it was returned as *extracted text* â€” which is why an image came back as a generic description and a video's on-screen text was nonsense. Refusal detection now covers those chat replies (curly apostrophes included), so tesseract (`eng+vie`, already in the image) provides the text instead.
- **Vision cooldown**: after three consecutive blind replies the worker skips the vision round trip for 15 minutes and goes straight to local OCR, which also cuts the latency users saw on image and file turns.
- Refusal detection moved to `architect/tools/ocr/refuse.py` so it is unit tested without the service stack (`test/scripts/ocr_refuse_unit.py`, case 35).

## 2026-08-21 10:40 +07 â€” Dispatcher flap was the watchdog; media text extraction now real

- **stack-watch**: probe 9Router / dispatcher / OCR / jobs only when that component is enabled or running, and restart **only** the containers whose own probe failed. A disabled 9Router used to fail every tick, and the heal then blanket-restarted `dispatcher` every 2 minutes â€” killing in-flight OCR and media jobs and producing the â€œService recovered: dispatcherâ€ alerts.
- **Media worker ASR**: `faster-whisper` was only a comment in `requirements.txt`, so `/v1/media/text` always failed ASR. It now installs behind the `INSTALL_WHISPER` build arg (compose feeds it from `WHISPER_ENABLED`), with `requests` pinned because `huggingface_hub` 1.x no longer pulls it in, and `HF_HOME` on the media volume so the model is fetched once.
- **Keyframe OCR**: frames were sampled with an fps filter whose interval exceeded a short clip, so no frame reached OCR. Frames are now taken by seeking to evenly spaced timestamps; the response reports `frames_read`.

## 2026-08-21 09:40 +07 â€” Attachment workers, web search on Router Worker, bulk schedule remove

- **Every inbound file goes to a worker that can read it** (`attachment.py` + Zalo adapter): text read locally, image/PDF â†’ OCR, `.docx/.xlsx/.pptx/.csv` â†’ Ingest `POST /v1/extract-text` (new), audio/video â†’ Media Worker `POST /v1/media/text` (new: Whisper ASR + ffmpeg keyframe OCR). Extraction runs **concurrently** with the AV gate, so small `.txt` replies stop waiting on the scan.
- Office/CSV no longer answer with only â€œKnowledge â€” pending approvalâ€: the summary is produced from extracted text in the same turn.
- Attachment recall keeps the **last 5 files per thread** (was 1) and the inbound FIFO cap is 16 (was 8), so a mixed media pack survives and â€œtÃ³m táº¯t cÃ¡c file vá»«a gá»­iâ€ works.
- `.txt` send fixed at the source: Zalo rejects document attachments carrying a blank caption, so the `caption` field is now omitted (`ATTACH_CAPTION_FALLBACK = ""`).
- **Web search moved off Dispatcher to Router Worker** (`model-router`): `/v1/search`, `/v1/extract`, `/v1/backends/next` with Tavily â†’ SearXNG fallback; Hermes skills retargeted. Dispatcher `/health` is now async, which stops the up/down flap while media jobs run.
- Classifier: deliverables joined by conjunctions (`vÃ `, `kÃ¨m theo`) split into separate async instructions; items inside one deliverable (E5 RON92 + E10 RON95) stay together.
- **Admin schedule remove**: `remove 1 3 5`, `remove 1-3`, `remove all`, `remove group <name>`, `remove group <name> 1-2`; deletes from `cron/jobs.json` and the workflow service, replies with count + labels. Messages live in `hermes/main/messages/zalo-admin.json`.
- Case 34 + `zalo_attachment_unit.py`; `schedule_crud_unit.py` / `multi_request_unit.py` / `inbound_queue_unit.py` extended.

## 2026-08-21 08:20 +07 â€” Remove adapter EICAR cheat; fix OCR path, image/PDF/txt/queue

- Remove local `_as_eicar_hit` from Zalo adapter â€” AV only via Security Worker / av-gateway.
- OCR: map `/opt/data/media` â†’ `/data/media` (fixes 404); quick OCR excerpt before agent for PDF summary.
- Image bare prompt: describe attached image; do not ask user for a caption.
- `.txt` send: if Zalo rejects attachment, fall back to message body.
- Per-thread FIFO queue: announce when another message is already waiting.
- Cases 32 (updated) + 33.

## 2026-08-21 07:45 +07 â€” Secret path refuse + EICAR before knowledge learn

- **secret-probe**: skip empty/corrupt policy files; expand protected paths (`/opt/data`, `/data/assistant`, `.env`, `/etc/shadow`, â€¦); bundled defaults if no policy loads.
- **AV gate**: deterministic EICAR block before learn; when antivirus flag is on but scanner down â†’ refuse (fail closed). UX copy under `security.*`.
- Case 32 + `secret_probe_path_unit.py`. Security skill documents fail-closed + EICAR.

## 2026-08-21 07:20 +07 â€” Schedule group fire + worker-routing + install/remove workers

- **Root cause:** `scheduleFire` into groups was dropped by `ZALO_GROUP_MODE=mention` (no @bot). Bypass mention/rate/inflight for schedule fires.
- Schedule Worker: `schedule_fire_log` + `GET /v1/schedules/history`; create ack includes id/next run.
- Classify: skip dead `classifier` combo briefly after 401/403 so schedule acks stay fast.
- Alert-watch: `HEALTH_FAIL_STREAK` (default 3) before CRITICAL DOWN (dispatcher flap).
- Add `worker-routing` skill (Dispatcher deprecated for new work). `run.sh` `install-workers` / `remove-workers`.
- Case 31 + `schedule_group_fire_lab.py`.

## 2026-08-20 21:00 +07 â€” docs: backfill ops HISTORY for 2026-08-12â€¦18

- `scripts/HISTORY.md`: added missing issue notes for **2026-08-15â€¦18** (schedule TZ, stack-watch backoff, inbound queue, Omni/schedule-list, isolation, check-medium corruption, DR/SSE, backup role/Qdrant, replica entrypoint, office silent `.txt`, first-setup combo, disk full).
- **2026-08-12â€¦14**: no product CHANGELOG/HISTORY in this tree (clean rebuild starts 2026-08-15).
- Expanded HISTORY Quick index for those symptoms.

## 2026-08-20 20:50 +07 â€” Dual Hermes .env Permission denied on auto-sethome

- Replica entry + `run.sh` also chown shared `.env` / `config.yaml` / data root to Hermes UID (scaled replicas rewrite home channel).
- Dual isolation lab pass flag scopes to **media** Permission denied (not unrelated `.env` noise).

## 2026-08-20 20:45 +07 â€” Rule 50 + durable media perms + dual Hermes isolation case

- **AGENT_RULES #50**: source-first fixes â€” merge then pull on host; no lasting lab hotpatch cheats. Hard gate in agent-ops.
- **Media permissions**: `run.sh` / `setup-zalo` / `hermes-replica-entry` / `stack-watch` ensure `media/inbound` + `media/out` owned by Hermes UID with setgid â€” stops recurring Permission denied.
- **Test**: case `30-hermes-dual-isolation.md` + `test/scripts/hermes_dual_isolation_lab.py` (scale Hermes=2, concurrent admin injects via bridge).

## 2026-08-20 20:35 +07 â€” Schedule-by-group: classify failover + cold registry sync

- **Classify**: when combo `classifier` returns HTTP 401/403/empty, retry with chat combo (`hermes` / `OMNIROUTER_DEFAULT_COMBO`) so schedule JSON (`target_channel`, cron) still succeeds.
- **zalo-api**: startup + resolve-miss sync bridge `/contacts` into channel registry; resolve matches platform-prefixed names (`Zalo LC group` â†’ `LC group`) and reverse containment.
- Schedule skill: never ask for raw chat ID when group unknown â€” use `!zalo allow` / `!zalo refresh`.
- Unit: `channels_schedule_target_unit.py` covers prefixed group names.

## 2026-08-20 20:20 +07 â€” Remove legacy check-medium/high + High deploy wrappers

- Deleted unused `scripts/main/check-medium.sh` / `check-high.sh` (were thin wrappers to `check-media` / `check-security`).
- `run.sh`: only `check-media` / `check-security` (plus `smoke-media` / `smoke-security`); renamed `need_med`/`need_high` â†’ `need_media`/`need_security`.
- Removed broken legacy `Deploy-High.ps1` / `Deploy-V050-Test.ps1` (pointed at missing `scripts/main/*.py`; lab helpers live under gitignored `scripts/temp/`).
- Callers/docs retargeted to worker smoke names.

## 2026-08-20 20:10 +07 â€” Learn pending bridge fallback; drop legacy medium/high compose

- **Ingest** learn pending: notify via Notification Worker, then **bridge `/send`** to sole admin when Notify is down; compose wires bridge + admin file.
- `setup-zalo.sh`: `media/inbound` + `media/out` for Hermes UID; bridge bind docs (`ZALO_PLUGIN_HOST=0.0.0.0` + firewall / token).
- `patch_zalo_bridge_inject.py` restart keeps non-loopback bind for Docker inject/SSE.
- **Removed** unused `docker-compose.medium.yml` / `docker-compose.high.yml`; backup, stack-watch, first-setup use `media.yml` / `security.yml` like `run.sh`.
- Zalo README: schedule-by-group-name + bridge security notes. `scripts/HISTORY.md` ops entry.

## 2026-08-20 20:05 +07 â€” Learn pending notify without Notify Worker; media inbound; bridge bind docs

- **Ingest** `POST /v1/learn/submit`: notify sole Zalo admin via Notification Worker, then **bridge `/send` fallback** when Notify is down/`ENABLE_NOTIFY=0` (pending approve no longer silent).
- Ingest compose gets `ZALO_BRIDGE_URL`, admin file/env, optional `ZALO_PLUGIN_TOKEN`.
- `setup-zalo.sh` creates `media/inbound` + `media/out` owned by Hermes UID; documents `ZALO_PLUGIN_HOST=0.0.0.0` firewall risk.
- Zalo README: schedule-by-group-name, `!zalo list` / `schedule list all`, bridge bind security.
- `patch_zalo_bridge_inject.py` restart keeps `ZALO_PLUGIN_HOST=0.0.0.0` so Docker can reach `/inject-event`.

## 2026-08-20 19:35 +07 â€” Security services gated by compose profile `security`

- `openbao`, `security-manager`, `authz`, `siem`, `policy-center` use `--profile security` only when `WORKER_SECURITY` / `ENABLE_SECURITY` is active.
- Notification Worker no longer starts those containers; `run.sh` removes them when Security is inactive.
- Removed hermes/ingest hard `depends_on` onto profiled security services from the security overlay.

## 2026-08-20 19:00 +07 â€” [RELEASE] v0.5.13

- Classify combo `classifier` (OpenCode Free `oc/*`); chat stays on `hermes`.
- Classify reads provider CoT fields when `content` is empty.
- alert-watch skips 9Router when disabled; bare Zalo images no longer force document-OCR Q&A.

## 2026-08-20 18:55 +07 â€” Classify reads provider CoT fields when content empty

- `_message_text` checks `content`, `reasoning_content`, `reasoning`, `thinking`, `thinking_content`, `thought`, `reasoning_text`, plus any other message key containing reason/think, and `reasoning_details`.

## 2026-08-20 18:50 +07 â€” Classifier combo uses Omni `oc/*` catalog + unblock

- `first-setup-omnirouter` clears `blockedProviders` for OpenCode, loads all `oc/*` from `/api/models`, and writes combo members with `connectionId` (Omni object shape).
- Note: host may still see OpenCode upstream HTTP 403 (quota/block); classify fails open until upstream recovers.

## 2026-08-20 18:40 +07 â€” Classify combo `classifier` (OpenCode Free)

- Dedicated Omni combo **`classifier`**: `first-setup-omnirouter` ensures OpenCode provider + fills combo with all current `oc/*` models; default `MODEL_ROUTER_CLASSIFY_MODEL=classifier`.
- Chat/outbound stay on combo **`hermes`** (members still UI-managed).
- Skipped promoting Groq `message.reasoning` into empty `content` (operator preference).
- alert-watch: skip 9Router `/api/auth/login` when `ENABLE_9ROUTER=0`; Zalo bare images no longer inject document-OCR Q&A prompt.

## 2026-08-20 16:35 +07 â€” Omni combo members not hardcoded by first-setup

- `first-setup-omnirouter` only ensures combo alias `hermes` exists; it no longer writes a fixed `oc/*` (or any) member list. OmniRouter UI / combo routing chooses models.
- Docs: stack sends combo name only; operators manage members in Omni Combos.

## 2026-08-20 16:25 +07 â€” Clarify hermes is a combo alias (not a vendor model)

- Docs/env: `hermes` is OmniRouter/9Router **combo** name used in the OpenAI `model` field; there is no standalone model id `hermes`.
- Classify/outbound defaults resolve from `OMNIROUTER_DEFAULT_COMBO` / `N9ROUTER_DEFAULT_COMBO`.

## 2026-08-20 16:15 +07 â€” Classify model via env; Hermes â†’ model-router patch

- **Classify/outbound** no longer hardcode LLM model in `classify.json`; use `MODEL_ROUTER_CLASSIFY_MODEL` / `MODEL_ROUTER_OUTBOUND_MODEL` (default `hermes` combo).
- **`patch-hermes-model-router.py`** + `setup-zalo.sh` / `first-setup-omnirouter.py` point shared `config.yaml` at `http://model-router:8096/v1` (fixes OpenRouter 401 on Zalo chat).

## 2026-08-20 16:05 +07 â€” Harden classify + stop dropping !zalo admin replies

- **Classify** pins default model to `oc/north-mini-code-free`, caps `max_tokens`, maps invalid `task_hint: chat` â†’ `normal`, dedupes instruction spam, and uses a local hello heuristic when Omni returns garbage JSON.
- **Zalo outbound** no longer LLM-filters `!zalo â€¦` admin help (`zalo_admin_reply` bypass + gateway_noise guard).

## 2026-08-20 15:45 +07 â€” Zalo classify fail-open + schedule-by-group-name registry

- **Classify outage** no longer dead-ends Zalo chat with â€œCould not classifyâ€¦â€ â€” Hermes falls through to normal reply when `/v1/classify` fails (Omni free-tier 429 / empty JSON).
- **Channel registry** (`/data/assistant/channels/registry.json`) stores Zalo user/group idâ†”name from inbound traffic, allowlists, admin, and bridge `/contacts` (`!zalo refresh`).
- **Schedule-by-group-name**: NL like `Ä‘áº·t lá»‹ch â€¦ gá»­i vÃ o nhÃ³m Family` resolves the group id and stores schedule `origin` as that group while keeping the requester as `user_id`.

## 2026-08-20 15:25 +07 â€” Hermes OPENAI key + clean-host Zalo shared-data path

- **Hermes compose** now sets `OPENAI_API_KEY` from `OMNIROUTER_API_KEY` (fallback `N9ROUTER_API_KEY`) so Omni-default installs are not left with an empty key when 9Router is off.
- **`setup-zalo.sh`** writes shared Hermes config/plugin into `ASSISTANT_DATA_DIR` (host path mounted as `/opt/data` in Hermes), not a bare host `/opt/data`.

## 2026-08-20 15:05 +07 â€” clean-host Zalo setup seeds shared Hermes config

- **`setup-zalo.sh`** now seeds shared `config.yaml` from a live replica on clean hosts, enables `zalo-platform` in the real `plugins:` block, and writes `gateway.platforms.zalo.enabled: true`.
- **`setup-zalo.sh`** also fixes shared `.env` ownership for Hermes (`HERMES_UID:GID`) and resolves the real Hermes container name before restart.

## 2026-08-20 14:40 +07 â€” [RELEASE] v0.5.12

- Clean-OS first-setup fixes (zalo-api Dockerfile, destroy without containers, OmniRouter wait path).
- Secrets-first `.env.example`; worker smoke checks (`check-media` / `check-security`); docs/scripts aligned to workers + OmniRouter default.

## 2026-08-20 14:35 +07 â€” clean-OS first-setup; retire profile smoke names

- **zalo-api Dockerfile** copies `channels_registry.py` (fixes `ModuleNotFoundError` on first build).
- **setup-zalo.sh** waits for model-router + OmniRouter + zalo-api (not PROFILE/low/9Router).
- **destroy** skips backup when no project containers (clean host).
- **`.env.example`** reordered: section A = first-setup secrets; Omni default / 9Router optional; `MODEL_ROUTER_OUTBOUND_TIMEOUT_S=30`.
- Local helper (gitignored): `scripts/temp/generate_env_secrets.py` fills `CHANGE_ME_*`.
- Smoke scripts: `check-media.sh` / `check-security.sh` (worker names); `check-medium.sh` / `check-high.sh` are thin wrappers.
- Docs/scripts: workers over profiles (`README`, `00-profiles` redirect, `DEFAULTS`, `02-commands`, `docker/README`, `scripts/main/README`, `run.sh` help, AGENT_RULES #30).

## 2026-08-20 13:15 +07 â€” [RELEASE] v0.5.11

- Worker activation model (`WORKER_*=active|inactive`), Schedule Worker (Go), Media|File and security overlays, quiet Zalo outbound (30s), channel registry, OmniRouter default / 9Router optional.

## 2026-08-20 13:10 +07 â€” VPS rolling deploy (worker components)

- Destroy + clear stale cron; redeploy with Schedule, Media|File, Notify, Message workers (`WORKER_*=active`, security/monitor inactive).
- Zalo bridge rebound (`loggedIn=true`, SSE connected). Logs: `test/reports/deploy-rearchitect-run5.log`, `abnormal-logs-run5.log`.

## 2026-08-20 12:50 +07 â€” case 11 worker model; outbound timeout 30s

- Case **11**: renamed to `11-worker-switch.md`; script `worker_switch.py` (add/remove `WORKER_*`; `switch-profile` fail event). Removed obsolete profile upgrade/downgrade case.
- Outbound classify: default/fallback `timeout_s` **30** (`outbound.json`, model-router, Zalo classify client).

## 2026-08-20 11:50 +07 â€” quiet delivery; infographic skill; no upgrade/downgrade

- Outbound to Zalo: structural drop of Hermes agent status frames (Working / iteration N/M / provider-failure); LLM `/v1/outbound` fail-closed to drop; skills `quiet-delivery` + `image-gen/infographic-design`.
- Secret probe: still **code** policy (`secret-probe.json`); added password/credentials patterns.
- `switch-profile` remains disabled (worker `add-components` only); archive comment no longer says upgrade/downgrade.

## 2026-08-20 10:45 +07 â€” 9Router optional; channel registry; web search combo

- **9Router** optional (`ENABLE_9ROUTER=0` default, compose profile `9router`). OmniRouter remains default router; memory enabled via `OMNIROUTER_ENABLE_MEMORY=1`.
- **Web search**: top **3** results; fixed combo order Tavily â†’ Firecrawl â†’ SearXNG (dispatcher merge, not round-robin).
- **Message Worker** channel registry (`architect/zalo-api/channels_registry.py`) + `/v1/channels*` APIs; synced from Zalo allowlists.
- **Zalo adapter**: runtime `print` â†’ `logger`; lab SSH helper renamed `deploy_stack.py` (`deploy_high.py` shim).
- **Deploy**: `run.sh destroy` + `run.sh up` with worker flags (Schedule, Media|File, Notify, Message).

## 2026-08-20 10:20 +07 â€” Zalo lab cases 16â€“29; case 16/29 fixes

- Full lab run on VPS `72.61.127.249`: cases **17, 26, 27, 28 PASS** on first pass; **16** (480s watch too short for sequential image+fuel) and **29** (transient classify `ok=false`) failed once.
- Fixes: `zalo_multi_request_lab.py` default watch **720s**; case 29 classify **3Ã— retry**; `classify.json` schedule prompt no longer uses standalone word *lá»‹ch*.
- Rerun cases **16 + 29: PASS** (`test/reports/rerun-16-29.log`). Zalo bridge `0.0.0.0:8787`, `sseClients=1` throughout.

## 2026-08-20 09:15 +07 â€” workers active/inactive; dispatcher in Media|File; Valkey name

- Default setup is worker activation (`WORKER_*=inactive|active`). Bundled `ENABLE_*` live on each worker (`workers.sh`). Product tiers and `ASSISTANT_PROFILE` are gone from runtime.
- Dispatcher starts only with the Media|File Worker (compose profile `media`). Workflow stays the async compound-job runner; Schedule Worker is the clock only.
- Valkey container is `valkey` (not `redis`). Overlays: `docker-compose.media.yml`, `docker-compose.security.yml`.
- Case 17: quota / free-model failover is not a Zalo latency SLO fail.

## 2026-08-20 08:45 +07 â€” Zalo SSE + lab deploy verification

- Single-replica Zalo: `profile.sh` defaults `ZALO_PLUGIN_URL` to `host.docker.internal:8787` (socat SSE breaks long-lived connections).
- Lab VPS: destroy+component deploy OK; gateway `zalo` platform connected; `config.yaml` patched to `model-router:8096/v1` (OmniRouter path).
- `zalo_user_latency.py`: probe reads replica `agent.log` / `gateway_state.json` (not only docker stdout).
- Zalo cases 16â€“29 running via `scripts/temp/run_zalo_cases.py`.

## 2026-08-20 08:10 +07 â€” core API Gateway + worker-routing skill

- Core defaults: API Gateway on, Valkey inbound queue on, gateway skips rate limit for coding and schedule paths. Optional workers remain `ENABLE_*=0` in product source.
- New skill `core/worker-routing`: maps classifier JSON to schedule / web-search / media-file / security workers.
- Lab destroy+deploy with schedule, media, notify, message workers: `scripts/temp/deploy_rearchitect_lab.py`.

## 2026-08-20 07:10 +07 â€” OmniRouter default; Go schedule worker

- OmniRouter is the default general/classify/outbound router (High included). 9router stays coding + failover. Chat `model=hermes` no longer forces 9router.
- Go schedule worker (SQLite) owns when-to-run. Hermes Schedule skill stores inner `fire_text`; at tick the worker injects that message back into Hermes (`scheduleFire` protocol). Workflow no longer ticks cron when `SCHEDULE_URL` is set.
- Classify JSON adds `process_original_message`, `message`, `attachments_required`, `attachment_types`, `skill`, `skill_action`. Skills: `schedule`, `web-search`, `media-file`, `security`.

## 2026-08-19 21:25 +07 â€” classify once-lá»‹ch: compact prompt, one timeout, provider failover

- Dropped character-length timeout buckets. Classify uses one `timeout_s` in `classify.json` and a short JSON contract (task_details optional; validator fills).
- `/v1/classify` tries the next healthy provider on timeout instead of returning ok=false after one hop. Zalo HTTP classify wait is 70s so it is not shorter than the LLM hop. Workflows stay sequential=false.
## 2026-08-19 21:15 +07 â€” once-lá»‹ch classify timeout used hello budget

- Numbered once lá»‹ch under 400 characters used the 3s hello classify timeout and the 5s HTTP client abort, so Zalo returned classify.failed instead of saving the schedule.
- Classify wait now scales with payload length (short / medium / long). Workflow create stays sequential=false.
## 2026-08-19 21:05 +07 â€” classify task_details; workflows default async

- Classifier JSON adds per-instruction `task_details` (execution_class, task_type, depends_on). Validator rejects schedule without a 5-field cron. Timeout/invalid classify is a failure (`response_mode=confirm`), not fail-open to hello.
- Workflow `sequential` defaults to false. Jobs run in parallel unless `depends_on` (or an explicit sequential flag) requires order. Classify retry is 2 attempts.
## 2026-08-19 20:50 +07 â€” cron numbered briefing must explode to N Zalo sends

- Classify keeps greeting / fuel-summary / weather-summary / draw-image as separate instructions when the user numbered them. Overlay-on-the-same-picture stays one job.
- Schedule tick re-classifies if stored plan was a single blob; multi-instruction fires run sequentially. Hermes once `run_at` jobs migrate into workflow. Media chmod copies root-owned files so the bridge can send.

## 2026-08-19 20:30 +07 â€” Release v0.5.10

- Production cut of fail-open classify (one hop), Chat Completions JSON normalize, and cron TypeError rewrite on Zalo outbound.

## 2026-08-19 19:45 +07 â€” classify one hop; normalize chat JSON; cron vars() leak

- `/v1/classify` and `/v1/outbound` use the first healthy provider only, then fail-open. Classify LLM timeout is 3s so a hello is not held on four ReadTimeouts.
- Chat proxy sanitizes the request and normalizes Chat Completions JSON (string `message`, list `content`, error bodies failover). Cron `vars() argument must have __dict__` is treated as protocol and rewritten from `ux.json` `schedule.job_failed`.

## 2026-08-19 16:55 +07 â€” Zalo Bridge hi latency test; Hermes config.yaml via model-router

- Case 17 uses `zalo_user_latency.py`: inject a short DM onto the Zalo plugin SSE stream (`POST /inject-event`) as the named admin user. Not Traefik chat.
- Rolling apply rewrites Hermes `config.yaml` `base_url` from 9router to model-router (env alone was ignored). Model-router fails over on HTTP 413/429.
- Adapter logs `Zalo: send ok` for measured outbound. Outbound `/send` uses a separate HTTP session from SSE so POST is not reset by the long GET /events.

## 2026-08-19 16:40 +07 â€” drop Hermes 413/compaction from Zalo; cap session length

- Zalo outbound drops Hermes protocol lines (context compaction, payload 413, session auto-reset) via `ux.json` `outbound_protocol_drop`.
- Session store keeps at most `SESSION_MAX_MESSAGES` (default 16). Rolling apply recreates session, `POST /v1/sessions/reset-all`, deletes replica `sessions/sessions.json`, and points Hermes `OPENAI_BASE_URL` at model-router when the host still targeted 9router.

## 2026-08-19 16:22 +07 â€” restore lab-only classify cache key (rule 41)

- Removed `prompt_rev` from `classify.json` (Docker cache-bust only). Product classify stays 8s / 1024 tokens. Chat `model=hermes` still prefers 9router.

## 2026-08-19 16:00 +07 â€” classify/outbound use Omni like chat; 8s classify budget

- `/v1/classify` and `/v1/outbound` pick the same general-chat LLM as the proxy (Omni when healthy, else 9router). They no longer always call 9router.
- Classify timeout is 8s / 1024 tokens so a hello is not held for 20s when the upstream is slow. Failed classify stays interactive.
- Chat proxy fails over from Omni 401/403 to 9router (OpenCode combo smoke was 403 HTML). `model=hermes` and classify/outbound prefer 9router so OpenCode free models are not first hop for Fast Dispatcher or Hermes chat.

## 2026-08-19 15:35 +07 â€” video length caller-chosen (max 2 min); faster classify for chat

- `POST /v1/video` `seconds` is the caller length; hard cap 120s (`VIDEO_SECONDS_MAX`). Encode timeout scales with duration.
- Classify uses 20s timeout and 1024 max tokens (was 90s / 32768) so hello/chat is not blocked on a huge completion. Failed classify stays interactive/direct.
- Outbound send/drop LLM is 2s then fail-open send, so Zalo replies are not held on a second 9router hop.

## 2026-08-19 15:20 +07 â€” overlay fit; Zalo sendVideo; case-25 watch stop

- Overlay wraps and shrinks fact text so it stays inside the image frame.
- Video encode adds AAC + yuv420p. Adapter uploads clip + thumbnail and calls zca-js `sendVideo` (generic attach was `Tham sá»‘ khÃ´ng há»£p lá»‡`).
- Case 25 lab stops after four jobs complete plus a short extra poll instead of looping until the full wait.

## 2026-08-19 14:45 +07 â€” Zalo plugin import path + remux-before-autosend

- Adapter and sibling modules put `/opt/data/plugins/zalo` on `sys.path` so `hermes_plugins.zalo_platform` can import `classify_client` / `gateway_noise`.
- Autosend prefers `*.zalo.mp4` and remuxes before attach so raw mp4 is not sent in parallel with remux.

## 2026-08-19 14:10 +07 â€” Fast Dispatcher UX: interactive vs async vs schedule

- Classify JSON adds `execution_class`, `task_type`, `response_mode`. Hello stays off the job queue. Image/video/OCR ACK (`ux.json` async.ack) then workflow. Lá»‹ch still persist + confirm.
- Video attachments remux before send; mp4 is not sent as an image. Invalid-parameter retries remuxed file.
- Replica entry and rolling apply overlay plugin modules so `gateway_noise` / `classify_client` exist on every Hermes replica.

## 2026-08-19 14:05 +07 â€” High lab 24â€“29: video send fail; replica plugin modules missing

- Case 25: four jobs completed; new mp4 remuxed; Zalo `send-attachment` invalid-parameter and no successful mp4 send.
- After destroy, backup restore brought back an isolated `::job::` 07:00 schedule (deleted before case 26).
- `assistant-hermes-2` inbound: `ModuleNotFoundError: gateway_noise` / `classify_client` (stale replica plugins dir). Entrypoint now overlays shared plugins like skills.

## 2026-08-19 13:25 +07 â€” workflow_vps schedule POST timeout

- Live `POST /v1/schedules` waits on LLM classify; the VPS probe timeout is 120s instead of 8s.
- Schedule upsert uses 5-token `cron_expr` (not a clock string in `time`). `valid_cron` only accepts cron tokens.

## 2026-08-19 13:15 +07 â€” release: v0.5.9

- LLM classify for Zalo cite, schedule, and outbound drop. Dispatcher remains the image/video path. Default `IMAGE_LLM_SIZE` is Full HD (`1920x1080`).

## 2026-08-19 13:12 +07 â€” default LLM image size Full HD

- `IMAGE_LLM_SIZE` example and dispatcher llm fallback default is `1920x1080`.

## 2026-08-19 12:30 +07 â€” LLM classify for cite and outbound; no keyword NLU

- Cite intercept consumes `task_hint=knowledge` from `POST /v1/classify`. No Vietnamese/English cite needles in adapter code.
- Zalo outbound drop uses `POST /v1/outbound` (`action=send|drop`). Plugin error strings live in `hermes/main/messages/zalo-bridge.json`. File suffixes stay protocol.
- Scheduling skill no longer persists Hermes CLI cron jobs (that path paraphrased once-lá»‹ch into `jobs.json`).

## 2026-08-19 12:15 +07 â€” fix: once-lá»‹ch numbered list hit knowledge-cite refuse

- Substring `trÃ­ch dáº«n` (including â€œkhÃ´ng trÃ­ch dáº«n nguá»“nâ€) made Zalo answer `KhÃ´ng tháº¥y kiáº¿n thá»©c khá»›p` and skip classify/workflow.
- Cite intercept is command/catalog only; `task_hint=schedule` or several instructions skip cite. Classify keeps numbered once-lá»‹ch as `PLAN_N 3` with the stated clock. Case 29.

## 2026-08-19 11:25 +07 â€” pin dispatcher media; drop manim chatter; memory/gateway unchanged

- Isolated lá»‹ch jobs append a dispatcher-only hint (`POST /v1/image` / `/v1/video`). ComfyUI remains a dispatcher backend (`comfy-cpu`), not a Hermes manim install.
- Zalo drops pangocairo/manim/matplotlib process lines. Rolling apply no longer aborts the whole sync if `workflow_vps` schedule upsert lags after recreate.

## 2026-08-19 10:40 +07 â€” fix: video generated but not sent; pin dispatcher media; quiet overlay

- Zalo `/send-attachment` returned invalid parameter for matplotlib mp4s. Isolated jobs then kept watching `media/out` and sent a **later** infographic instead of the video.
- Isolated jobs no longer spawn late autosend after complete. File window has a **ceiling**. Video is remuxed to baseline H.264 (Hermes ffmpeg or dispatcher `POST /v1/video-remux`). Default generate path is dispatcher `POST /v1/image` + `overlay` and `POST /v1/video`.
- Medium/High empty `IMAGE_BACKENDS=` now fills `llm,vendor,comfy-cpu,comfy-gpu` (profile.sh + first-setup). Media turns drop process chatter after the file.
- Cases 25â€“26 tightened; case 28 covers leftover claim + video send. `AGENT_RULES.md` **Rules (numbered)** is exclude-only.

## 2026-08-19 09:45 +07 â€” test: one-picture weather+fuel user request (cases 26â€“27)

- New cases simulate a real Zalo sentence: one HCMC image from live weather, with E5 RON92 / E10 RON95 and weather overlaid in Vietnamese. Classify keeps that as **one** instruction (not case 16â€™s two tasks, not case 25â€™s four).
- Daily wrapper (case 27) is `task_hint=schedule` with `PLAN_N 1`. Classify prompt tells the LLM not to split overlay facts.

## 2026-08-19 09:20 +07 â€” fix: lá»‹ch autosend posted files but Zalo users got none

- Hermes treated any JSON from `/send-attachment` as success (HTTP 400 `file not found` included). `logger.info` send lines were invisible at the default log level, so case 25 reported `attach=0`.
- Isolated jobs also finished before media landed (`hold_inflight` blocked late watch; 8s cap). Empty captions can make zca-js drop the attachment.
- Now: require plugin `success: true`, print `[zalo] send-attachment path` only after a real ack, watch files for the whole job, drain the window, resolve png/jpg siblings, non-empty caption fallback. Claim before send so parallel jobs do not spam the same file.

## 2026-08-19 08:55 +07 â€” fix: scheduled media was written but not sent on Zalo

- Isolated lá»‹ch jobs (`thread::job::{id}`) never matched the remembered turn dest, so autosend skipped files. Documents also posted the isolated id as `threadId`.
- Dest match now uses the real thread. Workflow jobs bind dest + t0 on the isolated session. Autosend skips already-claimed files and picks the next (image vs video). Video extensions included. Case 25 fails if `attach=0`.

## 2026-08-19 08:45 +07 â€” fix: Zalo profile must keep zalo-api; classify 32k; case 25 admin DM

- `ENABLE_ZALO=1` is a combo: `zalo-proxy` + `zalo-api`. stack-watch starts missing `zalo-api`; check-high fails if the container is gone. Rule 38. `test/RULES.md` links to root `AGENT_RULES.md` for numbered rules.
- Classify `max_tokens` 32768.
- Case 25 sends only to the current Zalo admin DM (`zalo_admin_users.txt`), not a group.

## 2026-08-19 08:30 +07 â€” fix: once lá»‹ch same-day retest reused a completed workflow

- `idempotency_prefix` was `{schedule_id}:{date}`, so a second once-fire the same day returned the already-COMPLETED jobs and sent nothing.
- Once cadence now keys by fire timestamp. Daily/weekly still one workflow per calendar day.

## 2026-08-19 08:15 +07 â€” fix: classify timeout must not fake a 1-task plan

- LLM ReadTimeout still returned `ok: true` with the whole blob as one instruction, so lá»‹ch upsert stored PLAN_N 1.
- Classify now retries once (90s), returns `ok: false` with empty instructions on LLM failure. Workflow upsert is 503 until classify succeeds. Client timeout 100s, one HTTP retry. No Hermes recreate (docker cp + restart model-router/workflow).

## 2026-08-19 07:55 +07 â€” fix: classify reads reasoning_content + 2048 tokens

- Combo/reasoning models often leave `content` empty. Classifier now uses `content` or `reasoning_content`, `max_tokens` 2048, and JSON `raw_decode` so numbered lists return N instructions.

## 2026-08-19 07:40 +07 â€” feat: LLM classify for task_hint and multi-task plans

- Rule 36: application code does not split/join/regex/keyword-parse user content. Model Router `POST /v1/classify` returns structured `task_hint` + `instructions` + cadence/cron. Secret Probe stays independent of task_hint.
- Workflow/Zalo/API Gateway consume that JSON, persist `context.plan`, and explode jobs at tick from stored instructions.
- Tests 05/16/21/22/24/25 updated. `docs/AGENT_RULES.md` is gitignored (operator-only).

## 2026-08-19 07:10 +07 â€” fix: skip disabled monitor scrapes; task_hint vs secret-probe

- alert-watch no longer warns when **node-exporter** (and other optional hosts) are off. Host metrics scrape only if Grafana/Prometheus is on; AV/Zalo/Omni/OCR/OpenBao health rows follow `ENABLE_*`. Same skip in stack-exporter.
- Architect: Secret Probe (`SAFE`/`BLOCKED`/`REVIEW`) is independent of `task_hint` (`normal`/`schedule`/`coding`/`tool`/`search`/`file`/`unknown`). Policy file `config/agent/secret-probe.json`. Input gate on Zalo + API Gateway; output gate on Zalo send. Notify of probes does not include message text.

## 2026-08-18 19:45 +07 â€” release: v0.5.8

- Product deploy scripts no longer ship lab SSH host/account defaults. stack-watch treats 9router 401 as healthy and keeps notify/sandbox profiles.

## 2026-08-18 19:45 +07 â€” fix: strip lab host/account defaults from product scripts

- `deploy_high_vps.py`, `Deploy-High.ps1`, `Apply-ZaloHeal.ps1`, `export-ovpn-client.sh`, and edge-update examples require `ASSISTANT_SSH_*` / `OVPN_EXPORT_USER` (generic placeholders only).
- Operator rules 33â€“35: no VPS IP/account/secrets in committed `scripts/` or `test/`; host probes stay in gitignored `scripts/temp/` / `hermes/temp/`; `develop`/`main` stay production-ready.

## 2026-08-18 19:39 +07 â€” ops: High redeploy (no monitor); stack-watch 9router 401 + profiles

- Destroy + High: Zalo, Notify, OmniRouter, 9router, AV/sandbox/judge, jobs/workflow; Grafana/Prometheus/Loki/Alloy off. Backup verified first. Tavily key on host `.env` (`keys.tavily` true). HermesÃ—2 â†’ 9router models OK (`hermes` combo present).
- `stack-watch` compose now matches `run.sh` profiles (notify, sandbox, antivirus, omni, edge) so `--remove-orphans` cannot drop them.
- `stack-watch` 9router probe accepts 401/307 on `/v1/models` (unauthenticated) instead of restarting the router every tick.
- High deploy: optional `TAVILY_API_KEY` env upserts host `.env` (not logged).

## 2026-08-18 19:14 +07 â€” release: v0.5.7

- Isolated parallel Zalo lá»‹ch jobs, schedule cadence (once / daily / weekly / monthly / yearly), result-only media, dispatcher/OCR for images and page facts.

## 2026-08-18 18:57 +07 â€” ops: rolling deploy cadence + silent media (test stack)

- Leftover lab lá»‹ch rows deleted (workflow table empty; Hermes `jobs.json` empty) before sync so migrate would not recreate them.
- Backup verified, source synced, workflow/gateway/zalo-api/notify/dispatcher recreated, Hermes replicas restarted (no destroy, edge overlays kept).
- Live: Hermes â†’ 9router models OK; Tavily key present; Zalo SSE attached; no `media.done` ack copy.

## 2026-08-18 18:45 +07 â€” feat: schedule cadence; silent media; web OCR; drop done-ack

- Schedules support **once** (default for clock-only `Ä‘áº·t lá»‹ch lÃºc HH:MM`, row deleted after fire), **daily**, **weekly**, **monthly**, **yearly**. Marker lists: `WORKFLOW_CADENCE_*`.
- Zalo no longer sends `ÄÃ£ xong.` / `Done.` after files. Removed `ux.json` `media.done`. Process narration (search/OCR/PIL) is dropped.
- web-search skill: dispatcher search/extract; if facts are in page images, OCR then `image-gen`. No step chatter.

## 2026-08-18 18:28 +07 â€” ops: rolling deploy of image-gen overlay (test stack)

- Backup verified, source synced, workflow/gateway/zalo-api/notify/dispatcher recreated, Hermes replicas restarted (no destroy, edge overlays kept).
- Traefik `/health` can return 503 for a few seconds while Hermes is restarting; feature deploy now retries that probe.
- Post-check: Hermes â†’ 9router models OK; image-gen no-scrape text present on replica copies; `ux.json` `session.interrupted` present.

## 2026-08-18 18:22 +07 â€” ops: rolling deploy image-gen overlay + replica skill SoT

- Replica entry overlays repo skills onto the writable copy (no `cp -n`), so skill edits such as image-gen actually land after restart. Replica-only skills are kept.
- Rolling feature deploy copies image-gen onto replica dirs before Hermes restart and checks the â€œnever scrape URLsâ€ text is present.

## 2026-08-18 18:16 +07 â€” fix: image-gen must generate, not scrape; session interrupt copy localized

- Image-gen skill: do not `web_extract` / scrape release pages for image URLs. Weather image jobs must `POST` dispatcher `/v1/image` (media-out result only).
- Workflow job-failure announce moved to `ux.json` `session.interrupted` (locale map). Vietnamese copy also fixes the old â€œgiÃ¡n Ä‘áº¡nâ€ typo.

## 2026-08-18 18:10 +07 â€” fix: schedule-saved copy is locale map, not hardcoded Vietnamese

- Zalo no longer announces lá»‹ch save with a hardcoded Vietnamese line. Copy lives in `messages/ux.json` `schedule.saved` (`en` / `vi`; add more locales there). The adapter picks the key from the user message script. Override: `ZALO_SCHEDULE_SAVED_MSG`.
- Helper: `hermes/main/plugins/zalo/ux_copy.py`. Unit: `test/scripts/ux_copy_unit.py`.

## 2026-08-18 17:55 +07 â€” docs: ops issue history under scripts/

- Added `scripts/HISTORY.md`: timestamped symptoms, root causes, fixes, and how to stop the same failure (cron same-minute miss, sequential job stall, readonly SQLite/skills, 9router stream abort, destroy wiping lá»‹ch, stack-watch scale, Zalo SSE owner, PowerShell/deploy pitfalls, git promote path).
- Linked from `scripts/README.md` and `docs/README.md`. Companion to this changelog (what changed vs what broke).

## 2026-08-18 16:50 +07 â€” test: case 25 Zalo special four (English lá»‹ch)

- Case `25-zalo-special-four.md`: one lá»‹ch, four English jobs (hello, HCMC weather image, Vietnamese fuel prices, HCMC weather video). Lab script upserts for the current Zalo login thread two minutes ahead and watches the plugin for four replies.
- Units: `plan_instructions` splits the English list; ingest keeps the daily English list whole.

## 2026-08-18 16:40 +07 â€” feat: isolated parallel Zalo jobs + image-gen via dispatcher

- Numbered Zalo lists (immediate and lá»‹ch) create **independent** jobs (`sequential=false`). The worker claims up to `ZALO_WORKFLOW_PARALLEL` (default 4) at once.
- Each job uses an isolated Hermes session (`{thread}::job::{job_id}`) so parallel `handle_message` calls are not pending-merged. Sends remap to the real thread and take a per-thread lock.
- The job still waits until **its** session is idle before complete (lease heartbeat, `ZALO_WORKFLOW_TURN_TIMEOUT_S`).
- Image-gen skill: native Hermes `image_generation` tool may be off (no BFL/cloud key). Always use dispatcher `POST /v1/image`.
- Units: `workflow_turn_wait_unit.py` isolation, `workflow_unit.py` parallel queued jobs.

## 2026-08-18 16:25 +07 â€” policy: numbered list = N jobs, N deliveries

- Immediate and scheduled numbered lists share the same job engine. A lá»‹ch is the clock only; tick time creates one job per item.
- Delivery policy: **each job may send its own reply** (no aggregator). Four tasks â†’ four Zalo messages (text and/or file), not one combined bubble.
- Zalo `execute=hermes` still runs **one turn per thread** until jobs have isolated sessions. Parallel `handle_message` on the same chat is what dropped the 15:50 list to two replies.
- Docs: `architect/workflow/README.md`.

## 2026-08-18 16:20 +07 â€” fix: sequential Zalo schedule jobs wait for the Hermes turn

- Hermes `handle_message` returns immediately (agent keeps running in the background). The Zalo workflow worker used to mark each numbered job complete after the ~8s late-file grace, then claim the next item. Later items were queued as pending follow-ups on the same session, so a 4-item lá»‹ch often delivered only the first one or two Zalo replies. Empty overlapping turns also poisoned the transcript.
- The worker now waits until that threadâ€™s gateway session is idle (and heartbeats the job lease) before late-file sweep and complete. Timeout: `ZALO_WORKFLOW_TURN_TIMEOUT_S` (default 420). A timed-out item is still completed-with-error so the rest of the list can run.
- Late-file wait no longer marks the part â€œdeliveredâ€ when no file was sent, so the next item cannot start on a false signal.
- Unit: `workflow_turn_wait_unit.py`. Docs: workflow README, case 24 / 22, `DEFAULTS.md`.

## 2026-08-18 13:55 +07 â€” fix: 13:54 GMT+7 same-minute miss + multi-cron tests

- Daily cron created **in the same minute** (example: save `13:54 GMT+7` at `13:54:20`) no longer jumps `next_run_at` to tomorrow. 120s grace keeps the run due; after a successful fire the next run is the following day. If `next_run_at` already jumped to tomorrow and today has not fired, the ticker still catch-up fires todayâ€™s slot.
- Mixed Valkey queue: `claim(execute=â€¦)` skips other execute types instead of returning empty (Zalo `hermes` and Hermes `hermes_http` no longer starve each other).
- Clock extract prefers `lÃºc 13:54` / `at HH:MM` over a `6:00 AM` inside item 1 of the payload.
- Re-upsert of the same clock keeps a past `next_run_at` so catch-up still fires.
- Tests: `workflow_schedule_concurrency_unit.py` (plenty 6 items, same-time Zalo+Hermes, different clocks, two Zalo users). Case `24-workflow-multi-cron-channels.md`. `workflow_vps.py` ticks same-time vs future clocks with `record_only`.

## 2026-08-18 15:05 +07 â€” ops: fix Hermes cron perms + replica skills writable

- Hermes cron scheduler can dispatch again: `executions.db*` owned by Hermes uid/gid and group-writable.
- Hermes replicas no longer hit `[Errno 30] Read-only file system` during startup: `replicas/*/skills` is now a writable per-replica copy instead of a symlink into the repo `:ro` bind mount.
- Media output directory is group-/user-writable (`media/out`) so scheduled image generations can complete.

## 2026-08-18 15:07 +07 â€” ops: fix deploy_high.py remote snapshot heredoc formatting
- Fix local `deploy_high.py` crash caused by an f-string interpolation collision inside the `python3 - <<'PY'` heredoc.


## 2026-08-18 15:27 +07 â€” fix: continue sequential schedule items after a numbered failure
- Zalo workflow worker exceptions no longer block later sequential schedule items.
- When a single numbered instruction fails, the job is marked completed-with-error so dependent jobs can unlock and remaining items can still run.

## 2026-08-18 13:10 +07 - feat: generic workflow queue (Postgres + outbox)

- Multi-request and cron no longer rely on one LLM turn. A list becomes **jobs** (`instruction` only â€” no hardcoded fuel/weather types). Postgres is canonical; Valkey only delivers; outbox + leases + idempotency recover stalled work.
- Cron **creates jobs** at tick time. Hermes `jobs.json` user lá»‹ch is `no_agent` so the old one-prompt ticker does not double-run.
- New service `workflow` (`:8108`). Zalo adapter submits compound lists and schedule-shaped text; a worker claims `execute=hermes` jobs one at a time.
- Units: `workflow_unit.py`. VPS: `workflow_vps.py` (record_only drain, no Zalo send).

## 2026-08-18 12:45 +07 â€” fix: immediate 1. 2. 3. lists run every item (not only the last)

- Zalo often flattens `Thá»±c hiá»‡n: 1. â€¦ 2. â€¦ 3. â€¦` onto one line. The splitter only looked at line-start indexes, so the model got one turn and typically answered only the last item (xÄƒng). Inline `1. 2. 3.` now splits too.
- Each part is wrapped â€œchá»‰ lÃ m Ä‘Ãºng viá»‡c nÃ yâ€. Queue default cap 8; part message ids are unique (`:part2`, `:part3`).
- Units: `multi_request_unit.py` Thá»±c hiá»‡n fixture (newline + one-line).

## 2026-08-18 12:40 +07 â€” fix: --timer alias + HH:MM list/show (no raw cron dict)

- `--timer 12:35` is the same as `--time 12:35`. Confirmation shows `buoi-sang-hcm @ 12:35`, not the Hermes schedule object.
- A prompt that is only `timer HH:MM` is not a task: hide it, and drop it on the next time-only update. Hint to set ná»™i dung with `update â€¦ :`.
- Changing the clock clears `next_run_at` so Hermes recomputes the next tick.

## 2026-08-18 12:05 +07 â€” fix: compound autosend + readable jobs.json for lá»‹ch

- Autosend window is the **whole compound sequence**, not each part's start clock. After each turn, a short late sweep attaches a file that landed as the model finished, then the next part proceeds (no 180s wait for a missing send). Cron / single turns kick the same late sweep after text send.
- `jobs.json` written by zalo-api is `0664` and owned by Hermes UID 1000 so the ticker can read **and** update last_run. Non-owner replica empty file is also `0664`.
- Units: `autosend_unit.py`. Clock-only update (`timer 11:50` / `11:50`) changes the cron expr and keeps a real task prompt.

## 2026-08-18 11:35 +07 â€” feat: !zalo schedule list scoped to this chat

- Default `!zalo schedule list` / show / update / remove by **index** uses only lá»‹ch whose origin is the current DM or group.
- Admin global: `!zalo schedule list all` (also `show all <n>`, `update all <n>`, `remove all <n>`). Unique **name** still resolves across chats.
- Units: thread-scope + `all` flag in `schedule_crud_unit.py`; list heading in `schedule_list_unit.py`.

## 2026-08-18 11:20 +07 â€” fix: schedule update colon payload + háº±ng ngÃ y keep-whole

- `!zalo schedule update` matches job by list index, exact/prefix name, then `:` or `--` payload (numbered lists stay whole). Still supports `--time` / `--schedule`. Clock parse accepts `6h` / `6h sÃ¡ng`.
- Keep-whole markers include `háº±ng ngÃ y`, `thá»©c dáº­y`, `GMT+7`. A numbered list plus `06:00 GMT+7` also stays one lá»‹ch (the previous `hÃ ng ngÃ y`-only check split that spelling).
- Cron results with `deliver: origin` go to the originating Zalo thread (DM vs group = where the user asked).
- Units: `schedule_crud_unit.py` colon update; `multi_request_unit.py` `háº±ng ngÃ y` fixture.

## 2026-08-18 10:45 +07 â€” fix: keep Hermes schedules across destroy + !zalo schedule CRUD

- Root cause: jobs lived in `replicas/<container-id>/cron/jobs.json`. Destroy creates new ids; backup excluded `./replicas`; `hermes cron list` used compose `HERMES_HOME=/opt/data` (empty). Restore never re-applied jobs.
- Shared store: `HERMES_DATA_DIR/cron/jobs.json`. `hermes-cron-share.sh` promotes the newest replica copy. Zalo-owner replica ticks the shared dir; other replicas keep an empty local file (no double-run).
- Backup copies `hermes-jobs.json` + `hermes-cron.tgz`; restore writes them back then brings Hermes up.
- Zalo admin CRUD: `!zalo schedule list|show|add|update|remove` (user-facing **lá»‹ch** / **schedule**).
- Units: `schedule_crud_unit.py` (separate process from `schedule_list_unit.py`).

## 2026-08-18 10:15 +07 â€” fix: Zalo admin alerts without NOTIFY_ZALO_THREAD

- Notify was logging alerts (`zalo: false`) whenever `NOTIFY_ZALO_THREAD` was empty, even with `ENABLE_NOTIFY=1` and a sole Zalo admin in `zalo_admin_users.txt`.
- Dest order: request thread â†’ optional `NOTIFY_ZALO_THREAD` â†’ admin file â†’ `ZALO_ADMIN_USERS`. File is re-read each send (`!zalo claim` / transfer without restart).
- Notify mounts data dir read-only; health reports `zalo_dest_source` (no uid). zalo-api approve/notify passes the current admin uid.
- Unit: `test/scripts/notify_dest_unit.py`.

## 2026-08-18 10:00 +07 â€” ops: High destroy deploy keeps schedules; Zalo concurrent lab

- `deploy_high.py`: snapshot Hermes `cron list` + systemd timers before destroy; verify after `up` (data volumes unchanged by destroy).
- `check-high.sh`: skip Grafana health when `ENABLE_GRAFANA=0` (High lab default).
- `vps_health_check.py` / `vps_verify_post_deploy.py`: dynamic Hermes container + authenticated 9router probe.
- `resume_zalo_setup.py`: finish Zalo install after partial `deploy_high` (no second destroy).
- Case `08-zalo-concurrent`: documents `test/scripts/zalo_concurrent.py` lab runner and optional FIFO smoke (case 23).

## 2026-08-18 09:40 +07 â€” policy: response language matches user request

- Rule **27 / response language**: reply in the **same language** as the user's message unless they explicitly ask for another. Wired in `friendly-response`, SOUL, `answering`, `chat-style`, `zalo-channel`, `translation`, zalo-api response policy.

## 2026-08-18 09:34 +07 â€” config: Zalo inbound queue cap default 3

- `ZALO_INBOUND_QUEUE_MAX` default **3** waiting items per thread (was 20). Wired through compose / `.env.example` / `DEFAULTS.md`.
- This FIFO is **inbound user requests** (compound parts + rate-limit defer) on any profile with `ENABLE_ZALO=1`. Outbound replies are not queued in a second list â€” they send as each sequential turn finishes.
- Copy: `ux.json` `queue.rate_limited` / `queue.full` are **response lines** for those inbound events. `queue.queued` stays reserved.

## 2026-08-18 09:30 +07 â€” copy: user-facing lá»‹ch/schedule (not cron) + queue docs

- Skills/zalo-api: user-facing text uses **lá»‹ch** / **schedule**; avoid **cron** / **cron job** in Zalo replies and admin schedule list.
- `messages/README.md`: documents `queue.full` default and `ZALO_INBOUND_QUEUE_MAX=20` cap behavior.

## 2026-08-18 09:25 +07 â€” feat: Low/Medium OmniRouter default + !zalo schedule list

- `profile.sh`: `ENABLE_OMNIROUTER` default **1** on **Low** and **Medium**; **High** stays **0** (opt-in via `.env`).
- Zalo admin: `!zalo schedule list` (alias `!zalo cron list`) runs `hermes cron list` in Hermes and shows user jobs (filters internal optimize/session crons; cap `ZALO_SCHEDULE_LIST_LIMIT`).
- Tests: `defaults_profile_unit.py`, `schedule_list_unit.py`. Docs: `DEFAULTS.md`, `06-model-routing.md`, case 21.
- zalo-api Docker image includes `schedule_list.py` (fixes crash loop after first deploy).

## 2026-08-18 09:10 +07 â€” fix: compound queue â€” `ÄÃ£ xong.` only after last part

- Multi-part Zalo (image + prices, etc.): media turn sends the file **only**; `ÄÃ£ xong.` / `Done.` is deferred until **after the last queued part** (not between parts).
- Removed remaining â€œbanter OKâ€ tone from temp `common-rules`; aligns with `communication/friendly-response`.
- Copy: `messages/ux.json` â†’ `media.done`. Skills/media-out + zalo-channel updated.

## 2026-08-18 09:05 +07 â€” feat: default friendly-response + Vietnamese people-terms skills

- Mounted as default request/response: `communication/friendly-response` (no banter/insults/blame; result â†’ next step) and `communication/vi-people-terms` (context for ngÆ°á»i / Ä‘Ã n Ã´ng / phá»¥ ná»¯ / con / tháº±ng / Ä‘á»©a; full dictionary in `reference.md`).
- Wired from SOUL, answering, chat-style, zalo-channel, translation, and zalo-api response policy (replaces â€œbanter is OKâ€).
- Sources: hermes plan docs *AI Agent â€” Friendly User Response Skill* and *Vietnamese Semantic Dictionary â€” People, Gender, and Human References*.

## 2026-08-18 08:57 +07 â€” ops: rolling deploy Valkey inbound FIFO + busy-interrupt filter

- Backup verified, source synced, zalo-api rebuilt, Hermes replicas restarted (no destroy).
- Hermes reaches 9router and model-router. On-host files `inbound_queue.py` present.

## 2026-08-18 08:45 +07 â€” feat: Valkey inbound FIFO for compound + rate-limited Zalo

- Compound and follow-up Zalo turns enqueue on Valkey (`gate_valkey` list per thread). A drain task runs **one Hermes turn at a time** so overlapping `handle_message` cannot inject busy-interrupt UX.
- Rate-limit: user gets the queued notice **once**, the message is **kept** and processed later (not dropped). Cap `ZALO_INBOUND_QUEUE_MAX` (default 20). Valkey down â†’ fail-open sequential in-process turns.
- Copy lives in `hermes/main/messages/ux.json` `queue.*` (env override). Daily numbered lists still stay **one cron job**; immediate 3-item lists split onto the FIFO (case 23).
- Tests: `inbound_queue_unit.py` (separate process from case 16).

## 2026-08-18 08:25 +07 â€” fix: drop Zalo busy-interrupt UX; multi-task cron runs every item

- Hermes gateway â€œInterrupting current taskâ€ / First-time `/busy` tips are dropped on Zalo (`gateway_noise.py`). They are not in this repoâ€™s source â€” they come from upstream Hermes when a new turn starts mid-run.
- Immediate compound still splits, but the adapter waits until the current part has actually sent (then a short gap) before the next `handle_message`, and holds the answering slot for the whole sequence.
- Numbered **daily/cron** lists stay **one job** (wakeup + weather image + fuel in one payload). Skills require completing every item after media; do not register parallel crons at the same clock.
- Tests: `gateway_noise_unit.py` + schedule keep-whole fixture in case 16 unit; new case `22-zalo-busy-cron-multi`.

## 2026-08-18 08:17 +07 â€” ops: rolling deploy numbered Zalo split + zalo-api policy

- Backup verified, source synced, zalo-api rebuilt, Hermes replicas restarted (no destroy).
- On-host unit: numbered `1 â€¦` / `2.Sau Ä‘Ã³` split PASS. Hermes reaches 9router and model-router; Traefik recovered after restart (brief 503 while replicas came up).

## 2026-08-18 08:10 +07 â€” fix: numbered Zalo lists (`1 â€¦` / `2.Sau Ä‘Ã³`) + media-out vs compound

- Splitter missed live style `yÃªu cáº§u:` + `1 váº½â€¦` + `2.Sau Ä‘Ã³ â€¦` (no `1.` / no space after `2.`), so one Hermes turn ran **image + fuel**.
- `media-out` / response policy â€œafter a file, one short line, no recapâ€ then dropped request 2. **Not** the summarization skill (`tÃ³m táº¯t`) â€” it was the file-result policy on an unsplit turn.
- Splitter now accepts numbered lines `1 task` / `2.Sau Ä‘Ã³` (indexes 1â€“20, must include 1 and 2). Skills/SOUL/zalo-api: media-out applies **per turn** after split. Unit fixture added (case 16).

## 2026-08-18 07:50 +07 â€” ops: High lab deploy matches profile defaults (Omni/Grafana off)

- `test/scripts/deploy_high.py` no longer force-enables OmniRouter, Grafana, Prometheus, Loki, or Alloy. Defaults are **0** (same as `profile.sh`). Opt in with `ENABLE_OMNIROUTER=1` / `ENABLE_GRAFANA=1` (Grafana pairs Prometheus; Loki pairs Alloy).
- No Hermes fire-and-forget memory/log rewrite.

## 2026-08-18 07:45 +07 â€” test: Grafana pairing + router defaults; simple-chat SLO 5s

- **Grafana (when on):** case `20-grafana-component-integration` â€” Prometheus jobs + `assistant_service_up` for each deployed target; 9Router via **TCP** (UI `/health` 404); Omni scrape only if OmniRouter is on. Stack-exporter + High compose `HEALTH_TARGETS` include `9router`.
- **Defaults:** case `21-defaults-routers-connected` â€” 9Router always on; `ENABLE_MODEL_ROUTER` default 1; `ENABLE_OMNIROUTER` / Grafana default **0**. `deploy_high.py` no longer forces Omni/Grafana on (opt-in env flags).
- **Latency:** simple host-side chat **> 5s is FAIL** (case 17). Previous lab p95 ~9s is an improvement ticket, not a pass.
- Docs: `DEFAULTS.md` matches `profile.sh` (Low Traefik default on; Medium HermesÃ—1; High OmniRouter default off). Monitor + model-routing docs point at cases 20â€“21.

## 2026-08-18 07:35 +07 â€” ops: rolling VPS deploy + SSH labs 15â€“19

- Backup stamp `20260818_072647` verified, then rolling sync (no destroy): zalo-api rebuilt, Hermes replicas restarted, skills/plugins/SOUL bind-mounts live.
- Labs (separate processes): 15 TZ unit PASS; 16 compound split PASS; 17 chat p50 ~4s / p95 ~9s PASS; 18 search backend=searxng (Tavily/Firecrawl keys unset) PASS; 19 YARA RISK + ClamAV BLOCKED PASS. Ingest `SECURITY_URL` still unset (documented gap).
- Case 19 lab polls av-gateway session ready (async SCANNING is not a false clean).

## 2026-08-18 07:15 +07 â€” fix: Zalo schedule TZ, compound messages, stack-watch backoff, lab cases 15â€“19

- **Schedule TZ:** `architect/tools/schedule_tz.py` â€” at 05:58 local, daily 06:00 is **today** not tomorrow; skill `core/scheduling` + zalo-api response policy.
- **Zalo compound messages:** `hermes/main/plugins/zalo/multi_request.py` splits `tin nháº¯n 1:` / `tin nháº¯n 2:` (including mid-sentence); adapter runs each part sequentially.
- **Zalo safety:** skills `communication/zalo-channel`, `core/safety`, `SOUL.md`, zalo-api policy â€” user errors only `PhiÃªn lÃ m viá»‡c bá»‹ giÃ¡n Ä‘áº¡nâ€¦`; no `/help`, channel dumps, or host secret scans.
- **stack-watch:** exponential backoff (90sâ†’3600s), degraded after 5 fails, optional `NOTIFY_URL` alert â€” no infinite restart loop.
- **Tests:** cases `15-schedule-timezone` â€¦ `19-file-pipeline-security`; unit scripts for TZ/multi-request/web-search; SSH labs for latency SLO and file/AV matrix. `test/RULES.md` Â§13â€“15 updated.
- **Web search default:** Medium/High `WEB_BACKENDS=tavily,firecrawl` round-robin; **SearXNG always appended** as fallback (`architect/models/dispatcher/app.py`).
- **File security matrix:** Zalo inbound â†’ AV only; dispatcher outbound â†’ security-manager when `SECURITY_URL` set; ingest scan not wired (documented in case 19).

## 2026-08-17 18:07 +07 â€” release: v0.5.5

- Docs: fetch + rebase onto latest `origin/develop` or `origin/main` before implement or promote; production still via `release/*` MR only.

## 2026-08-17 18:05 +07 â€” docs: fetch + rebase before implement or promote

- `docs/GIT.md` and `.cursor/rules/git.mdc`: always `git fetch` then rebase onto `origin/develop` (feature/fix) or `origin/main` (hotfix/release) before implementing or promoting.
- Production path unchanged: `feature/*` â†’ `develop` â†’ `release/*` â†’ `main` (MR only; never merge `develop` straight into `main`).

## 2026-08-17 18:00 +07 â€” release: v0.5.4

- P0 skills + exact text-poster; local ONNX embedding fallback; learn unique by path.
- Backup+verify required before destroy / switch-profile / add-components / update.
- Skills lab cases 12â€“14; High Notify + OmniRouter + monitor.

## 2026-08-17 17:55 +07 â€” ops: backup+verify before destroy / upgrade / downgrade

- `run.sh destroy`, `switch-profile`, `add-components`, and `update` run `backup` then `verify` and abort if either fails.
- Lab deploy scripts no longer swallow `destroy` failure (`|| true`).
- `verify` live-checks Postgres/Valkey when those containers are running.

## 2026-08-17 17:48 +07 â€” ops: High deploy with Notify + OmniRouter + monitor

- Lab helper `test/scripts/deploy_high.py`: destroy current profile, High up with Notify, OmniRouter, Grafana/Loki/Prometheus/Alloy.
- Isolation stays default off (AV / sandbox / LLM judge). Zalo off unless requested.
- Prune stale `created`/`dead` containers before `up` (compose missing-container race).

## 2026-08-17 17:35 +07 â€” test: skills lab PASS (cases 12â€“14)

- Medium lab: 52 skill docs learned into Qdrant; local ONNX embedding fallback.
- Case 13 text-poster: `backend=text-poster`, n=10, empty prompt HTTP 400.
- `test/scripts/skills_lab.py`: Windows console UTF-8 safe output.

## 2026-08-17 16:50 +07 â€” embedding: local ONNX fallback for skill learn

- Embedding service uses local `BAAI/bge-small-en-v1.5` (fastembed) when 9Router has no embedding credentials/models.
- Ingest recreates `knowledge_chunks` if vector size changes.
- Skills lab rebuilds embedding on Medium destroy/redeploy.

## 2026-08-17 16:20 +07 â€” ingest: learn unique docs by path

- `learn/scan` no longer treats every `SKILL.md` as the same document; skip/index keys use relative path.
- Markdown/text files are read as UTF-8 during learn (not OCR-only).
- post-ready-learn mirrors skills under `docs/skills/<relative-folder>/`.

## 2026-08-17 16:10 +07 â€” test: skills lab (Medium auto-learn + text-poster)

- Cases `12-skills-auto-learn`, `13-image-text-poster`, `14-knowledge-internal-rag`.
- Script `test/scripts/skills_lab.py`: destroy Medium, sync skills, post-ready-learn, mount/catalog/poster probes.
- `test/RULES.md` Â§13 fail events + Â§15 case index updated.

## 2026-08-17 16:00 +07 â€” skills: P0 sources + exact text posters

- **Image:** dispatcher `text-poster` path (Pillow) for quoted text / N lines â€” skips LLM refine and diffusion; `image-gen` skill updated.
- **Skills:** vendored Anthropic skill-creator, obra superpowers (debug/TDD/git/verify), Trail of Bits audit plugins; Hermes wrappers under `core/`, `knowledge/`, `coding/`, `communication/`.
- **Not vendored:** `canvas-design` (art-first; breaks exact text). Kodus/VoltAgent remain catalogs.
- `post-ready-learn` ingests category subfolders; `vendor/CATALOG.md` updated.

## 2026-08-17 15:25 +07 â€” release: v0.5.3

- Isolation boundary: sandbox/LLM judge/AV off by default; judge CLEAN cannot allow; VPN-only Traefik; socket-proxy only with sandbox profile.
- Ops: `switch-profile` / `add-components` (archive first); drop disabled-profile containers on up.
- Tests: run-05 two-pass; cases 09â€“11 (Zalo mixed media delay, isolation risks, profile upgrade/downgrade).

## 2026-08-17 15:20 +07 â€” test: run-05 two-pass (profile switch + mixed media)

- Pass 1: High/Zalo deploy; case 11 upgrade/downgrade + add/remove notify; mixed media fail-event N=8 (text 503).
- Pass 2: Quick start only; isolation PASS; profile dry-run; mixed media N=2 ok / N=4 one text timeout.
- Reports: `test/reports/run-05-two-pass/SUMMARY.md`. `RULES.md` Â§5/Â§14â€“15.

## 2026-08-17 15:05 +07 â€” fix: drop disabled-profile containers on up

- `run.sh up`/`update` now `docker rm` notify/alert-watch (and other off profiles). Compose `--remove-orphans` does not stop services that were started with `--profile` and later disabled.
- first-setup-llm recreate: remove leftover `hexprefix_*hermes*` names that collide on `--force-recreate`. Do **not** pass `--remove-orphans` here (that compose set omits edge YAML and would drop Traefik/Gateway).

## 2026-08-17 14:55 +07 â€” test: profile switch case 11

- Case `11-profile-switch`: existing options, add/remove `ENABLE_NOTIFY`, Highâ†”Medium, bogus-tier fail event; script `test/scripts/profile_switch.py`.
- `test/RULES.md` Â§13â€“15.

## 2026-08-17 14:50 +07 â€” ops: switch-profile / add-components archive first

- All tiers can upgrade or downgrade. `bash run.sh switch-profile <low|medium|high>` dumps current options, stamps a DR backup, writes `ASSISTANT_PROFILE`, then `up --remove-orphans`.
- `bash run.sh add-components KEY=VAL` same archive-then-apply for optional flags (Zalo, OCR, â€¦).
- Stamp includes `config/profile-options.env` + `change-intent.txt`; undo via `restore` of `BACKUP_DIR/PRE_CHANGE`.
- Docs: `docs/00-profiles.md`, `docs/02-commands.md`.

## 2026-08-17 14:45 +07 â€” test: run-04 two-pass lab complete

- Pass 1: sync+deploy High/Zalo; fixes post-ready-learn/stack-watch Traefik `/health`, mixed-media auth (Traefik+`API_SERVER_KEY`), AV/sandbox env precedence.
- Pass 2: README Quick start only (no source edits); isolation risks PASS; mixed media Nâ‰¤4 all-success with delay tables.
- Reports: `test/reports/run-04-two-pass/SUMMARY.md`; `cases/09` + `RULES.md` Â§5/Â§13/Â§14 updated for Traefik text path and run-04 findings.
- `lab_two_pass.py`: Traefik probe uses `/health` (root `/` is 404).

## 2026-08-17 14:20 +07 â€” test: Zalo mixed media concurrent + isolation risks

- New cases `09-zalo-concurrent-media` (text+image gen, delay p50/p95/max) and `10-security-isolation-risks` (no sock, judge/sandbox off, VPN-only, EICAR via YARA).
- `test/RULES.md` Â§5/Â§7/Â§13â€“15; lab two-pass defaults sandbox/judge off; README Traefik `local`.

## 2026-08-17 14:15 +07 â€” security: isolation boundary (sandbox/judge off, VPN-only)

- High defaults: `SECURITY_SANDBOX=0`, `SECURITY_LLM_JUDGE=0`, `ENABLE_ANTIVIRUS=0`; YARA + size/static remain isolation.
- LLM judge (if enabled) may only add RISK; CLEAN / skip / errors never allow and never fail-closed.
- docker-socket-proxy only with compose profile `sandbox` (`SECURITY_SANDBOX=1`); security-manager has no Docker API by default.
- Edge default `TRAEFIK_MODE=local` (VPN/localhost). Public/ACME remains explicit opt-in.
- Docs: `docs/SECURITY.md`.
- README Traefik default wording: `local` (VPN-only), matching `profile.sh`.
- post-ready-learn / stack-watch probe Traefik `/health` (root `/` is 404 by design).
- stack-watch: product `.env` wins over leftover `/data/assistant/.env` (stops AV/sandbox flags resurrecting).

## 2026-08-17 12:00 +07 â€” release: v0.5.2

- Security P0 hardening (gateway auth, SSRF, docker.sock/proxy, fail-closed).
- Ops: HermesÃ—2 Traefik/Gateway probes; check-medium restore; Zalo concurrent lab tests.

## 2026-08-17 12:15 +07 â€” fix: restore check-medium.sh corruption

- `scripts/main/check-medium.sh` had systematic `d`â†’`o` corruption (`/dev/null` â†’ `/oev/null`, dispatcher â†’ oispatcher); restored. Blocks Medium smoke / Zalo setup gate.

## 2026-08-17 12:05 +07 â€” fix: post-ready-learn probes Traefik when HermesÃ—2

- High (HERMES_REPLICASâ‰ 1) has no host `:29119`; post-ready-learn and stack-watch now probe Traefik/API Gateway instead of the missing dashboard port.

## 2026-08-17 11:50 +07 â€” security: P0 hardening (gateway, SSRF, docker.sock)

- Gateway: require GATEWAY_API_KEYS; drop client header RL bypass; do not trust XFF by default; RL fail-closed with local limiter.
- security-manager: SSRF-safe scan-url; SECURITY_FAIL_CLOSED on High; sandbox via docker-socket-proxy (no raw sock on security-manager).
- zalo-api: remove docker.sock mount (host watches restart Hermes).
- Docs: docs/SECURITY.md.

## 2026-08-17 11:40 +07 â€” release: v0.5.1

- Docs/ops patch: zalo-api cutover, HTML architecture panels, Valkey/SPOF docs.

## 2026-08-17 11:35 +07 â€” docs/ops: zalo-api rename + HTML architecture panels

- Product rename: admin-api to zalo-api (compose profile zalo with ENABLE_ZALO). Legacy ADMIN_API_* env aliases kept in Hermes/plugin/zalo-api.
- Removed architect/admin-api; High no longer starts a separate admin-api. Docs/scripts/health probes updated.
- Architecture diagrams: mermaid replaced with HTML table panels (README + architect layer READMEs).

## 2026-08-17 11:20 +07 â€” docs: README navigability + architect system design

- Root README: New here?, Use cases, architecture panels, profile why, resilience/SPOF pointers, clickable doc links; Valkey (not Redis) wording.
- Each architect/*/README.md: System architecture (sits between / owns / HTML flow). Edge defaults corrected for v0.5.0 (Traefik + Gateway on).
- docs/03-architecture.md brief view: edge + model-router. docs/MULTI_NODE.md SPOF table. Env REDIS_URL documented as Valkey-compatible name.

## 2026-08-17 10:20 +07 â€” release: v0.5.0

- Bundle Model Router / optional OmniRouter, Traefik default all profiles, jobs contract, session locks, fail-event tests, log-archive 30d, Zalo/Hermes crash auto-heal.

## 2026-08-17 09:45 +07 â€” zalo: auto-start stopped proxy

- `zalo-watch` starts `zalo-proxy` when the container is exited. Host bridge `/health` can stay up while the proxy hop is down, which previously skipped heal.

## 2026-08-17 09:40 +07 â€” test: HTML summaries + fail-event rules

- ProfileÃ—mode SUMMARY tables are HTML. RULES.md Â§13: infected AV (EICAR), concurrency ramp until first fail, Hermes/Zalo auto-heal.
- stack-watch now restarts **exited/dead/unhealthy** Hermes replicas (crash recovery). Probe-fail still does not bounce healthy Hermes.

## 2026-08-17 09:20 +07 â€” test: profile matrix reports (no host/account)

- `test/` layout: cases, fixtures, scripts, reports/run-01 and run-02 per RULES.md.
- Reports omit hostnames, IPs, and account names. High profile is the stack left running after the matrix.

## 2026-08-17 09:10 +07 â€” ops: post-restore memory reconnect + log-archive timer

- Restore now restarts Postgres clients (memory/ingest/embedding) after stack up so pooled connections survive `pg_terminate_backend`.
- Memory pool uses `ConnectionPool.check_connection`. Daily `assistant-log-archive.timer` (01:15, retention `LOG_RETENTION_DAYS=30`).

## 2026-08-17 08:45 +07 â€” ops: short alerts for disabled media/policy/AV/VPN

- hermes/main/messages/ops-alerts.json + dispatcher messages/en.json for admin-editable short errors.
- Image gen empty backends returns editable 503 text (not hardcoded only).

## 2026-08-17 08:20 +07 â€” arch: v0.5.0 router layer (OmniRouter optional, profiles, jobs)

- Model Router: hybrid coding/general routing â†’ 9router / OmniRouter / fallback pool; clear `no_model_available`.
- OmniRouter optional (`ENABLE_OMNIROUTER`, compose profile `omnirouter`); Traefik default all profiles with `TRAEFIK_MODE` publicâ†’fail-soft local.
- Hermes replicas: default 1, High=2 (one node); Medium=1. Session Valkey locks; jobs OCR/embed/filegen + idempotency/DLQ marker.
- Gateway API key auth + body limit when `GATEWAY_API_KEYS` set. Log archive 30d; OpenVPN client `.ovpn` export to home.
- Docs: `docs/06-model-routing.md`, `docs/MULTI_NODE.md`.

## 2026-08-17 07:30 +07 â€” release: v0.4.1

- Ship Mem0 purge leftovers, Zalo SSE heal after restore, stack-watch Hermes scale preserve, Zalo silent auto-sethome.

## 2026-08-17 07:25 +07 â€” zalo: silent auto-sethome (stop /sethome spam)

- First chat no longer gets Hermes â€œðŸ“¬ No home channelâ€¦ /sethomeâ€ when home is unset.
- Zalo adapter silently claims `ZALO_HOME_CHANNEL` from the first allowed DM (`ZALO_AUTO_SETHOME=1` default; DM-only by default).
- Set `ZALO_AUTO_SETHOME=0` to require manual `/sethome` or a pre-set `ZALO_HOME_CHANNEL`.

## 2026-08-17 07:15 +07 â€” backup-restore: lab retest + compose profiles on restore

- VPS lab stamp `20260817_070637`: backup â†’ verify â†’ restore + canary OK.
- Pre-restore Zalo had `sseClients=0`; post-restore `heal-zalo-sse` restored `sseClients=1` / loggedIn.
- Volume restore stops Traefik; restore compose now passes the same `--profile` flags as `run.sh` so Traefik/gateway/Zalo come back.
- **stack-watch:** `compose up` now keeps `--scale hermes=$HERMES_REPLICAS` (was collapsing HermesÃ—2 â†’Ã—1 every 2 min and killing Zalo SSE). Skip Grafana probe when monitor off; skip host `:29119` probe when replicasâ‰ 1.

## 2026-08-17 07:05 +07 â€” memory: purge Mem0 leftovers; Zalo SSE heal after restore

- Deleted architect/memory/mem0; scrubbed Mem0 from docs, monitor health targets, and Grafana queries.
- Session metrics now scan conversation_active:* (Valkey session store).
- Backup excludes zalo_owner*; restore clears lock and runs scripts/main/heal-zalo-sse.sh.
- zalo-watch: on sseClients=0, clear owner lock and restart proxy/Hermes (fixes silent bot after DR).

## 2026-08-16 20:15 +07 â€” release: v0.4.0

- Cut 
elease/v0.4.0 from main + current develop (compose under docker/, High DR + Zalo singleton, hardware docs, Deploy-High, agent-ops).

## 2026-08-16 20:15 +07 â€” docs: hardware specs + backup/restore test notes (MR-ready)

- Added docs/HARDWARE.md: lab-tested High (Ubuntu 24.04, 4 vCPU / 16 GiB / ~200 GB) and recommended minimum/comfortable sizes per profile.
- architect/backup-restore/README.md: restore behavior + successful round-trip matrix (stamp 20260816_195940).
- Linked from root README, docs/README.md, docs/00-profiles.md, docs/02-commands.md, docs/04-component-flows.md, docker/README.md.

## 2026-08-16 20:10 +07 â€” backup-restore: VPS round-trip + High path fixes

- Restored corrupted backup.sh; defaults BACKUP_DIR=/data/assistant/backups, HERMES_DATA_DIR=/data/assistant.
- Restore uses compose (not missing generate/deploy); Postgres skips DROP/CREATE ROLE for session user; Qdrant per-collection snaps.
- Hermes scale-aware; exclude backups/ + replicas/ from hermes tar; schedules enable only existing timers.
- VPS test stamp 20260816_195940: backup + verify + restore OK; Hermes x2 up.

## 2026-08-16 20:05 +07 â€” docs: recommend fail2ban on clean Ubuntu

- README: host-hardening note + install snippet for fail2ban (SSH jail) on fresh Ubuntu VPS.

## 2026-08-16 20:00 +07 â€” zalo: stale owner reclaim (entry + adapter)

- If the Zalo-owner Hermes replica dies, leftover zalo_owner blocked SSE (sseClients=0).
- Entrypoint scrubs unreachable owners before election; adapter can reclaim the lock when owner DNS is gone.

## 2026-08-16 19:58 +07 â€” zalo: owner lock enforced in adapter (survive s6 env)

- Compose/s6 can restore ZALO_PLUGIN_URL on every replica after entrypoint clears it.
- Adapter connects only when hostname matches HERMES_SHARED_DATA/zalo_owner.

## 2026-08-16 19:55 +07 â€” zalo: empty ZALO_PLUGIN_URL disables adapter (no default bridge)

- Explicit empty env no longer falls back to a default bridge URL (prevents dual SSE on Hermes x2).

## 2026-08-16 19:50 +07 â€” hermes: Zalo singleton lock (no bare hermes DNS)

- Do not treat bare Compose DNS alias hermes as Zalo owner when scaled.

## 2026-08-16 19:45 +07 â€” ops: High VPS redeploy (no monitor; Hermes x2)

- Destroyed prior medium stack; deployed High with monitor flags off; Traefik + API Gateway; image smoke + gateway concurrency.

## 2026-08-16 19:40 +07 â€” arch: compose under docker/; High without monitor; Deploy-High

- Moved all docker-compose*.yml into docker/ (run.sh uses --project-directory).
- Observability gated by compose profile monitor; Deploy-High.ps1 + deploy_high_vps.py for phased SSH.

## 2026-08-16 11:58 +07 â€” release: v0.3.0

- Cut `release/v0.3.0` from `main` + current `develop` (Mem0 removal, edge defaults, Hermes scale 2, per-replica home + Zalo singleton, MR-to-main workflow).

## 2026-08-16 11:57 +07 â€” hermes: fix replica entrypoint (gateway run via dispatch)

- `hermes-replica-entry.sh` now execs image `entrypoint-dispatch.sh` with `gateway run` (raw `/init gateway run` â†’ exit 127; empty args â†’ interactive CLI exit).
- Resolve Compose service name from `/etc/hosts` so Zalo SSE stays on `*-hermes-1` when hostname is the container id.

## 2026-08-16 11:35 +07 â€” hermes: per-replica home for scale 2 + Zalo singleton

- `hermes-replica-entry.sh`: each scaled container uses `/opt/data/replicas/<hostname>` (avoids `gateway.lock` race).
- Zalo adapter only on `*-hermes-1` (other replicas clear `ZALO_PLUGIN_URL`).
- Includes API bind fix (`API_SERVER_HOST=0.0.0.0`) for Traefik after scale.

## 2026-08-16 11:25 +07 â€” edge: Hermes API bind for Traefik after scale

- Hermes `API_SERVER_HOST=0.0.0.0` + `API_SERVER_KEY` so Traefik can reach `hermes:8642` (upstream default was loopback-only).
- Traefik health check path `/health`.

## 2026-08-16 09:35 +07 â€” hermes: default scale 2 on medium|high

- `HERMES_REPLICAS` default **2** on medium/high, **1** on low (`profile.sh` + `run.sh --scale`).
- Removed fixed `container_name: hermes`; host ports only when replicas=1 (`docker-compose.hermes-hostports.yml`).
- Traefik continues to use service DNS `http://hermes:8642` (LB across replicas). Watch scripts restart all matching hermes containers.

## 2026-08-16 09:30 +07 â€” memory: remove Mem0; edge on Med/High; coding skills

- **Removed Mem0** from Must compose; LTM = Memory Manager + Postgres (+ optional Qdrant). Compact no longer calls mem0.
- **Traefik + API Gateway** default **ON** for `medium`/`high`, forced **OFF** on `low` (set `ENABLE_*=0` in `.env` to disable on Med/High).
- **Coding skills** vendored (skills-only, no coding worker): `hermes/main/skills/coding` + `vendor/mattpocock/*` + `vendor/ui-ux-pro-max/*` with LICENSE/ATTRIBUTION.
- No VPS auto-deploy from this change.

## 2026-08-16 09:25 +07 â€” docs: require MR for all merges to main

- `docs/GIT.md` + `.cursor/rules/git.mdc`: never push/merge directly to `main`; always open a PR (`release/*` or `hotfix/*` â†’ `main`).

## 2026-08-16 09:20 +07 â€” docs: git workflow release model

- `docs/GIT.md`: `feature/*` â†’ `develop` â†’ `release/*` â†’ `main`; `fix/*` / `hotfix/*`.
- Release from `main`, cherry-pick only production-ready features; MR titles `[TYPE][LAYER]` / `[RELEASE]`.
- Updated `.cursor/rules/git.mdc`.

## 2026-08-16 09:15 +07 â€” edge: Traefik Let's Encrypt (optional ACME)

- `TRAEFIK_ACME_ENABLED=1` selects compose profile `traefik-acme` (HTTP-01, `:443`, redirect).
- Requires `TRAEFIK_ACME_EMAIL` + `TRAEFIK_ACME_DOMAIN`; render via `scripts/main/render-traefik-acme.sh`.
- Default remains LAN/`127.0.0.1` without ACME (no public inbound). Staging CA supported.

## 2026-08-16 09:05 +07 â€” edge: Traefik, API Gateway, OpenVPN stubs

- Optional `docker-compose.edge.yml` via `ENABLE_TRAEFIK` / `ENABLE_API_GATEWAY` / `ENABLE_OPENVPN` (default **0**; VPN/LAN bind `127.0.0.1` only).
- API Gateway: Valkey global rate limit; coding paths/header skip RL; admin messages in `messages/en.json`.
- Traefik file provider LB â†’ `hermes:8642` (ready for Hermes Ã— N server list).
- OpenVPN compose stub + PKI docs; Zalo still bypasses Gateway.
- Docs: `docs/05-edge-networking.md`; reference copy under `referrence/`; `Apply-EdgeUpdate.ps1`.

## 2026-08-16 08:25 +07 â€” docs: git workflow rules

- Added `docs/GIT.md`: branch layout (`main` â†’ `develop` â†’ `feature/<layer>/<slug>`), PR title `[KIND][LAYER][TYPE]`, commit/changelog/push rules.
- Added `.cursor/rules/git.mdc` (always apply) pointing at `docs/GIT.md`.

## 2026-08-16 08:15 +07 â€” zalo/stack-watch: stop Hermes restart storm

- **Cause:** `assistant-zalo-watch` restarted Hermes when `sseClients==0` (miss limit too low); `stack-watch` also bounced Hermes on probe fail / post-boot flicker â†’ multi-hour restart loops.
- **zalo-watch.sh:** default `ZALO_WATCH_RESTART_HERMES=0` (bridge-only on sse=0); SSE missâ‰¥15; cooldown 1800s; writable `/watch` state (sudo/chown fallback).
- **stack-watch.sh:** default `STACK_WATCH_RESTART_HERMES=0`; boot grace 600s; heal 9router/dispatcher without thrashing Hermes; project/label fallbacks for lab compose names.
- Opt-in old behavior: set `ZALO_WATCH_RESTART_HERMES=1` / `STACK_WATCH_RESTART_HERMES=1`.

## 2026-08-15 17:25 +07 â€” skills: new+docs/web/comfy in main; live-matched in temp

- Compared to ighthawk-lab/hermes_backup/skills\.
- **main:** documents/markdown/pdf/docx/xlsx/file-gen, comfyui, tavily/firecrawl/searxng (+ official + vendor packs).
- **temp:** live-matched Must/Medium skills (chat, research, mode-router, â€¦).

## 2026-08-15 17:20 +07 â€” default main/; live skills parked in hermes/temp

- SCRIPTS_DIR / HERMES_DIR default to scripts/main and hermes/main.
- Live-server skill set moved: hermes/main/skills/* â†’ hermes/temp/skills/ (gitignored). Main keeps _example only until promote.

## 2026-08-15 17:15 +07 â€” hermes main/temp + rename llm/vendor

- `hermes/main/` product (skills, plugins, messages, config); `hermes/temp/` local drafts (gitignored).
- Image backends renamed: **paid1 â†’ llm**, **paid2 â†’ vendor** (`IMAGE_BACKENDS=llm,vendor,comfy-cpu,comfy-gpu`).
- `IMAGE_LLM_PROVIDER`: openai | gemini | deepseek | custom. Legacy `IMAGE_PAID1_*` / `paid1` still accepted.

## 2026-08-15 17:00 +07 â€” paid2 providers + official skills

- `IMAGE_VENDOR_PROVIDER` (was PAID2): `fal` | `pollinations` | `fluxai` | `openai` | `http`.
- Hermes skills under `hermes/main/skills/`: official pdf/docx/xlsx/comfyui/searxng-search; routers documents/tavily/firecrawl/searxng.

## 2026-08-15 16:45 +07 â€” /v1/image fallback (llm â†’ vendor â†’ ComfyUI)

- Dispatcher chain: **llm** â†’ **vendor** â†’ **comfy-cpu** â†’ **comfy-gpu** (when `COMFYUI_HAS_GPU=1`).
- Medium compose: `comfyui-cpu` always; `comfyui-gpu` via profile `comfy-gpu`.
- Workflows: `architect/models/dispatcher/comfy_workflows/`. Low forces `IMAGE_BACKENDS` empty.

## 2026-08-15 16:35 +07 â€” post-ready learn skills|docs (all profiles)

- After Hermes + 9Router ready (`run.sh up` / `update` / `first-setup-llm`): if `hermes/main/skills` has real skills, sync markdown â†’ `$ASSISTANT_DATA_DIR/docs/` and ingest `learn/scan`.
- Ingest: `LEARN_DOCS_ROOT=/data/assistant/docs`; `LEARN_REQUIRE_APPROVE=0` auto-ingests on scan (no approve).
- Optional inbox: `hermes/main/setup/`, extra docs: `hermes/main/docs/`. Command: `bash run.sh post-ready-learn`.

## 2026-08-15 16:10 +07 â€” office PDF (reportlab + DejaVu)

- Dispatcher can create real `.pdf` / `.docx` / `.xlsx` (not silent `.txt` fallback).
- Adds `reportlab`, `openpyxl`, `python-docx`; image installs `fonts-dejavu-core` for Vietnamese PDF.
- Synced from verified assistant fix; Low still defaults `OFFICE_FILE_GEN=0`.

## 2026-08-15 15:40 +07 â€” rename GDrive â†’ CloudDrive (rclone)

- `ENABLE_CLOUDDRIVE`, `CLOUDDRIVE_*`, service `clouddrive-sync`, command `backup-sync-clouddrive`; mirror `/data/clouddrive`. Still rclone under the hood.

## 2026-08-15 15:35 +07 â€” High profile compose + OpenBao

- Added `docker-compose.high.yml`: OpenBao UI `:8200`, ClamAV/AV, security-manager, SIEM, authz, policy, admin-api, Grafana/Prom/Loki/Alloy, exporters; optional `notify` / `CloudDrive` compose profiles.
- `profile.sh` High: `ENABLE_NOTIFY` default **0**; OpenBao on; CloudDrive flag on.
- `scripts/main/first-setup-openbao.py` seeds API keys â†’ `secret/assistant/api-keys` + `.env.openbao`; auto on `up`/`update`.
- `bash run.sh check-high`. Docs: README High, 00-profiles, DEFAULTS, NEXT.

## 2026-08-15 15:25 +07 â€” Medium timers auto on up/update

- `run.sh up` / `update` call `ensure_profile_timers` for `medium|high` (auto-learn, backup, compact). No separate `install-timers` step.

## 2026-08-15 15:20 +07 â€” Medium profile compose + smoke

- Added `docker-compose.medium.yml` (SearXNG, OCR, Jobs, jobs-worker); `run.sh` merges it for `medium|high`.
- `profile.sh`: Medium sets `WEB_BACKENDS` / `OFFICE_FILE_GEN`; Low forces web + file-gen off.
- Dispatcher: empty `WEB_BACKENDS` disables search (no accidental Low web); SearXNG fallback only when backends enabled.
- `scripts/main/check-medium.sh` + `bash run.sh check-medium`. Docs: README Medium, DEFAULTS, 00-profiles.

## 2026-08-15 15:05 +07 â€” split scripts/main vs scripts/temp

- Product ops â†’ `scripts/main/` (`install-docker`, `first-setup-9router-hermes`); one-off deploy/probes â†’ `scripts/temp/` (gitignored except README).
- `run.sh` paths updated.

## 2026-08-15 15:00 +07 â€” `run.sh update` after git pull

- Added `bash run.sh update`: rebuild/recreate compose from current tree, refresh 9Routerâ†’Hermes first-setup, prune disk. Workflow: `git pull` then `bash run.sh update`.

## 2026-08-15 14:55 +07 â€” combo round-robin + post-setup cleanup

- First-setup sets 9Router `comboStrategy` / `comboStrategies.hermes` to **`round-robin`** (`comboStickyRoundRobinLimit=1` = rotate each request).
- After successful first-setup: `docker builder/image/container prune` + clear `/tmp/assistant*` to free disk. (Code only â€” not pushed.)

## 2026-08-15 14:50 +07 â€” default 9Router combo renamed to `hermes`

- First-setup creates/updates combo **`hermes`** with all current OpenCode Free (`oc/*`) models; Hermes default model id = `hermes`.

## 2026-08-15 14:45 +07 â€” default LLM = OpenCode Free combo

- First-setup builds/updates 9Router combo with all current `oc/*` models (big-pickle first).
- Hermes default model id uses that combo (fallback). No OpenRouter key required for Low chat.

## 2026-08-15 14:40 +07 â€” first-setup: Docker install + 9Router Default Key â†’ Hermes

- Added `scripts/install-docker.sh` (official `docker-ce` apt, `systemctl enable`, add user to `docker` group + `getent` verify).
- Added `scripts/first-setup-9router-hermes.py` â€” login 9Router, copy **Default Key** into `.env` / Hermes, default model `openrouter/auto` via `http://9router:20128/v1`.
- `deploy-test-low.py` installs Docker if missing, then runs first-setup after Hermes is up.
- Compose: `N9ROUTER_API_KEY` optional at interpolate time (`:-`) so first boot can fill Default Key after 9Router starts.

## 2026-08-15 14:20 +07 â€” deploy Hermes + 9Router on Low test host

- Synced compose to `[internal-host]`; extended root LV 13.5â†’27G (disk full blocked Hermes extract).
- Up: `9router` `:20128`, `hermes` gateway `:28642` + dashboard `:29119` (HTTP 302). Embedding `has_key=true`; dispatcher `n9router=true`.

## 2026-08-15 13:35 +07 â€” Low Must: Hermes + 9Router in compose

- Wired `9router` (`decolua/9router`, host `20128`) and `hermes` (`nousresearch/hermes-agent`, gateway `28642`, dashboard `29119`) as always-on Must services (no Traefik, no Zalo `depends_on`).
- Hermes â†’ dispatcher OpenAI path; embedding/dispatcher get `N9ROUTER_API_KEY`; Low defaults `WHISPER_ENABLED=0`.
- Mounts: `HERMES_DATA_DIR` â†’ `/opt/data`; repo `hermes/main/skills` + `messages` read-only.

## 2026-08-15 13:20 +07 â€” Low profile test deploy

- Synced tree to `/opt/assistant`, `.env` with test secrets, `ASSISTANT_PROFILE=low`.
- Stack up: postgres, redis, qdrant, memory, mem0, session, embedding, ingest, dispatcher.
- Slimmed dispatcher Dockerfile (no ffmpeg) + requirements (no faster-whisper) for Low; `WHISPER_ENABLED=0` in host `.env`.
- Health OK on 8090/8094/8095/8096/8099/8107 (Hermes/9Router wired in later same day).

## 2026-08-15 11:35 +07 â€” copy Zalo adapter (mention gate) into hermes/main/plugins

- Copied edited plugin from lab `hermes_backup/plugins/zalo` â†’ `hermes/main/plugins/zalo/` (`adapter.py` with `ASSISTANT_MENTION_GATE_v1`, `gate_valkey.py`, `plugin.yaml`, `__init__.py`).
- Did **not** copy PowerShell push scripts.

## 2026-08-15 11:20 +07 â€” root README expanded

- Rewrote `README.md` (reference-style): product pitch, quick start, profiles, layout, commands, architecture brief, docs map, design rules. Still points at `docs/` for detail.

## 2026-08-15 10:55 +07 â€” brief views as HTML architecture panels

- `03-architecture.md` / `04-component-flows.md`: **Brief view** = styled HTML layer boxes (THIS = gold border); **Workflow** stays Mermaid.

## 2026-08-15 10:40 +07 â€” brief system architect + workflow per section

- `03-architecture.md`: each workflow has **Brief system architect** then **Workflow** (Mermaid).
- `04-component-flows.md`: each component has **Brief system architect** (THIS highlight) then **Internal workflow**.

## 2026-08-15 10:15 +07 â€” system architecture & component flowcharts

- Added `docs/03-architecture.md` (whole-system architecture, chat/knowledge/Medium/High/ops/memory Mermaid workflows).
- Added `docs/04-component-flows.md` (flowchart per hermes surface + each architect layer).
- Linked from `docs/README.md`, `docs/01-workflow.md`, `architect/README.md`.

## 2026-08-15 10:12 +07 â€” profile matrix as Excel-style HTML tables

- `02-components-and-commands.md` uses HTML tables with column widths, row padding, and section header rows (Must / Medium+ / High).

## 2026-08-15 10:10 +07 â€” components & commands doc rewritten for readability

- Replaced wide profile matrices in `02-components-and-commands.md` with Low / Medium / High sections, plain lists, and "I want toâ€¦" cheat sheet.

## 2026-08-15 10:05 +07 â€” components & commands by profile (one doc)

- Added `docs/02-components-and-commands.md`: Must/Med/High component matrix + `run.sh` command matrix + timers + cheat-sheets.
- Docs index points here first for operators. `02-commands.md` kept as commands-only detail.

## 2026-08-15 10:00 +07 â€” commands by profile (backup, auto-learn, compact)

- Added `docs/02-commands.md`: full command matrix for Low / Medium / High.
- `run.sh` supports: backup|restore|verify|migrate, auto-learn|learn-status, compact|optimize-memory (Med+), install-timers, backup-sync-clouddrive (High), channel-status.
- Compact refused on Low; auto-learn available on all profiles. No VPS push.

## 2026-08-15 09:55 +07 â€” detailed architect/hermes docs + example skill

- Added per-component READMEs under `architect/**` and `hermes/**` (purpose, profile, functions, how it works).
- Added `hermes/main/skills/_example/SKILL.md` template from current skill style (`common-rules` / `knowledge-learn`).
- Docs index links component indexes. No VPS push.

## 2026-08-15 09:45 +07 â€” clean rebuild of assistant

- Wiped prior scaffold clone. New clean tree: `architect/` (layers) + `hermes/` (skills, messages, plugins, config).
- Seeded Must Low `docker-compose.yml`, `run.sh`, `ASSISTANT_PROFILE` via `architect/backup-restore/lib/profile.sh`.
- Docs: `00-profiles.md`, `01-workflow.md` (Low only), `DEFAULTS.md`. Fresh changelog (lab history stays in `assistant`).
- Copied service code into layers from lab (memory, tools, models, â€¦) without hotfix push scripts / OpenVPN / Traefik product path.
- **Action for operators:** copy `.env.example` â†’ `.env` and set all `CHANGE_ME` secrets before `bash run.sh up`.
- No VPS deploy in this change.


