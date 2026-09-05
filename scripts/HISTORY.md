## 2026-09-05 20:45 +07 — bounded Zalo sends and non-interfering live evaluation

See `history/2026-09-05/README.md` section “Synthetic quote metadata and
concurrent judges distorted delivery tests”.

## 2026-09-05 19:20 +07 — cold-start OpenBao ordering

See `history/2026-09-05/README.md` section “Clean startup depended on an
already-running secret service”.

## 2026-09-05 16:30 +07 — quoted-image editing and slow-provider timeout

See `history/2026-09-05/README.md` section “Quoted images were analyzed instead of edited”.

## 2026-09-04 20:10 +07 — scheduled live-scene execution and overlay ownership

See `history/2026-09-04/README.md` sections “Scheduled live-scene intent survives storage and fire” and “One renderer owns live-scene text”.

## 2026-09-04 18:10 +07 — OpenBao export ownership

See `history/2026-09-04/README.md` section “Privileged OpenBao refresh preserves runtime ownership”.

## 2026-09-04 16:55 +07 — Omni still drops at maxWaitMs 15000 after update

### Symptom
Chat returned “Request dropped … maxWaitMs (15000ms)” even when host `.env` pinned `OMNIROUTER_REQUEST_QUEUE_MAX_WAIT_MS=600000`.

### Root cause
Omni container recreate resets resilience DB defaults to 15s. `run.sh update` did not re-run update-omnirouter; ensure skipped PATCH when a prior read looked high enough; API-key GET `/api/resilience` is 403 (cookie login required).

### Fix
Default pin 86400000 (24h clamp); always force PATCH `/api/resilience`; call `update-omnirouter` from `run.sh update` after compose (membership stays setup_only).

### Prevent recurrence
Never rely on env alone for Omni resilience; always re-PATCH after Omni recreate.

## 2026-09-04 16:40 +07 — obsolete env pins linger after scrub

### Symptom
VPS ROOT/.env still had empty `ADMIN_API_TOKEN` and example still shipped `WEB_BACKENDS=omni` after combo-only search.

### Root cause
Scrub emptied secret *values* but left retired keys; no durable delete of non-secret obsolete pins.

### Fix
`scripts/main/cleanup-obsolete-env.py` + `OBSOLETE_ENV_KEYS` in `openbao_common.py`; called from scrub and load-openbao; KV export filters obsolete keys.

### Prevent recurrence
Add new retirements to `OBSOLETE_ENV_KEYS` / `OBSOLETE_SECRET_KEYS` only — never delete live `ENABLE_*` / `WORKER_*` install flags blindly.

## 2026-09-04 16:20 +07 — Hermes non-owner Zalo adapter ERROR spam

### Symptom
Scaled non-owner Hermes replicas logged `Platform 'zalo' is registered but adapter creation failed` on every start.

### Root cause
Replica entry cleared `ZALO_PLUGIN_URL` for non-owners but still symlinked shared `config.yaml` with Zalo platform + `zalo-platform` plugin enabled.

### Fix
`hermes-replica-entry.sh`: non-owners get a local config copy with gateway Zalo disabled and `zalo-platform` removed; owners keep the shared config symlink.

### Prevent recurrence
Never leave messaging platform enabled in config when the replica intentionally has no plugin URL.

## 2026-09-04 15:35 +07 — Omni maxWaitMs 15s drops slow free models

### Symptom
Omni returned “Request dropped after exceeding the local rate-limit queue budget maxWaitMs (15000ms)” for slow OpenCode members.

### Root cause
`resilienceSettings.requestQueue.maxWaitMs` defaults to 15s Bottleneck job expiration. `PATCH /api/settings` silently ignores nested resilienceSettings.

### Fix
`ensure_request_queue_max_wait` patches `PATCH /api/resilience` (default 600000ms via `OMNIROUTER_REQUEST_QUEUE_MAX_WAIT_MS`) on first-setup and update-omnirouter. Does not rewrite operator combo membership.

### Prevent recurrence
Always use `/api/resilience` for queue knobs; never set maxWaitMs to 0 (skip-never-queue).

## 2026-09-04 15:05 +07 — Omni 401: scrub emptied compose keys

### Symptom
Host probes to Omni returned AUTH_002; `OMNIROUTER_API_KEY` / `API_SERVER_KEY` / `GATEWAY_API_KEYS` empty in ROOT/.env while OpenBao KV still held values.

### Root cause
`run.sh update` seeded OpenBao then `scrub-plaintext-env` cleared compose host keys and deleted `.env.openbao` without an immediate refill.

### Fix
After scrub, always `do_load_openbao_env_for_compose`. VPS: refill + recreate router-worker.

### Prevent recurrence
Never leave scrub as the last OpenBao step before idle; refill COMPOSE_HOST_KEYS in the same update.

## 2026-09-04 14:35 +07 — VPS .env literal-\\n; Hermes scale; delivery soften

### Symptom
Only one Hermes replica up despite `HERMES_REPLICAS=2`; bash could not source host `.env`; chat later hit Omni member 503.

### Root cause
`/opt/assistant/.env` had nearly all newlines stored as literal `\\n` (unparseable). A compose run without `--project-directory` also bound `pg_hba.conf` to a directory under `docker/docker/…`.

### Fix
Expanded literal newlines (backup kept); recreated postgres with correct project-dir mount; scaled Hermes to 2. Softened classify `delivery.txt`. `load-openbao-env` now auto-repairs literal-`\\n` `.env` files.

### Prevent recurrence
Always use `run.sh` / `--project-directory $ROOT`. Do not rewrite operator Omni combos — refill unhealthy free members in UI when pre-dispatch skips everything.

## 2026-09-04 12:00 +07 — flexible live-scene overlays; soften media prompts

### Symptom
Live overlay / classify media still read weather-first; fixed poster/weather headings left gaps for other topics.

### Root cause
First live-facts path was weather-named; classify/file-gen examples biased to weather.

### Fix (core)
`run_search_then_live_scene` + aliases; classify EXACT-TEXT / live-scene synonyms; generic file-gen HTML example; unique info-scene filenames.

### Prevent recurrence
Prefer topic-agnostic live-scene naming; keep weather aliases only for compatibility.

## 2026-09-04 11:50 +07 — §15 unit align; greeting PASS; visual weather inject fix

### Symptom
Offline case-index units failed on legacy `1`/`0` defaults and empty secret-probe markers; visual weather PDF lab curl failed after sanitize redacted loopback IP.

### Root cause
Product moved to `active`/`inactive` and classify-owned soft secret probes; lab sanitize strips IPs from inject URLs.

### Fix
Update units/fixtures; visual weather inject via remote urllib. Omni combo preflight + Tn greeting PASS on VPS.

### Prevent recurrence
`test/scripts/run_case_index_lab.py` includes newer scripts; do not sanitize live inject URLs.

## 2026-09-04 11:30 +07 — Playwright primary abandon; archive lab; office shell

### Symptom
Hermes chat hung / 503 after Omni returned Cloudflare Playground Playwright 502; rotate retries burned on the same `hermes` combo id.

### Root cause
`expand_chat_candidates` retries the primary combo several times for Omni RR; Playwright session death does not recover on the same combo pool within that budget.

### Fix (core)
`chat_abandon_primary_rotates` + router loop skips remaining primary rotates and continues failover model ids (not full Omni skip). Office PDF HTML shell polish. Archive extract Tn lab for Security zips.

### Prevent recurrence
`test/scripts/model_router_chat_norm.py` Playwright cases; `test/scripts/zalo_tn_archive_extract_lab.py`. See `history/2026-09-04/`.

### Fix (core)
`plan_is_image_analyze_chat` blocks async workflow; `_as_try_workflow_submit` no longer calls `office_shortcut` without `media_urls` when `has_image_attachment`. Image/PDF reads use `architect/lib/vision_ocr.py` → router-worker combo `vision-ocr` (no OCR container).

## 2026-09-03 07:00 +07 — Weather Pillow overlay; ingest PDF/zip read

### Symptom
Weather-on-image showed garbled Vietnamese from diffusion text. Bare PDF and zip inner files returned empty extract or member listing only.

### Root cause
Labeled facts were baked into image-gen SCENE (models corrupt diacritics). Hermes read PDF locally without pymupdf; archive temp dir deleted before durable member read.

### Fix (core)
Restore dispatcher `overlay.py` + `/v1/overlay` (bottom-left Noto badge). `run_search_then_weather_scene` applies overlay after scenic gen. Ingest adds pymupdf PDF layer + persisted `media/extracted/` members. Zalo PDF → ingest `/v1/extract-text` first. Image-gen waits 300s with 5xx retry before combo failover.

### Prevent recurrence
`test/scripts/weather_overlay_unit.py`; `test/scripts/zalo_tn_pdf_zip_weather_inject.py` for Tn inject lab.

## 2026-09-02 22:40 +07 — router-worker stripped image_url; kimi saw text only

### Symptom
Direct Omni `ai-box/kimi-k3` described the DSLR correctly; same payload via `router-worker` / `vision-ocr` returned “chưa nhận được ảnh” or invented cafe scenes.

### Root cause
Container `chat_norm.sanitize_chat_payload` still flattened every message with `parts_to_text`, dropping `image_url`. Blind text models then hallucinated scenic Vietnamese cafe replies.

### Fix (core)
Ship `normalize_message_content` that keeps vision parts; do not force `model=hermes` on vision payloads. Zalo adds structural prompt-echo gate and media path/base64 describe path.

### Prevent recurrence
`test/scripts/model_router_chat_norm.py` asserts multimodal lists survive sanitize; VPS must rebuild/restart `router-worker` after router code changes (image bake, not Hermes bind-mount alone).

## 2026-09-02 22:00 +07 — Remove OCR worker container entirely

### Symptom
Separate OCR container still ran legacy paddle health on VPS; duplicate hop vs shared vision lib.

### Root cause
OCR worker was retired in code but compose/service/skills still referenced `ocr:8091`.

### Fix (core)
Deleted `architect/tools/ocr/`. Ingest/jobs/dispatcher/Zalo call `vision_read` / `vision_read_path`. Removed `ocr` service, `OCR_URL`, `ENABLE_OCR`, monitor health probes, paddle test case.

### Prevent recurrence
`test/scripts/vision_ocr_policy_unit.py` fails if `architect/tools/ocr` exists.

## 2026-09-02 21:15 +07 — OCR worker: vision-ocr only (remove paddle/tesseract)

### Symptom
Image describe still wrong or empty: Paddle returned glyph noise and skipped vision; large photos refused or hallucinated on vision-ocr.

### Root cause
Media OCR worker ran pymupdf → PaddleOCR → vision-ocr → tesseract. Paddle short-circuit blocked vision; tesseract added unreliable fallback.

### Fix (core)
`architect/tools/ocr/app.py` v2: pymupdf PDF text layer → vision-ocr combo only. Large images downscaled (`OCR_VISION_MAX_PX`). Removed `paddle_engine.py`, tesseract deps, paddle compose env/volume. Skills/classify/media.txt aligned.

### Prevent recurrence
`test/scripts/vision_ocr_policy_unit.py` locks vision-only app policy.

## 2026-09-02 21:00 +07 — zalo: image-analyze host reply via OCR vision-ocr

### Symptom
`hình gì đây` + Saigon skyline returned unrelated scenes (dog on sofa, girl in meadow) despite native vision attach and router multimodal fix.

### Root cause
Hermes `hermes` combo still hallucinates on inline vision; probe showed `vision-ocr` via OCR `/v1/ocr` describes skyline correctly.

### Fix (core)
`_as_try_image_analyze_vision_reply`: classify `plan_is_image_analyze_chat` → OCR worker with Vietnamese describe prompt → host Zalo reply; bypass Hermes chat turn. Hooked in enqueue + queue drain before `handle_message`.

### Prevent recurrence
`attachment.image_analyze_vision_*` helpers + unit tests in `image_analyze_chat_unit.py`.

## 2026-09-02 20:45 +07 — model-router: preserve multimodal image parts

### Symptom
Zalo `hình gì đây` + Saigon skyline photo returned hallucinated text (GitHub repo page, cybernetic brain) instead of describing the attached image.

### Root cause
`architect/models/model-router/chat_norm.sanitize_chat_payload` flattened every message to text via `parts_to_text`, dropping `image_url` parts. Hermes `vision_analyze` and combo chat saw only the Vietnamese prompt — models invented content from session prior turns.

### Fix (core)
`normalize_message_content` keeps multimodal lists when vision parts are present. Remove erroneous `OCR_URL=127.0.0.1` stack pin; Hermes config: `image_input_mode: native`, `auxiliary.vision` → `vision-ocr` via router-worker. OCR container `OPENAI_BASE_URL` → router-worker.

### Prevent recurrence
`test/scripts/model_router_chat_norm.py` vision preserve case.

## 2026-09-02 20:15 +07 — zalo: image analyze Hermes chat (not txt file / OCR garbage)

### Symptom
Captioned image ask (`đây là hình gì`) delivered a `.txt` file whose body was the classify instruction template. Bare image returned OCR garbage (`crn ae maa`) as the only reply.

### Root cause
Classify mis-tagged image analyze as async `file_processing` with `output_type=txt`, so workflow/file-gen wrote instructions as file content. Bare-image host-ack sent raw OCR noise without Hermes multimodal.

### Fix (core)
`plan_is_image_analyze_chat` blocks async workflow when an image is attached; coerce plan to interactive Hermes. Disable image host-ack; filter short OCR noise before prompt. Harden classify media part: image analyze never emits file output_type.

### Prevent recurrence
Unit test for txt misclassify coercion and OCR noise filter.

## 2026-09-02 19:45 +07 — zalo: classify strips attachment recall for schedule

### Symptom
Relative remind schedule (`N phút nữa nhắc tôi: …`) stored 0 rows when thread memory had recent attachments; logs showed `attach_followup` without `schedule stored`.

### Root cause
Host injected `[Recent attachments…]` into inbound text before classify; router received the full blob (not user line only), so timed intent was drowned by prior file context.

### Fix (core)
`strip_prior_for_classify` drops attachment-recall blocks; classify HTTP payload sends stripped user line. Schedule classify part: recall must not downgrade remind-with-body creates.

### Prevent recurrence
Unit test locks strip of attachment recall before schedule classify.

## 2026-09-02 19:15 +07 — zalo: image-gen 5m timeout; Hermes image path; schedule ack

### Symptom
Combo image-gen member attempts timed out around 60s; captioned image analyze hit OCR-worker vision-ocr (Omni queue saturation) instead of Hermes multimodal; relative remind schedule stored/fired but user saw no saved ack or fire text when a prior turn had delivered media.

### Root cause
Default host diffusion timeout was below operator budget; captioned images always ran OCR worker (vision combo) before Hermes; `_as_job_file_sent` muted later text sends including schedule ack/fire in the same thread.

### Fix (core)
Pin/default `OMNI_IMAGE_GEN_TIMEOUT_S=300` in first-setup and host diffusion. Skip OCR worker for captioned images; empty bare-image OCR prompt routes Hermes multimodal. Clear job-file-sent mute on new inbound; exempt schedule/gate sends from post-media text drop. Harden classify schedule/media parts.

### Prevent recurrence
Unit tests for 300s timeout default, once_after remind body timing, and existing combo failover import safety.

## 2026-09-02 17:45 +07 — zalo: image-gen failover helper had broken signature

### Symptom
Zalo inbound message (scenic/image shortcut) got no reply; Hermes logged `SyntaxError: '(' was never closed` importing `media_shortcuts`, so the host turn threw before classification/execution.

### Root cause
Failover refactor left `_omni_request_image_blob_once` with an unterminated `def (` signature; module import failed on every inbound message, aborting the whole media shortcut path.

### Fix (core)
Restored the complete keyword-only signature on `_omni_request_image_blob_once`. Added regression tests asserting combo→member failover order and `/v1/combos` member parsing.

### Prevent recurrence
Keep image-gen helpers import-safe; unit tests import the module (which fails fast on syntax errors) and cover the failover call order.

## 2026-09-02 17:15 +07 — image-gen: custom provider wiring + host combo failover

### Symptom
Direct `prefix/model` image routes worked; `model=image-gen` returned `No images-capable targets` for custom providers (e.g. ai-box).

### Root cause
Omni `executeImageCombo` filters targets via built-in image registry only — custom `provider-models` are invisible to combo execution. Prefix/model routing resolves via provider-nodes to the chat provider node id.

model=image-gen still returns No images-capable targets because Omni’s executeImageCombo only accepts targets in the built-in image registry — custom provider-models are ignored (OmniRoute v3.8.50).

### Fix (core)
`first-setup-omnirouter`: `POST sync-models`, register provider-models on prefix-resolved provider node from admin/`/v1/combos` image-gen members. Host diffusion (`media_shortcuts`) fails over to `/v1/combos` members as direct routes when combo name fails.

Register provider-models on _prefix_resolved_provider_node_id() from provider-nodes API (same rule as Omni’s imageRouteModel.ts)

### Prevent recurrence
Do not parse provider prefixes in setup scripts; use provider-nodes + provider-models + combo APIs. Do not rely on Omni combo name alone for custom image providers until image-combo supports custom registry entries.

## 2026-09-02 16:45 +07 — image-gen: Omni provider-models sync; combo-only diffusion

### Symptom
Omni `image-gen` combo listed custom-provider models (e.g. `ai-box/qwen-image-2.0`) but `/v1/images/generations` returned `No images-capable targets in combo "image-gen"`. Host diffusion fell back to slow Horde head; Zalo showed "Đang vẽ hình…" before scenic delivery.

### Root cause
Combo members used catalog ids without matching `provider-models` on an `images-generations` provider node. Chat-only provider nodes (`apiType=chat`) do not route `/images/generations`. Legacy `IMAGE_GEN_HEAD_MEMBER` bypassed combo failover.

### Fix (core)
`ensure_images_generations_nodes` uses Omni provider-nodes API (chat → images-generations sibling). `ensure_provider_image_models` syncs from `/api/providers/{id}/models` onto images-generations provider-models. Combo members = wired prefix/model ids only. Host diffusion uses combo `image-gen` only. Obsolete env keys cleared via session temp script — not in first-setup.

### Prevent recurrence
Custom image providers must be wired through OmniRoute provider-nodes + provider-models; do not parse provider prefixes in setup scripts. Do not embed obsolete env key cleanup in durable setup scripts.

## 2026-09-02 11:45 +07 — Zalo: search+image workflow split + image-gen single-provider fail

### Symptom
Compound weather+image ask delivered a generic Hermes greeting plus a scenic image without weather labels; image-gen logged Pollinations 401; quote-image vision returned garbage.

### Root cause
Classify search+image plans expose two `instructions[]` entries — workflow treated them as separate async jobs (Hermes chat + diffusion). Host diffusion called only `IMAGE_GEN_HEAD_MEMBER` (Pollinations) with no combo failover. Pollinations without API key still appeared in image-gen catalog head selection.

### Fix (core)
`plan_is_search_then_image_turn` blocks workflow FIFO split; adapter routes unified search+image to host media shortcut. Diffusion tries combo `image-gen` then head member. first-setup skips Pollinations image members when unkeyed; repairs API key ACL when stack combos drop.

### Prevent recurrence
Dual-instruction search+image plans must never enqueue separate Hermes workflow jobs; image-gen must use combo failover, not a single pinned provider.

## 2026-09-02 11:30 +07 — Zalo: quote local image path + weather-on-image silent turns

### Symptom
(1) Quote-reply with embedded image path + đọc hình → no Zalo response. (2) Weather update + draw HCMC with weather text on image → no response.

### Root cause
Quote media extraction only accepted HTTP URLs; local `/opt/data/media/...` paths in quoted bot text were ignored. Workflow submit returned True after a no-op media shortcut, swallowing the turn. Weather+labeled-image asks without `RENDER:` marker missed the info-card host gate.

### Fix (core)
Resolve local media paths from quote payloads; `_download_media` uses existing staged files. Return shortcut consumed status; announce workflow start. Classify parts + host gate for labeled weather-on-image.

### Prevent recurrence
Quote media must accept shared-volume paths; never return True from workflow submit unless the turn was consumed or dispatched.

## 2026-09-02 11:00 +07 — first-setup: vision-ocr rejects blind supportsVision models

### Symptom
Vision OCR returned garbage ("crn ae maa") — model replied "I don't see any image attached" despite image in request.

### Root cause
`vision-ocr` combo included OpenCode models with `supportsVision` but no image-input modality (e.g. qwen3.7-plus).

### Fix (core)
Filter vision-ocr members by catalog image-input capability; refill combo when blind members present.

### Prevent recurrence
Do not trust `supportsVision` alone for vision-ocr; require image-input modality or explicit vision capability.

## 2026-09-02 10:45 +07 — first-setup: image-gen from catalog metadata only

### Symptom
`image-gen` combo routed chat models to `/images/generations` (401/empty); some members were chat-only under image-looking ids.

### Root cause
First-setup used hardcoded provider prefixes and model-name whitelists that drift when Omni renames namespaces.

### Fix (core)
Select and rank image-gen members from catalog `supportedEndpoints` / `apiFormat` / `type` / `capabilities`; register/repair provider custom models via `images-generations` provider-nodes only.

### Prevent recurrence
Never gate image-gen on id prefixes or fixed model lists; use Omni catalog fields and provider-node `apiType`.

## 2026-09-02 10:15 +07 — setup-zalo: show QR/logs during health capture

### Symptom
After `core ready for QR`, setup-zalo printed nothing — no logs, no ASCII QR — until timeout or Ctrl+C.

### Root cause
`setup-zalo` captures stdout via `health_json="$(zalo_qr_login_phase)"`, swallowing all `zalo_log` output and login CLI QR. Inside `$(...)`, `[[ -t 1 ]]` is false so console QR path was skipped.

### Fix (core)
`zalo_log` → stderr; QR instructions → stderr; detect TTY via `/dev/tty`; run `hermes-zalo-plugin login` with stdin/stdout on `/dev/tty`.

### Prevent recurrence
Functions whose stdout is machine-readable JSON must log and render UI on stderr or `/dev/tty`, not stdout.

## 2026-09-02 10:00 +07 — setup-zalo: print Zalo QR in terminal

### Symptom
`setup-zalo` waited silently after npm install; users expected a scannable QR in the SSH console, not only `http://127.0.0.1:8787/qr.png`.

### Root cause
`hermes-zalo-plugin login` ran in the background with stderr discarded; upstream only renders ASCII QR when stdout is a TTY. The systemd bridge also logs QR to a file path, not the terminal.

### Fix (core)
Stop the bridge, run login CLI in the foreground (TTY), then restart bridge and verify `/health`.

### Prevent recurrence
Do not background Zalo login helpers during setup; interactive QR requires a foreground process attached to the user's terminal.

## 2026-09-02 09:45 +07 — setup-zalo: headless Node.js install (no apt hang)

### Symptom
`setup-zalo.sh` stopped after "core ready for QR" on fresh VPS; `apt install` stuck in stopped state (`T+`); no QR because Node was never installed.

### Root cause
`zalo_need_node` ran NodeSource `setup_20.x` via curl|bash, which spawned nested apt jobs that hung on headless SSH when debconf/readline waited on a background TTY.

### Fix (core)
Direct NodeSource apt repo add + `DEBIAN_FRONTEND=noninteractive` install; `zalo_wait_apt_lock`; Node preflight in `setup-zalo` before QR phase; clearer QR browser instructions.

### Prevent recurrence
Never pipe NodeSource setup scripts into bash on headless VPS; use explicit apt repo + noninteractive flags and apt-lock waits for any setup-zalo package installs.

## 2026-09-02 09:30 +07 — combo priority failover: classifier, embedding, web-search

### Symptom
Classifier, embedding, and web-search combos inherited global round-robin; `web-search` combo was missing on fresh installs so Router search had no Omni failover chain.

### Root cause
Only image-gen had an explicit per-combo strategy; web-search creation was deferred to manual Omni UI.

### Fix (core)
`FALLBACK_COMBO_STRATEGY=priority` for classifier, embedding, vision-ocr, image-gen, and web-search; `ensure_web_search_omni_combo` seeds Tavily -> Firecrawl -> SearXNG when empty.

### Prevent recurrence
Any stack combo that must exhaust a ranked head before failover needs an explicit priority strategy in first-setup, not the global round-robin default.

## 2026-09-02 09:15 +07 — vision-ocr combo: priority (fallback) strategy

### Symptom
Vision OCR combo used global round-robin, rotating across multimodal members instead of exhausting the ranked head before failover.

### Root cause
`ensure_media_combos` did not pass a per-combo strategy for `vision-ocr`; only chat combos inherited `OMNIROUTER_COMBO_STRATEGY=round-robin`.

### Fix (core)
`VISION_OCR_COMBO_STRATEGY=priority` (env `OMNIROUTER_VISION_OCR_COMBO_STRATEGY`); `_put_or_create_combo` preserves member order when fixing strategy on an existing combo.

### Prevent recurrence
Media combos that need head-first failover must declare their own strategy constant, not rely on the global round-robin default.

## 2026-09-02 09:00 +07 — first-setup: catalog-only media combos; drop vendor hardcoding

### Symptom
First-setup carried AI Box whitelists, Horde/namespace filters, obsolete env scrubbing, and remapped image/vision routes to `hermes` when media worker was inactive.

### Root cause
Setup script duplicated operator concerns (vendor model lists, combo member surgery) that belong in Omni UI or runtime, not first-run wiring.

### Fix (core)
Media combos seed from `/v1/models` image/vision/embed signals only when empty; `pin_media_combos` pins combo names when media is active without hermes fallback; removed `ensure_aibox_image_models` and related hardcoded filters.

### Prevent recurrence
First-setup wires providers and empty combos — never maintain vendor-specific model allowlists in setup code.

## 2026-09-02 08:45 +07 — first-setup: Pollinations Flux image head; drop setup smokes

### Symptom
`first-setup-omnirouter` aborted on VPS when AI Horde head diffusion exceeded setup timeout; `IMAGE_GEN_HEAD_MEMBER` pinned slow Horde instead of free Flux.

### Root cause
Setup smoke-tested `/images/generations` against the ranked head (AI Horde ICBINP when no AI Box); Horde workers routinely exceed any sane first-setup timeout.

### Fix (core)
Pollinations provider is created when missing (`POLLINATIONS_API_KEY` or anonymous placeholder); Flux slug is ranked first and pinned as `IMAGE_GEN_HEAD_MEMBER`. Pollinations chat/community paths are excluded from image combo membership. Setup smoke probes removed.

### Prevent recurrence
Do not hard-fail first-setup on free diffusion latency; pin a fast free Flux head instead of Horde for scenic delivery.

## 2026-09-02 07:30 +07 — router-worker URL; reasoning_effort; labeled weather-on-image

### Symptom
Compound asks (weather update + draw city with facts on image) went silent; short follow-ups ("ê") ignored prior turns; `model-router` hostname lingered after rename to `router-worker`.

### Root cause
1. Search+image plans with two instructions but no `task_details` search marker failed `_plan_has_search` gate.
2. Ultra-short classify bypass treated contextual nudges as fresh hello.
3. Image shortcuts stored empty assistant turns — session hydrate had no assistant history.
4. Info-card path blocked the event loop without ack.

### Fix (core)
`router-worker` URL defaults; classify `reasoning_effort`; prompt hardening for labeled weather-on-image and prior-turn recap; `_plan_has_search` contract detection; info-card asyncio + ack; session `append_turn` records image delivery.

### Prevent recurrence
Search+labeled-scene combos must pass host gate without `task_details` alone; never store blank assistant turns after delivered images.

## 2026-09-01 21:30 +07 — classify Local now for scene lighting; drop host lighting heuristics

### Symptom
Evening weather-scene asks still produced bright daytime diffusion when host-side hour buckets overrode or duplicated classify intent.

### Root cause
`_local_lighting_hint()` and `_weather_visual_cues()` in `media_shortcuts.py` hardcoded time-of-day and weather atmosphere in Python instead of letting the classifier read current local time.

### Fix (core)
Model-router classify injects `Local now: {local_now}` into the user template from timezone; `media` classify part instructs SCENE lighting from that line. Host weather-scene prompt uses classify SCENE plus search facts only (no readable on-image text).

### Prevent recurrence
Scene lighting for diffusion must be decided at classify time from Local now — never re-derived in host Python heuristics.

## 2026-09-01 21:00 +07 — weather-scene visual-only diffusion; fix duplicate image send

### Symptom
Weather-scene asks (city + current conditions) delivered duplicate images; diffusion rendered misspelled Vietnamese text on-image; evening asks produced bright daytime scenes.

### Root cause
1. `_scene_prompt_with_facts` asked diffusion for a readable caption board with raw fact strings — models garble non-English text.
2. Prompt hardcoded `daytime outdoor scene` regardless of local clock.
3. Host direct `send_image_file` plus `_as_autosend_late_files` (and queue worker autosend) sent the same still twice.

### Fix (core)
`_weather_scene_visual_prompt` uses visual cues + `_local_lighting_hint()`; classify `media` part drops on-image caption for weather-scene; adapter skips autosend when direct image delivery succeeds.

### Prevent recurrence
Weather-scene must not request readable text in diffusion; one delivery path per shortcut image.

## 2026-09-01 20:30 +07 — scenic gate ack bypasses outbound filter

### Symptom
Classify and diffusion succeeded intermittently, but Zalo users saw no ack, no failure line, and sometimes no image — silent turn after classify.

### Root cause
1. `_as_gate_announce` sent scenic ack/fail lines through `send()` without `skip_outbound_filter`, so `gateway_noise.filter_outbound` / `/v1/outbound` could drop host-owned copy.
2. Media shortcut ran late in the inbound handler (after inflight drop) and workflow submit could return `True` on media gates without invoking the host shortcut on a secondary path.

### Fix (core)
Gate announces bypass outbound filter; early bare-text media shortcut before inflight; workflow media-gate path calls `_as_run_host_media_shortcut`. Omni image HTTP errors log status code.

### Prevent recurrence
Host-owned gate lines (ack, fail, queue) must always set `skip_outbound_filter`.

## 2026-09-01 20:15 +07 — scenic image delivery: shared media/out + direct Zalo send

### Symptom
Classify succeeded and container `run_scene_image` returned OK (~26s), but Zalo users received no image — inbound messages logged with no outbound attachment.

### Root cause
1. Diffusion wrote under `/data/media/out` while Zalo autosend and bridge scan `/opt/data/media/out` first (`HERMES_SHARED_DATA`).
2. Autosend grace window (8s) expired before ~26s diffusion finished, so late files were never claimed.
3. Synchronous `run_scene_image` blocked the adapter event loop during generation.

### Fix (core)
`media_shortcuts._media_out_candidates()` prefers shared SoT; adapter acks, offloads diffusion to a worker thread, and direct-sends images on success; autosend roots include legacy `/data/media/out`. patch-hermes syncs head member and clears obsolete image pins on shared `.env`.

### Prevent recurrence
Scenic output paths must match Zalo bridge scan order; long diffusion must not rely on autosend grace alone.

## 2026-09-01 19:45 +07 — image-gen AI Box head pin; drop Horde from combo

### Symptom
Classify and Hermes chat combos responded in seconds; scenic image asks timed out with media-out failure. Omni logs showed `image-gen` falling through to AI Horde (30s timeouts) while direct `wan2.7-image-pro` smoke passed.

### Root cause
1. Host `run_scene_image` posted `model=image-gen` (combo) — Omni priority drained into broken free Horde workers.
2. Obsolete `IMAGE_GEN_HEAD_MODEL` lingered in shared `/data/assistant/.env`.
3. Plugin overlay sync failed without sudo (fixed separately).

### Fix (core)
Pin `IMAGE_GEN_HEAD_MEMBER` to ranked AI Box head; media_shortcuts calls head directly. first-setup: AI Box-only combo when heads exist; clear obsolete pins on stack + shared `.env`.

### Prevent recurrence
Scenic diffusion must not use combo names that include Horde when AI Box heads are registered; first-setup smoke uses the same head member as runtime.

## 2026-09-01 19:30 +07 — sync-zalo-plugins without sudo when deploy user owns overlay

### Symptom
After `git pull`, scenic asks still failed; host overlay `/data/assistant/plugins/zalo` stayed one revision behind SoT because `sync-zalo-plugins.sh` required `sudo` and exited without copying.

### Root cause
Deploy user `tn` owns `/data/assistant/plugins` but the sync script always invoked `sudo rm/cp`; non-interactive runs failed password prompt, leaving stale adapter on the host path.

### Fix (core)
When the deploy user can write the plugin parent directory, sync uses plain `rm`/`cp`; sudo remains only for root-owned paths.

### Prevent recurrence
Always run `bash scripts/main/sync-zalo-plugins.sh` after plugin pulls; script must not require sudo on standard deploy-user layouts.

## 2026-09-01 19:15 +07 — host media shortcut owns scenic turns; classify retry

### Symptom
Scenic asks returned the media-out failure line while Hermes logs showed `execute_code` calling Omni `/v1/images/generations` with `NO_API_KEY` — bypassing the host `run_scene_image` path that resolves keys via `omni_env`.

### Root cause
1. When classify succeeded on enqueue but failed on first inbound pass, `_as_try_workflow_submit` created an async workflow for `media_generation` and the workflow worker sent the SCENE instruction to Hermes.
2. Queued drain called `handle_message` without re-running media shortcuts.
3. Single-shot classify HTTP had no retry on transient OmniRouter queue saturation.

### Fix (core)
Extract `_as_run_host_media_shortcut` and invoke it from inbound, workflow submit (before schedule/workflow), and queue drain. Block workflow creation when `plan_media_shortcut_gate` is set. Classify client: three attempts with backoff; normalize forces `process_original_message=false` for pure host media.

### Prevent recurrence
Host-owned media (`plan_media_shortcut_gate`) must never open Hermes diffusion or async workflow; queue drain must re-check shortcuts before gateway.

## 2026-09-01 18:30 +07 — scenic image-gen HD canvas; drop head-model env pin

### Symptom
Scenic asks still failed after priority combo rollout; troubleshooting asks routed to Hermes architecture essays. Legacy `IMAGE_GEN_HEAD_MODEL` env pin lingered in patch scripts.

### Root cause
1. Host scenic path used Full HD `1920x1080` / square `1024x1024` inconsistently; combo drains timed out on large canvases.
2. Classifier had no family for image-gen failure/status asks.
3. Obsolete per-member `IMAGE_GEN_HEAD_MODEL` pin conflicted with combo-only routing.

### Fix (core)
Host scenic path: HD `1280x720` default, configurable timeout, combo `image-gen` only, scaled quality guard. Drop `IMAGE_GEN_HEAD_MODEL` from patch-hermes; first-setup clears obsolete key. Classifier media part: image-gen diagnostic → host direct reply.

### Prevent recurrence
Scenic diffusion stays on combo `image-gen` with `priority` strategy; no per-member env pins; diagnostic asks never open Hermes chat.

## 2026-09-01 16:30 +07 — image-gen priority fallback; scenic-vs-OCR classification guard

### Symptom
Scenic "vẽ hình …" asks intermittently returned either "Hiện chưa tạo được file này" (media-out failure) or "mình không thấy hình ảnh nào được gửi kèm" (image-analyze misroute).

### Root cause
1. The `image-gen` combo used `round-robin` across 8 members (AI Box + free AI Horde). Round-robin cycles evenly, so free Horde workers — which hang or return censored placeholders — served many scenic requests, failing host delivery.
2. The classifier `media` part still referenced `combo image-gen` for the OCR handoff, and did not explicitly reject draw/paint asks with no attachment; weaker classifier members in rotation drifted to image-analyze.

### Fix (core)
`IMAGE_GEN_COMBO_STRATEGY` defaults the `image-gen` combo to `priority` (OmniRoute's fallback: head model drains before the next). Classifier media part now routes image analyze through `combo vision-ocr` and hard-disambiguates a no-attachment draw/paint ask into `media_generation` + SCENE. Baked `config/classify.json` re-assembled from parts.

### Prevent recurrence
Keep `image-gen` (diffusion) distinct from `vision-ocr` (multimodal); scenic diffusion combos must favor fast paid heads over free fallbacks via `priority`.

## 2026-09-01 11:25 +07 — OCR vision on vision-ocr; image-gen diffusion-only

### Symptom
Inbound image analyze routed `OCR_MODEL=image-gen`, but the `image-gen` combo holds diffusion-only models (AI Box qwen-image, AI Horde) that reject `/chat/completions` with HTTP 400/502 — so every image analyze failed.

### Root cause
The OCR worker's vision path posts `/v1/chat/completions` with `model=OCR_MODEL`; pointing it at a diffusion combo cannot produce a text description. The earlier "route image analyze through image-gen" decision conflated diffusion (`/images/generations`) with multimodal chat.

### Fix (core)
`pin_media_combos` sets `OCR_MODEL` from `OMNIROUTER_VISION_COMBO` (`vision-ocr`); OCR worker default `MODEL` and its docstring reverted to `vision-ocr`. Combo `image-gen` remains diffusion-only.

### Prevent recurrence
Keep image generation (`/images/generations`) and image analyze (`/chat/completions` multimodal) on separate combos: `image-gen` vs `vision-ocr`.

## 2026-09-01 11:10 +07 — AI Box custom image-model repair; neutral image analyze; slim acks

### Symptom
AI Box image generators never returned an image from combo `image-gen`: `/v1/images/generations` silently skipped them. Image acks still appended a fixed "summarize / translate / save knowledge" footer, and the host adapter still hardcoded image/vision prompts plus timing helpers.

### Root cause
The AI Box custom model `qwen-image-2.0` was registered with `supportedEndpoints: ["chat"]`, not `["images"]`; the other three whitelisted models were absent as active custom models. OmniRoute only routes a custom model through `/v1/images/generations` when `supportedEndpoints` includes `images`. The host adapter owned natural-language prompt/timing concerns that belong to the LLM/OCR worker.

### Fix (core)
first-setup registers/repairs the four AI Box image models on their `images-generations` provider node via `/api/provider-models` (POST add / PUT fix) with `apiFormat=images-generations` + `supportedEndpoints=["images"]`. Zalo image/file acks drop the fixed footer; OCR keeps only a "Đã đọc chữ:" header. Host-side scene-text and timing helpers removed; OCR worker owns multimodal summarization through `image-gen`.

### Prevent recurrence
After adding an AI Box provider, run first-setup so its image models get the correct image endpoint tags; keep image analysis prompting in the OCR worker, not the host adapter.

## 2026-09-01 07:15 +07 — Quote-reply image; AI Box in image-gen combo; analyze path

### Symptom
Quote-reply to a photo in Zalo did not download/analyze the quoted image. Inbound image analyze still routed to `vision-ocr`. AI Box image generators were excluded from combo `image-gen` after the prior chat-junk fix.

### Root cause
Quote media merge ran after the group mention gate, so quoted images were invisible to buffered-media logic. `_as_vision_scene_text` forced `image-gen` → `vision-ocr`. first-setup excluded all `img-gen/*` models, including whitelisted AI Box image generators.

### Fix (core)
`merge_inbound_quote_media` before mention gate; bridge `quoted` alias + attachment quote forward; first-setup whitelists four AI Box image models with Horde fallback; OCR_MODEL pins to image-gen combo; neutral multimodal summary prompt.

### Prevent recurrence
Run first-setup after AI Box provider changes; keep quote media extraction ahead of gates; do not blanket-exclude `img-gen/` — only chat junk.

## 2026-08-31 23:00 +07 — Hermes execute_code blocked on image-gen key probe

### Symptom
Image ask got no attachment; Hermes tried `execute_code` to read replica `.env` / config for API keys — security denied; user saw no image.

### Root cause
Host `_omni_generate_still` only read process env; replica/shared `.env` often lacked synced `OMNIROUTER_API_KEY`. Classify sometimes kept `process_original_message true`, so Hermes image-gen skill hunted keys via scripts instead of failing cleanly.

### Fix (core)
`omni_env.resolve_omni_api_key()` reads stack/shared env files; patch-hermes writes Omni keys into `/opt/data/.env` and non-symlink replica copies; skills forbid execute_code secret scans.

### Prevent recurrence
Never probe `.env`/replica paths from Hermes for diffusion; host owns scenic delivery with synced stack keys.

## 2026-08-31 22:00 +07 — image-gen combo polluted with AI Box chat models

### Symptom
Omni combo `image-gen` round-robin hit AI Box `image-gen/qwen-image-2.0` and `image-gen/deepseek-v4-flash`; `/images/generations` returned no image (`No images-capable targets in combo`).

### Root cause
AI Box chat endpoints share the `image-gen/` model namespace (colliding with combo name `image-gen`). Catalog lacks image modalities for AI Horde workers, so first-setup never refilled after operator added AI Box members.

### Fix (core)
first-setup treats `aihorde/*` and OpenRouter Flux/image as diffusion targets, excludes `image-gen/*` chat models, force-refills bad combos; load_env expands literal `\n` in corrupted one-line `.env` templates.

### Prevent recurrence
Never pin AI Box chat models into combo `image-gen`; run first-setup after Omni provider changes to restore aihorde diffusion members.

## 2026-08-31 21:00 +07 — Host scenic image-gen shortcut; security-safe delivery

### Symptom
Hermes image-gen skill attempted `curl | python` to plain HTTP OmniRouter; Tirith/security blocked the turn. Scenic-only classify path set `process_original_message true` but adapter had no host shortcut despite `plan_allows_scene_image`.

### Root cause
Scenic-only diffusion was delegated to Hermes shell one-liners; host already had `_omni_generate_still` via urllib but no `run_scene_image` wiring. Low-quality AI Horde stubs still passed the 48KB guard.

### Fix (core)
`run_scene_image` host shortcut + classify `process_original_message false` for scenic-only; image-gen skill documents non-shell Omni path; quality guard 960×540 / 80KB; first-setup photoreal-first image-gen combo ordering.

### Prevent recurrence
Never route scenic-only diffusion through bash curl pipes; keep classify host-owned media families on internal HTTP shortcuts.

## 2026-08-31 20:00 +07 — Omni-only web-search; drop direct adapter chain

### Change
Router Worker `/v1/search` proxies only to Omni combo `web-search`. Removed `WEB_BACKENDS`, baked `web-search-combo.json`, and direct Tavily/Firecrawl/SearXNG/Exa search adapters. first-setup clears legacy env keys; page extract keeps Tavily/Firecrawl on `/v1/extract`.

## 2026-08-31 19:00 +07 — Combo-only web-search; low-quality image-gen guard

### Symptom
Omni logs showed `tavily-search` instead of combo `web-search`; Zalo-delivered scenic images were blurry low-res stubs.

### Root cause
Router Worker fell through to provider-specific Omni search bodies after combo attempt; diffusion workers returned tiny/censor placeholders that host still saved and sent.

### Fix (core)
Omni search uses `{ combo: web-search }` only; image-gen rejects sub-HD/tiny blobs before Zalo send.

### Prevent recurrence
Do not hardcode provider failover lists in repo JSON — operator combo members live in Omni UI; validate pixel size before delivering generated stills.

## 2026-08-31 18:30 +07 — Zalo bare image skipped vision-ocr combo

### Symptom
Random image from Zalo got OCR-only failure line even when the photo had visible subjects; Omni logs showed classifier/hermes but not vision-ocr.

### Root cause
Host-ack path treated all `ocr` attachments (including images) as deterministic OCR ack and returned before classify; empty Paddle text never triggered adapter vision fallback.

### Fix (core)
Vision-ocr combo call when OCR text empty; host-ack only for bare images with OCR/vision content; captioned or empty-after-vision images fall through to classify/Hermes with media kept.

### Prevent recurrence
Do not put image attachments in the same host-ack bucket as office/text PDF extract; vision-ocr must run before OCR-only user messaging.

## 2026-08-31 18:00 +07 — image-gen HD canvas 1920x1080

### Symptom
Scenic diffusion still used square 1024 canvas while operator docs described Full HD landscape output.

### Root cause
Skill and Zalo host shortcut hardcoded `1024x1024` after the combo-only migration.

### Fix (core)
image-gen skill and host `_omni_generate_still` default to `1920x1080` (16:9); dispatcher comment aligned.

### Prevent recurrence
Canvas size lives in image-gen skill only — no `.env` size pins.

## 2026-08-31 17:00 +07 — strict active|inactive; web-search combo routing

### Symptom
Legacy truthy env values (`1`, `true`, `yes`, `on`) still enabled features; search provider cascade duplicated between env and router JSON; image-gen first-setup hardcoded model/style lists.

### Root cause
Gradual active|inactive migration left read-time legacy acceptance in Python; `OMNIROUTER_SEARCH_PROVIDERS` bypassed operator Omni combo `web-search`.

### Fix (core)
`env_active()` accepts only `active`/`inactive`; web-search uses combo env chain + JSON `omni_providers`; image-gen fill from catalog only; first-setup verifies `web-search` combo on API key ACL.

### Prevent recurrence
New toggles use active|inactive only; search failover order owned by combo JSON + Omni UI, not host env lists.

## 2026-08-31 16:20 +07 — active|inactive env flags; web-search cascade

## 2026-08-31 08:15 +07 — Pillow image layout retired; diffusion labeled stills

### Symptom
Labeled/weather images used hardcoded Pillow info-card and overlay layout; NSFW censor recovery used fixed retry prompts in dispatcher code; vision-ocr kimi returned empty `content`.

### Root cause
Dispatcher owned layout modules (`info_card`, `overlay`) instead of diffusion; image_backends retried with hardcoded cityscape templates; OCR vision parser read only `message.content`.

### Fix (core)
Remove layout modules; host/classify route labeled and weather stills through Omni combo `image-gen` with facts in SCENE; NSFW/SFW guidance in classify/image-gen skills; OCR reads `reasoning_content` fallback; `RENDER: weather-scene` / `labeled-scene` gates.

### Prevent recurrence
No new Pillow layout for informational stills; strengthen classify SCENE prompts instead of Python retry templates.

## 2026-08-31 07:40 +07 — Media defaults not OpenCode-first; invented aerial SCENE

### Symptom
Vision/embedding first-setup preferred non-OpenCode providers; scenic classify/examples still steered toward aerial/top-down phrasing even when the user did not ask for that viewpoint.

### Root cause
Capability-matched media fill ranked Gemini/OpenRouter ahead of OpenCode; scenic examples and fixtures reused aerial wording from older weather cases.

### Fix (core)
OpenCode-first for vision-ocr and embedding defaults; keep image-gen on diffusion-capable members; classify/image-gen and lab fixtures stop inventing aerial viewpoints; image attachment instructions require scene summary plus text extract.

### Prevent recurrence
Default combo fills for chat/vision/embed start with OpenCode; only add aerial/top-down SCENE text when the user asks for that viewpoint.

## 2026-08-31 07:10 +07 — image-gen empty; scenic ask refused; search combo naming

### Symptom
Scenic image asks failed with “image-gen has no image-capable targets”; Omni key could block stack combos when `allowedCombos` was empty; web-search combo naming/backends were inconsistent with Tavily→Firecrawl→SearXNG failover.

### Root cause
`image-gen` accepted any `aihorde/*` id including aphrodite chat workers; Omni treats empty `allowedCombos` as deny-all for combo names; web-search SoT still used legacy `websearch` / Omni-only backends.

### Fix (core)
Require image modality (reject aphrodite/non-diffusion) when filling `image-gen`; pin API key `allowedCombos` for stack combos; rename/align combo `web-search` with Omni→direct adapter failover and skill docs; refill `embedding` with embed-capable catalog models and smoke `/v1/embeddings`.

### Prevent recurrence
Never classify AI Horde LLM workers as diffusion; always pin key combo allowlists after creating stack combos; keep web-search backends Omni-first with direct fallbacks.

## 2026-08-30 20:55 +07 — Image OCR blocked by AV-down; weather ask silent; cartoon stills

### Symptom
Inbound images for OCR were refused with antivirus-not-ready while ClamAV/av-gateway were down; live weather scene asks could end with no Zalo reply; Omni image-gen stills looked cartoonish.

### Root cause
Zalo AV gate treated `ENABLE_ANTIVIRUS=active` as hard-required even when the gateway was unreachable; antivirus containers were not healed by stack-watch; diffusion prompts/combo members under-emphasized photoreal photography.

### Fix (core)
Soft-fail AV when gateway/clamd are down (Security Manager fallback; hard refuse only with `AV_REQUIRED=active`); heal antivirus profile in stack-watch; strengthen weather/scenic classify + image-gen photoreal prompts; exclude cartoon/anime models from image-gen combo fill; raise classify retry.

### Prevent recurrence
Never equate ENABLE_ANTIVIRUS with AV_REQUIRED; keep photoreal constraints in classify SCENE / image-gen skill; keep antivirus heal when the flag is active.

## 2026-08-30 20:25 +07 — Backup/security still compared ENABLE_*=1 after migrate

### Symptom
With `.env` toggles already migrated to `active`/`inactive`, backup compose profile selection, security-manager gates, and several host helpers still compared against `1`/`0`, so optional profiles and AV/YARA paths could be skipped incorrectly.

### Root cause
Earlier writer conversion did not cover all readers/checkers in backup, workers, security-manager, OCR/office, and channel helpers.

### Fix (core)
Use `_env_active` / explicit `active` membership for ENABLE_* and related toggles across backup.sh, workers.sh, security-manager, model-router defaults, OCR, office_file, and Zalo/log/ovpn scripts; keep legacy `1`/`0` accepted.

### Prevent recurrence
Any new ENABLE_* check must accept `active` (and migrate writers must emit only `active`/`inactive`).

## 2026-08-30 20:10 +07 — Core scripts still wrote ENABLE_*=1|0

### Symptom
After the active/inactive toggle migration, install/resolve, Zalo setup, and security smoke paths still emitted or compared `ENABLE_*=1|0`, so new writes and checks could disagree with migrated `.env` values.

### Root cause
Writers and equality checks were not fully converted when canonical values became `active`/`inactive`.

### Fix (core)
`install-component.sh`, setup/restore/Zalo helpers, `stack-watch`, `check-security`, and related comments/docs now set and test `active`/`inactive`. Legacy `1`/`0` remains accepted via migrate/`_env_active`.

### Prevent recurrence
Never write `ENABLE_*=1|0` from core install/setup paths; use `active`/`inactive` only.

## 2026-08-30 19:20 +07 — Scenic Hermes still guided to dispatcher / manim path

### Symptom
After classify, still-image jobs still pointed at dispatcher `/v1/image` (or inactive-worker `model=hermes`) with legacy manim/matplotlib/PIL framing instead of Omni combo image-gen.

### Root cause
Workflow suffix and skills still treated dispatcher diffusion as the scenic API; inactive-worker policy reused chat combo hermes for stills.

### Fix (core)
Always Omni `/images/generations` model `image-gen` for still diffusion; retire dispatcher diffusion (HTTP 410); Pillow-only `/v1/info-card` and `/v1/text-poster`; host weather Omni + `/v1/overlay`. Container classify/websearch path resolution no longer assumes repo parents. Setup refills `image-gen` when chat-only (e.g. OpenCode) members displace AI Horde / Flux. Model-router enable flags accept `active` so classify candidates are not empty after the active/inactive toggle migration.

### Prevent recurrence
Never reintroduce dispatcher `/v1/image` for scenic diffusion, Comfy/manim/PIL generation hints, or `model=hermes` for still images. Keep `image-gen` members image-capable only. Keep enable-flag parsers accepting `active`.

## 2026-08-30 19:00 +07 — Scenic ask still guided to dispatcher/Comfy-era path

### Symptom
Image-generation asks still followed a dispatcher/Comfy-era Hermes hint instead of OmniRouter combo image-gen /images/generations.

### Root cause
Workflow suffix and image-gen skill centered on dispatcher /v1/image (legacy stack framing).

### Fix (core)
image-gen skill, classify media, media-file, and Zalo workflow suffix call OmniRouter /v1/images/generations with model image-gen; Hermes env gets Omni URL/key and IMAGE_GEN_COMBO.

### Prevent recurrence
Never route scenic diffusion through ComfyUI or local drawing scripts; keep Omni combo image-gen as the still-image SoT.

## 2026-08-30 18:55 +07 — Scenic ask still got Comfy-era manim/PIL workflow hint

### Symptom
Scenic image asks still received a Hermes workflow suffix telling the agent to avoid manim/matplotlib/PIL via dispatcher only — leftover Comfy-era framing instead of Omni combo image-gen.

### Root cause
Zalo workflow job runner appended a fixed pre-Omni media hint; classify/image-gen still under-emphasized OmniRouter combo image-gen.

### Fix (core)
Replace the workflow suffix and strengthen image-gen/classify so still images use dispatcher → OmniRouter combo image-gen /images/generations.

### Prevent recurrence
Never reintroduce ComfyUI or local drawing-script hints for scenic diffusion; keep Omni combo image-gen as the SoT path.

## 2026-08-30 18:45 +07 — Scenic aerial example bias; OCR extract-only prompt

### Symptom
Scenic examples pushed “Aerial view … from above” wording. Image OCR used an extract-only markdown prompt that skewed vision answers.

### Root cause
Hardcoded scenic examples and a shared OCR prompt that only asked to extract text as markdown.

### Fix (core)
Neutral scenic examples in image-gen/answering/classify; OCR callers and defaults use an analyze-file prompt that still preserves readable text as markdown.

### Prevent recurrence
Do not hardcode aerial-view stock phrases in scenic examples; keep OCR prompts analysis-first for images.

## 2026-08-30 10:50 +07 — Scenic Saigon image returned NSFW censor stub

### Symptom
Aerial cityscape asks using colloquial Saigon returned an image labeled as censored NSFW blocked content.

### Root cause
AI Horde safety filters false-positive on the colloquial place name Saigon even for SFW skyline prompts; official English Ho Chi Minh City does not trigger the stub.

### Fix (core)
Classify/image-gen SCENE guidance maps Saigon/Sài Gòn → Ho Chi Minh City for diffusion. Dispatcher sanitizes the same aliases and treats tiny censor placeholders as backend failure (retry/fail).

### Prevent recurrence
Never put colloquial Saigon alone in diffusion prompts; prefer official English toponyms when safety filters are known to false-positive.

## 2026-08-30 10:30 +07 — Scenic aerial still host-shortcut; prompt not LLM-owned

### Symptom
Scenic/aerial draw asks were owned by a host scene_image shortcut instead of Hermes image-gen, so the diffusion English prompt was not produced by the LLM skill path.

### Root cause
Classify SCENE IMAGE set process_original_message false and the adapter gated scene_image as a host-owned turn.

### Fix (core)
Remove scene_image host shortcut/gate; classify scenic-only as Hermes+image-gen with English SCENE: instructions; strengthen image-gen/answering skills accordingly.

### Prevent recurrence
Never add a separate aerial skill or host shortcut for scenic-only diffusion; keep English SCENE prompts in classify + image-gen.

## 2026-08-30 10:15 +07 — Scenic image fail; ENABLE toggles still numeric

### Symptom
Aerial/scenic image asks returned the media-out failure line. Host feature flags still used 1/0. OpenBao retained retired image-vendor secrets; unused search skill trees lingered.

### Root cause
image-gen combo accepted multimodal chat models (Gemini) as image capable because modality checks treated input-image chat as diffusion. Intersection with those members kept a broken combo. Toggle SoT mixed numeric and active.

### Fix (core)
Strict diffusion detector + force refill + setup smoke for image-gen; canonical active/inactive migrate in workers/run/env; OpenBao obsolete-key purge; remove unused firecrawl/tavily/searxng skill trees from repo.

### Prevent recurrence
Never put chat/vision models in image-gen; never leave ENABLE_*=1 as the documented on-value; purge retired secrets on each OpenBao seed.

## 2026-08-30 09:30 +07 — Media toggles and hardcoded image model/size

### Symptom
Media flags mixed `1`/`true`/`active`; `.env` pinned `IMAGE_GEN_SIZE` and `IMAGE_OMNI_MODEL` so diffusion did not rely solely on type-based combos.

### Root cause
Compat truthy sets and first-setup/dispatcher fallbacks treated single-model and size as env SoT.

### Fix (core)
`ENABLE_MEDIA_FILE` / `WORKER_MEDIA_FILE` → `active` only (with legacy migrate); clear obsolete image env keys; dispatcher sends combo name only and optional request `size`; image-gen skill declares default HD `1024x1024`.

### Prevent recurrence
Never pin a single Omni image model or canvas size in `.env`; never treat media `1` as the canonical on-value.

## 2026-08-30 09:00 +07 — Aerial image fail; bare photo OCR skipped vision-ocr

### Symptom
Scenic image asks returned the media-out failure line; bare photo replies said OCR found no clear text. Combo `image-gen` / `vision-ocr` were not used.

### Root cause
`.env` pinned `IMAGE_GEN_COMBO=hermes` / `OCR_MODEL=hermes` because pin only checked `ENABLE_MEDIA_FILE` (not `WORKER_MEDIA_FILE=active`). `image-gen` members were chat models (not images-capable). Paddle returned glyph noise and short-circuited vision.

### Fix (core)
Pin media when worker is active; fill `image-gen` with AI Horde / image-output models and `vision-ocr` with supportsVision models; OCR noise → vision; Omni `IMAGE_OMNI_MODEL` fallback on dispatcher.

### Prevent recurrence
Never put chat-only models in `image-gen`; never treat Media worker active as inactive for combo pins.

## 2026-08-30 08:50 +07 — Dispatcher still documented Low profile search; media combos were stubs

### Symptom
Dispatcher README still described Low/Medium/High and `POST /v1/search` on the media worker; media Omni combos had a single stub instead of OpenCode members like hermes.

### Root cause
Stale profile-tier docs after search moved to model-router; media ensure used a one-model shell path.

### Fix (core)
Rewrite dispatcher README; office-file comments follow Media worker flags; `ensure_media_combos` uses OpenCode fill (`refill_if_below=3`).

### Prevent recurrence
Do not document profile Low/Med/High on dispatcher; media combos share the hermes OpenCode ensure path.

## 2026-08-30 08:40 +07 — Omni combo shells image-gen / vision-ocr / embedding missing

### Symptom
After media combo cutover, OmniRoute UI only showed `hermes` and `classifier` — dedicated media combos never appeared.

### Root cause
`ensure_combo_shell` POSTed `models: []`; Omni rejects empty combos. `http_json` raised HTTP 400 so the stub retry never ran.

### Fix (core)
Create media combo shells with one OpenCode stub member; do not overwrite existing operator-owned members.

### Prevent recurrence
Never create Omni combos with an empty models list.

## 2026-08-30 08:30 +07 — Legacy Comfy aliases and stub skills left behind

### Symptom
Dispatcher still accepted `comfy-cpu` aliases; `comfyui` skill folders and first-setup Qwen/Ollama cleanup helpers remained after the Omni combo cutover.

### Root cause
Incomplete removal after media combo migration.

### Fix (core)
Delete Comfy skill trees/workflows/ensure script; simplify `image_backends`; drop first-setup cleanup helpers; inactive media pins `hermes`; OCR Paddle→vision-ocr for all scanned docs.

### Prevent recurrence
Do not leave disabled stubs for removed engines — delete the code and skills.

## 2026-08-30 08:00 +07 — Drop ComfyUI; route image/OCR/embed via router combos

### Symptom
Stack depended on ComfyUI checkpoints and host API keys (FAL/Flux/Pollinations/dall-e defaults) for image gen; OCR/embed combo names were not first-class.

### Root cause
Media worker pinned `IMAGE_BACKENDS=comfy-cpu,…` and optional paid keys in `.env.example`; skills pointed Hermes at Comfy.

### Fix (core)
Dispatcher omni→n9 with `IMAGE_GEN_COMBO=image-gen`; remove Comfy compose services; OCR `vision-ocr`; embed `embedding`; first-setup creates combo shells; refuse music/audio/URL transcripts; skills + classify media policy updated.

### Prevent recurrence
Never reintroduce ComfyUI or host image vendor keys — operators fill Omni/9Router combo members in the router UI.

## 2026-08-29 19:30 +07 — IMAGE_BACKENDS omni-first in .env broke Comfy-first policy

### Symptom
`/health` showed `image_backends: ["omni","comfy-cpu","comfy-gpu"]`; scenic images skipped Comfy unless `provider` forced.

### Root cause
`.env` pinned Omni before Comfy; empty `IMAGE_BACKENDS=` in compose disabled dispatcher backends; health read raw env not resolved list.

### Fix (core)
`image_backends.py` canonical order + empty→default; compose/first-setup pin `comfy-cpu,comfy-gpu,omni`; health uses `image_backends()`.

### Prevent recurrence
Never accept arbitrary backend list order — always canonicalize Comfy before Omni on dispatcher.

## 2026-08-29 19:00 +07 — IMAGE_OMNI_MODEL default dall-e-3 with no OpenAI creds

### Symptom
Scenic image `POST /v1/image` failed: OmniRouter `No credentials for image provider: openai` while Comfy `/models/checkpoints` was `[]`.

### Root cause
Default `IMAGE_OMNI_MODEL=dall-e-3` in `.env.example` / compose; lab `.env` inherited it after pull.

### Fix (core)
Default to `aihorde/Flux.1-Schnell fp8 (Compact)` — works via OmniRouter without OpenAI. Quote value in `.env` when it contains spaces/parens.

### Prevent recurrence
Never ship dall-e-3 as default unless OpenAI image creds are part of first-setup; document quote requirement in `.env.example`.

## 2026-08-29 18:15 +07 — Aerial image silent after attachment recall

### Symptom
`vẽ hình … nhìn từ trên cao` after earlier photos/files → complete silence (no image, no error line).

### Root cause
`_as_attachment_followup` injected `[Recent attachments…]`; media shortcut block skipped when recall present; workflow media-gate returned handled without sending anything.

### Fix (core)
Classify `user_text_before_attach` for media shortcuts (recall stays for Hermes only). Remove workflow swallow; `_as_gate_announce` for fail-line; sync-zalo-plugins overlays all replica plugin dirs.

### Prevent recurrence
Never gate scenic/weather shortcuts on attachment-recall blocks — only sheet/office paths need that guard.

## 2026-08-29 18:30 +07 — Zalo plugins stale after git pull

### Symptom
After `git pull` + `run.sh update`, aerial image asks still got Hermes backend-error prose (not host media-out failure line).

### Root cause
Hermes mounts `/data/assistant/plugins/zalo`, not `hermes/main/plugins/zalo` from git. Only `setup-zalo.sh` copied plugins; `run.sh update` did not.

### Fix (core)
`sync-zalo-plugins.sh` on every update; restart Hermes replicas. Workflow submit skips host-owned media gates.

### Prevent recurrence
Any plugin-only fix must ship via sync-zalo-plugins on update, not git pull alone.

## 2026-08-29 18:00 +07 — Scenic image shortcut fail → /help intro

### Symptom
Aerial HCMC image ask returned backend-unavailable prose plus a first-meeting `/help` greeting instead of a file or a single failure line.

### Root cause
Host `run_scene_image` returned `None` on diffusion 502; adapter only short-circuited on success, so Hermes handled the turn and produced persona/backend recovery chatter.

### Fix (core)
`plan_media_shortcut_gate` + `shortcut_consumed` contract: failed host shortcuts send media-out failure line and return (no Hermes). Weather-scene falls back to Pillow info-card when diffusion is down. Classify: `process_original_message false` on host-owned image paths.

### Prevent recurrence
Any host media gate must consume the turn on failure — never fall through to Hermes for classified image shortcuts.

## 2026-08-29 17:00 +07 — Aerial city vs weather picture vs info-card

### Symptom
“Draw aerial HCMC” and “draw current HCMC weather picture” both produced the same metrics info-card dashboard instead of a scenic photo or city+overlay weather image.

### Root cause
Classify and host treated all live-data image asks as LABELED INFO IMAGE → info-card. No separate scenic-only or weather-scene+overlay contract.

### Fix (core)
Classify: WEATHER SCENE IMAGE (`RENDER: scene-overlay`, `SCENE:`, search), SCENE IMAGE (scenic `SCENE:` only), LABELED INFO IMAGE (`RENDER: info-card` / TITLE). Host: `run_search_then_weather_scene`, `run_scene_image`, `run_search_then_info_card` gates.

### Prevent recurrence
Never route scenic or weather-picture asks to info-card unless the user wants a metrics dashboard card.

## 2026-08-29 14:00 +07 — Sheet follow-up lost workbook memory

### Symptom
User asked what sheet 2 describes after an Excel extract; chat stayed silent or the bot claimed no file was attached and asked for a re-upload.

### Root cause
Attachment recall TTL was short; large workbook extracts truncated away sheet inventory; ingest headers lacked 1-based indices; media shortcuts/Hermes treated the ask as a missing file.

### Fix (core)
Ingest: `Workbook sheets:` inventory + `## Sheet N (title)`. Longer recall TTL; prefer inventory when truncating. Classify WORKBOOK/SHEET FOLLOW-UP with `SHEET_REF:`. Host answers from remembered extract; skip media shortcuts on Recent attachments. Answering skill: never ask re-send when extract is present.

### Prevent recurrence
Keep sheet inventory durable in recall; resolve sheet asks via classify SHEET_REF + host memory, not re-upload prompts.

## 2026-08-29 12:15 +07 — Weather info image on disk but no Zalo reply

### Symptom
User asked for a labeled live weather image; the PNG was created under media/out but the chat stayed silent.

### Root cause
`/v1/image` info-card mode wrote the file and returned ok without honoring `send_zalo`. The host shortcut set `send_zalo=false` and relied on late autosend, which often missed shortcut-created files (turn dest not remembered before late watch).

### Fix (core)
Info-card path sends via bridge when `send_zalo=true` (file still kept for autosend if send fails). Host search→info-card enables send. Adapter calls `_as_autosend_remember_turn` before late autosend on media shortcuts.

### Prevent recurrence
Treat labeled info images like office-file: write + deliver, with autosend as fallback only.

## 2026-08-29 11:45 +07 — Weather info image: greeting + empty broken card

### Symptom
User asked for a beautiful image with current city weather. Bot replied with a default AI/`/help` intro; the delivered card showed a truncated English scene prompt as the title and “(no details)”.

### Root cause
Labeled live-data **image** asks had no host search→info-card path (unlike PDF), so Hermes often fell through under rate-limit/persona defaults. Hermes/`refine` passed an English scene sentence into info-card without TITLE markers or fact lines; overlay was ignored; layout clipped a single long title.

### Fix (core)
Classify LABELED INFO IMAGE (search + media_generation, markers only). Host `plan_allows_search_then_image` / `run_search_then_info_card`. Info-card: reject scene-prompt dumps, merge overlay, wrap title, OVERVIEW/BACKGROUND, never “(no details)”. Auto-route TITLE: prompts to info-card without refine.

### Prevent recurrence
Never send English scene prose alone to info-card. Prefer host search→info-card for live labeled images.

## 2026-08-29 10:45 +07 — Place visual PDFs needed overview/background

### Symptom
When the ask named a place/city in the visual PDF title, the sheet still showed metrics only — no place intro or atmosphere/background.

### Root cause
Classify/file-gen contract stopped at TITLE/ICON/facts. Renderer and host body builder had no OVERVIEW/BACKGROUND path.

### Fix (core)
Classify PLACE SUBJECT rule (intent-based, no city dictionary). file-gen requires OVERVIEW/BACKGROUND for place titles. Host extracts/fills those markers from search prose. Styled sheet renders overview/background panels.

### Prevent recurrence
Keep place context as contract markers, not hardcoded place names.

## 2026-08-29 10:00 +07 — Visual office classify was weather/fuel-locked

### Symptom
Attractive live-data PDF asks outside the weather/fuel wording risked weak classify guidance because prompts named weather-app sheets, specific VN phrases, and fixed ICON enums.

### Root cause
Media classify / file-gen / image-gen treated one product family as the rule instead of a generic visual + live-facts office pattern.

### Fix (core)
Rewrite to generic VISUAL / ATTRACTIVE OFFICE FILE rules: markers TITLE/SUBTITLE/ICON, search sibling when live facts are needed, office-file owns in-document visuals, no decorative media_generation, no chat-only when a file was asked. Reassemble classify bake. Keep schedule/split examples as families only.

### Prevent recurrence
Do not hardcode topic dictionaries into classify media policy; keep examples illustrative.

## 2026-08-29 09:30 +07 — Weather PDF still looked cluttered (badge strip)

### Symptom
After the “rich icons” update, PDFs still looked poor: a row of Nắng/Mây/Mưa/… labels, duplicated temperature, and busy panels instead of a polished weather card.

### Root cause
ReportLab composition stacked too many decorations (badge strip + banner + fact rows) without a single visual hierarchy. No post-render layout check caught the clutter.

### Fix (core)
Pillow full-page weather sheet (sky band, one hero temp, one condition icon, 2-column metric tiles). `verify_styled_pdf_layout` rejects badge-strip clutter; fallback is a minimal clean card. Ship `weather_sheet.py` in the Dispatcher image.

### Prevent recurrence
Prefer one weather-app composition over stacking strips. Always verify layout after write.

## 2026-08-29 09:20 +07 — Attractive weather PDF still looked sparse (few icons)

### Symptom
Asks for a weather PDF “with full attractive images and icons” delivered a clean but plain card — one header glyph and text rows, no image panel.

### Root cause
Prior hardening blocked diffusion decoration (502 menus / Vietnamese tofu) and left office-file with a single vector icon. Skills told Hermes not to call image-gen for PDF decoration, so no visual banner was produced either.

### Fix (core)
Rich styled PDF: badge strip, companion icons, per-fact glyphs, embedded Pillow info-card banner (Unicode-safe). Classify/file-gen/image-gen: keep visual weather as one office-file PDF with internal visuals; optional scenic image-gen only for standalone photos, never block PDF delivery.

### Prevent recurrence
Do not equate “no diffusion” with “no images” — use info-card + vectors inside the PDF.

## 2026-08-29 09:10 +07 — Weather PDF still showed JSON dumps and fake hero temp

### Symptom
Delivered weather PDFs included raw `{'location': ...}` API text, markdown section headers, and used wind bearings like `246°WSW` as the large header temperature.

### Root cause
Search snippets often embed weather-API JSON or Python dict dumps. The host body builder pasted them as fact lines. Hero-temp scanned any token with `°`, so compass bearings won over Celsius.

### Fix (core)
Filter JSON/dict/markdown/label-only noise; parse valid weather JSON into labeled fact rows; hero temperature only from °C / temperature-labeled values. Classify: never paste raw JSON into the PDF body.

### Prevent recurrence
Never render search payload serialization on the card. Keep wind bearings out of the hero metric.

## 2026-08-29 09:00 +07 — Weather PDF UI: create-verb title + SERP junk rows

### Symptom
PDF files arrived, but the card showed create-instruction text as the title and raw search-result page titles (site chrome, truncated words) instead of clean weather facts.

### Root cause
Host body assembly treated the whole file instruction as TITLE when markers were mid-line, and appended SERP titles verbatim. `TITLE:` substring matching also stole values from `SUBTITLE:`. Styled PDF clipped long lines with no label/value layout.

### Fix (core)
Safe contract-marker extraction; SERP noise filter; prefer answer/snippets; infer icon from facts; richer office-file card (wrap, hero temperature, label/value). Classify media part: PDF instruction is TITLE/SUBTITLE/ICON only — no create-verb wrapper.

### Prevent recurrence
Never dump search page titles into the PDF body. Keep TITLE: parsing from mistaking SUBTITLE:.

## 2026-08-29 08:40 +07 — Designed weather PDF became chat text only

### Symptom
User asked for an attractive PDF of live Ho Chi Minh weather with icons. Bot replied with chat weather (and sometimes a text “card”) and no `share.file` PDF.

### Root cause
Classify correctly emitted search + file_processing(pdf). Host `plan_skips_media_shortcut` blocked the plain office shortcut for any search sibling. Hermes completed search then answered in chat and never called Dispatcher office-file.

### Fix (core)
Host `plan_allows_search_then_office` + `run_search_then_office` (model-router `/v1/search` → styled `/v1/office-file`). Classify media part + answering: never rewrite a file ask into chat-only weather. Unit covers gates and body assembly.

### Prevent recurrence
Never rely on Hermes to finish search→PDF after the host skipped the office shortcut. Keep search+file in classify so the host gate matches.

## 2026-08-29 08:15 +07 — Weather card Vietnamese diacritics became tofu boxes

### Symptom
Attractive weather/info visuals rendered Vietnamese with missing diacritics (white squares). Plain PDFs also risked incomplete glyph coverage.

### Root cause
Diffusion image backends bake text into pixels without a Unicode font. Overlay/poster/PDF font lists preferred incomplete paths or fell back to bitmap defaults.

### Fix (core)
Ship Noto Sans with the Dispatcher image; shared `fonts.py` picks a TTF that covers Vietnamese samples (cached). New Pillow `info-card` image mode for dashboards; office PDF/overlay/text-poster share the resolver. Local concurrent media smoke (no LLM).

### Prevent recurrence
Never ask diffusion to paint Vietnamese labels for dashboards — use info-card or office-file with bundled Noto.

## 2026-08-29 08:00 +07 — Attractive weather PDF became a menu + plain text file

### Symptom
User asked for a designed PDF of live Ho Chi Minh weather with icons/images. Bot replied with session-restore text and numbered options (retry image / PDF without images / supply API key). Delivered PDFs were plain one-line dumps.

### Root cause
Classify/Hermes treated “icons/images” as a hard `/v1/image` dependency. Image backends returned 502; the agent narrated internals and asked for keys. Dispatcher `office-file` PDF writer only drew monospaced text lines — no layout.

### Fix (core)
Styled PDF renderer in office-file (header band, vector icon, fact card) driven by TITLE/ICON/fact lines from file-gen. Classify: visual weather PDF stays search + pdf — no decorative image job. Harden skills so image failure never becomes an API-key / recovery menu; deliver the styled PDF instead.

### Prevent recurrence
Never block a PDF deliverable on image-backend health. Keep decorative visuals inside office-file for document asks.

## 2026-08-29 07:45 +07 — Weather PDF ask: SOUL blocked; reportlab path; no file

### Symptom
A request to design a PDF with current Ho Chi Minh weather (with attractive icons/images) produced chat weather text and/or Hermes default `/help` intro instead of a PDF. Logs showed SOUL blocked and local `pdf` skill collisions / reportlab attempts.

### Root cause
SOUL.md contained the literal jailbreak phrase scanned by Hermes `threat_patterns` as `prompt_injection`, so the entire SOUL context was dropped every turn. Without SOUL, the agent used default persona and tried ambiguous local pdf skills instead of Dispatcher `file-gen` / office-file (compound search+PDF also skipped the host office shortcut).

### Fix (core)
Reword SOUL and related safety/classify text to preserve untrusted-content policy without matching Hermes injection patterns. Expand the SOUL unit for `prompt_injection`. Harden classify + file-gen + answering so chat PDF create-and-send stays on Dispatcher office-file (never pip/reportlab / `skill_view pdf`).

### Prevent recurrence
Keep SOUL free of classic injection literals; bake/classify must not reintroduce them. Chat office create always routes through file-gen.

## 2026-08-28 19:30 +07 — Excel with sheet soft-probe returned a new txt file

### Symptom
Reading an `.xlsx` that contained a soft env/secret probe in one sheet returned a newly created `.txt` instead of a host extract ack.

### Root cause
After ingest extract, office media paths were cleared but host-ack only ran for bare/blank office. Meaningful extracts could fall through to the classify→office_shortcut path, which treated sheet text as a create-file job.

### Fix (core)
Always host-ack office/text/ocr attachment reads (same as archives). Skip attachment-body secret classify for office (sheet cells are DATA; caption-only). Do not run office shortcuts on `[Attachment text —` payloads. Harden classify accordingly.

### Prevent recurrence
Never route inbound office extracts into create-file shortcuts. Keep standalone short risk `.txt` refuse on the text kind path.

## 2026-08-28 18:50 +07 — Omni Grafana quota all zeros with scrape OK

### Symptom
OmniRouter LLM quota / usage panels showed 0 requests/tokens/cost and “No data” rate charts while OmniRouter scrape stayed OK.

### Root cause
`omni-exporter` (nine-exporter image) scraped legacy `/api/usage/stats` (and siblings). Current OmniRoute returns 404 there; optional 404 became empty usage while providers/login still succeeded, so scrape_success stayed 1.

### Fix (core)
Scrape `/api/usage/history` then `/api/usage/analytics`, coerce summary + list/dict breakdowns into the flat totals Grafana already queries. Keep older paths for 9Router compatibility.

### Prevent recurrence
When OmniRoute renames usage APIs, update exporter path list and coercion — do not treat scrape_success alone as proof that usage series are populated.

## 2026-08-28 18:30 +07 — Host regex scrub for chat/thread ids and locale folder text

### Symptom
Outbound sanitization used host regex (including locale-hardcoded folder wording) to hide chat/thread identifiers, conflicting with LLM-owned NLU/privacy rules.

### Root cause
Adapter post-filter tried to phrase-match identity leaks instead of classifying/outbound LLM policy.

### Fix (core)
Drop identity/DM/folder regex from adapter redact. Harden classify + outbound prompts; outbound may return cleaned `text` on send. Normalize outbound actions via a map.

### Prevent recurrence
Never reintroduce host phrase regex for chat privacy. Keep path/secret structural redact only; privacy language belongs in classify/outbound SoT.

## 2026-08-27 08:25 +07 — Mixed risk+safe zip silent or refused entirely

### Symptom
Zip packs with one short risk text member and one blank/safe office produced no useful extract reply (silence or whole-pack refuse).

### Root cause
Archive host-ack still ran classify on the combined extract body. A short risk member looked like a user secret ask; under Omni queue saturation the sync classify hop blocked the turn.

### Fix (core)
Skip attachment-body secret classify for archives; host-ack media extract always. Classify treats archive member text as data. Standalone short risk files still refuse.

### Prevent recurrence
Never map archive member bodies to secret probes. Prefer caption/user ask only for refuse on compressed attachments.

## 2026-08-27 07:45 +07 — Zip with caption silent; answering lock 45s

### Symptom
Sending zip files produced no Zalo reply when a caption was present. Long turns were cut off while the user was still waiting.

### Root cause
Archive extract with meaningful text skipped host ack and waited on Hermes (Omni queue rate-limit). Queue turn timeout defaulted to 5 minutes; answering lock TTL was hardcoded to 45 seconds.

### Fix (core)
Always host-ack archives from ingest extract. Raise Zalo queue turn wait floor to 15 minutes; align answering TTL and drain max; increase archive worker timeout.

### Prevent recurrence
Never route zip/7z/rar/tar chat reads through Hermes after the worker extract. Keep turn wait ≥ archive/OCR budget.

## 2026-08-27 07:10 +07 — Quote file reply, folder-zip empty text, English refuse, auto-learn risk docs

### Symptom
Reply-quoting a prior file did not process the attachment. Folder zip packs with images looked empty. Secret refuse stayed English. Blank/risk documents still opened Knowledge pending; PDF paths reached Hermes terminal tools.

### Root cause
Quote media lacked `fileUrl`/bridge `media`. Archive extract dropped text when OCR was empty despite media members. Host used a fixed English refuse string. File pipeline auto-staged learn for every extract; OCR/PDF binaries were not stripped after worker extract.

### Fix (core)
Bridge quote media map; wider quote URL keys; archive returns media member list when OCR empty; classify refuse in user language; learn only when classify allows knowledge; strip office/text/archive/ocr paths before Hermes.

### Prevent recurrence
Never auto-learn blank/risk/archives. Never hand worker-extracted packages to Hermes tools. Prefer classify instructions for refuse copy.

## 2026-08-26 19:40 +07 — Multi-format archives needed media-only extract + password gate

### Symptom
Zip was insufficient; 7z/rar/tar and password-protected packs could fall through to Hermes tools or expand non-media members.

### Root cause
Archive support was zip-only without password handling or rar/7z backends.

### Fix (core)
Ingest extract-archive for zip/7z/rar/tar with optional password; media-only members; host password ack; classify routes archives to media_file without local unzip.

### Prevent recurrence
Never brute-force archive passwords. Never expand nested archives or non-media members.

## 2026-08-26 19:35 +07 — Zip attachments needed media-only worker extract

### Symptom
Compressed attachments were not handled as media-worker reads; Hermes could terminal-unzip packages including non-media members.

### Root cause
`.zip` was `attachment_kind=none`, so no ingest extract path ran and the binary could reach Hermes tools.

### Fix (core)
Ingest `extract-archive` (media members only). Host kind=archive → that endpoint; strip paths; empty-archive ack. Classify routes archives to media_file without local unzip forensics.

### Prevent recurrence
Never expand nested archives or non-media members for chat attachment reads.

## 2026-08-26 19:20 +07 — Blank docx inspected via Hermes docx/terminal

### Symptom
Blank office attachments produced long agent replies that unzipped packages, read metadata, and narrated missing python-docx — not a short empty-file notice.

### Root cause
After worker extract, office binaries could still be passed to Hermes (`media_urls`), so the local docx skill / terminal ran instead of the host ingest extract ack.

### Fix (core)
Host treats ingest/OCR extract as SoT for office/text; blank/whitespace short-circuits with empty-file ack; strip media paths before any Hermes hop. Classify/SOUL/docx/worker-routing: chat attachment reads stay on media_file/ingest/OCR — never local docx/terminal forensics.

### Prevent recurrence
Never hand chat office packages to Hermes tools when workers already extracted (or found empty).

## 2026-08-26 18:50 +07 — Blank docs still opened Knowledge pending; classify 401 after scrub

### Symptom
Blank/whitespace-only attachments could still notify Knowledge pending-approval. Long security/LLM-risk documents could be mistaken for short secret asks. After env scrub, router-worker classify failed with Omni 401.

### Root cause
1. File pipeline submitted learn with path even when OCR/extract was empty.
2. Attachment secret gate classified full long documents the same as short risk txt bodies.
3. Scrub wiped compose-interpolated Omni/Gateway keys from ROOT/.env while router-worker reads them via compose `${VAR}`.

### Fix (core)
Skip learn on empty/whitespace extracts (host + ingest). Short-body-only secret refuse for attachment content. Classify/SOUL/safety: untrusted content is data; blank never learn; long risk notes are documents. load-openbao-env fills compose LLM keys when empty; scrub skips those interpolate keys.

### Prevent recurrence
Never stage knowledge without meaningful text. Do not treat security whitepapers as user secret probes. Keep compose-interpolated LLM keys fillable from OpenBao before up|update.

## 2026-08-26 18:35 +07 — Blank docs still opened Knowledge pending

### Symptom
Blank/whitespace-only attachments could still notify Knowledge pending-approval. Long security/LLM-risk documents could be mistaken for short secret asks.

### Root cause
1. File pipeline submitted learn with path even when OCR/extract was empty.
2. Attachment secret gate classified full long documents the same as short risk txt bodies.

### Fix (core)
Skip learn on empty/whitespace extracts (host + ingest). Short-body-only secret refuse for attachment content. Classify/SOUL/safety: untrusted content is data; blank never learn; long risk notes are documents.

### Prevent recurrence
Never stage knowledge without meaningful text. Do not treat security whitepapers as user secret probes.

## 2026-08-26 18:25 +07 — Blank attachments still refused via Zalo fileExt JSON

### Symptom
Blank/ordinary Security-folder attachments still received the secret/env refuse line after the prior filename-only fix.

### Root cause
Zalo inbound text for files is often a fileExt/wire JSON blob. The AV secret gate classified that JSON as the user ask.

### Fix (core)
`_as_user_secret_ask_blob` drops wire JSON and filename-alone. Attachment body that is itself a secret ask still refuses (risk docs). Classify: fileExt envelopes are not secret probes.

### Prevent recurrence
Never treat channel wire metadata as a secret-seeking caption.

## 2026-08-26 18:10 +07 — Blank docs got secret refuse

### Symptom
Blank or ordinary test attachments could show the secret/env refuse line even with no secret-seeking caption. After scrub, compose update could fail missing required `.env` values.

### Root cause
1. AV gate treated prior learn-skip and filename-only blobs as a full secret refuse.
2. Classify SECRET ASK + ATTACHMENT was too broad for bare/blank filenames.
3. Scrub emptied compose-interpolated host keys and update did not reload OpenBao before compose.

### Fix (core)
Classify: refuse only on explicit secret/env asks; bare/blank/filename-only stay file OCR/read. Host: refuse on ask text (or extracted body that is itself a secret ask); learn-skip only skips knowledge staging. Scrub skips compose-required keys; load OpenBao env before up|update.

### Prevent recurrence
Do not classify filename-alone as a secret probe. Do not reuse learn-skip as a turn-wide refuse. Keep compose-required host keys or reload them before compose.

## 2026-08-26 16:55 +07 — Dual secret-probe marker lists collapsed

### Symptom
Policy still carried separate input and output marker arrays after soft intent moved to classify.

### Root cause
Schema kept two lists for a gate that is classify-owned and empty by default.

### Fix (core)
Single `block_patterns` (default empty) in secret-probe policy and probe/ingest readers.

### Prevent recurrence
Do not reintroduce input/output keyword dictionaries for soft secret intent — strengthen classify.

## 2026-08-26 16:50 +07 — Secret file ask still opened knowledge-learn; probe keywords grew

### Symptom
Refuse could succeed while Knowledge pending-approval still staged the attachment. Soft env/secret asks encouraged expanding secret-probe keyword lists.

### Root cause
1. Async file → learn/submit did not honor classify refuse.
2. Intent was partially encoded as literal markers in secret-probe.json.
3. Plaintext OpenBao/stack env exports remained after deploy/restore.

### Fix (core)
Policy intent_owner=classify with empty marker lists. Strengthen classify SECRET/ENV + safety. Host learn-skip on classify refuse; AV/file path classifies caption before learn. Scrub plaintext exports after up|update|restore.

### Prevent recurrence
Do not grow soft-phrase dictionaries in secret-probe.json — strengthen classify/skills. Never stage knowledge after a secret refuse.

## 2026-08-26 16:10 +07 — Secret probe hardcoding + quote envelope miss

### Symptom
Env-storage soft asks could reach Hermes as a greeting. Probe Python carried embedded deny lists and regex. @mention with a quoted message/file could hide probe wording in the quote.

### Root cause
1. `_DEFAULT_INPUT` / `_DEFAULT_OUTPUT` and `re.compile` lived in probe modules instead of policy-only matching.
2. Host secret-probe scanned outer text only.
3. Classify refuse (`process_original_message=false`) was not always delivered by the host.

### Fix (core)
Policy-only literal markers; fail closed if policy missing. Probe outer + quoted snip/filename. Host direct refuse for classify `process_original_message=false`. Harden classify SECRET/ENV for quote/mention envelopes. Generic SOUL/safety/zalo-channel; ops alert for missing policy.

### Prevent recurrence
Do not embed deny dictionaries or regex in probe Python. Soft paraphrases belong in classify/LLM. Always scan quote envelopes before Hermes.

## 2026-08-26 15:30 +07 — Env-variable storage ask got a greeting, not a refuse

### Symptom
User asked how environment variables are stored on the server; the visible reply was a generic greeting with /help instead of a short refuse (looked like no useful response).

### Root cause
1. Secret-probe patterns covered “file môi trường” but not “biến môi trường” / environment-variable storage phrasing, so the gate did not short-block.
2. Classify already emitted a refuse with `process_original_message=false`, but the Zalo host never delivered that line and fell through to Hermes, which greeted.

### Fix (core)
Expand `config/agent/secret-probe.json` (+ gateway copy / defaults). Harden classify SECRET/ENV policy and SOUL/safety/zalo-channel for env-variable storage asks. Host: when classify sets `process_original_message=false` with a refuse body (skill null/security), send that body and do not call Hermes.

### Prevent recurrence
Secret probe must block env-variable paraphrases before LLM. Host must honor `process_original_message=false` for direct refuse lines.

## 2026-08-26 11:20 +07 — Multi-delay schedule bubbles got no reply

### Symptom
One message with several sequential relative delays could produce no assistant reply. Pause/resume/update on an existing lịch could create a new job instead of changing the matched one.

### Root cause
Classify schema required top-level delay/cron, so a wrapper with only `tasks[]` timing was `classify_invalid` and fell through. Schedule fanout re-classified inner instruction text and dropped delays. Host clock used processing time, not request receipt. Wrapper `task_hint=schedule` always forced create.

### Fix (core)
Prompt: keep timed intent as schedule; independent `tasks[]`; accumulate relative delays from receipt; resolution/selector/timezone source. Host: schema accepts `tasks[]`; fanout without a second classify hop; `request_received_at + delay_seconds`; lifecycle via selector + upsert enabled; transform maps to process at fire.

### Prevent recurrence
Do not re-classify schedule parts. Do not invent schedule ids. Do not default omitted cadence to daily. Classify timeout must cover a multi-job JSON answer.

## 2026-08-26 09:25 +07 — Operator scripts still offered a removed local LLM path

### Symptom
Product combos are Omni OpenCode, but docs and scripts still told operators how to turn a host LLM path back on. Leftover env pins and Omni connections could fight `hermes`/`classifier`.

### Root cause
The product default changed; enable scripts, compose pass-through, and lab preflight stayed.

### Fix (core)
Remove those operator scripts and flags. first-setup clears leftover pins, deactivates leftover Omni Ollama/Qwen connections, and drops leftover Qwen-named combos. Live OpenCode-family members stay. Case 38 checks combo fill only.

### Prevent recurrence
Do not document or wire a host LLM enable flag. Keep first-setup clearing old pins on upgrade.

## 2026-08-26 08:40 +07 — Office shortcut timed out while the PDF send was still in flight

### Symptom
PDF write succeeded, but the user got a text fallback. Shortcut waited 45s; Dispatcher send waited 90s. Send timeout crashed office-file.

### Root cause
Shortcut timeout shorter than bridge send. office-file only caught HTTPException, not ReadTimeout. Dispatcher /v1/mode still scanned Vietnamese/English verbs.

### Fix (core)
Catch send failures after write; shortcut wait 120s. Auto mode uses media flag only.

### Prevent recurrence
Shortcut wait must exceed Dispatcher Zalo send timeout. Do not infer mode from user-language word lists.

## 2026-08-26 08:20 +07 — Workflow cadence still scanned user prose

### Symptom
Cadence and some clock helpers still chose once/daily/weekly or AM/PM from Vietnamese/English words when classify JSON omitted cadence.

### Root cause
`plan.infer_cadence_heuristic` and `schedule_tz.parse_hhmm` duplicated classify.

### Fix (core)
Remove those scanners. Cadence is classify JSON or an explicit enum. Digit clocks only.

### Prevent recurrence
Do not add language AM/PM or cadence dictionaries to host Python.

## 2026-08-26 07:35 +07 — Host still scanned user prose for office, poster, and clocks

### Symptom
Office kind/body, text-poster N/phrase, memory mode, and once_at fire time could still be chosen from Vietnamese/English regex in Dispatcher, memory-manager, and schedule helpers.

### Root cause
Those modules duplicated classify. Phrase lists cannot cover paraphrases and fought structured JSON.

### Fix (core)
Remove those scanners. Classify emits `output_type`, `poster_n` / `poster_phrase` / `poster_bw`, and `clock_hm`. Host consumes those fields. Prior-conversation strip and status-frame filters are string protocol.

### Prevent recurrence
Do not add user-language regex to host/classifier Python. Extend `skills/classify/parts/` and structured fields.

## 2026-08-26 07:20 +07 — Classify Python still scanned schedule prose

### Symptom
Schedule, delay, clock, destination, and numbered-list intent could still be chosen from user text inside the classifier module when the LLM failed or as a host fill.

### Root cause
Regex fallbacks and clock extraction in classify Python duplicated the LLM job and fought structured JSON.

### Fix (core)
Remove those scanners. Normalize keeps JSON fields only. Fail open when classify is down. Harden the schedule skill part so delay, cron, destination, and split are emitted by the model. Host digit-clock mapping stays after `once_at`.

### Prevent recurrence
Do not add phrase scanners to classify Python. Extend `skills/classify/parts/` and consume JSON.

## 2026-08-26 07:05 +07 — Classify prompt was one unmaintainable JSON string

### Symptom
Operators could not edit classify policy without scrolling a 20k-character embedded string; copies drifted from the skill SoT.

### Root cause
All taxonomy, schedule, media, delivery, and schema rules lived in a single `system` field.

### Fix (core)
Split the skill into `parts/` (core, schedule, media, delivery, schema). Router assembles them into one LLM hop. Sync writes an assembled bake fallback. Remove keyword infographic NLU from the offline heuristic.

### Prevent recurrence
Edit the matching part file, not the bake JSON. Do not add a second classify call. Do not restore substring intent lists.

## 2026-08-25 21:10 +07 — Model-router config folder was a second SoT

### Symptom
Operators edited `architect/models/model-router/config/*.json` while skills/docs pointed elsewhere; classify/outbound/web-search combo drifted after updates.

### Root cause
Router prompts lived under model-router bake config instead of Hermes skills.

### Fix (core)
SoT: `skills/classify`, `skills/outbound`, `skills/web-search/web-search-combo.json`. Sync bake on update. Drop unused `heuristic.json` (never loaded).

### Prevent recurrence
Edit skill JSON only; never hand-edit bake copies. Do not reintroduce keyword NLU files.

## 2026-08-25 21:05 +07 — Classify prompt lived in three places

### Symptom
Prompt hardenings were re-applied under model-router/config while Zalo/gateway clients and docs pointed at different paths, so behavior drifted after updates.

### Root cause
`classify.json` was treated as a model-router-only file instead of the inbound Zalo classify skill contract.

### Fix (core)
Move SoT to `hermes/main/skills/classify/`. Router mounts skills and reads that file. Sync bake fallback on update. Document that every Zalo message classifies purpose via this skill.

### Prevent recurrence
Edit only the skill `classify.json`. Do not hand-edit the bake copy.

## 2026-08-25 20:55 +07 — List ask deleted a schedule

### Symptom
Users asking where a reminder was (often while quoting the create message) got “Đã xóa 1 lịch” instead of a list. Bare list phrasing stayed chat.

### Root cause
Classify had no strong list/inspect family; quoted create context was treated as delete. Host normalize forced non-delete schedules to create_schedule, so list could not survive schema.

### Fix (core)
Harden `classify.json` for list vs delete and process-group `target_channel`. Accept `list_schedule` in classify clients; adapter lists via schedule-worker when `skill_action=list`.

### Prevent recurrence
Never map where/list/show/inspect to delete. Quotes do not change the current ask’s action.

## 2026-08-25 20:20 +07 — Zalo still phrase-scanned Vietnamese for intent

### Symptom
Office/poster/schedule/destination/search paths could still be chosen by host regex and keyword lists even after classify owned delivery mode.

### Root cause
`plugins/zalo` kept semantic scanners (`looks_*`, group-name extractors, topic wraps, lyric keywords) that inferred task_hint / routing from user prose.

### Fix (core)
Remove those scanners. Host consumes classify JSON only. Harden `classify.json` for ownership, live-data files, destination, and lyric/search families. Units assert plan gates.

### Prevent recurrence
Do not add Vietnamese natural-language dictionaries under `plugins/zalo`. Extend `classify.json` and structured fields instead.

## 2026-08-25 19:50 +07 — Verb regex was fake NLU on the host

### Symptom
Fixes kept adding Vietnamese/English verb lists in host and heuristic to choose verbatim vs process.

### Root cause
Classify owns paraphrases; host dictionaries cannot and must not.

### Fix (core)
Remove lead-verb / schedule-shell regex from host. Trust `schedule_delivery` and plan fields. Heuristic uses only the `nội dung:` protocol marker (verbatim once_after) vs default process. Refuse fire_text identical to the full inbound ask.

### Prevent recurrence
Do not grow natural-language dictionaries for schedule delivery. Harden `classify.json` instead.

## 2026-08-25 19:45 +07 — Group describe fire echoed the schedule ask

### Symptom
One-shot “send into named group + describe …” saved, then the group received the original schedule sentence instead of a description.

### Root cause
Classifier treated “gửi vào [group]” as dictated send (`verbatim`) and left timing/destination in `message`/`fire_text`. Host fell back to the create ask when no `nội dung:` marker existed.

### Fix (core)
Harden `classify.json` so destination + work verb is `process` with inner-work only. Heuristic strips destination before delivery choice. Host never fires a create-schedule shell as `fire_text`.

### Prevent recurrence
`message`/`instructions` must never contain relative-delay or “gửi vào [group]” wrappers; destination stays in `target_channel`.

## 2026-08-25 19:10 +07 — Verbatim fire stored then silently dropped

### Symptom
Relative send-later lịch saved and fired; no Zalo message arrived.

### Root cause
Classify and host stored `schedule_delivery=verbatim`. At fire the adapter called send, then `/v1/outbound` treated the dictated body as process chatter and dropped it (`drop approval/resume chatter`).

### Fix (core)
Verbatim scheduleFire metadata skips the outbound noise filter. That filter stays for Hermes-generated lines only.

### Prevent recurrence
Do not run `/v1/outbound` on a payload the host already committed to deliver as-is.

## 2026-08-25 18:40 +07 — Dictated schedule body fired as process; gateway crash-loop

### Symptom
Relative one-shot send-later jobs saved, then never delivered. API gateway restarted on classify client import.

### Root cause
1. Classify treated any `nội dung:` containing describe-like words as assistant task-work (`process`), so fire went through Hermes and hung.
2. Gateway `classify_client.py` compiled a regex without importing `re`.

### Fix (core)
Harden `classify.json` so dictated send-bodies are `verbatim` and skill-lists stay `process`. Host consumes `schedule_delivery`. Heuristic fallback only treats lead describe-verbs as generate-jobs. Add the missing gateway import.

### Prevent recurrence
Do not keyword-spot payload words to choose process vs verbatim. Classifier JSON owns that decision.

## 2026-08-25 08:05 +07 — Phrase scanners stole mixed jobs from classify

### Symptom
Mixed image+file bubbles could produce only a text file. Relative one-shot schedules and cross-thread sends depended on incomplete word lists, so paraphrases missed the intended path.

### Root cause
Dispatcher shortcuts and host extractors classified intent with phrase dictionaries before (or instead of) model-router JSON.

### Fix (core)
Harden classify so it owns paraphrases, mixed deliverables, immediate adapter deliver, and delay_seconds. Host consumes those fields; office shortcut runs only for a single classified file job.

### Prevent recurrence
Do not add natural-language dictionaries for schedule/media/destination. Extend `classify.json` and structured plan fields instead.

## 2026-08-25 07:55 +07 — Classify still taught one-shot cron

### Symptom
Weak classify models could still emit invented `cron_expr` for one-shot schedules despite relative-delay harden rules.

### Root cause
Prompt contradictions: intent/keys/examples still implied cadence+cron for every schedule, including once_at / once_after.

### Fix (core)
Harden `classify.json` so only recurring schedules emit `cron_expr`. One-shot forms leave cron null; host resolves timing.

### Prevent recurrence
Any new schedule guidance in classify must name `schedule_form` and must not teach one-shot → cron.

## 2026-08-25 07:45 +07 — Relative schedule wrong clock; image+txt collapsed

### Symptom
Relative one-shot group delivery confirmed at the wrong local clock; list did not show the new job. Compound image+text-file asks lost the image deliverable; some PDF creates bypassed Dispatcher.

### Root cause
1. Classify guided the model to compute absolute fire times into cron / next_run_at.
2. Schema rejected delay-only plans.
3. Host preferred model timestamps over runtime delay resolution.
4. Office shortcut treated mixed image+file bubbles as a single file create.

### Fix (core)
- Harden classify for once_after + delay_seconds and multi-deliverable splits.
- Accept delay-only schedules; host owns fire instant.
- Skip office shortcut when image and file are requested together.

### Prevent recurrence
Classifier never resolves wall-clock for relative delays. Confirmations must come from schedule-worker/tool responses, not model prose.

## 2026-08-24 19:55 +07 — One schedule became many jobs; LC Group lost; 19:30 weather-only

### Symptom
Daily 06:00 LC Group and once 19:30 (poem + fuel + weather) saved, but list showed several rows at wrong clocks into DM. 19:30 fired weather only.

### Root cause
`hydrate_user_text` prepended prior turns with old HH:MM. `split_compound_requests` counted those clocks and zipped them onto skill instructions, dropping `vào Zalo LC Group`.

### Fix (core)
Clock-split and target extract use `strip_prior` current text only. Fan-out requires 2+ run-at clocks on the current bubble. Same clock + several skills = one schedule.

### Prevent recurrence
Never scan `[Prior conversation]` for schedule clocks or destination. Incidental times in a skill body (`6:00 AM` wakeup text) are not extra jobs.

## 2026-08-24 19:00 +07 — Daily schedule → poster / no save (heuristic bypass)

### Symptom
`đặt lịch chạy hằng ngày lúc 06:00 vào Zalo LC Group nội dung: mô tả thơ 4 dòng về trời xanh…, giá xăng, thời tiết` → DM photo or silence; schedules table empty.

### Root cause
1. Text-poster shortcut matched before schedule create (`4 dòng` + `anh` substring of `xanh`).
2. Classify early-returned `schedule_heuristic_plan` before LLM — no `target_channel` / `process` / skill split from classify.json.

### Fix (core)
- Skip office/poster shortcuts when `looks_schedule_create`; harden `_DRAW` word boundaries.
- Prefer LLM classify; enrich schedule heuristic only as post-LLM fallback; preserve split instructions in `force_timed`; extract `vào Zalo LC Group`.

### Prevent recurrence
Schedule-create prose must never take Dispatcher media shortcuts. Timed schedules with task `nội dung:` must hit classify.json (or enriched heuristic fallback), not a bare clock stub.

## 2026-08-24 18:15 +07 — Daily 06:00 LC group: no image/skills, !zalo hung

### Symptom
`đặt lịch chạy hằng ngày lúc 06:00 vào Zalo LC Group nội dung: mô tả thơ 4 dòng…, giá xăng E5/E10, thời tiết HCM` → DM photo in 2s, no save ack, `!zalo schedule list all` no reply. Image and admin CLI “not work”.

### Root cause
1. Classify `target_channel` null; `nội dung:` host defaulted **verbatim** on a **task** body.
2. Skills not split (one blob); leftover autosend flushed an old image to DM.
3. Per-thread inbound lock blocked `!zalo` while media/LLM turn was stuck.

### Fix (core)
Classify process + split skills + “vào Zalo LC Group”; host never verbatim on task work; admin bypasses inbound lock; cancel late autosend on new user text.

### Prevent recurrence
Task `nội dung:` (mô tả/cập nhật/dự báo/search/image) must be `schedule_delivery=process` with per-skill instructions. Admin CLI must not share the media-turn lock.

## 2026-08-24 16:30 +07 — Schedule fire paraphrased; target/list UX unclear


### Symptom
`2 phút nữa gửi vào zalo lc group nội dung: <poem>` saved OK and fired into LC group, but Hermes rewrote the poem. Save ack was only `Đã lưu lịch!` with no `→ nhóm`. List said `lịch chat này` without destination. Classify emitted `target_channel: "zalo lc group"`.

### Root cause
1. Every `scheduleFire` inject was treated as inbound chat → LLM paraphrase.
2. UX/list did not surface destination when requester DM ≠ delivery group.
3. Classify target_channel kept platform noise (`zalo …`).

### Fix (core)
- `schedule_delivery` verbatim vs process; adapter verbatim send; worker passes `scheduleDelivery`.
- Classify + `_clean_group_ref` harden display-name targets; save/list show `→ nhóm …`.

### Prevent recurrence
Send-body schedules must set/store `schedule_delivery=verbatim` and never re-enter Hermes chat on fire.

## 2026-08-24 15:25 +07 — Cannot delete schedules of other groups from DM

### Symptom
`!zalo schedule list` in DM: empty. `list all` showed jobs. `!zalo schedule delete 1 2 3…` → “Không có lịch số 1 (đang có 0).” Relative create could still fire into LC group while admin could not clear those rows from DM.

### Root cause
1. `jobs_for_thread` only matched `origin.chat_id`/`thread_id` (destination group), not `requester_id`.
2. Admin list merged workflow schedules only — not Go `schedule-worker` (adapter SoT).
3. Digit remove did not fall back to the full visible pool after `list all`.
4. Postgres DELETE still used unqualified `schedules`.

### Fix (core)
- Expand thread matching; merge schedule-worker into list; dual-delete worker+workflow; PG-qualified DELETE; classify+adapter delete with `target_channel`; repair classify.json JSON.

### Prevent recurrence
Any schedule created for a named group must remain listable/deletable from the requester chat and via `remove group <name>`.

## 2026-08-24 15:00 +07 — Schedule not triggered: relative-time next_run_at + fire_text verbatim

### Symptom
User issued "2 phút nữa gửi vào LC group nội dung: xuân chưa tới…". Bot replied "Đã lưu lịch!" but message never fired. DB row showed `next_run_at = 2026-08-25 14:01` (next day) and `fire_text = "sẽ gửi tin nhắn vào nhóm LC group"` (paraphrase).

### Root cause
1. Classify returned `cron_expr "1 14 * * *"` only, no `next_run_at`. The 14:38 retry stored the row after 14:01; `nextDaily()` in the worker rolled it to next day.
2. Classify paraphrased `instructions[0]` as "sẽ gửi tin nhắn vào nhóm LC group" instead of copying poem verbatim; `fire_text_from_plan` fell back to that paraphrase.

### Fix (core)
- `classify.json`: relative-time rule → emit `cron_expr` + `next_run_at` (RFC3339 UTC). Verbatim rule hardened for `nội dung:` body.
- `schedule_client.py`: `next_run_at_from_relative()` parses N phút/giây/giờ offset; used as adapter safety-net.
- `adapter.py`: compute and pass `next_run_at` to worker on schedule create.
- `workflow_client.py`: `create_schedule` accepts `next_run_at`.

### Prevent recurrence
Any schedule with relative-time ("N phút nữa") must carry explicit `next_run_at`; worker only computes from cron when field absent.

## 2026-08-24 14:30 +07 — SOUL blocked + schedule-worker missing public schema

### Symptom
SOUL.md blocked every turn (`deception_hide`). Schedule-worker PG loop errors every 2s (`relation "schedules" does not exist`). Hermes fell back to inventing outbound endpoint `/v1/zalo/send`.

### Root cause
1. SOUL queue-state rule: "Do not tell the user that a request is queued…" triggered the Hermes `do_not…tell…user` deception scan.
2. SOUL language section missing Spanish/Japanese/English examples; `soul_deception_unit.py` did not cover the 8-word window pattern.
3. `store_pg.go` used unqualified `schedules` table name; after restore, workflow schema `wf.schedules` also present but this worker needs `public.schedules`.

### Fix (core)
- SOUL.md queue-state line reworded; language examples added.
- `soul_deception_unit.py` extended with broad window pattern.
- `store_pg.go`: `applyPgSchema()` splits DDL statements, forces `search_path=public`, verifies tables; all DML qualified with `public.` prefix.

### Prevent recurrence
Any PG-backed worker sharing a DB must qualify schema; SOUL edits must pass `soul_deception_unit.py` before merge.

## 2026-08-24 13:05 +07 — find_thread SoT: sync entities → normalized, no dual search

### Symptom
`!zalo list` shows "LC group" but `threads/find` returned not_found.

### Root cause
Dual search in `find_thread` (zalo_threads + zalo_entities) produced duplicate exact matches. Dedupe at search time was a bypass, not a data fix.

### Fix (core)
- `sync_normalized_from_entities()` at startup: one-way backfill entities → `zalo_users`/`zalo_threads`; prune denied rows from threads.
- `find_thread` / `get_current_context` query normalized tables only.

### Prevent recurrence
Compat mirror (`zalo_entities`) feeds normalized SoT on startup; routing APIs never merge two stores at query time.

## 2026-08-24 13:00 +07 — !zalo list shows LC group but find_thread not_found

### Symptom
`!zalo list` shows allowed group "LC group", but bot/Hermes says "Không tìm thấy nhóm LC Group" and asks for `!zalo allow`/`refresh`. PG had the row in both `zalo_entities` and `zalo_threads`.

### Root cause
`find_thread` appended the same thread twice (normalized table + legacy entities mirror). `len(exact)==2` so it returned `None` instead of the single group.

### Fix (core)
Superseded by normalized SoT sync (see 13:05 entry).

### Prevent recurrence
Any name search merging two stores must dedupe before uniqueness checks.

## 2026-08-24 12:05 +07 — Quote fix shipped; zalo-api 500 / missing tables

### Symptom
After quote-photo fix, zalo-api returned 500 on `/v1/zalo/claims/active` (`relation "zalo_claims" does not exist`); Hermes also 404 on invented `/threads/search`, `/context/current`. Quote OCR path itself could extract `params.rawUrl`, but context/claim calls failed.

### Root cause
`zalo_store._ensure()` ran the full multi-statement `SCHEMA` via a single `psycopg` `Connection.execute()` (one command only). Process marked ready while DB still only had legacy tables from restore (`zalo_entities`, `zalo_settings`, `zalo_message_history`) — never creating `zalo_users` / `zalo_threads` / `zalo_group_members` / `zalo_claims`.

### Fix (core)
Statement-by-statement SCHEMA apply + required-table verification; startup `ensure_schema(force=True)`; route aliases for common wrong paths; skill documents allowed endpoints only.

### Prevent recurrence
Never apply multi-statement DDL with one `execute()`; always verify required tables after ensure; re-run schema on every zalo-api startup.

## 2026-08-24 11:40 +07 — Backup should include router combos + OpenBao

### Symptom
Operators expected backup/restore to preserve OmniRouter/9Router combo configuration and OpenBao secrets as first-class components (not only buried in generic volumes / skipped KV import).

### Root cause
Router volumes were mixed into `volumes`; no human-readable combo export. OpenBao KV restore skipped when the -dev container was not yet up.

### Fix (core)
Component `routers` (volumes + env.router + combo JSON export); OpenBao restore brings container up then imports KV.

### Prevent recurrence
Treat routers and OpenBao as named backup components with verify-friendly artifacts.

## 2026-08-24 11:20 +07 — Quote-reply photo: only "[quoted image]", no OCR

### Symptom
After type-32 mapping, bot still says it only received `[quoted image]` and asks to send the photo directly. Hermes may also show "Recovered reply — gateway restarted".

### Root cause
Inbound Zalo `TQuote` fields are `cliMsgType` + `attach` (JSON string) + `msg` — not `content`/`href` like a normal message. Media extract looked only at `content`, so no URL → no download/OCR. Gateway watchdog restarts (event-loop hang) caused the recovered-reply banner.

### Fix (core)
Bridge merges/parses `attach` into quote content; attachment helpers read `attach`/`hdUrl`/`thumbUrl`/params; RAW logs attach preview.

### Prevent recurrence
Treat inbound quotes as TQuote shape; never assume Message.content for quoted media.

## 2026-08-24 09:00 +07 — Quote-reply to image: bot sees type=32 only

### Symptom
User quotes an old **photo** and asks "đọc nội dung trong ảnh"; bot says it only received `[quoted message type=32]` with no image.

### Root cause
Zalo sends numeric `msgType=32` for photos. Snip/media-from-quote only matched string types like `chat.photo`.

### Fix (core)
`normalize_zalo_msg_type` + `extract_media_from_quote` in attachment; bridge maps numeric types; adapter uses shared helper.

### Prevent recurrence
Always normalize Zalo numeric msgType before media/quote handling.

## 2026-08-24 09:00 +07 — Backup missing OmniRouter combos; OpenBao KV not restored

### Symptom
After restore, OmniRouter combos empty; OpenBao -dev lost API keys (only `.env.openbao` copied back).

### Root cause
Volume backup listed `nine_router_data` but not `omni_router_data`; OpenBao -dev is ephemeral with no KV re-import on restore.

### Fix (core)
Backup/restore `omni_router_data`; `restore_openbao_kv.py` imports KV export on restore.

## 2026-08-24 08:35 +07 — Restore fails: No such container: redis

### Symptom
`bash run.sh restore <stamp>` → `no such service: redis`, then valkey step `No such container: redis` / `ERROR: valkey ping after restore`. Postgres/qdrant may already have been restored.

### Root cause
Compose renamed Redis → Valkey (`container_name: valkey`). Restore still hardcoded `docker stop|start|exec redis` and `compose up … redis`.

### Fix (core)
`architect/backup-restore/lib/backup.sh`: datastore up uses `valkey`; restore resolves container via `assistant_container`; `run.sh` compact pings `valkey`.

### Prevent recurrence
Never hardcode legacy container name `redis` for stack ops; use `assistant_container` or compose service `valkey`.

## 2026-08-24 08:20 +07 — Scoped `run.sh update` fails on zalo-api (hermes scale)

### Symptom
`bash run.sh update hermes zalo-api …` stops after hermes with `no such service: hermes: disabled` on `up zalo-api`.

### Root cause
`compose()` always appended `--scale hermes=N` after scoped service names → invalid compose CLI for non-hermes updates.

### Fix (core)
Only add `--scale hermes=N` when no explicit services, or `hermes` is among them.

### Prevent recurrence
Any scoped `compose up <svc>` must not attach unrelated `--scale` targets.

## 2026-08-24 08:10 +07 — Quote reply: bot cannot read old message (DM + group)

### Symptom
User replies by quoting an older Zalo message (DM or group); bot answers as if no quoted content was attached (asks what to read / ignores quote).

### Root cause
1. Bridge only forwarded `data.quote`; some reply payloads use `refMsg`/`reference`, or put `uidFrom` without `ownerId` (group reply-to-bot gate misses).
2. Hermes snip returned empty for media quotes without caption/title, and required non-empty user text before injecting `[Quoted message]`.
3. Media-from-quote only matched narrow `chat.photo` / `share.*` prefixes.

### Fix (core)
`scripts/main/zalo-bridge/zaloClient.js` quote extract/map + RAW `hasQuote` diagnostics; `attachment.quoted_context_snip` media placeholders; adapter inject + media-from-quote + address fallback.

### Prevent recurrence
Always log hasQuote on inbound; snip must never drop a present quote object to silent empty when msgType is known.

## 2026-08-24 08:00 +07 — Env-file probe answered with path listing

### Symptom
User asked whether the server stores environment files; bot confirmed existence and listed `.env`, `.env.openbao`, and backup `profile-options.env` paths/sizes.

### Root cause
1. Secret-probe policy did not match Vietnamese “file môi trường” existence phrasing → message reached Hermes.
2. Skills/SOUL forbade scans but not soft “does it exist / is it stored” probes; model enumerated host paths.

### Fix (core)
Expand `config/agent/secret-probe.json` (+ gateway copy) for env-file existence phrases; harden classify prompt + SOUL + zalo-channel + safety + ux refuse; remove unused compose `SQLITE_PATH`; document host timezone at first setup; clarify `.env` is gitignored (example only in source).

### Prevent recurrence
Secret probe must block before LLM; classify/SOUL refuse with one line and no follow-up enumeration menus.

## 2026-08-24 07:30 +07 — Trace LC schedule miss + durable PG/claim/context foundations

### Symptom
User asked to schedule into Zalo “LC group”; bot later claimed group missing, only “Home” connected, and a 60-minute confirmation window expired — while earlier `!zalo allow` + schedule fire had already delivered into LC.

### Root cause
1. First attempt ran before `!zalo allow` (allowlist empty) — correct miss.
2. Hermes agent path invented a confirmation wait / Home substitution instead of fail-fast allow/refresh guidance and durable thread lookup.
3. Claim stored only admin `user_id`; channel registry was JSON-primary; schedules still SQLite — incomplete SoT for identity vs delivery.

### Fix (core scripts)
PG Zalo normalized tables + claims; zalo-context skill/API; claim persists `claimed_thread_id`; schedule-worker Postgres path with execution/correlation ids; security message-check before Hermes; scoped `run.sh update`; media conditional routing skill text.

### Prevent recurrence
Always resolve named groups via zalo-context/PG before schedule/create; never swap `user_id`↔`thread_id`; never invent confirmation waits.

## 2026-08-23 18:15 +07 — Zalo bridge overlay: bundle markdownToZalo.js + verify

- VPS trace: full `zaloClient.js` overlay without `markdownToZalo.js` → `ERR_MODULE_NOT_FOUND`, no bridge on `:8787`.
- Vendored `markdownToZalo.js`; `zalo_install_bridge_overlays()` installs bundle + pre-start verify.

## 2026-08-23 17:35 +07 — classify + schedule: sequential compound (not parallel)

- Classify prompt + workflow `sequential=True` for N immediate instructions; schedule multi-clock vs single-fire docs.

## 2026-08-23 17:05 +07 — video policy: OmniRouter refuse messages

- Dispatcher `video_summary.py`: LLM-written policy response for inaccessible social-media content.

## 2026-08-23 17:00 +07 — Zalo quote: durable bridge overlay (not runtime patch)

- Vendored `scripts/main/zalo-bridge/zaloClient.js`; `zalo_install_bridge_overlays()` in `zalo-common.sh` copies after npm install / before bridge start. Quote regex patch removed from `patch_zalo_bridge_inject.py`.

## 2026-08-22 16:00 +07 — §15 classify heuristics when Ollama JSON fails

### Symptom
Case index lab on main VPS: case 25 (`zalo_special_four_lab`) HTTP 503 on schedule create; case 26 (`zalo_weather_fuel_lab`) `classify_llm_failed` / `PLAN_N 0`; case 21 ping 5431ms counted as FAIL on Ollama CPU lab.

### Root cause
`heuristic_plan()` returned None for numbered lists and weather+fuel infographic text when local Qwen could not emit valid classify JSON; workflow rejected empty plans. `defaults_routers_lab` lacked Ollama-lab SLOW tolerance already used in `zalo_latency_lab`.

### Fix
`numbered_list_heuristic_plan`, `infographic_weather_fuel_plan` (ordered before short-text guards); infographic guard skips ≥2 numbered lines; `defaults_routers_lab` OLLAMA_LAB ping SLOW; unit coverage in `schedule_classify_heuristic_unit`.

### Prevent recurrence
Run `schedule_classify_heuristic_unit` in §15 batch; mirror Ollama SLO policy across latency + defaults labs.

## 2026-08-22 15:10 +07 — Release v0.5.24 lab: §15 fixes, Ollama ensure, Zalo SSE gate

### Symptom
Two-round main lab: 9 §15 fails; real Zalo (Tn) no-reply — model-router 503 (`ollama: All connection attempts failed`), Omni free-tier inactive, Hermes SSE thrash during bridge restart, Zalo send `Tham số không hợp lệ`.

### Root cause
Ollama bound localhost-only (containers could not reach `host.docker.internal:11434`); no stack-watch heal for Ollama/bridge; Hermes opened SSE before bridge `/health`; corrupted admin allowlist backup; unit tests assumed 9router when `ENABLE_9ROUTER=0`.

### Fix
`ensure-ollama.sh` (OLLAMA_HOST=0.0.0.0, stack-watch/run.sh/post-lab); model-router Ollama probe; adapter `_wait_for_bridge_ready`; §15 cadence heuristic + Omni-only skips; `seed-zalo-admin-from-postgres.sh`; AGENT_RULES §29 full §15 + post-lab restore.

### Prevent recurrence
stack-watch + zalo-watch timers; case 38 preflight; `run_case_index_lab.py` batch; post-lab-restore before stopping host.

## 2026-08-22 12:30 +07 - Postgres pg_hba blocked Docker services on clean deploy

### Symptom
After round-2 wipe, workflow/authz/zalo-api crash-looped: `no pg_hba.conf entry for host … no encryption`; DB list lacked `hermes_memory`.

### Root cause
Postgres data volume initialized with localhost-only hba; Docker bridge IPs had no rule; POSTGRES_DB not applied on bad partial init.

### Fix
Mount `docker/postgres/pg_hba.conf` + `POSTGRES_HOST_AUTH_METHOD=scram-sha-256`; recreate postgres volume on clean deploy.

### Prevent recurrence
Document: after wipe, verify `\l` shows hermes_memory and zalo-api `/health` before tests.

## 2026-08-22 11:35 +07 - Zalo Postgres SoT + session backup (no second QR)

### Symptom
Admin/users/groups lived in text files; clean redeploy required a second QR scan; develop tests assumed Tn while main must accept any admin.

### Root cause
Allowlists were file-only; no durable credentials backup path; lab identity mixed into production assumptions.

### Fix
zalo_store (Postgres) + CRUD APIs; AGENT_RULES lab vs main language/identity; backup/restore-zalo-session under ASSISTANT_DATA_DIR/zalo-session-backup.

### Prevent recurrence
zalo_store_unit + zalo_admin_resolve_unit; round-2 restore credentials before stack up — do not ask to re-scan QR when backup exists.

## 2026-08-22 18:20 +07 - !zalo claim from QR account (Tn) failed

### Symptom
Operator scanned Zalo QR as Tn then sent !zalo claim. No useful admin grant. Bridge health often loggedIn=false; zalo-api admin_users=0.

### Root cause
1. Chat QR image expired (~100s); scan did not persist a session.
2. claim rejected sender==bot_id (same account as QR login).
3. claim also required zalo-api bridge /health loggedIn, which can fail even when Hermes later receives DMs.

### Fix
Allow first-setup claim for the QR uid; skip extra health gate; seed admin from ownId on zalo-api start; pass ZALO_PLUGIN_TOKEN to the systemd override.

### Prevent recurrence
zalo_claim_unit.py. After QR: wait loggedIn=true, login-zalo seed, docker restart hermes, then !zalo claim.

﻿## 2026-08-22 17:10 +07 - Prod gap suite, SOUL multi-lang, ENABLE_QWEN empty combos

### Symptom
Clean production posture still risked stale Omni models in hermes/classifier, Vietnamese-only SOUL tone, and parallel=4 too low for 5-10 concurrent multi-request Zalo users. HISTORY gaps (no-reply, PDF fake send, schedule) needed a Tn regression pack + failure choreography cases.

### Root cause
Qwen fill was not gated by an explicit component switch; SOUL examples skewed Vietnamese; workflow parallel default undersized; gap matrix lived only outside the repo.

### Fix
ENABLE_QWEN=0 default with empty round-robin combos; parallel default 8 + sizing table; SOUL multi-language; cases 40-74 + Tn history/parallel scripts.

### Prevent recurrence
soul_deception_unit + qwen_parallel_recommend_unit; zalo_tn_history_regression (retry single case via ZALO_HISTORY_CASE).
## 2026-08-22 16:10 +07 - Mixed schedule bubble: dup weather, missing fuel

### Symptom
User message: schedule once at 09:50 greeting + then fuel E5/E10 + HCMC weather. Saw duplicated weather replies; greeting/fuel seemed missing; 09:50 lịch did not behave as expected.

### Root cause
1. Classify sometimes demoted timed `đặt lịch … lúc HH:MM` (with sau/kèm theo fuel+weather) to immediate `async` workflow → 3 parallel jobs now.
2. Fuel job (`tóm tắt giá xăng…`) answered with weather-like content while weather job also ran → two weather sends.
3. Greeting job did send (~224 chars) but was easy to miss beside two weather bubbles; no schedule row for 09:50.

### Fix
Force schedule when schedule-trigger + clock present; cron from HH:MM; classify prompt + stronger per-job topic wraps (fuel/weather/greeting).

### Prevent recurrence
Smoke classify on mixed đặt-lịch text must return `task_hint=schedule` + 3 instructions. Tn inject store-only test must see `schedule stored` and not `workflow created jobs=3`.

## 2026-08-22 15:20 +07 - Omni unforced /v1/search always labels SearXNG

### Symptom
Tavily active; operators still saw “SEARXNG default” (Omni unforced `provider=searxng-search`; Hermes env named `SEARXNG_URL`). Suspected stale router-worker / priority tie.

### Root cause
1. Naming: Hermes `SEARXNG_URL` → searxng-compat shim, not “prefer SearXNG engine.”
2. Router-worker was **not** stale (514 lines, searxng-compat present); Hermes `POST /v1/search` already returned `backend=omni:tavily-search`.
3. OmniRoute quirk: unforced `/v1/search` keeps labeling `searxng-search` even when that connection is blocked or deleted; connection `priority` does not persist on GET after PUT. Forced `provider=tavily-search` works.

### Fix
Document the quirk; first-setup smoke checks **forced** Tavily; keep Router Worker cascade as Hermes SoT. Do not treat Omni unforced smoke as the Hermes default.

### Prevent recurrence
Judge search health via router `backend=omni:tavily-search` + forced Tavily smoke. Rebuild router-worker after websearch.py changes. Never hotpatch only on VPS.

## 2026-08-22 14:50 +07 - Omni defaulted to SearXNG while Tavily active

### Symptom
Operators saw Tavily enabled but assumed SearXNG was still the default.

### Root cause (partial — superseded by 15:20 entry)
Suspected priority=1 tie + SEARXNG_URL naming; Hermes cascade already Tavily-first.

### Fix
Priority enforce attempt + apply/probe scripts; later clarified Omni unforced quirk.

## 2026-08-22 11:00 +07 - Weather HCMC: searxng-compat 404 + OpenRouter 402

### Symptom
User message asking current Ho Chi Minh weather took too long and got no useful Zalo reply.

### Root cause
1. Running router-worker websearch.py was stale (no searxng-compat route) while Hermes called that URL → 404.
2. OpenRouter combo members hit 402 credits / 502 / 503; retries burned time inside the 150s Zalo queue turn budget.

### Fix
Rebuild/recreate router-worker; ensure WEB_BACKENDS=omni + HERMES_SEARXNG_URL shim; raise queue turn timeout default to 300s and per-provider search timeout to 30s; document Qwen lab performance.

### Prevent recurrence
After model-router websearch changes, rebuild router-worker (do not leave an old image). Smoke GET /v1/searxng-compat/search and POST /v1/search before weather tests. Monitor router-worker 404/402 and Hermes queue turn timeout lines.

## 2026-08-22 10:30 +07 - Compound wait burned queue; /help in greetings; Omni credential spam

### Symptom
Queue turn waited on mark_delivered (~180s) and burned the 150s budget; greetings suggested /help or "Hermes — trợ lý AI"; Omni kept testing provider credentials.

### Root cause
Compound wait defaulted to delivery sync; SOUL allowed command tips; Omni credential health scheduler enabled; too many Qwen RR members.

### Fix
Default ZALO_COMPOUND_WAIT_FOR_DELIVERY=0; SOUL warm greeting without slash-commands; disable credential health check; slim Qwen combos + qwen-fast; OpenVPN Omni access docs; Tn Qwen perf test.

### Prevent recurrence
Keep compound wait opt-in; after SOUL edits scan for deception_hide; keep OMNIROUTE_DISABLE_CREDENTIAL_HEALTH_CHECK=true on lab; prefer ≤2 hermes Qwen members.


English log of **problems we actually hit** (lab and product) and **how they were fixed**. Newest first.

This is the operator-facing companion to [`docs/CHANGELOG.md`](../docs/CHANGELOG.md). Changelog answers â€œwhat changed.â€ This file answers â€œwhat broke, why, and how to stop it happening again.â€

**Do not put hostnames, IPs, accounts, or secrets here.**

---

## 2026-08-22 09:00 +07 — Inject test false FAIL while send ok

### Symptom
zalo_tn_greeting_inject reported FAIL_NO_REPLY while gateway.log showed send ok for the same Tn greeting.

### Root cause
Logs landed in replica gateway.log; docker logs were empty. Early compound mark_delivered also raced with async send.

### Fix
Test reads gateway/agent logs. Remove premature mark_delivered; keep shorter compound timeout.

## 2026-08-22 08:40 +07 — Greeting DM still silent after SOUL unblock

### Symptom
Tn greeting inject / real DM still timed out at 150s with no Zalo send ok after SOUL deception_hide fix and Qwen-only combos.

### Root cause
1. Lead combo model groq/qwen/qwen3.6-27b returned only think-tag content and finish_reason=length (empty user-visible text).
2. Zalo compound wait default 180s waited for mark_delivered that never came, burning the 150s queue turn budget. Timeout UX often never reached the user either.

### Fix
- Prefer non-thinking Qwen (2.5 / plus / instruct) in omnirouter_qwen sort.
- Skip compound wait when the part had no outbound; shorten compound part timeout default.

### Prevent recurrence
After first-setup, confirm hermes combo first member is not Qwen3.x. Monitor finish_reason=length + empty content on greeting turns.

## 2026-08-22 08:20 +07 — Greeting inject: SOUL blocked, queue timeout

### Symptom
Tn morning greeting (and bridge inject of the same text) got no Zalo reply. Hermes showed queue turn timeout after 150s.

### Root cause
1. Omni hermes combo still had flaky ollamacloud members (fixed earlier: Qwen-only).
2. SOUL.md still blocked every turn: threat pattern deception_hide matches any do not … tell … the user within 8 words — SOUL had that phrasing for /help and media rules.
3. Without SOUL, the model over-tooled (e.g. terminal) until the Zalo queue turn budget expired; often no outbound.

### Fix
Reword SOUL.md to avoid the deception_hide pattern. Keep Tn greeting inject lab case.

### Prevent recurrence
After editing SOUL, scan for 	ell the user under the FILLER window. Monitor Context file SOUL.md blocked: deception_hide.

## 2026-08-22 08:05 +07 — Greeting DM no reply (queue turn timeout)

### Symptom
User message greeting in the morning got no Zalo reply.

### Root cause
Hermes received the DM (Tn thread). Omni hermes combo was Qwen-first but still appended prior ollamacloud / other RR members. Sticky round-robin landed on ollamacloud models that returned empty_choices / errors, burned retries, and hit the 150s Zalo queue turn timeout.

### Fix
- omnirouter_qwen: when Qwen active, write hermes/classifier as Qwen-only.
- Add Tn greeting inject lab case (bridge /inject-event) to catch no-reply regressions.

### Prevent recurrence
Do not keep known-flaky non-Qwen members beside Qwen when the operator asked for Qwen default. Re-run first-setup after combo changes; monitor queue turn timeout lines.

## 2026-08-22 07:40 +07 — Qwen default + scheduleFire / group allow misfires

### Symptom
Lab asked for Qwen as Omni/9Router provider and default for hermes+classifier (round-robin, Qwen first). Abnormal replies: group search still looked SearXNG-first; bot said unknown command scheduleFire; schedule target looked like allow-status text.

### Root cause
1. Combos were emptied / filled without Qwen priority; no alibaba provider wiring in first-setup.
2. scheduleFire inject could sit behind FIFO / be treated as user text when worker defaults off.
3. Loose group regex + classify fields accepted allow-list status text as a group name.

### Fix
- scripts/main/omnirouter_qwen.py + first-setup: alibaba/qwen provider + Qwen-first combos.
- Zalo: reject allow-status group refs; scheduleFire queue bypass; schedule worker defaults on.

### Prevent recurrence
Keep only chat Qwen models in classifier. Never parse admin allow status as target_group. Monitor Hermes + Zalo bridge after first-setup.

## How to add an entry

When you hit a real failure (deploy, cron, Zalo, routers, permissions):

1. Add a section at the **top** with timestamp `YYYY-MM-DD HH:MM +07`.
2. Fill **Symptom**, **Root cause**, **Fix**, **Prevent recurrence**.
3. Mirror a short bullet in `docs/CHANGELOG.md`.
4. Prefer a reusable config/skill/queue fix over a one-off keyword patch.

---

## 2026-08-21 20:40 +07 — Classifier 400: CF models want prompt/text/audio

### Symptom

Classify `model=classifier` with OpenAI `messages` returned CF AiError 400:
required `prompt` / `text` / `audio`. Logs showed Cloudflare AI, not Codex chat.

### Root cause

1. Combo `classifier` members were (or remapped to) Workers AI models that are
   not chat/completions-capable; Omni RR tried several and each 400’d.
2. Our classify only skipped 401/403/502/503 — not 400 — so it waited on the
   dead combo longer than needed.
3. Valkey `[Prior conversation]` was prepended before classify, so the current
   ask (and schedule wording) was buried under older PDF/image turns.

### Fix

- Skip classify combo on HTTP 400 and AiError schema bodies; failover to `hermes`.
- `strip_prior_for_classify` before LLM/heuristic.

### Prevent recurrence

Keep only **chat** models in the `classifier` combo (same class as `hermes`).
Do not add CF translation / ASR / vision-only / prompt-only models.


## 2026-08-21 20:25 +07 — Đặt lịch no reply (classifier 503 + queue timeout)

### Symptom

User: “đặt lịch chạy một lần lúc 20:07/20:17 với nội dung…”. No Zalo reply;
schedule never stored (`jobs.json` empty / no new rows).

### Root cause

1. Omni combo `classifier` returned 503 “all upstream accounts are inactive”
   (~50ms) but was **not** skipped (only 401/403/404/429 were).
2. Failover to `hermes` hit ReadTimeout (classify `timeout_s=60`).
3. Hermes turn then hit Zalo queue turn timeout (150s) → no useful reply;
   Valkey `gate:ans` / `gate:qwork` could stay occupied.
4. Schedule heuristic explicitly returned `None` for “đặt lịch”, so LLM failure
   did not fall back to a storeable cron plan.

### Fix

- Skip classify combos on 502/503; shorten classify timeout to 15s.
- Deterministic schedule heuristic for once/daily `lúc HH:MM` (early + fallback).
- Ops: clear stuck answering/queue keys for the thread when applying.

### Prevent recurrence

Dead Omni classify combos must not burn the full Zalo turn budget. Clocked
“đặt lịch” must store via heuristic when LLM classify is unavailable.


## 2026-08-21 19:55 +07 — SOUL blocked; empty session; wrong PDF/image content

### Symptom

After Hermes recreate: canned “Chào bạn /help” intro (forgot chat). PDF “điền
số 1” contained the instruction sentence. “5 dòng hello” image was an unrelated
photo (sana diffusion), not five lines of hello.

### Root cause

1. Hermes threat scan matched SOUL “do not tell the user…” → `deception_hide`
   → entire SOUL replaced with a BLOCKED placeholder.
2. Gateway transcript lived under per-replica `sessions.json`; recreate →
   msgs:0. Valkey session service was not hydrating the next turn.
3. `parse_office` missed `chứa số 1`; agent-rewritten prompts became the PDF
   body. Text-poster left “hello và gửi cho tôi”; agent skipped poster mode
   and called diffusion.

### Fix

- Rewrite SOUL without the deception trigger phrase.
- Zalo `session_memory`: hydrate inbound + append outbound via `SESSION_URL`.
- Harden office/text-poster parsers; Zalo `media_shortcuts` for clear create
  intents (Dispatcher only).

### Prevent recurrence

Never put “do not tell the user” in SOUL. Short-term chat SoT is Session/Valkey.
Exact text posters and simple office creates must not depend on the LLM
rewriting the prompt.


## 2026-08-21 19:30 +07 — PDF claim + gpt-oss-120b request storm

### Symptom

User: “tạo 1 file pdf và điền vào số 1”. Bot: “Đây là file PDF… (File được
gửi kèm)” but Zalo had no attachment. OmniRouter showed many
`openrouter/openai/gpt-oss-120b` (and groq) turns with huge tool lists.

### Root cause

1. Three skills still registered as `name: pdf` (SoT + official + Hermes
   `productivity/` clone). `skill_view('pdf')` refused (ambiguous).
2. Agent fell back to local pdf scripts → missing `reportlab` → pip/uv
   install loops. Each failure = another chat.completions call (~20+ tools
   in the body) → Omni “plenty of requests” to gpt-oss-120b.
3. Model narrated success without `"ok":true` / file in `media/out`.
4. `file-gen` already pointed at Dispatcher office-file, but the skill
   index still advertised “Create… PDF files” under name `pdf`.

### Fix

- Rename office SoT skills to `pdf-tools-local` / `docx-tools-local` /
  `xlsx-tools-local` (and `official-*`); descriptions defer to `file-gen`.
- `hermes-replica-entry.sh` deletes category clones under
  `productivity|documents/{pdf,docx,xlsx}` after skill overlay.
- Unit `office_skill_collision_unit.py` forbids reserved names `pdf|docx|xlsx`.

### Prevent recurrence

Never ship multiple skills with the same frontmatter `name`. Chat
create-and-send must only go through Dispatcher `/v1/office-file`. Do not
claim delivery without `"ok":true` or autosend of a real `media/out` file.


## 2026-08-21 18:50 +07 — PDF/txt “created” but never sent on Zalo

### Symptom

User asked to create a PDF and a text file with content `1`. Bot replied that
files were created; Zalo never received an attachment.

### Root cause

1. Hermes tried ambiguous skill name `pdf` (3 collisions) then `pip`/`uv`
   install of `pypdf` failed (externally managed Python). No file in `media/out`.
2. Model still answered as if creation succeeded.
3. Omni combos were filled with OpenCode Free by first-setup (unwanted; 503s).

### Fix

- Skills `file-gen` / `documents` / `media-out`: use Dispatcher
  `POST /v1/office-file` only; never local pdf skill / pip.
- Compose default `OFFICE_FILE_GEN=1`; empty Zalo caption on office deliver.
- first-setup clears `hermes` and `classifier` to empty member lists.

### Prevent recurrence

Office create must go through Media Worker office API. Never claim success
without `"ok":true` / autosend. Do not auto-populate OpenCode into chat combos.


## 2026-08-21 18:20 +07 — Web search hang locked next Zalo message

### Symptom

A web-search turn hung on Hermes; the next user message got no reply (queue
appeared stuck).

### Root cause

Per-thread inbound FIFO drain awaited `handle_message` with no hard timeout.
`_as_queue_kick` refused to start another drain while that task was still
running, so later messages sat in Valkey. Search provider HTTP timeouts were
also long (60s/90s), so failover waited the sum of worst cases.

### Fix

- Wrap queued turn in `asyncio.wait_for` (`ZALO_QUEUE_TURN_TIMEOUT_S=150`);
  on timeout send UX line, `compound_end`, continue drain.
- Cap drain age (`ZALO_QUEUE_DRAIN_MAX_S`); cancel stuck drain so kick can restart.
- Omni providers default Tavily → Firecrawl → SearXNG; per-provider timeout 20s.

### Prevent recurrence

Never let one Hermes turn hold the Zalo FIFO without a hard deadline. Keep
search provider timeouts short enough that failover finishes inside the turn budget.


## 2026-08-21 18:05 +07 — Native Hermes search ignored Omni / Router Worker

### Symptom

Zalo weather query answered with search-tool technical failure.

### Root cause

Hermes toolset `web` calls `SEARXNG_URL/search` (or Tavily with
`TAVILY_API_KEY`). `WEB_SEARCH_URL` is unused by the native tool. Lab Hermes
only had raw SearXNG; Omni Tavily key cannot be read unmasked from Omni API.

### Fix

- `GET /v1/searxng-compat/search` on Router Worker wraps Omni search.
- Hermes `SEARXNG_URL=http://model-router:8096/v1/searxng-compat`.
- Keep Router Worker `SEARXNG_URL` as real SearXNG for direct adapter fallback.

### Prevent recurrence

Never assume Hermes env `WEB_SEARCH_URL` feeds the native web tool; wire
`SEARXNG_URL` / `TAVILY_API_KEY` explicitly.


## 2026-08-21 17:55 +07 — Weather search soft-fail: Hermes tool used SearXNG only

### Symptom

Zalo weather ask got a soft failure about the search tool being broken.

### Root cause

Hermes native `web_search` (toolset `web`) ignores `WEB_SEARCH_URL` /
Router Worker. With only `SEARXNG_URL` set and no `TAVILY_API_KEY` in the
Hermes container, SearXNG returned unusable results and the model apologized.

Also: two skills named `web-search` caused cron skill load collisions.

### Fix

- Compose: inject `TAVILY_API_KEY` / `FIRECRAWL_API_KEY` into Hermes.
- Rename knowledge skill frontmatter to `web-search-strategy`.
- Recreate Hermes on lab; verify native `web_search_tool`.

### Prevent recurrence

Any provider key required by Hermes built-in tools must be on the Hermes
service env, not only on router-worker / Omni.


## 2026-08-21 16:53 +07 — Omni owns search; Router Worker proxies

### Symptom

Search was split: skills said Router Worker combo, Omni UI already had Search
providers / Engine Combos; lab SearXNG was not connected in Omni.

### Root cause

Stack treated Omni as LLM-only. Local SearXNG needs `providerSpecificData.baseUrl`
(Omni SSRF guard rejects bare private URLs on test without that path). Default
Omni search preferred `ollama-search`.

### Fix

- `first-setup-omnirouter.py`: ensure Tavily + SearXNG search providers, block
  ollama-search, smoke `/v1/search`.
- `websearch.py` `omni` backend; combo JSON / compose default `WEB_BACKENDS=omni`.
- Skills + CHANGELOG updated.

### Prevent recurrence

Run first-setup after Omni upgrades; keep SearXNG on `assistant_internal` with
Omni; do not put the SearXNG URL in the apiKey field alone.

## 20 2026-08-21 16:30 +07 â€” Web search order must not be hardcoded in .py

### Symptom

Requirement: web-search skill â†’ Router Worker; default combo failover
Tavily â†’ local SearXNG like OmniRouter combos; do not hardcode order in Python.

### Root cause

`websearch.py` kept `DEFAULT_CHAIN = ("tavily", "searxng")` and reshuffled
SearXNG to the end in code, which duplicated/overrode operator config.

### Fix

- Combo file `architect/models/model-router/config/web-search-combo.json`.
- Order from `WEB_BACKENDS` or that JSON only; adapters remain a registry.
- Skills document Router Worker path and config sources.

### Prevent recurrence

Change search failover by editing the JSON/env â€” never add a Python default tuple.

---

## 2026-08-21 16:05 +07 â€” Web search combo vs OmniRouter; SearXNG empty

### Symptom

Operators asked whether OmniRouter had a Tavilyâ†’SearXNG web-search combo.
Lab `/v1/search` returned 502; Hermes `web_extract` errored that SearXNG
cannot extract.

### Root cause

1. **Architecture:** web search is on **Router Worker** (`model-router`), not
   OmniRouter. OmniRouter only routes chat completions.
2. `TAVILY_API_KEY` was empty on lab.
3. SearXNG was up but Brave/DDG/Google/Startpage were CAPTCHA / rate-limited
   from the VPS IP â†’ empty `results` â†’ combo failed.

### Fix

- Document clearly; harden SearXNG engine list + searx client error detail.
- Lab: `ENABLE_SEARXNG=1`, `WEB_BACKENDS=tavily,searxng`; recreate searxng +
  router-worker. Operator must set a real `TAVILY_API_KEY` for primary.

### Prevent recurrence

Do not add web search as an OmniRouter LLM combo. Keep Tavilyâ†’SearXNG on
Router Worker. Extract must use Tavily/Firecrawl only.

---

## 2026-08-21 15:35 +07 â€” Cron body wrapped; lyric ask ignored Multo.mp3

### Symptom

1. Due lá»‹ch on Zalo included `Cronjob Response: â€¦ (job_id: â€¦)` and
   `To stop or manage this jobâ€¦` around the real answer.
2. After Multo mp3, user said `tÃ¬m lá»i bÃ i hÃ¡t` (quote reply) and the bot asked
   for song/artist instead of web-searching.

### Root cause

1. Agent created a **Hermes CLI cron** job; `cron/scheduler.py` wraps every
   delivery. Schedule skill forbids this, but wrappers still reached Zalo.
2. Empty Whisper transcript â†’ attachment not remembered; quoted text not injected
   into the agent prompt â†’ model had no Multo context.

### Fix

- `strip_cron_delivery` on Zalo outbound (body only).
- Always remember bare attachment filenames; inject `[Quoted message]`; lyric
  follow-up hints Router `/v1/search` from filename.
- Skills updated; lab: `hermes tools disable cronjob`.

### Prevent recurrence

Never surface Hermes cron envelopes on Zalo. Lyric intents must use recent
audio filename / quote before clarifying.

---

## 2026-08-21 14:25 +07 â€” Bare csv/xlsx/mp3/txt silent; mp4 â€œno video attachedâ€

### Symptom

Zalo user sent bare files. Photo OCR-ack worked. mp3/txt only got
`Knowledge â€” pending approval`. csv/xlsx produced no bot reply. mp4 reply was
â€œI don't see a video file attachedâ€¦â€ despite a staged `.mp4`. Hermes logged
HTTP 503 `Structurally heavy chat request capacity is busy`.

### Root cause

1. Only **bare images** short-circuited to a deterministic OCR ack. Other bare
   attachments still entered the agent/LLM path.
2. Omni free capacity was busy; rotate exhausted without backoff â†’ agent died â†’
   no content reply (Knowledge-pending is learn notify, not a summary).
3. With empty/failed extract in the agent prompt, the model hallucinated â€œno
   video attached.â€

### Fix

- Deterministic `file_extract_ack_message` for bare text/office/av (same send
  path as image OCR ack: skip autosend, clear answering, kick queue).
- Router: `chat_busy_capacity` + `OMNIROUTER_BUSY_BACKOFF_S`; rotate default 5.

### Prevent recurrence

Any bare attachment that workers can extract must reply without waiting on Omni.
Knowledge-pending must never be the only user-visible outcome of a file send.

---

## 2026-08-21 14:05 +07 â€” Second photo after OCR ack got no reply

### Symptom

User sent two bare images. The first got `ÄÃ£ Ä‘á»c chá»¯ trong áº£nh (OCR): â€¦`.
The second was downloaded and OCRâ€™d (Paddle returned glyph noise) but Zalo
never showed a second bot message.

### Root cause

1. SSE handler **awaited** the full inbound path (AV + OCR). While the first
   photo blocked the reader for tens of seconds, follow-up events were at risk
   and ordering/backpressure became fragile.
2. OCR-ack `send()` did not set `as_skip_autosend`, so autosend could hang the
   second ack; `as_skip_inflight` also skipped clearing the Valkey answering slot.

### Fix

- Background `_on_inbound_guarded` + per-thread lock (SSE keeps reading).
- OCR ack: `as_skip_autosend` / `skip_outbound_filter`, explicit `answering_done`,
  queue kick, part-delivered signal.
- Glyph-noise OCR treated as empty for the user-facing ack.

### Prevent recurrence

Never block the Zalo SSE loop on OCR/AV. Deterministic OCR replies must not
enter autosend or leave the answering slot held.

---

## 2026-08-21 13:45 +07 â€” OCR succeeded; user still got silence (Omni 403)

### Symptom

Inbound `chat.photo` was staged and PaddleOCR returned text, but Zalo showed no
bot reply. Hermes logged `[ollama-cloud/deepseek-v4-pro] [403] requires a
subscription`, compound part wait timeouts, and occasional tool noise (`pdf`
skill collision, missing `file` binary).

### Root cause

1. OmniRouter `hermes` combo round-robins into paid cloud models. Model-router
   passed SSE streams through, so a subscription refuse reached Hermes as a hard
   APIError and exhausted retries with no send.
2. Bare-image turns with OCR text still entered the full agent/tool loop, which
   can fail entirely when the LLM path dies â€” unlike the empty-OCR deterministic
   ack path.

### Fix

- Router: sync chat upstream, failover on 403/subscription error bodies, **retry
  the Omni combo several times** (free-member rotation) with a **180s** timeout,
  then try `OMNIROUTER_FAILOVER_MODELS` (default `auto/best-free`), synthesize
  SSE for streaming clients.
- Adapter: bare image â†’ send OCR ack immediately and skip agent (text or empty).
- Regression: `test/scripts/omni_rotate_noreply_unit.py`, case 37.

### Prevent recurrence

Never stream opaque upstream errors past the router when another free Omni
member or failover model can answer. Attachment OCR success must produce a
user-visible Zalo message even if the agent cannot complete a tool turn.

---

## 2026-08-21 12:15 +07 â€” PaddleOCR init failed until version line matched

### Symptom

OCR health reported `primary=paddle` but every image returned `via=tesseract`
(or `paddle_not_installed`) after the first Paddle rebuilds.

### Root cause

paddleocr and paddlex majors must stay on the same minor line. 3.1.1 + 3.7.x
broke `PaddlePredictorOption`; forcing paddlex 3.1.1 then failed on a removed
langchain import path.

### Fix

Pin `paddleocr==3.7.0` with `paddlex==3.7.2`. Lab verify: still text extracted
with `via=paddle`.

### Prevent recurrence

When bumping either package, follow the official paddleocrâ†”paddlex table; do not
mix 3.1.x OCR with 3.7.x paddlex.

---

## 2026-08-21 12:10 +07 â€” Vision-first OCR kept failing on text-only routers

### Symptom

Inbound images either got a generic photo description, a blind-model â€œplease uploadâ€
excuse, or an empty tesseract scan after vision cooldown â€” Hermes never reliably
received the glyphs that were on the picture.

### Root cause

The OCR worker called a vision LLM first. On this stack the routed model has no
vision, so every image paid for a failed round trip. Tesseract was only a fallback
and is weak on UI screenshots / Vietnamese receipts.

### Fix

PaddleOCR is the primary engine in the OCR container (Media Worker boundary,
separate from dispatcher). Vision is opt-in (`OCR_VISION=0`). Inference runs on a
thread pool so ASR and other media jobs stay responsive. Tesseract stays as the
secondary local fallback.

### Prevent recurrence

OCR answers â€œwhat text is there?â€; the LLM answers â€œwhat does it mean?â€. Do not
put a vision chat model in front of deterministic OCR for screenshots and documents.

---

## 2026-08-21 11:52 +07 â€” OCR crash-loop: result.py missing from image

Dockerfile only copied `app.py`/`refuse.py`; after PR #93 the container imported
`result.empty_scan_result` and exited. COPY fixed; rebuild returns
`{"ok":true,"empty":true}` for the staged no-text photo.

---

## 2026-08-21 11:50 +07 â€” Staged photo still greets; empty OCR treated as failure

### Symptom

After the shared-media staging fix, a resent `chat.photo` wrote
`/data/media/inbound/â€¦/image.jpg`. Bridge later sent a Zalo reply, but it was only
â€œChÃ o báº¡n, tÃ´i lÃ  Hermesâ€¦ /helpâ€. Hermes logs showed the usual tool/SOUL warnings;
OCR logged `vision_cooldown` then `ocr_failed` with empty tesseract output.

### Root cause

1. Vision cooldown (blind model) forced tesseract; the photo had no readable text, so
   OCR returned **`ocr_failed`** instead of an empty success â€” Hermes treated that like
   a hard miss.
2. After `hermes` recreate the agent session was fresh; with an empty excerpt the model
   ignored the attachment prompt and introduced itself.
3. Residual OCR 404s / empty-path probes still appeared from path races; b64 retry covers
   that class of miss.

### Fix

- OCR: empty local scan â†’ `ok:true, empty:true`; require `path` or `image_b64`.
- Adapter: bare image + empty OCR â†’ deterministic ack and **no agent turn**; OCR 404/empty
  retries with `image_b64`.

### Prevent recurrence

Never send a bare inbound image into a full agent turn when OCR returned no text â€”
ack first. Never report â€œocr_failedâ€ when the local scanner finished and found nothing.

---

## 2026-08-21 11:40 +07 â€” Zalo photo: bridge OK, media-proxy OK, OCR 404, no reply

### Symptom

User sent a `chat.photo`. Bridge logged the RAW message and `/media/fetch` wrote a JPEG into
`~/.hermes-zalo/media-cache`. Hermes started a turn (tool-registry warnings + `SOUL.md`
blocked). OCR logged `POST /v1/ocr 404`. Classify/outbound returned 200. No bridge `send`
followed â€” the user got silence. The SOUL/kanban warnings were unrelated noise.

### Root cause

1. `_download_media` stores bytes via `cache_image_from_bytes` under
   `/opt/data/replicas/<id>/cache/images/â€¦`. Workers mount only `/data/media`
   (shared with `/opt/data/media`). `worker_media_path` left the replica path unchanged,
   so OCR correctly answered **file not found / 404**.
2. With an empty OCR excerpt, the bare-image prompt told the agent to **open the image
   file and describe it**. Vision/browser tools were unavailable (`check_* returned False`),
   so the turn burned model calls without a deliverable Zalo send.

### Fix

Stage every inbound download onto `/opt/data/media/inbound/{thread_id}/` before OCR/AV
workers run (`attachment.stage_shared_media`). Soften the empty-OCR image prompt so the
agent replies without calling missing vision tools.

### Prevent recurrence

Anything Hermes asks a worker to read must live on the shared media volume. Replica cache
paths are for the gateway only â€” never pass them to OCR/ingest/dispatcher.

---

## 2026-08-21 11:20 +07 â€” Bridge crash-loop on :8787; Hermes cannot POST /media/fetch

### Symptom

`journalctl --user -u com.hermes.zaloplugin -f` showed a continuous `EADDRINUSE
0.0.0.0:8787` restart storm (counter past 9500). At the same time
`docker logs assistant-hermes-1` logged `Zalo: media-proxy fetch HTTP 404 Cannot
POST /media/fetch`, so inbound images never reached OCR.

### Root cause

1. An orphan Node bridge started via `runuser` (from `patch_zalo_bridge_inject.py`
   / historical `nohup`) already owned `:8787`. The user systemd unit stayed
   enabled with `Restart=always`, so it kept failing to bind.
2. Hermes expects `POST /media/fetch` on the host bridge (`ASSISTANT_MEDIA_PROXY_v1`),
   but upstream `hermes-zalo-plugin` 1.0.9 never shipped that route. The inject
   patcher's marker was also wrong (`POST /inject-event` vs `app.post("/inject-event"`),
   so `/inject-event` was inserted three times.

### Fix

- Patcher installs `/media/fetch` + `/media/:id` (CDN GET with session cookies),
  dedupes inject handlers, and restarts via the systemd user unit after clearing
  orphans â€” never a competing `nohup`/`runuser` listener while the unit is enabled.
- `setup-zalo.sh` and `zalo-watch.sh` use that path for heal/setup.

### Prevent recurrence

One process must own the bridge port. Prefer the systemd user unit; any helper that
starts Node directly must stop or disable the unit first. Adapter â†” bridge contracts
(`ASSISTANT_MEDIA_PROXY_v1`) need a matching route in the patcher when upstream omits them.

---

## 2026-08-21 11:10 +07 â€” Images â€œreadâ€ but the text was the model asking for the image

### Symptom

An image sent to Zalo came back as a generic description instead of its text, and video
keyframe OCR returned paragraphs like â€œI'd be happy to help extract text as markdown, but
you haven't provided any source materialâ€. OCR logs said `stage=ocr ok=True chars=472`, so
from the outside the worker looked healthy.

### Root cause

OCR sends the picture to the router as an `image_url` part, but the model behind the alias
on this stack is text-only, so it replied 200 OK asking the user to upload an image. That
reply was over `OCR_MIN_CHARS` and matched none of the refusal patterns â€” â€œdonâ€™t see an
imageâ€ was absent, and the model's curly apostrophe would have defeated the `don't`
patterns anyway â€” so the excuse was returned as extracted text and the tesseract fallback
(already installed with `eng+vie`) never ran.

### Fix

Refusal detection now recognises the â€œno image attached / please upload / once you shareâ€
family after normalising smart quotes, and lives in `refuse.py` with a unit test. After
three consecutive blind replies the worker stops calling vision for 15 minutes and uses
local OCR directly, which also removes a pointless round trip from every image turn.

### Prevent recurrence

A worker that forwards an upstream answer must validate that the answer is the *kind* of
thing it asked for. Length alone is not evidence, and `ok=True` in a log line is only as
honest as that check.

---

## 2026-08-21 10:40 +07 â€” â€œService recovered: dispatcherâ€ every 2 minutes; media text always empty

### Symptom

Notify alternated dispatcher DOWN/UP roughly every two minutes, and it looked like media work was crashing the service. Verifying the new `POST /v1/media/text` on the lab returned `text: ""` for both an mp4 with on-screen text and an mp3, and long calls to dispatcher or ingest sometimes died mid-request with a connection reset.

### Root cause

1. `stack-watch` probed 9Router unconditionally. This lab runs OmniRouter only, so the probe failed on every tick (`fail_count` had reached 577), and the heal branch then ran a blanket `docker restart dispatcher` â€” every 2 minutes, regardless of dispatcher's own health. In-flight OCR and media requests died with it.
2. `faster-whisper` was listed only as a comment in the media worker requirements, so ASR raised `ModuleNotFoundError` and the transcript was always empty. After installing it, `faster_whisper.utils` still failed on `import requests`, because `huggingface_hub` 1.x dropped that dependency.
3. Keyframes were sampled with `fps=1/7`, so a clip shorter than the interval produced no frame and OCR never ran.

### Fix

- stack-watch probes optional components only when enabled or running, and restarts only the containers whose own probe failed.
- ASR wheels install behind the `INSTALL_WHISPER` build arg with `requests` pinned; `HF_HOME` lives on the media volume.
- Keyframes are taken by seeking to evenly spaced timestamps, and the endpoint reports `frames_read`.

### Prevent recurrence

A watchdog must restart only what it proved unhealthy, and must not probe components the stack does not run. When a capability is optional at build time, verify the import inside the built image â€” a commented-out requirement looks enabled from the outside.

---

## 2026-08-21 09:40 +07 â€” Files answered without being read; dispatcher flap; schedules only removable one at a time

### Symptom

Sending an image got a generic â€œfluffy kittenâ€ description instead of its text. A `.txt` with `123` replied slowly, and asking again still felt slow. A video got â€œwhat should I do with it?â€, then â€œpaste the content you want summarizedâ€. `.docx/.xlsx/.pptx/.csv` only produced â€œKnowledge â€” pending approvalâ€. Asking for a text file said it was sent but nothing arrived. `gá»­i tin chÃ o buá»•i sÃ¡ng vÃ  tÃ³m táº¯t giÃ¡ xÄƒng â€¦ kÃ¨m theo thá»i tiáº¿t â€¦` ran as one job. Notify kept alternating dispatcher DOWN/UP while OCR and media jobs ran. Admins could only remove one schedule per command.

### Root cause

1. No worker owned most extensions: office/CSV went only to the async learn pipeline, audio/video went nowhere, so the agent answered from the filename alone.
2. Text extraction waited behind the AV gate instead of running alongside it, and the AV poll started with a long sleep.
3. Attachment recall stored a single file, so a mixed pack lost everything but the last item, and the inbound FIFO capped at 8 dropped the tail of a pack.
4. Zalo rejects a document attachment whose `caption` is present but blank (`Tham sá»‘ khÃ´ng há»£p lá»‡`); the fallback caption was a single space.
5. Dispatcher served web search **and** blocking media work behind a synchronous `/health`, so probes timed out under load and looked like a crash.
6. The classifier prompt only split numbered lists, not conjunction-joined deliverables.
7. `schedule remove` resolved exactly one selector, with no group or range support.

### Fix

- `attachment.py` routes each extension to its worker (local read / OCR / Ingest `POST /v1/extract-text` / Media `POST /v1/media/text`), runs concurrently with the AV gate, and keeps 5 files of recall per thread; FIFO cap 16.
- Omit the `caption` field entirely when blank.
- Move web search to Router Worker (`model-router`) with Tavily â†’ SearXNG fallback; make dispatcher `/health` async.
- Classify prompt: conjunction-joined deliverables become separate async instructions; grouped items (E5 RON92 + E10 RON95) stay in one.
- `schedule remove` accepts index lists, ranges, `all`, and `group <name>`, deleting from `cron/jobs.json` and the workflow service.

### Prevent recurrence

Never answer about a file the stack has not read â€” add an extension to a worker route or say plainly it could not be read. Keep long-running work off the same event loop path as `/health`, and keep one search implementation (Router Worker) so skills cannot drift to a second one.

---

## 2026-08-21 08:20 +07 â€” Image asks for caption; PDF learn without summary; txt â€œsentâ€ but missing; adapter EICAR cheat

### Symptom

Photos got â€œcáº§n mÃ´ táº£â€. PDF triggered learn-approve but no summary. Creating a text file claimed sent but Zalo showed nothing (`Tham sá»‘ khÃ´ng há»£p lá»‡`). Concurrent messages felt stuck. Operator forbade local EICAR matching in the Zalo adapter.

### Root cause

1. OCR called with Hermes path `/opt/data/media/...` while OCR mounts `/data/media` â†’ HTTP 404 â†’ empty excerpt.
2. Learn pipeline ran async; agent turn had no OCR text.
3. Zalo rejects some `.txt` attachments; autosend still reported success from LLM copy.
4. Local `_as_eicar_hit` duplicated Security Worker AV.

### Fix

- Remove adapter EICAR; keep AV gateway fail-closed.
- OCR path mapping + quick excerpt before agent summary.
- Text-attachment fallback to chat body; clearer image prompts; queue ack when FIFO depth > 1.

### Prevent recurrence

Never put virus signatures in channel adapters. Always pass media paths OCR/ingest containers can resolve.

---

## 2026-08-21 07:45 +07 â€” `/opt/data` probe not refused; EICAR file asked to learn

### Symptom

User asked to find `/opt/data` â€” Hermes used terminal and returned path info instead of a refuse. Sending `question.txt` with EICAR still prompted knowledge learn. Security Worker was inactive; no clamav.

### Root cause

1. Secret-probe patterns lacked `/opt/data` / common host paths; empty data-volume policy could disable blocking.
2. When antivirus gateway was down, AV gate skipped and still enqueued learn (`AV_REQUIRED` defaulted off).
3. No local EICAR check without Security Worker.

### Fix

- Expand secret-probe policy; skip empty files; default path patterns.
- Local EICAR block; fail closed when antivirus enabled but unavailable.
- Enable Security Worker (+ antivirus) on lab when deploying this fix.

### Prevent recurrence

Never learn untrusted files without AV/EICAR gate. Keep secret-probe patterns in editable JSON; do not leave empty `secret-probe.json` on the data volume.

---

## 2026-08-21 07:20 +07 â€” LC group schedule fired but no group reply; dispatcher CRITICAL flap

### Symptom

Schedules targeting Zalo group **LC group** showed `fired zalo` in schedule-worker but the group got no bot reply. Creating a lá»‹ch felt slow. Concurrent chat felt stuck. Notify spammed CRITICAL Dispatcher DOWN/UP. Operators asked for schedule history and `run.sh` install|remove workers; target architecture removes generic Dispatcher.

### Root cause

1. `ZALO_GROUP_MODE=mention` dropped inbound without @bot â€” including `scheduleFire` injects into groups.
2. Classify always tried broken `classifier` combo first (401/403) before `hermes` â†’ slow schedule ack.
3. Thread inflight/rate-limit could drop fires when queue off.
4. Alert-watch fired DOWN on a single failed probe during brief dispatcher restarts.
5. No durable fire history API on Schedule Worker.

### Fix

- Bypass mention / rate / inflight for `scheduleFire`.
- Classify skip TTL after auth failures; prefer chat combo while skipped.
- Schedule Worker fire log + `/v1/schedules/history`.
- `HEALTH_FAIL_STREAK=3` before CRITICAL DOWN.
- `worker-routing` skill; `run.sh install-workers` / `remove-workers`.

### Prevent recurrence

Never apply group mention-gate to protocol injects (`scheduleFire`). Health alerts must require a failure streak. New routing goes through Hermes skills â†’ workers, not Dispatcher.

---

## 2026-08-20 20:45 +07 â€” Recurring media Permission denied; dual Hermes lab

### Symptom

Hermes repeatedly hit `Permission denied` on `/opt/data/media/inbound` or `media/out` after redeploys / root-owned mkdir. Operators asked for durable prevention and a dual-Hermes concurrent isolation check (hello / web / txt / OCR mix).

### Root cause

Media dirs were only created in `setup-zalo` (or one-off lab chown). Fresh volumes or root tools left dirs non-writable for Hermes UID 1000. Replica entry did not heal media ownership on start.

### Fix

- Ensure media dirs + ownership in `run.sh` (up/update), `setup-zalo.sh`, `hermes-replica-entry.sh`, and `stack-watch.sh` (setgid + ug+rwX).
- AGENT_RULES #50: fix in source, pull on host â€” no hotpatch-only â€œfixes.â€
- Case 30 + `hermes_dual_isolation_lab.py` for HERMES_REPLICAS=2 concurrent admin injects.

### Prevent recurrence

Do not mkdir media as root without chown to `HERMES_UID`. Prefer entrypoint + stack-watch heal over manual SSH chown. Shared `.env` / `config.yaml` must also stay Hermes-UID-writable when replicas rewrite home-channel settings.

---

## 2026-08-20 20:35 +07 â€” DM schedule into named group asked for chat ID

### Symptom

From DM: â€œÄ‘áº·t lá»‹ch â€¦ vÃ o group Zalo LC group â€¦â€ â€” bot replied to send the request inside the group or provide a chat ID, instead of creating a schedule that delivers to that group.

### Root cause

1. Classify combo `classifier` returned HTTP 403 / empty content â†’ `classify_llm_failed` â†’ Zalo fail-open to Hermes chat, which invented the â€œgo to the group / give chat IDâ€ reply.
2. Channel registry had only the DM user (no groups) until someone ran `!zalo refresh`, so even a good `target_channel: LC group` would have hit `group_not_found`.
3. Name â€œZalo LC groupâ€ did not match registry name â€œLC groupâ€ (prefix / reverse containment).

### Fix

- Classify retries with the chat combo (`hermes`) when the classify combo is forbidden or empty.
- zalo-api syncs bridge contacts on startup and again on resolve miss; resolve accepts platform-prefixed and reverse-contained names.
- Schedule skill documents `!zalo refresh` / `!zalo allow` UX â€” never ask for raw chat IDs.

### Prevent recurrence

Keep a working classify path (dedicated combo or failover to chat combo). Do not rely on Hermes free-chat to create schedules. Registry must stay warm from bridge contacts without requiring the operator to remember `!zalo refresh` before the first named-group schedule.

## 2026-08-20 20:20 +07 â€” Legacy check-medium/high wrappers and High deploy PS1

### Symptom

`scripts/main/check-medium.sh` and `check-high.sh` still existed after workers renamed smokes to `check-media` / `check-security`. `Deploy-High.ps1` / `Deploy-V050-Test.ps1` referenced Python entrypoints that are not in `scripts/main`.

### Root cause

Compatibility aliases left after the medium/high â†’ media/security rename; PowerShell deploy wrappers never moved with the Python helpers into `scripts/temp/`.

### Fix

Delete the wrappers and broken PS1 entrypoints. Keep only `check-media.sh` / `check-security.sh` and `run.sh` worker command names.

### Prevent recurrence

Do not add profile-tier smoke aliases. New smoke scripts must use worker names (`media`, `security`, â€¦).

## 2026-08-20 20:10 +07 â€” Learn pending silent; schedule inject 404; legacy medium/high compose

### Symptom

1. Zalo file/OCR reached ingest pending but admin never got approve (`!zalo learn approve â€¦`).
2. Saved schedules did not run; `schedule-worker` logged `inject 404` / `EOF` on `zalo-proxy:8787/inject-event`.
3. Bridge restarted on `127.0.0.1` only â†’ Docker Hermes SSE / socat could not reach host `:8787`.
4. File pipeline: `Permission denied: /opt/data/media/inbound`.
5. Ops still referenced obsolete `docker-compose.medium.yml` / `high.yml` while runtime used workers + `media`/`security`.

### Root cause

1. Ingest notify posted only to Notification Worker; with Notify inactive, `notified=false` and no bridge fallback; admin file not wired on ingest.
2. Host `hermes-zalo-plugin` lacked `POST /inject-event`; wrong bind after restart dropped Docker reachability.
3. Shared media dirs missing / root-owned so Hermes could not stage inbound files.
4. Duplicate legacy profile overlays drifted from `run.sh` (media/security) and confused backup/stack-watch/first-setup.

### Fix

- Ingest: notify â†’ bridge `/send` fallback to sole admin; compose wires `ZALO_BRIDGE_URL` + `ZALO_ADMIN_USERS_FILE`.
- `patch_zalo_bridge_inject.py`: keep `ZALO_PLUGIN_HOST=0.0.0.0` on restart; document firewall risk (do not publish 8787 publicly; use `ZALO_PLUGIN_TOKEN`).
- `setup-zalo.sh`: create `media/inbound` + `media/out` owned by Hermes UID.
- Remove `docker-compose.medium.yml` / `docker-compose.high.yml`; point backup, stack-watch, and first-setup at `media.yml` / `security.yml` like `run.sh`.

### Prevent recurrence

Do not reintroduce ASSISTANT_PROFILE overlays. Learn pending must never depend on Notify Worker alone. After any bridge restart, verify listen is `0.0.0.0:8787` and `/inject-event` returns `{"ok":true}` from the schedule network.

## 2026-08-20 19:35 +07 â€” Security containers started while Security Worker inactive

### Symptom

Hosts with Security Worker inactive still ran OpenBao / security-manager / authz / SIEM / policy-center. Notify or other workers pulled those services up as hard dependencies.

### Root cause

Security services lived on the always-on compose path (or Notify `depends_on`) instead of compose profile `security` gated by `WORKER_SECURITY` / `ENABLE_SECURITY`.

### Fix

- Put OpenBao and security-plane services behind `--profile security`.
- Notification Worker no longer starts them; `run.sh` removes them when Security is inactive.
- Drop hermes/ingest hard `depends_on` onto profiled security services from the security overlay.

### Prevent recurrence

Optional security plane must follow the same worker activation pattern as Media|File. Do not hard-depend core chat on Security containers.

## 2026-08-20 18:55 +07 â€” Classify returned empty JSON from reasoning / CoT models

### Symptom

Dedicated classify combo still failed with empty `content` even when the provider returned a usable plan in reasoning / thinking fields. Schedules and multi-task plans fell through or timed out.

### Root cause

`_message_text` only read `message.content`. OpenCode / reasoning models often leave `content` empty and put the answer in `reasoning_content`, `reasoning`, `thinking`, `thinking_content`, `thought`, `reasoning_text`, or `reasoning_details`.

### Fix

Expand `_message_text` to read those CoT fields (and any other message key containing reason/think) before declaring classify empty.

### Prevent recurrence

Any new classify provider must be tested with â€œcontent empty, CoT filled.â€ Do not require non-empty `content` alone.

## 2026-08-20 18:50 +07 â€” Classifier combo had no usable OpenCode members

### Symptom

`MODEL_ROUTER_CLASSIFY_MODEL=classifier` returned 401/403 or empty; combo existed but members were wrong shape or OpenCode stayed in `blockedProviders`.

### Root cause

`first-setup-omnirouter` did not clear OpenCode blocks, did not load the live `oc/*` catalog, and wrote combo members without Omniâ€™s `connectionId` object shape.

### Fix

- Clear `blockedProviders` for OpenCode.
- Load all current `oc/*` from `/api/models`.
- Write combo members with `connectionId`.
- Note: upstream OpenCode HTTP 403 (quota/block) can still occur â€” classify must fail open / failover until upstream recovers (see 20:35 failover).

### Prevent recurrence

After first-setup, probe classify with the `classifier` combo. If members are empty, re-run Omni first-setup rather than hardcoding model ids in product code.

## 2026-08-20 18:40 +07 â€” Chat and classify shared one Omni combo

### Symptom

Classify burned free-tier quota / slow models used for chat. alert-watch still probed 9Router login when `ENABLE_9ROUTER=0`. Bare Zalo images triggered document-OCR Q&A prompts.

### Root cause

One combo (`hermes`) handled both interactive chat and classify. Watch scripts assumed 9Router always on. Image inbound path treated every image as a document OCR job.

### Fix

- Dedicated Omni combo **`classifier`** (OpenCode Free `oc/*`); chat/outbound stay on **`hermes`**.
- Default `MODEL_ROUTER_CLASSIFY_MODEL=classifier`.
- alert-watch skips 9Router `/api/auth/login` when 9Router is disabled.
- Bare Zalo images no longer force document-OCR Q&A.

### Prevent recurrence

Keep classify and chat on separate combos. Optional routers must be skipped by watches when disabled.

## 2026-08-20 16:35 +07 â€” first-setup overwrote Omni combo member lists

### Symptom

Operators curated Omni Combos in the UI; next `first-setup-omnirouter` rewrote a fixed `oc/*` member list and undid their routing.

### Root cause

First-setup treated combo membership as code-owned SoT.

### Fix

`first-setup-omnirouter` only ensures combo alias `hermes` exists (classifier setup still fills `classifier` from catalog where required). Chat combo members stay UI-managed. Stack sends the combo **name** only.

### Prevent recurrence

Do not hardcode chat combo members in product setup. Document that operators manage members in Omni Combos.

## 2026-08-20 16:25 +07 â€” Operators treated `hermes` as a vendor model id

### Symptom

Docs and env looked like a standalone model named `hermes`. People set OpenRouter / vendor model ids and got 401s.

### Root cause

Naming collision: `hermes` is the **OmniRouter/9Router combo alias** in the OpenAI `model` field, not a vendor model id.

### Fix

Clarify in docs/env: classify/outbound resolve from `OMNIROUTER_DEFAULT_COMBO` / `N9ROUTER_DEFAULT_COMBO`. There is no standalone model id `hermes`.

### Prevent recurrence

Keep the wording â€œcombo aliasâ€ in DEFAULTS and model-routing docs.

## 2026-08-20 16:15 +07 â€” Zalo chat OpenRouter 401; classify model hardcoded

### Symptom

Zalo chat hit OpenRouter 401. Classify/outbound still used a hardcoded model string in `classify.json` instead of the env combo.

### Root cause

Shared Hermes `config.yaml` still pointed at the wrong `base_url` / key path. Classify ignored `MODEL_ROUTER_CLASSIFY_MODEL`.

### Fix

- Classify/outbound use `MODEL_ROUTER_CLASSIFY_MODEL` / `MODEL_ROUTER_OUTBOUND_MODEL` (default combo name).
- `patch-hermes-model-router.py` + `setup-zalo.sh` / `first-setup-omnirouter.py` point shared `config.yaml` at `http://model-router:8096/v1`.

### Prevent recurrence

After Zalo setup, verify Hermes `base_url` is model-router, not a direct OpenRouter or stale 9Router URL.

## 2026-08-20 16:05 +07 â€” Classify garbage JSON; `!zalo` admin help dropped

### Symptom

Omni returned invalid JSON / `task_hint: chat` for admin commands. `!zalo â€¦` help text was LLM-filtered away by outbound quiet-delivery.

### Root cause

Classify lacked a tight token cap, invalid-hint map, and local hello heuristic. Outbound treated admin command replies like agent chatter.

### Fix

- Classify: pin a small default free model where needed, cap `max_tokens`, map invalid `task_hint: chat` â†’ `normal`, dedupe instruction spam, local hello heuristic on garbage JSON.
- Zalo outbound: do not LLM-filter `!zalo â€¦` (`zalo_admin_reply` bypass + gateway_noise guard).

### Prevent recurrence

Admin protocol replies must bypass outbound LLM drop. Classify must never invent `task_hint: chat` for `!zalo` commands.

## 2026-08-20 14:35 +07 â€” clean-OS first-setup blocked (zalo-api / destroy / smoke names)

### Symptom

Fresh host: zalo-api crash-looped (`ModuleNotFoundError: channels_registry`); destroy failed backup with no containers; setup waited on 9Router / Low profile; smoke still named `check-medium` / `check-high`.

### Root cause

Dockerfile omitted `channels_registry.py`. Destroy always required a backup when the project had never been up. Setup still assumed profile/9Router. Product tiers renamed to workers but smoke script names lagged.

### Fix

- Copy `channels_registry.py` into zalo-api image.
- `setup-zalo.sh` waits for model-router + OmniRouter + zalo-api.
- Destroy skips backup when no project containers.
- Secrets-first `.env.example`; smoke `check-media` / `check-security` (wrappers removed later at 20:20).

### Prevent recurrence

Clean-host first-setup must not assume 9Router or ASSISTANT_PROFILE. New modules added to zalo-api must be listed in the Dockerfile.

## 2026-08-20 13:10 +07 â€” Worker-component rolling redeploy left stale cron / SSE

### Symptom

After rearchitecture deploy, leftover cron and unbound Zalo SSE caused abnormal schedule/media behavior on the lab host.

### Root cause

Destroy without clearing stale cron + bridge rebind left old schedules and a half-attached Zalo owner path.

### Fix

Destroy + clear stale cron; redeploy with Schedule / Media|File / Notify / Message workers (`WORKER_*=active`; security/monitor inactive). Rebind Zalo bridge (`loggedIn=true`, SSE connected).

### Prevent recurrence

Worker redeploys that change schedule ownership must clear or migrate old cron before up. Verify SSE after every Zalo-affecting recreate.

## 2026-08-20 12:50 +07 â€” Case 11 still profile upgrade/downgrade; outbound 3â€“8s too short

### Symptom

Case 11 still tested `switch-profile` tiers. Outbound classify timed out on free models and dropped quiet-delivery decisions.

### Root cause

Product moved to workers; tests and outbound budget did not.

### Fix

- Case **11** â†’ `11-worker-switch.md` / `worker_switch.py` (add/remove `WORKER_*`; fail event for obsolete `switch-profile`).
- Outbound classify timeout default/fallback **30s**.

### Prevent recurrence

Rule 48: after rearchitecture, update cases to workers. Rule 43: do not use overly strict free-model timeouts.

## 2026-08-20 11:50 +07 â€” Zalo users saw Hermes â€œWorking / iteration Nâ€ frames

### Symptom

Outbound Zalo showed agent status / provider-failure frames. Infographic requests had no dedicated skill. Docs still mentioned profile upgrade/downgrade.

### Root cause

Hermes status lines were not structurally dropped before send. Quiet-delivery was incomplete. `switch-profile` archive copy still said upgrade/downgrade.

### Fix

- Structural drop of Working / iteration / provider-failure frames; LLM `/v1/outbound` fail-closed to drop; skills `quiet-delivery` + `image-gen/infographic-design`.
- Secret-probe stays code policy; add password/credentials patterns.
- `switch-profile` stays disabled; worker `add-components` only.

### Prevent recurrence

Protocol/status frames must be dropped in code, not only by LLM outbound. Do not re-enable profile upgrade/downgrade UX.

## 2026-08-20 10:45 +07 â€” 9Router always-on; web search round-robin; no channel registry

### Symptom

Labs without 9Router still expected it. Web search order was unpredictable. Schedules could not resolve named Zalo groups. Deploy helpers still named `deploy_high`.

### Root cause

9Router was core Must. Search backends round-robin. No durable channel idâ†”name store.

### Fix

- 9Router optional (`ENABLE_9ROUTER=0` default). OmniRouter default; memory via `OMNIROUTER_ENABLE_MEMORY=1`.
- Web search: top **3**; fixed order Tavily â†’ Firecrawl â†’ SearXNG.
- Message Worker channel registry + `/v1/channels*` APIs.
- Lab deploy helper renamed `deploy_stack.py` (`deploy_high.py` shim).

### Prevent recurrence

Optional routers must default off in product source. Named-group schedules need a warm registry (see 15:45 / 20:35).

## 2026-08-20 10:20 +07 â€” Zalo lab 16/29 failed once then passed

### Symptom

Batch cases 16â€“29: **16** timed out watching sequential image+fuel; **29** saw transient classify `ok=false`. Other listed cases passed.

### Root cause

Watch budget 480s too short for sequential media. Classify free-tier flaked once. Schedule prompt used standalone word *lá»‹ch* as a brittle cue.

### Fix

- `zalo_multi_request_lab.py` default watch **720s**.
- Case 29 classify **3Ã— retry**.
- `classify.json` schedule prompt no longer keys off standalone *lá»‹ch*.
- Rerun 16 + 29 PASS.

### Prevent recurrence

Media compound labs need long watches. Classify flakes need retry, not a weaker assertion (rule 47).

## 2026-08-20 09:15 +07 â€” Product still spoke Low/Medium/High profiles at runtime

### Symptom

Operators enabled â€œHighâ€ and got the wrong optional set. Dispatcher always started. Redis container name confused Valkey docs.

### Root cause

Runtime still centered on `ASSISTANT_PROFILE` instead of worker activation. Dispatcher was Must rather than Media|File.

### Fix

- `WORKER_*=inactive|active`; bundled `ENABLE_*` on each worker (`workers.sh`). Product tiers gone from runtime.
- Dispatcher only with Media|File (`docker-compose.media.yml`). Schedule Worker is the clock; workflow is async jobs.
- Valkey container renamed `valkey`. Case 17: quota/failover is not a latency SLO fail.

### Prevent recurrence

Do not reintroduce ASSISTANT_PROFILE as the runtime gate. New optionals attach to a worker, not a tier name.

## 2026-08-20 08:45 +07 â€” Single-replica Zalo SSE broke via socat URL

### Symptom

Gateway showed Zalo disconnected or flaky SSE on single-replica hosts using a socat-style plugin URL.

### Root cause

Long-lived SSE does not survive some socat/proxy hops. Defaults still preferred that path.

### Fix

- `profile.sh` / defaults: `ZALO_PLUGIN_URL` â†’ `host.docker.internal:8787` for single-replica.
- Patch Hermes `config.yaml` to `model-router:8096/v1`.
- Latency probe reads replica `agent.log` / `gateway_state.json`, not only docker stdout.

### Prevent recurrence

Prefer host.docker.internal (or documented bridge) for SSE. After deploy, check `sseClients=1` and gateway platform connected.

## 2026-08-20 08:10 +07 â€” Optional workers off; no skill mapping classifier â†’ workers

### Symptom

Core stack lacked a clear map from classify JSON to Schedule / web-search / media-file / security workers. API Gateway and Valkey queue were not default-on for core.

### Root cause

Rearchitecture incomplete: workers existed as flags but skills/gateway defaults lagged.

### Fix

- Core: API Gateway on, Valkey inbound queue on; gateway skips RL for coding and schedule paths.
- Skill `core/worker-routing` maps classifier JSON to workers.
- Lab helper under gitignored temp for destroy+component deploy.

### Prevent recurrence

Classifier schema changes must update `worker-routing` in the same change. Keep optional workers default inactive in product source.

## 2026-08-20 15:45 +07 â€” Classify dead-end + schedule by group name

### Symptom

First Zalo message returned â€œCould not classify this request. Please send it again.â€; later messages had no reply. Operator wanted schedules that deliver to a named Zalo group.

### Root cause

1. `model-router` `/v1/classify` returned `ok:false` (`classify_llm_failed`) while chat completions still worked â€” Zalo adapter **consumed** the turn with an error instead of falling through to Hermes.
2. Channel registry was never populated (`NO_CHANNELS_DIR`), so there was no durable idâ†”name map for â€œgá»­i vÃ o nhÃ³m Xâ€.
3. Schedule `origin` always used the **current** thread, so DM-created schedules could not retarget a group.

### Fix

- Adapter: classify failure â†’ fall through to Hermes (fail-open).
- Persist Zalo users/groups in `channels/registry.json` (inbound upsert, allowlist/admin sync, bridge contacts via `!zalo refresh`).
- On schedule create, resolve `target_channel` / â€œnhÃ³m â€¦â€ and rewrite `origin.thread_id` to the group id (requester stays `user_id`).

### Prevent recurrence

Keep Hermes API key + Omni/fallback healthy for classify, but never block interactive chat on classify failure. Seed group names with `!zalo allow` / `!zalo label` / `!zalo refresh` before scheduling by name.

## 2026-08-20 15:25 +07 â€” Zalo connected but no bot replies (claim + normal chat)

### Symptom

Bridge `loggedIn=true` and `sseClients=1`, but `!zalo claim` / normal Zalo messages got no useful reply.

### Root cause

1. `!zalo claim` had already succeeded (`zalo_admin_users.txt` had a sole admin); re-claim only returns â€œalready has adminâ€.
2. Hermes `OPENAI_API_KEY` was wired only to `N9ROUTER_API_KEY` while OmniRouter is the default â†’ empty key on Omni-only installs.
3. Model path returned `omni-router:429` (OpenCode Free rate-limit / credential exhaustion) so LLM chat could not complete.

### Fix

- Compose: Hermes `OPENAI_API_KEY=${OMNIROUTER_API_KEY:-${N9ROUTER_API_KEY:-}}`.
- `setup-zalo.sh`: use `ASSISTANT_DATA_DIR` as the host shared Hermes data dir.
- Operator: wait out Omni free-tier cooldown, or enable an alternate provider (9Router / paid fallback).

### Prevent recurrence

Keep Hermes API key wiring aligned with the default router (Omni first). First-setup docs should note OpenCode Free 429 as a no-reply cause distinct from Zalo SSE attach failures.

## 2026-08-20 15:05 +07 â€” clean-host Zalo bridge logged in but Hermes never attached

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

## 2026-08-20 14:20 +07 â€” clean Ubuntu first setup blocked

### Symptom

Fresh host: `run.sh up` failed missing secrets; `destroy` failed backup (postgres not running); `zalo-api` crash-looped; `setup-zalo` waited forever on 9Router / â€œLow coreâ€.

### Root cause

1. `.env` not seeded with required `CHANGE_ME_*` / compose required vars.  
2. `do_destroy` always ran `backup_first` even with zero containers.  
3. `zalo-api` Dockerfile omitted `channels_registry.py`.  
4. `setup-zalo.sh` still branched on `ASSISTANT_PROFILE` and waited for 9Router on â€œlowâ€.

### Fix

- Reorder `.env.example` (secrets first); local `scripts/temp/generate_env_secrets.py`.  
- Skip backup on destroy when no project containers.  
- COPY `channels_registry.py` in zalo-api Dockerfile.  
- `wait_core_ready`: model-router + OmniRouter + zalo-api.  
- Docs/scripts updated to workers + OmniRouter default.

### Prevent recurrence

Keep Dockerfile COPY list in sync with `app.py` imports. First-setup docs must not mention PROFILE/low/9Router-as-default.

---

## 2026-08-20 07:35 +07 â€” profiles mixed optional workers into core

### Symptom

A fresh Low install started schedule/media/security-shaped services, and classify sent `max_tokens` that truncated long JSON.

### Root cause

`ASSISTANT_PROFILE=low|medium|high` turned whole overlays on. Schedule worker was always-on in compose. Classify always set `max_tokens`.

### Fix

Core is Hermes + Memory + Router Worker + Traefik local + watchdog. Other workers are `ENABLE_*=0` / compose profiles. Lab host `.env` can still turn Zalo/schedule/media on for tests. Classify omits `max_tokens` unless configured.

### Prevent recurrence

Do not map a profile name to a secret bundle of workers. Do not `depends_on` optional workers from Hermes.

---

## 2026-08-20 07:10 +07 â€” classify hit 9router; workflow owned cron ticks

### Symptom

Numbered once-lá»‹ch still classified slowly or failed closed. Schedules could re-enter classify as â€œÄ‘áº·t lá»‹châ€ and create another lá»‹ch.

### Root cause

Classify/outbound preferred 9router (`prefer_omni=False`) and `model=hermes` chat skipped Omni even when Omni was healthy. Workflow `fire_due` executed cron inside Hermes/workflow instead of a dedicated worker, and fired the wrapper text.

### Fix

OmniRouter is the default general router. A Go SQLite schedule worker stores when-to-run and injects inner `fire_text` back into Hermes. Workflow tick is disabled when `SCHEDULE_URL` is set.

### Prevent recurrence

Do not put a cron ticker in Hermes. Do not fire the original â€œÄ‘áº·t lá»‹ch lÃºc HH:MMâ€ wrapper. Do not force classify onto 9router when Omni is the default.

---

## 2026-08-19 21:25 +07 â€” once lá»‹ch still classify.failed at 21:21

### Symptom

The same numbered once lá»‹ch (21:21) still got the classify.failed Zalo line.

### Root cause

Length-based timeouts were a heuristic, not a fix. Both LLM attempts still ReadTimeout at 14s because the classify system prompt and required task_details JSON were too large for the first provider. Zalo then treated ok=false as â€œdid not understand.â€

### Fix

One classify timeout from `classify.json` (no character-count routing). Compact JSON contract; task_details optional. Fail over to the next model-router provider on timeout. Zalo HTTP classify wait is 70s. Workflows remain sequential=false.

### Prevent recurrence

Do not branch classify wait on message length. Make the LLM contract small enough to finish, and fail over providers.

---


### Symptom

A once lá»‹ch at 21:13 with four numbered tasks got â€œplease send againâ€ and was not stored.

### Root cause

Classify fail-closed on timeout. The payload was shorter than 400 characters so the LLM hop used the 3s hello budget. Two ReadTimeouts plus a 5s Zalo HTTP client timeout never returned JSON. Workflow then 503â€™d if anything reached `/v1/schedules`.

### Fix

Length-based classify budget (medium â‰¥120 chars â†’ 14s, long â‰¥400 â†’ 18s). HTTP client waits budget + 8s. Hello stays 3s. Workflows remain sequential=false.

### Prevent recurrence

Do not reuse the hello classify timeout for a multi-instruction lá»‹ch JSON payload.

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

## 2026-08-19 20:50 +07 â€” cron briefing returned only one picture

### Symptom

A once lá»‹ch at 20:35 asked for a greeting, fuel summary, weather summary, and an HCMC weather image. Zalo received only the picture.

### Root cause

The job stayed on Hermes native cron (`jobs.json` `run_at`, no 5-field `expr`) so migrate skipped it. One agent turn ran the whole prompt and mostly produced media. Classify timeout on long text also fail-opened. Overlay-merge wording in classify.json encouraged collapsing text+image. Root-owned `hcm_weather.jpg` failed chmod for the bridge.

### Fix

Keep numbered text tasks separate from a later draw. Re-classify at tick when stored instructions are a single blob. Sequential workflow jobs. Migrate once `run_at`. Copy media when chmod is denied. Longer classify timeout for long payloads.

### Prevent recurrence

Do not run a numbered briefing as one Hermes cron agent turn. Explode at tick through workflow.

## 2026-08-19 20:25 +07 â€” hi >15s; cron TypeError vars() on Zalo

### Symptom

A short Zalo ping still took more than 15s. A lá»‹ch job posted a Python `vars() argument must have __dict__` crash to the user.

### Root cause

Classify tried every model-router candidate (8s ReadTimeout each). Cron chat completions from 9router were not valid OpenAI message objects, so the Hermes OpenAI client raised TypeError (HTTP None).

### Fix

One classify/outbound provider then fail-open. 3s classify budget. Normalize/sanitize chat JSON in model-router. Rewrite the Python exception protocol line via `ux.json` `schedule.job_failed`. Restart the host bridge with `node server.js` after inject-event is patched â€” `hermes-zalo-plugin start` overwrites `server.js` and drops the route. Do not restart the bridge as root (cookies live in uid 1000â€™s home).

### Prevent recurrence

Do not loop every LLM provider on the Fast Dispatcher hop. Do not pass through non-ChatCompletion JSON as HTTP 200. Rolling apply must wait until the bridge is logged in before recreating Hermes, and must not call the plugin CLI `start` after a file patch.

## 2026-08-19 16:55 +07 â€” hi still 413; Hermes config.yaml still pointed at 9router

### Symptom

After the previous apply, a short Zalo ping still compacted/413'd. Hermes logs showed `base_url=http://9router:20128/v1` even though the container env was model-router.

### Root cause

Shared `/data/assistant/config.yaml` `model.base_url` overrides `OPENAI_BASE_URL`. 9router mapped `hermes` to `gpt-oss-120b` which rejects the tool-heavy payload.

### Fix

Hermes `POST /send` shared the aiohttp session with `GET /events`, so the reply often failed with Server disconnected (~30s after inject). Outbound `_post` now uses its own short-lived session.

### Prevent recurrence

Do not treat compose env as the Hermes LLM URL when `config.yaml` also sets `base_url`.

## 2026-08-19 16:40 +07 â€” Zalo ping waited on compaction then 413 leak

### Symptom

A short Zalo message waited more than 15s. The user received Hermes compaction / HTTP 413 / session auto-reset text instead of a greeting.

### Root cause

The same Zalo thread reused a huge Hermes `sessions/sessions.json` (Valkey `conversation_active` was empty). Hermes compacted; 9router (Hermes was calling it directly, not model-router) returned 413 from `gpt-oss-120b`. Outbound classify fail-opens to send, so protocol chatter reached Zalo. 9router 429 retries also added seconds.

### Fix

Drop known protocol markers from `ux.json` before classify. Cap Valkey history (`SESSION_MAX_MESSAGES=16`). Delete replica `sessions/sessions.json`. Recreate Hermes so chat uses model-router. Recreate session and reset-all. Overlay `messages/` onto the shared data dir.

### Prevent recurrence

Do not let one social thread accumulate unbounded turns. Protocol status lines stay in editable config, not adapter keyword tables.

## 2026-08-19 16:22 +07 â€” leftover lab cache key in classify.json

### Symptom

`prompt_rev` was left in product classify config after the High latency lab.

### Root cause

A Docker layer cache-bust was committed as if it were a product field.

### Fix

Removed `prompt_rev`. Rule 41 now in AGENT_RULES / test RULES / agent-ops hard gates.

### Prevent recurrence

After a lab run, strip test-only keys before calling the tree production-ready.

## 2026-08-19 16:00 +07 â€” classify stuck on 9router; chat >3s

### Symptom

Simple chat p50 ~14s. Classify timed out on 9router while Omni was enabled for general proxy traffic.

### Root cause

`/v1/classify` always posted to 9router. Nvidia 502 overload blocked Fast Dispatcher. Classify also waited 20s before fail-open.

### Fix

Classify/outbound use the same Omni-first candidate list as chat. Classify timeout 8s.

### Prevent recurrence

Case 17 records classify vs text separately. Omni on High lab for general chat.

## 2026-08-19 15:35 +07 â€” clip capped at 12s; chat waited on classify

### Symptom

Video length was clamped to 12 seconds. Simple Zalo/chat turns waited on classify (90s timeout, 32k max tokens).

### Root cause

Encoder treated a lab-era 12s ceiling as the product max. Classify completion budget was sized like a full chat turn.

### Fix

Caller `seconds` up to 120s. Classify timeout 20s / 1024 tokens / one attempt. Outbound filter 2s then send.

### Prevent recurrence

`video_clip_unit` asserts 45s allowed and 200s capped. Case 17 records classify p50 separately.

---

## 2026-08-19 15:20 +07 â€” video attach invalid param; overlay clip; lab watch loop

### Symptom

Generated mp4 was on disk; Zalo returned `Tham sá»‘ khÃ´ng há»£p lá»‡`. Overlay text ran past the image edge. Case 25 watch reprinted the same fail until the SSH wait expired.

### Root cause

zca-js `sendVideo` needs `videoUrl` + `thumbnailUrl` + duration. `sendMessage` attachments do not fill those fields. Encode used jpeg-range `yuvj420p` and `-an`. Overlay drew full-width strings without wrapping. Watch required `attach_mp4>=1` before break.

### Fix

Remux with AAC/yuv420p. Adapter `send_video` uploads thumb + clip then `/api/sendVideo`. Overlay wrap-to-width. Watch exits after four jobs plus four extra polls.

### Prevent recurrence

`overlay_unit` long-line wrap. Case 25 prints `VIDEO_MISSING` and stops.

---

## 2026-08-19 14:45 +07 â€” replica ImportError + video sent before remux

### Symptom

Hermes replica inbound: `ModuleNotFoundError: gateway_noise`. Case 25 wrote `.zalo.mp4` after Zalo rejected the original mp4.

### Root cause

Hermes loads the adapter as `hermes_plugins.zalo_platform.adapter`; relative imports do not see files in `/opt/data/plugins/zalo`. Autosend attached the encoder mp4 before remux finished.

### Fix

Insert plugin dirs on `sys.path`. Prefer/send remuxed video; remux in the autosend path before `send_video`.

### Prevent recurrence

Rolling apply checks `import classify_client, gateway_noise`. Autosend unit covers `foo.mp4` vs `foo.zalo.mp4`.

---

## 2026-08-19 14:10 +07 â€” interactive chat waited on media; video send invalid param

### Symptom

Hello and simple chat shared the heavy path. Case 25 wrote `.zalo.mp4` but Zalo rejected the attachment. Replica missing `gateway_noise`.

### Root cause

No Fast Dispatcher lane. Video files could go through `send_image`. Replica `plugins/` dirs were stale.

### Fix

LLM classify returns `execution_class`. Async ACK then workflow. Remux mp4 before send; overlay plugins on rolling apply.

### Prevent recurrence

`llm_classify_unit` asserts hello is interactive and media is async. Lab cases 25/28 require `send-attachment path â€¦mp4`.

---

## 2026-08-19 14:05 +07 â€” High lab: video not sent; leftover job schedule; replica plugin ImportError

### Symptom

Case 25 four jobs COMPLETED; `.zalo.mp4` written; Zalo invalid-parameter on attach; no `send-attachment path â€¦mp4`. Leftover 07:00 schedule used `thread_id=â€¦::job::â€¦`. hermes-2 logged `No module named 'gateway_noise'`.

### Root cause

Remux retry did not log a successful mp4 send. Destroy restore reapplied an isolated-job schedule. Replica `plugins/` was an old directory, so `link_shared` skipped new modules.

### Fix

Delete leftover `::job::` schedules before later labs. Overlay shared plugins onto replica dirs in `hermes-replica-entry.sh`. Video send still FAIL for case 25/28 this run.

### Prevent recurrence

Entrypoint plugin overlay. Lab cleanup of `::job::` origins after restore. Do not count leftover mp4 as a send.

---

## 2026-08-19 13:25 +07 â€” workflow_vps schedule POST timed out at 8s

### Symptom

Case 24 VPS probe hung on `POST /v1/schedules` after health/create/plan passed.

### Root cause

Schedule upsert waits for live LLM classify; the probe used an 8s HTTP timeout.

### Fix

`workflow_vps.py` uses a 120s request timeout, matching other live classify labs.

### Prevent recurrence

Do not use short localhost timeouts for classify-backed schedule upserts on a live host.

---

## 2026-08-19 12:30 +07 â€” keyword cite/noise lists; Hermes cron skill stole lá»‹ch

### Symptom

Once-lá»‹ch with â€œkhÃ´ng trÃ­ch dáº«n nguá»“nâ€ was refused as knowledge cite. Gateway noise used a growing English/Vietnamese needle list. Hermes `jobs.json` still held a paraphrased tomorrow 11:25 once.

### Root cause

Application code classified user and outbound text with keyword dictionaries (rule 36). The scheduling skill told Hermes to persist CLI cron jobs, which rewrote numbered tasks into one wrapper prompt.

### Fix

Inbound: `task_hint=knowledge` from LLM classify. Outbound: `POST /v1/outbound`. Bridge errors in editable JSON. Scheduling skill executes due jobs only and does not persist cron.

### Prevent recurrence

`knowledge_cite_unit.py` fails if the once-lá»‹ch fixture is `knowledge`. `gateway_noise_unit.py` uses an injected outbound planner, not production needles.

---

## 2026-08-19 12:15 +07 â€” once-lá»‹ch refused as knowledge cite; tick ran one wrapper job

### Symptom

Zalo 11:22 GMT+7: numbered once-lá»‹ch at 11:24 (greeting, fuel E5/E10, HCMC weather, â€œkhÃ´ng trÃ­ch dáº«n nguá»“nâ€) got `KhÃ´ng tháº¥y kiáº¿n thá»©c khá»›p Â«â€¦Â»`. A 11:25 tick ran **one** English job (â€œSchedule a one-time taskâ€¦ greet and send weather and gasolineâ€¦â€) instead of three tasks.

### Root cause

1. Knowledge-cite intercept matched substring `trÃ­ch dáº«n` anywhere, so ingest listed docs and bypassed Hermes classify (rule 15).
2. Classify sometimes stored the schedule wrapper as a single paraphrased instruction and rounded the clock (`11:24` â†’ `25 11 * * *`). Tick explodes stored `instructions[]` only.

### Fix

Cite intercept: explicit `cite`/`find`/catalog-list commands only. Classify `schedule` or `instructions.length >= 2` skips cite. Prompt: numbered deliverables stay separate, wrapper is cadence/cron only, keep the userâ€™s language, exact clock. Case 29.

### Prevent recurrence

`knowledge_cite_unit.py` fails if the live fixture is treated as cite. Mock classify for that fixture must be `once` + `24 11 * * *` + three instructions.

---

## 2026-08-19 12:10 +07 â€” dispatcher video used; Zalo still rejects mp4 attachments

### Symptom

Manim/pangocairo chatter on Zalo. Case 25 wrote a new mp4 then `send-attachment` failed (invalid parameter).

### Root cause

Hermes invented manim/matplotlib instead of dispatcher. After the skill/job hint it did `POST /v1/video`. zca-js `sendMessage` still rejects these clips. ComfyUI CPU is up as a dispatcher backend, not removed.

### Fix

Dispatcher `/v1/video`, isolated-job dispatcher hint, drop manim lines. Video delivery still needs zca-js `sendVideo` + thumbnail (not sendMessage attachments).

### Prevent recurrence

Case 25 fails without `send-attachment` of a new mp4. Case 26 requires the infographic file sent.

---

## 2026-08-19 10:40 +07 â€” video on disk, requester got nothing; leftover job stole the next image

### Symptom

Case 25 wrote `hcmc_weather.mp4` then Zalo `send-attachment` failed (invalid parameter). The isolated video job stayed active and later sent case 26â€™s infographic. Users saw many mid-generation messages. Images did not match weather/fuel overlay.

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

## 2026-08-19 09:45 +07 â€” need tests that match one infographic sentence

### Symptom

Users ask for one picture (HCMC weather + fuel overlay in Vietnamese). Existing cases were four numbered jobs (25) or image-then-fuel text (16).

### Root cause

Lab coverage did not include that one-task phrasing. Classify could split overlay facts into extra jobs.

### Fix

Cases 26â€“27 + fixtures. Classify system rule: one image/video with overlay facts is one instruction.

### Prevent recurrence

`zalo_weather_fuel_lab.py` fails if live classify is not `PLAN_N 1`.

---

## 2026-08-19 09:20 +07 â€” lá»‹ch created media, plugin â€œokâ€, user still got no file

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

## 2026-08-19 08:55 +07 â€” lá»‹ch media created, user got no file

### Symptom

Schedule jobs completed. Files appeared under `media/out`. Zalo user received text (or nothing extra) and no image/video.

### Root cause

Autosend compared isolated session id `{thread}::job::{id}` to the last inbound dest `{thread}` and skipped. `send_document` could also post the isolated id as `threadId`. Parallel jobs also raced on the newest file claim.

### Fix

Treat isolated and real ids as the same dest. Remap attachments with `real_thread_id`. Bind dest/t0 per job. Skip claimed files and send the next unclaimed one. Include video extensions.

### Prevent recurrence

Case 25 requires `send-attachment` (`MEDIA_SENT`), not only four job-done lines.

---

## 2026-08-19 08:45 +07 â€” Zalo up but zalo-api not treated as required

### Symptom

Host bridge / plugin can be logged in while operators expect zalo-api (allowlists, `!zalo`, admin DM). Rolling compose without profile `zalo` can leave the API behind.

### Root cause

zalo-proxy and zalo-api share profile `zalo`, but health/heal did not require the API container to exist.

### Fix

Proxy `depends_on` zalo-api. stack-watch starts the combo if `zalo-api` is missing. check-high fails when ENABLE_ZALO=1 and the container is absent. Case 25 uses the sole admin DM from `zalo_admin_users.txt`.

### Prevent recurrence

Rule 38. Do not recreate Hermes/Zalo without `--profile zalo`.

---

## 2026-08-19 08:30 +07 â€” case 25 watch saw old completed jobs

### Symptom

Lab upsert stored 4 instructions, but watch showed 4 COMPLETED jobs and zero `[zalo] workflow job done` lines.

### Root cause

Same schedule id fired earlier the same day. Fire reused `{id}:{date}` idempotency and deleted the once row. No new jobs.

### Fix

Once cadence uses `{id}:{timestamp}` idempotency. Lab watch filters workflows created at/after the fire clock.

### Prevent recurrence

Do not treat a COMPLETED workflow from earlier the same day as a new once-fire.

---

## 2026-08-19 08:15 +07 â€” classify timeout stored one fake job

### Symptom

Case 25 upsert stored `PLAN_N 1` / `task_hint unknown` even though a later classify probe returned 4 instructions.

### Root cause

9router ReadTimeout. Classifier still returned `ok: true` with the original blob as the only instruction. Workflow persisted that plan.

### Fix

Retry classify. On LLM failure return `ok: false` and empty instructions. Schedule upsert fails closed (503) instead of saving one merged job. Longer timeout (90s LLM / 100s client).

### Prevent recurrence

Lab fail-fast on `PLAN_N != 4`. Do not treat classify fallback as a successful multi-task plan.

---

## 2026-08-19 07:55 +07 â€” classify empty JSON from reasoning models

### Symptom

`POST /v1/classify` returned one instruction (the whole blob) instead of four numbered tasks.

### Root cause

The default combo model writes JSON in `reasoning_content` and leaves `content` empty. `max_tokens` 256/400 also hit `finish_reason=length`.

### Fix

Read `content` or `reasoning_content`, raise `max_tokens` to 2048, parse the first JSON object from the model text.

### Prevent recurrence

Classify config `max_tokens`/`timeout_s` live in `classify.json`. Probe classify `n` after model-router recreate.

---

## 2026-08-19 07:40 +07 â€” numbered lists classified in app code

### Symptom

Task routing and â€œ1. 2. 3.â€ job splits used regex/keyword/split in gateway, Zalo, and workflow. That drifted from the architect (LLM owns understanding) and broke when phrasing changed.

### Root cause

`plan_instructions`, `looks_like_schedule`, and model-router substring heuristics interpreted user prose in application code.

### Fix

`POST /v1/classify` (LLM JSON). Callers validate cron tokens and enums, persist `context.plan`, execute jobs. No split/join NLU in product code.

### Prevent recurrence

Operator rule 36. New classify behavior needs a prompt/config change, not a new regex.

---

## 2026-08-19 07:10 +07 â€” notify alerted node-exporter while monitor was off

### Symptom

With High + Notify and Grafana/Prometheus off, Zalo received `[WARNING] node-exporter unreachable` (DNS name resolution failure). CPU/RAM/disk alerts were paused even though host metrics were never enabled.

### Root cause

alert-watch always scraped `http://node-exporter:9100`. The prometheus profile (which starts node-exporter) was off. Python defaults also listed optional services (AV, Zalo) that compose may not run.

### Fix

Gate scrapes on `ENABLE_*`. Empty `NODE_EXPORTER_URL` and monitor-off â†’ skip, no alert. Skip optional health targets and DNS failures for disabled hosts. Same filter in stack-exporter.

### Prevent recurrence

Do not default scrape URLs to containers that only exist under optional compose profiles. Pass ENABLE flags into alert-watch/stack-exporter.

---

## 2026-08-18 19:45 +07 â€” lab SSH host and account in product scripts

### Symptom

Committed High deploy helpers defaulted SSH host and login name, so clones of `develop`/`main` contained lab identity.

### Root cause

Product entrypoints used fallback literals instead of requiring `ASSISTANT_SSH_*`. Comment examples repeated the same account. OpenVPN export defaulted the chown user to a named login.

### Fix

Require env/flags with no host or account defaults. Placeholders only (`USER@HOST`, `<user>`). VPS probes stay in gitignored `scripts/temp/`.

### Prevent recurrence

Before merging to `develop` or `main`, grep product trees for IPv4 literals and `ASSISTANT_SSH_HOST` defaults. Do not copy temp-folder credentials into `scripts/main/` or committed `test/`.

---

## 2026-08-18 19:39 +07 â€” stack-watch treated 9router 401 as down

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

## 2026-08-18 19:14 +07 â€” promote v0.5.7 via MR (not developâ†’main)

### Symptom

Need the lá»‹ch/cadence/media-ack work on both integration and production branches without a direct developâ†’main merge.

### Root cause

Repo rule is feature â†’ develop â†’ release/* â†’ main, each via GitHub PR.

### Fix

MR #42 `fix/zalo/workflow-wait-turn` â†’ `develop`, then `release/v0.5.7` cherry-pick â†’ MR #43 â†’ `main`, then sync `main` back into `develop`.

### Prevent recurrence

Do not merge `develop` straight into `main`. Empty leftover lab lá»‹ch before rolling deploy so migrate does not recreate them.

---

## 2026-08-18 18:57 +07 â€” leftover daily lá»‹ch would have been re-imported by migrate

### Symptom

Lab clock-only lá»‹ch kept firing every day. A rolling deploy runs `migrate_jobs_to_workflow.py`, which upserts every `jobs.json` user row back into workflow.

### Root cause

Emptying Postgres schedules alone is not enough if `jobs.json` still holds the 17:24 Hermes cron.

### Fix

Delete workflow schedule rows **and** set `jobs.json` jobs to `[]` before migrate. Confirm `schedules_left=0` and `cron_n=0` after deploy.

### Prevent recurrence

Do not leave lab lá»‹ch enabled. After a lab, delete workflow rows and empty `jobs.json` before the next rolling deploy.

---

## 2026-08-18 18:45 +07 â€” lá»‹ch web-search dumped process text; fuel â€œimagesâ€ with no OCR

### Symptom

Zalo received step chatter (â€œNow I have the Petrolimex pageâ€¦â€, â€œLet me get a Python environment with PILâ€, session-restored, â€œÄÃ£ xongâ€, â€œMÃ¬nh Ä‘ang láº¥y giÃ¡ xÄƒngâ€¦â€). Fuel/weather image jobs still hit `web_extract` on SearXNG. Dispatcher `keys.tavily` was false.

### Root cause

- Tavily key was empty, so extract could not use Tavily and Hermes fell back to SearXNG extract (unsupported).
- Skills told the model to send `ÄÃ£ xong.` / `Done.` after files; adapter also announced that line.
- Clock-only `Ä‘áº·t lá»‹ch lÃºc HH:MM` was stored as a **daily** cron, so leftover lists kept firing.
- Agent narrated scrape/OCR/PIL instead of OCR service + dispatcher image.

### Fix (source)

- Cadence: once / daily / weekly / monthly / yearly; once deletes after fire.
- Remove media done-ack (ux.json, adapter, skills, SOUL).
- web-search: dispatcher extract + OCR on page images; drop process narration on Zalo.

### Prevent recurrence

Clock-only lá»‹ch must not become daily. Image facts on a web page â†’ OCR, then generate â€” never PIL overlay chatter. `keys.tavily` on dispatcher health must be true when WEB_BACKENDS includes tavily.

---

## 2026-08-18 18:28 +07 â€” Traefik 503 during Hermes restart (false deploy fail)

### Symptom

Rolling feature deploy marked Hermesâ†’9router fail because Traefik `/health` returned 503 while replicas had been up only a few seconds.

### Root cause

Traefik still had Hermes backends draining. 9router itself was up (`/` 307, `/v1/models` 401 without a key). A second probe ~1 minute later: Traefik 200, gateway 200, Hermes models 200, Zalo SSE connected.

### Fix

Retry Traefik health after Hermes restart. Overlay repo skills onto replica copies so image-gen updates are live.

### Prevent recurrence

Do not treat a 503 in the first seconds after `docker restart` Hermes as a downed edge. Do not run bare `compose up` (that still strips host ports / scale).

---

## 2026-08-18 18:22 +07 â€” skill updates did not reach Hermes replicas

### Symptom

Repo `image-gen/SKILL.md` was synced, but the live job still used `web_extract` and sent scrape chatter.

### Root cause

Each replica uses a writable **copy** of skills (the bind mount is `:ro`). The entrypoint merged with `cp -n`, so existing `SKILL.md` files were never overwritten.

### Fix

Overlay repo skills onto the replica copy (`cp -a` without `-n`). Keep replica-only skills. Rolling deploy also copies before restart and verifies the no-scrape wording.

### Prevent recurrence

After a skill edit, confirm the replica path `replicas/<id>/skills/<name>/SKILL.md` matches the repo, not only `/opt/assistant/hermes/main/skills`.

---

## 2026-08-18 18:16 +07 â€” lá»‹ch â€œváº½ hÃ¬nhâ€ replied with a release-page scrape, no image

### Symptom

A 4-item lá»‹ch (hello, HCMC weather image, fuel, current weather) sent text like â€œThe latest release is dated 13/8/2026. Let me fetch the page and extract image URLsâ€ and **no image file**.

### Root cause

The image job called `web_extract` (SearXNG cannot extract). Native `image_generation` was off. The model treated â€œváº½ hÃ¬nhâ€ as â€œfind pictures on the webâ€ instead of dispatcher `/v1/image`. Step chatter leaked to Zalo (`media-out` was ignored).

Same run: leftover daily lá»‹ch still enabled; Hermes cron `2864b2a9c2b4` (`no_agent=false`, isolated `::job::` origin) still scheduled for 17:24 tomorrow.

### Fix (source)

- `image-gen` skill: never search/extract image URLs; generate via dispatcher.
- Session-interrupt user line â†’ `ux.json` `session.interrupted`.

### Prevent recurrence

If an image jobâ€™s Hermes log has `web_extract` and no `POST /v1/image`, it is this class of bug. Do not scrape GitHub/news â€œlatest releaseâ€ pages for drawings.

---

## 2026-08-18 18:10 +07 â€” hardcoded Vietnamese â€œÄÃ£ lÆ°u lá»‹châ€ on schedule save

### Symptom

Confirming a lá»‹ch always sent one Vietnamese sentence, even when the user wrote English (or another language).

### Root cause

The adapter hardcoded the announce string in Python.

### Fix

- Copy in `hermes/main/messages/ux.json` â†’ `schedule.saved` as a locale map.
- `ux_copy.reply_lang` picks `vi` / `en` / â€¦ from Unicode script in the user text.
- Env `ZALO_SCHEDULE_SAVED_MSG` forces one string if an operator wants that.

### Prevent recurrence

Do not put user-facing sentences in `adapter.py`. Add locales in `ux.json`. Python fallback must stay **English**.

---

## 2026-08-18 16:50 +07 â€” lab: English four-item lá»‹ch (hello + image + fuel + video)

### Symptom

Need a repeatable lab for one English schedule with **four independent jobs** (hello, HCMC weather image, Vietnamese fuel prices, HCMC weather video). Earlier numbered lá»‹ch often delivered fewer Zalo messages than jobs.

### Root cause

Same engine as the 15:23 / 15:50 misses: numbered items must become **N jobs** and **N deliveries**, not one LLM prompt.

### Fix

- Case `test/cases/25-zalo-special-four.md`.
- Lab upserts the lá»‹ch for the current Zalo login thread a few minutes ahead and watches the plugin for four replies.
- Units: `plan_instructions` splits the English list; ingest keeps the daily English list whole.

### Prevent recurrence

Run case 25 as its **own process**. Do not mix with cases 12â€“14 (quota) in the same runner.

---

## 2026-08-18 16:40 +07 â€” parallel numbered jobs still merged on one Hermes session

### Symptom

Policy required **N jobs, N Zalo replies**. Sequential wait helped, but a same-thread burst still **pending-merged** parallel `handle_message` calls. A four-item list could still collapse to two replies.

### Root cause

Hermes sessions are per chat. Two workers calling `handle_message` on the same `thread_id` share one gateway session, so later jobs look like follow-ups of the first turn.

### Fix

- Numbered Zalo lists (immediate and lá»‹ch) create **independent** jobs (`sequential=false`).
- Worker claims up to `ZALO_WORKFLOW_PARALLEL` (default **4**) at once.
- Each job uses an isolated Hermes session `{thread}::job::{job_id}`. Sends remap to the real thread under a per-thread lock.
- Job waits until **its** session is idle before complete (`ZALO_WORKFLOW_TURN_TIMEOUT_S`).
- Image-gen skill: native Hermes `image_generation` may be off (no cloud key). Always use dispatcher `POST /v1/image`.

### Prevent recurrence

Do not call `handle_message` in parallel on the **same** Hermes session. Isolation is mandatory for parallel Zalo jobs.

---

## 2026-08-18 16:25 +07 â€” policy: numbered list must be N jobs and N deliveries

### Symptom

Operators expected four numbered tasks to produce four Zalo messages. The old â€œone cron payload, one LLM turnâ€ design produced one (or two) combined replies.

### Root cause

A lá»‹ch is only a **clock**. The body is a list of instructions. Delivery must not wait for an aggregator.

### Fix

- Immediate and scheduled numbered lists share the same job engine.
- At tick time: **one job per item**.
- Each job may send its own reply (text and/or file). No aggregator bubble.

### Prevent recurrence

Documented in `architect/workflow/README.md`. If a lab sees â€œ4 jobs, 1 message,â€ treat it as a delivery/session bug, not â€œthe model summarized.â€

---

## 2026-08-18 16:20 +07 â€” sequential schedule jobs completed before Hermes finished the turn

### Symptom

A 4-item lá»‹ch often delivered **only the first one or two** Zalo replies. Later items looked queued then vanished. Overlapping empty turns poisoned the transcript.

### Root cause

Hermes `handle_message` **returns immediately** while the agent keeps running in the background. The Zalo workflow worker marked the job complete after the ~8s late-file grace, then claimed the next item. Those later items became pending follow-ups on the **same** session.

The late-file waiter also marked a part â€œdeliveredâ€ when **no file** was sent, so the next item started on a false signal.

### Fix

- Worker waits until that threadâ€™s gateway session is **idle** (and heartbeats the job lease) before late-file sweep and `complete`.
- Timeout: `ZALO_WORKFLOW_TURN_TIMEOUT_S` (default **420** seconds).
- A timed-out item is still completed-with-error so the rest of the list can run.
- Late-file wait no longer marks delivered when nothing was sent.
- Unit: `test/scripts/workflow_turn_wait_unit.py`.

### Prevent recurrence

Never `complete_job` on a Zalo `execute=hermes` turn until the session is idle or the timeout fires. Do not treat â€œno file after 8sâ€ as success for the next numbered item.

---

## 2026-08-18 15:27 +07 â€” one numbered job exception blocked the rest of the lá»‹ch

### Symptom

Cron at **15:23** (hello + HCMC weather image + fuel prices + current weather) sent **only the first message**. Items 2â€“4 never arrived.

### Root cause

Workflow jobs for a numbered list were **sequential** (job N depends on job Nâˆ’1 completing). The Zalo worker called `fail_job(...)` when `handle_message` threw. Failed jobs do **not** unlock children, so the chain stopped after item 1.

Typical triggers: image-gen / media-out error, 9router stream abort, read-only skills/media, or a timeout inside item 2.

### Fix

- On worker exception: send the short user line `PhiÃªn lÃ m viá»‡c bá»‹ giÃ¡n Ä‘áº¡nâ€¦` (best effort), then `complete_job` with `{ok: false, error: â€¦}` so dependents unlock.
- Fall back to `fail_job` only if complete itself fails.
- File: `hermes/main/plugins/zalo/adapter.py` (`_as_workflow_worker`).

### Prevent recurrence

Sequential lists must treat â€œthis item failedâ€ as **done for dependency purposes**, unless you intentionally want a hard stop. Prefer isolated parallel jobs (16:40 entry) so one crash cannot stall the others.

---

## 2026-08-18 15:07 +07 â€” `deploy_high.py` crashed locally before any remote destroy

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

Inside `rf""" ... """` remote scripts, never write `{var}` unless it is a **local** format field (`{REMOTE}`, `{zalo}`, â€¦). Remote Python braces must be doubled (`{{` / `}}`) or avoided.

---

## 2026-08-18 15:05 +07 â€” Hermes cron â€œreadonly databaseâ€ + skills copy `[Errno 30]`

### Symptom

- Hermes cron could not `INSERT INTO executions` â†’ `sqlite3.OperationalError: attempt to write a readonly database`.
- Replica startup: `Failed to copy â€¦ [Errno 30] Read-only file system: '.../replicas/<id>/skills/creative'`.
- Scheduled image jobs could not write `media/out`.
- User-facing: lá»‹ch confirmed, then no dispatch / no media.

### Root cause

1. **`executions.db`** on the shared cron dir was owned by **root** `644`. The scheduler runs as Hermes uid **1000**.
2. **`replicas/<id>/skills`** was a **symlink** to `/opt/data/skills`, which is a **`:ro` bind mount** from the repo. Writes follow the symlink â†’ read-only FS.
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
- Compose warnings â€œrefusing chown through symlinked pathâ€ are a hint this class of bug is back.

---

## 2026-08-18 15:00 +07 â€” 9router `ResponseAborted` / Zalo `[response interrupted]`

### Symptom

Zalo showed `[response interrupted]` even when schedule **detection** succeeded (`ÄÃ£ lÆ°u lá»‹ch`). 9router logs: many `DISCONNECT: ResponseAborted` on free OpenCode models (5â€“13s each), then fallback to the next model.

### Root cause

Hermes **client** aborts the stream and tries the next combo member. That is the designed fallback loop. When **all** members abort, the user sees interrupt copy.

Contributing factors:

- User sending a new message before the previous turn finished (busy/interrupt path).
- Upstream free-model latency / provider drops (not a local 9router crash; process stayed `running`, restart count 0).
- Parallel numbered jobs colliding on one session (see 16:20 / 16:40).

This is **not** the same bug as â€œcron did not tick.â€ Workflow logs still showed jobs created.

### Fix

- Restart 9router only to clear stale sockets (does not fix provider aborts).
- Isolate jobs + wait for turn idle so Hermes does not abort because a second job started mid-stream.
- Do not treat 9router UI `/health` 404 as down; `/` 307 and `/v1/models` 401 still mean the process is up.

### Prevent recurrence

If interrupt copy appears **and** `workflow job done` is missing, inspect session isolation first. If jobs complete but the model stream dies, it is upstream quota/latency â€” recreate router keys when the lab hits quota (cases 12â€“14).

---

## 2026-08-18 13:55 +07 â€” daily lá»‹ch at 13:54 GMT+7 did not fire the same minute it was saved

### Symptom

User saved `13:54 GMT+7` at about `13:54:20`. Confirmation returned, but **todayâ€™s** run never happened. Next fire jumped to **tomorrow**.

### Root cause

`next_daily_cron` used `if candidate <= local: +1 day`. Same-minute create is already â€œpastâ€ by a few seconds, so `next_run_at` skipped today.

A second bug: `claim(execute=â€¦)` returned empty when the **first** dequeued job had a different execute type, so Zalo `hermes` and Hermes `hermes_http` **starved** each other on one Valkey list.

A third bug: clock extract preferred `6:00 AM` **inside item 1** of the payload over `lÃºc 13:54`.

### Fix

- `next_daily_cron(..., grace_s=120)`: if now is 0â€“120s after the clock, keep **today**.
- Re-upsert of the same clock keeps a **past** `next_run_at` so catch-up still fires.
- Ticker catch-up: if `next_run_at` already jumped to tomorrow and today has not fired, still fire todayâ€™s slot (within grace).
- `claim`: skip non-matching execute types and re-enqueue; do not return empty.
- Clock extract prefers `lÃºc` / `at` / `vÃ o` + `HH:MM`.

### Prevent recurrence

Units in `workflow_schedule_concurrency_unit.py` and `workflow_unit.py` (`test_same_minute_grace_1354`). Never take the first `HH:MM` in the body as the schedule clock.

---

## 2026-08-18 13:10 +07 â€” multi-request and cron depended on one LLM turn

### Symptom

A numbered list in one Zalo bubble (or one lá»‹ch payload) was one Hermes prompt. The model typically answered **only the last item** (fuel) or **only the first**. Restart/crash lost in-flight work.

### Root cause

No durable job graph. Cron in Hermes `jobs.json` ran **one agent prompt**. Immediate lists were split in-process only.

### Fix

- New **workflow** service (`:8108`): Postgres canonical state, Valkey delivery, outbox, leases, idempotency.
- At ingest: schedule-shaped text stays **one schedule**. At **tick**: explode into jobs (`plan_instructions`).
- Hermes user lá»‹ch is `no_agent` so the old ticker does not double-run the same prompt.
- Zalo adapter submits compound lists and schedule text; workers claim `execute=hermes`.

### Prevent recurrence

Do not add new â€œone prompt does the whole listâ€ paths. Lists go through workflow jobs.

---

## 2026-08-18 12:45 +07 â€” one-line `1. 2. 3.` only ran the last item

### Symptom

`Thá»±c hiá»‡n: 1. â€¦ 2. â€¦ 3. â€¦` flattened onto one line by Zalo. Only the last item (xÄƒng) ran.

### Root cause

Splitter only matched **line-start** indexes (`^1.`), not inline `1. â€¦ 2. â€¦`.

### Fix

- `_inline_numbered_bodies` in `multi_request.py`.
- Wrap each part: â€œchá»‰ lÃ m Ä‘Ãºng viá»‡c nÃ y.â€ Unique part message ids (`:part2`, â€¦).

### Prevent recurrence

Unit fixture: newline list **and** one-line list in `multi_request_unit.py`.

---

## 2026-08-18 12:40 +07 â€” `--timer` vs `--time`; list showed raw cron objects

### Symptom

`--timer 12:35` was ignored or treated unlike `--time`. Admin list dumped a Hermes schedule dict instead of `name @ HH:MM`. A payload that was only `timer HH:MM` was stored as if it were a real task.

### Fix

- `--timer` alias of `--time`.
- Human label `buoi-sang-hcm @ 12:35`.
- Clock-only prompt is not a task; hint to set ná»™i dung with `update â€¦ :`.
- Clock change clears `next_run_at` so Hermes recomputes.

---

## 2026-08-18 12:05 +07 â€” compound autosend window too short; `jobs.json` unreadable by Hermes

### Symptom

Image arrived after text send; next compound part started too early or waited 180s. Hermes ticker could not update `last_run` because zalo-api wrote `jobs.json` as **root `0600`**.

### Fix

- Autosend window = **whole compound sequence**.
- After each turn, short late sweep for a file that landed as the model finished.
- `jobs.json` `0664`, owner uid 1000. Replica empty file also `0664`.

### Prevent recurrence

After any zalo-api write of cron files, assert mode and uid (deploy scripts already chmod/chown).

---

## 2026-08-18 11:20 +07 â€” `háº±ng ngÃ y` list split into parallel crons; colon update dropped the numbered body

### Symptom

`háº±ng ngÃ y` + `06:00 GMT+7` numbered list became **several** schedules at the same clock â†’ busy-interrupt and dropped items. `!zalo schedule update TÃªn : 1. â€¦ 2. â€¦` did not keep the list whole.

### Fix

- Keep-whole markers include `háº±ng ngÃ y`, `thá»©c dáº­y`, `GMT+7`, `Ä‘áº·t lá»‹ch`, â€¦
- Numbered list + clock hint also stays one lá»‹ch even if a spelling is missing.
- Update parser: index / name / `:` / `--` payload.
- `deliver: origin` so results go to the chat that asked.

---

## 2026-08-18 10:45 +07 â€” destroy profile wiped lá»‹ch

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

Never store durable lá»‹ch only under `replicas/<id>/`. Always snapshot cron before destroy. Verify `HERMES_JOBS_AFTER` â‰  empty when `HERMES_JOBS_BEFORE` > 0.

---

## 2026-08-18 10:15 +07 â€” Notify alerts logged `zalo: false` with no thread env

### Symptom

`ENABLE_NOTIFY=1` and a sole Zalo admin existed, but alerts never reached Zalo unless `NOTIFY_ZALO_THREAD` was set.

### Fix

Dest order: request thread â†’ optional `NOTIFY_ZALO_THREAD` â†’ admin file â†’ `ZALO_ADMIN_USERS`. Re-read the admin file on each send.

---

## 2026-08-18 09:34 +07 â€” inbound FIFO default cap 20 flooded threads

### Symptom

Busy threads queued too many deferred rate-limit / compound parts; users saw long backlog or `queue.full` late.

### Fix

`ZALO_INBOUND_QUEUE_MAX` default **3**. Copy in `ux.json` `queue.*`. Cap is inbound waiting items only â€” outbound still sends as each turn finishes.

### Prevent recurrence

Do not raise the default cap without measuring per-thread Valkey memory and user UX.

---

## 2026-08-18 09:25 +07 â€” zalo-api crash loop missing `schedule_list.py`; Omni off on Low/Medium

### Symptom

After first schedule-list deploy, zalo-api crash-looped. Low/Medium labs had no OmniRouter by default while docs expected it.

### Root cause

Docker image omitted new module. Profile defaults lagged product intent.

### Fix

- Include `schedule_list.py` in zalo-api image.
- `ENABLE_OMNIROUTER` default **1** on Low/Medium; High stays **0** (later product flipped Omni default on everywhere â€” see Aug 20).
- `!zalo schedule list` (alias cron list) filters internal optimize crons.

### Prevent recurrence

New zalo-api modules must be listed in the Dockerfile in the same change.

---

## 2026-08-18 09:10 +07 â€” `ÄÃ£ xong.` between compound parts

### Symptom

Image part sent the file **and** `ÄÃ£ xong.`, then the text part ran. Users thought the sequence was finished.

### Fix

Media-out success line is **deferred until after the last queued part**. Copy: `messages/ux.json` â†’ `media.done`.

---

## 2026-08-18 08:45 +07 â€” overlapping Zalo turns injected busy / interrupt UX

### Symptom

Users saw:

```text
âš¡ Interrupting current task. I'll respond to your message shortly.
ðŸ’¡ First-time tip â€” â€¦ /busy queue â€¦
```

Rate-limited follow-ups were **dropped**.

### Root cause

Upstream Hermes injects interrupt copy when a new turn starts mid-run. Compound `handle_message` without waiting (or several crons at the same clock) triggered it. Rate-limit path discarded the extra message.

### Fix

- Drop busy/interrupt `/busy` copy on Zalo (`gateway_noise.py`).
- Valkey inbound FIFO per thread; drain **one** Hermes turn at a time.
- Rate-limit: tell the user **once**, **keep** the message, process later.
- Cap `ZALO_INBOUND_QUEUE_MAX` (later default **3**).
- Valkey down â†’ fail-open sequential in-process turns.

### Prevent recurrence

Do not start a second `handle_message` on a thread that is still running unless jobs use isolated sessions (16:40).

---

## 2026-08-18 08:25 +07 â€” multi-task cron only ran item 1; busy tip on Zalo

### Symptom

Daily numbered wakeup + image + fuel ran only the first line. Users saw Interrupting / `/busy` tips.

### Root cause

Upstream Hermes injects busy UX on overlapping turns. Parallel crons at the same clock, or unsplit media-out â€œstop after file,â€ dropped later items.

### Fix

- Drop busy/interrupt copy on Zalo (`gateway_noise.py`).
- Schedule-shaped lists stay **one** job (keep-whole); skills complete every item after media.
- Immediate compound waits until part sent before next turn.
- Case `22-zalo-busy-cron-multi`.

### Prevent recurrence

Do not register one cron per numbered line at the same HH:MM. Prefer workflow N jobs (later Aug 18 afternoon).

---

## 2026-08-18 08:10 +07 â€” numbered style `1 váº½` / `2.Sau Ä‘Ã³` plus media-out dropped request 2

### Symptom

Live Zalo: `yÃªu cáº§u:` + `1 váº½â€¦` + `2.Sau Ä‘Ã³ â€¦` ran **image + fuel in one turn**. After the file, media-out â€œone short line, no recapâ€ dropped request 2. This was **not** the summarization skill.

### Fix

Splitter accepts `1 task` / `2.Sau Ä‘Ã³` (indexes 1â€“20, must include 1 and 2). Media-out applies **per turn after split**.

---

## 2026-08-18 07:50 +07 â€” High lab force-enabled Omni/Grafana against profile defaults

### Symptom

`deploy_high.py` always turned on OmniRouter and the full monitor stack; labs disagreed with `profile.sh` defaults.

### Fix

Lab helper no longer force-enables Omni/Grafana/Prometheus/Loki/Alloy (opt-in env). Defaults match `profile.sh` at that time.

### Prevent recurrence

Lab deploy helpers must not override product defaults unless the operator passes explicit flags.

---

## 2026-08-18 07:45 +07 â€” simple chat >5s treated as pass; Grafana optional scrape noise

### Symptom

Lab p95 ~9s still â€œpassed.â€ Monitor targets scraped 9Router HTTP `/health` (404) and Omni when Omni was off.

### Root cause

Latency SLO was soft. Health probes used wrong paths/targets for optional routers.

### Fix

- Case 17: simple host-side chat **> 5s is FAIL** (network latency excluded).
- Case 20: Grafana integration â€” Prometheus jobs + `assistant_service_up`; 9Router via **TCP**; Omni scrape only if on.
- Case 21: 9Router always on at that time; Omni/Grafana default off for High lab helpers.

### Prevent recurrence

Do not raise the SLO to match a slow free-model path. Fix routing/timeouts instead (later rule 43 / outbound 30s).

---

## 2026-08-18 07:35 +07 â€” stack-watch infinite restart after probe fail; compound Zalo not split

### Symptom

Rolling labs 15â€“19: stack-watch could loop restarts. Zalo compound `tin nháº¯n 1` / `tin nháº¯n 2` ran as one turn. User errors dumped `/help` or host paths.

### Root cause

No backoff on heal. Splitter missed mid-sentence labels. Safety policy not wired for Zalo user-facing errors.

### Fix

- stack-watch exponential backoff 90sâ†’3600s; degraded after 5 fails; optional `NOTIFY_URL`.
- Compound split in `multi_request.py`; sequential adapter runs.
- User errors only `PhiÃªn lÃ m viá»‡c bá»‹ giÃ¡n Ä‘oáº¡nâ€¦` (no `/help`, channel dumps, secret scans).
- Cases 15â€“19 + unit/SSH labs.

### Prevent recurrence

Never restart-storm on a single probe fail. Keep user-facing errors short and editable.

---

## 2026-08-18 07:15 +07 â€” daily 06:00 scheduled for tomorrow when created at 05:58

### Symptom

At 05:58 local, â€œdaily 06:00â€ confirmed as **tomorrow**.

### Root cause

Comparison used UTC or already-passed logic without â€œstill ahead today.â€

### Fix

`architect/tools/schedule_tz.py` â€” `next_daily_run(hour, minute)`: if the local clock is still ahead, schedule **today**. Skill `core/scheduling` + zalo-api policy. Later reused by workflow `next_daily_cron` grace.

### Prevent recurrence

Always compare schedule clocks in the userâ€™s IANA zone (default `Asia/Ho_Chi_Minh`), not UTC midnight rules.

---

## Note: 2026-08-12 â€¦ 2026-08-14

No hermes-stack CHANGELOG or ops HISTORY entries for these dates. The clean rebuild that this tree documents starts **2026-08-15 09:45 +07**. Earlier lab history lived outside this repo.

---

## 2026-08-17 17:55 +07 â€” destroy / profile switch without a verified backup

### Symptom

A failed destroy left the lab with no rollback stamp.

### Root cause

Destroy / switch-profile / add-components / update did not require a verified backup first. Lab scripts sometimes used `destroy || true`.

### Fix

`run.sh destroy`, `switch-profile`, `add-components`, and `update` run `backup` then `verify` and **abort** if either fails. Lab deploy scripts must not swallow destroy failure.

### Prevent recurrence

Rule 24 (backup first): never destroy without a verified stamp.

---

## 2026-08-17 17:35 +07 â€” skills lab: every SKILL.md treated as one doc; no embedding key

### Symptom

Medium skills learn indexed almost nothing useful; embedding failed without 9Router embedding credentials. Text-poster path still went through LLM refine.

### Root cause

Learn/scan keyed only on basename `SKILL.md`. Embedding had no local fallback. Exact text posters used diffusion/LLM.

### Fix

- Unique learn keys by relative path; UTF-8 read for markdown.
- Local ONNX `BAAI/bge-small-en-v1.5` embedding fallback (16:50 same day).
- Dispatcher `text-poster` (Pillow) for quoted text / N lines.
- Cases 12â€“14 + `skills_lab.py`.

### Prevent recurrence

Never key knowledge docs only on filename. Exact text â†’ text-poster, not art models.

---

## 2026-08-17 15:05 +07 â€” disabled Notify/AV containers stayed up after profile change

### Symptom

After turning `ENABLE_NOTIFY=0` (or similar), containers kept running. `--remove-orphans` did not remove them.

### Root cause

Compose services started with `--profile` are not orphans when the profile is later omitted. Leftover `hexprefix_*hermes*` names collided on `--force-recreate`.

### Fix

`run.sh up`/`update` explicitly `docker rm` disabled-profile containers. first-setup-llm removes colliding Hermes names. Do **not** pass `--remove-orphans` on a compose set that omits edge YAML (would drop Traefik/Gateway).

### Prevent recurrence

When disabling a profile, remove those containers by name/label â€” do not rely on `--remove-orphans` alone.

---

## 2026-08-17 14:15 +07 â€” sandbox/judge on by default; judge CLEAN allowed malware

### Symptom

High isolation expectations failed: docker.sock on security-manager, public Traefik, LLM judge CLEAN treated as allow.

### Root cause

Defaults were fail-open for sandbox/judge/AV. Judge path could short-circuit allow.

### Fix

- High defaults: sandbox/judge/AV **off**; YARA + size/static remain.
- Judge may only add RISK; CLEAN/skip/errors never allow.
- docker-socket-proxy only with profile `sandbox`; no raw sock on security-manager.
- Traefik default `local` (VPN/localhost).
- Product `.env` wins over leftover `/data/assistant/.env` in stack-watch.

### Prevent recurrence

Never let an LLM CLEAN verdict bypass static/YARA isolation. Keep public ACME opt-in only.

---

## 2026-08-17 12:15 +07 â€” `check-medium.sh` systematically corrupted

### Symptom

Medium smoke / Zalo setup gate failed with paths like `/oev/null` and `oispatcher`.

### Root cause

File had systematic `d`â†’`o` corruption (editor/encoding mishap).

### Fix

Restore `scripts/main/check-medium.sh` from a known-good copy. (Later renamed to worker `check-media` â€” Aug 20.)

### Prevent recurrence

Smoke scripts are gatekeepers â€” verify after any bulk encoding/line-ending pass.

---

## 2026-08-17 12:05 +07 â€” post-ready-learn probed missing Hermes dashboard port on High

### Symptom

HermesÃ—2 has **no** host `:29119`. post-ready-learn and stack-watch treated Hermes as down.

### Fix

When `HERMES_REPLICAS â‰  1`, probe **Traefik / API Gateway** `/health` (root `/` is 404 by design).

---

## 2026-08-17 11:50 +07 â€” gateway open; zalo-api mounted docker.sock; SSRF on scan-url

### Symptom

Unauthenticated gateway, client RL bypass via headers, security-manager could scan arbitrary URLs, zalo-api could restart Hermes via host docker.sock.

### Fix

- Gateway: require `GATEWAY_API_KEYS`; drop header RL bypass; do not trust XFF by default; RL fail-closed.
- security-manager: SSRF-safe scan-url; `SECURITY_FAIL_CLOSED` on High; sandbox via socket-proxy.
- zalo-api: remove docker.sock (host watches restart Hermes).
- Docs: `docs/SECURITY.md`.

### Prevent recurrence

No product service gets raw docker.sock unless explicitly designed (and documented) for it.

---

## 2026-08-17 09:45 +07 â€” zalo-proxy exited but heal skipped

### Symptom

Host bridge `/health` up while `zalo-proxy` container exited â†’ bot silent; watch did not start the proxy.

### Fix

`zalo-watch` starts `zalo-proxy` when the container is exited (not only when SSE miss counters trip).

### Prevent recurrence

Bridge health alone is not enough â€” check proxy container state too (later rule 38: zalo-api + proxy).

---

## 2026-08-17 07:25 +07 â€” `/sethome` spam on first Zalo chat

### Symptom

Every new DM got Hermes â€œðŸ“¬ No home channelâ€¦ /sethomeâ€.

### Fix

Silent auto-claim `ZALO_HOME_CHANNEL` from first allowed DM (`ZALO_AUTO_SETHOME=1` default; DM-only). Set `0` for manual `/sethome`.

### Prevent recurrence

Do not reintroduce home-channel nag in user-facing Zalo copy.

---

## 2026-08-17 07:15 +07 â€” restore dropped Traefik/Gateway/Zalo profiles; SSE 0 after DR

### Symptom

Backupâ†’restore OK but edge/Zalo profiles missing. Pre-restore `sseClients=0`; post-restore still silent until heal.

### Root cause

Restore compose did not pass the same `--profile` flags as `run.sh`. Mem0 leftovers confused memory metrics. Backup included/excluded zalo_owner inconsistently.

### Fix

- Restore compose uses the same profiles as `run.sh`.
- Purge Mem0; session metrics use `conversation_active:*`.
- Backup excludes `zalo_owner*`; restore clears lock + `heal-zalo-sse.sh`.
- stack-watch keeps Hermes scale (see 19:40).

### Prevent recurrence

DR path must mirror live `run.sh` compose files and profiles exactly.

---

## 2026-08-16 20:10 +07 â€” High backup/restore broke on Postgres role and Qdrant snaps

### Symptom

Restore failed DROP/CREATE ROLE for the session user; Qdrant snapshots incomplete; Hermes scale wrong; backup tar included huge `replicas/` / `backups/`.

### Fix

- Restore uses compose (not missing generate/deploy).
- Postgres skips DROP/CREATE ROLE for session user; Qdrant per-collection snaps.
- Hermes scale-aware; exclude `backups/` + `replicas/` from hermes tar.
- Lab stamp verified backup + verify + restore OK with HermesÃ—2.

### Prevent recurrence

Backup excludes must stay in sync with shared cron (later moved out of replicas â€” Aug 18 10:45).

---

## 2026-08-16 19:40 +07 â€” stack-watch collapsed HermesÃ—2 â†’ Ã—1 every ~2 minutes

### Symptom

Dashboard: â€œChat connection interrupted. Reconnectingâ€¦â€. Zalo SSE dropped. Hermes host ports (`:29119` / `:28642`) vanished on a timer.

### Root cause

`stack-watch` ran `docker compose up` **without** hostports/edge overlays and **without** `--scale hermes=$HERMES_REPLICAS`, so every ~2 minutes it stripped scaled Hermes and edge.

### Fix

- `compose up` keeps `--scale hermes=$HERMES_REPLICAS`.
- Skip Grafana probe when monitor is off; skip host `:29119` when replicas â‰  1.
- Default `STACK_WATCH_RESTART_HERMES=0` so probe-fail does not bounce healthy replicas.
- Boot grace + exponential backoff (later 90sâ†’3600s) so a bad probe cannot restart-storm.

### Prevent recurrence

Any host `compose up` from watch/heal **must** pass the same `-f` overlays and `--profile` flags as `run.sh`. Caution in operator rules: full PowerShell deploy can buffer-hang; prefer Python SSH helpers.

---

## 2026-08-16 19:50 +07 â€” two Hermes replicas both attached Zalo SSE

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

## 2026-08-16 11:57 +07 â€” Hermes replica entrypoint ran `gateway` as a binary

### Symptom

Scaled Hermes replicas exited immediately; gateway never listened.

### Root cause

Entrypoint invoked `gateway` as if it were on PATH; Hermes expects `hermes gateway run` (or dispatch).

### Fix

`hermes-replica-entry.sh` runs gateway via the Hermes dispatch/`hermes gateway run` path. Per-replica home under `replicas/<id>` + Zalo singleton election (11:35).

### Prevent recurrence

Replica entry must match the same CLI the primary Hermes image uses.

---

## 2026-08-16 11:25 +07 â€” Traefik could not reach Hermes after scale

### Symptom

API/chat via Traefik failed after HermesÃ—2; direct container health OK.

### Root cause

Hermes API still bound for single-host dashboard path; Traefik service discovery expected the shared compose network bind.

### Fix

Hermes API bind for Traefik after scale; edge stubs (Traefik / API Gateway / OpenVPN) default off. Later High defaults Traefik on (Aug 20).

### Prevent recurrence

Any scale change must re-validate Traefik â†’ `hermes:8642` health, not only host `:29119`.

---

## 2026-08-16 09:30 +07 â€” Mem0 leftovers; coding skills missing on Medium/High

### Symptom

Memory metrics pointed at removed Mem0. Medium/High lacked edge + coding skill packs expected by labs.

### Fix

Remove Mem0; edge on Med/High; ship coding skills. Session metrics use `conversation_active:*` (Aug 17).

### Prevent recurrence

Do not leave dead memory backends in compose or docs after a cutover.

---

## 2026-08-16 08:15 +07 â€” zalo-watch + stack-watch Hermes restart storm

### Symptom

Hours of Hermes restart loops. Zalo SSE never stable.

### Root cause

`zalo-watch` restarted Hermes when `sseClients==0` (miss limit too low). `stack-watch` also bounced Hermes on probe fail / post-boot flicker.

### Fix

- Default `ZALO_WATCH_RESTART_HERMES=0` (bridge-only on sse=0).
- SSE miss â‰¥ 15; cooldown 1800s.
- `STACK_WATCH_RESTART_HERMES=0`; boot grace 600s; heal 9router/dispatcher without thrashing Hermes.

### Prevent recurrence

Default watches to **heal bridge / routers**, not bounce Hermes. Opt-in restart only.

---

## 2026-08-15 16:50 +07 â€” skill learn failed when 9router had no embedding models

### Symptom

Cases 12â€“14: learn/scan produced 0 vectors or quota errors.

### Root cause

Embedding depended on 9Router provider keys. No local fallback.

### Fix

Embedding service uses local ONNX `BAAI/bge-small-en-v1.5` (fastembed) when 9Router has no embedding credentials. Ingest recreates `knowledge_chunks` if vector size changes. If the lab still hits **chat** quota, recreate router keys (operator caution).

### Prevent recurrence

Skill learn must work offline for embeddings even when chat uses free remote models.

---

## 2026-08-15 16:10 +07 â€” office files silently fell back to `.txt`

### Symptom

PDF/DOCX/XLSX requests produced plain text files; Vietnamese PDF glyphs broken.

### Root cause

Dispatcher lacked reportlab/openpyxl/python-docx and DejaVu fonts. Low defaulted `OFFICE_FILE_GEN=0`.

### Fix

Install office deps + `fonts-dejavu-core`; real `.pdf`/`.docx`/`.xlsx` generation. Low still defaults office gen off unless enabled.

### Prevent recurrence

Never ship a silent format downgrade without a user-visible error.

---

## 2026-08-15 14:55 +07 â€” combo round-robin + post-setup left stale provider state

### Symptom

First-setup LLM left wrong default combo / leftover vendor keys; 9Router Default Key not wired to Hermes.

### Root cause

Defaults still pointed at paid/OpenCode naming; post-setup cleanup incomplete.

### Fix

- Default LLM = OpenCode Free combo; rename default 9Router combo to `hermes`.
- Combo round-robin + post-setup cleanup.
- first-setup: Docker install + Default Key â†’ Hermes.
- Low Must: Hermes + 9Router in compose; `run.sh update` after git pull; scripts split `main/` vs `temp/`.

### Prevent recurrence

First-setup must leave a single documented default combo; no orphan provider env.

---

## 2026-08-15 14:20 +07 â€” first Low deploy: disk full blocked Hermes extract

### Symptom

Hermes image extract failed on a small root volume.

### Root cause

Root filesystem too small for image layers; no prune after failed extract.

### Fix

Extend the data LV before extract; prune builder/image after first-setup. See `docs/HARDWARE.md`.

### Prevent recurrence

Check free space / LV size before first Hermes pull (hardware doc gate).

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

Request â€œcreate MR then merge to develop **and** mainâ€ while sitting on `develop` with mixed temp files.

### Root cause

[`docs/GIT.md`](../docs/GIT.md): **never** merge `develop` straight into `main`. Feature/fix â†’ `develop`; `release/*` â†’ `main`. Temp reports / `_tmp_*` probes must not ship.

### Fix

1. Branch `fix/zalo/workflow-schedule-reliability` from current work.
2. Stage product files only (workflow service, Zalo adapter, compose, docs, unit/VPS scripts). Leave `test/reports/**` and `test/scripts/_tmp_*`.
3. Fetch + rebase onto `origin/develop`.
4. PR [#40](https://github.com/7ringuy4n/hermes-stack/pull/40) â†’ merge into `develop`.
5. `release/v0.5.6` from `origin/main`, cherry-pick the fix commit, PR [#41](https://github.com/7ringuy4n/hermes-stack/pull/41) â†’ merge into `main`.
6. Fast-forward local `develop` / `main`; delete local fix/release branches.

### Prevent recurrence

Do not `gh pr create --base main` from `develop`. Do not commit `_tmp_` probes.

---

## Quick index (symptom â†’ section)

| You saw | Go to |
|---------|--------|
| Lá»‹ch saved, no run today (same minute) | 13:55 same-minute grace |
| Lá»‹ch saved, only first Zalo message | 15:27 fail_job; 16:20 turn wait; 16:40 session isolation |
| `[response interrupted]` | 15:00 9router abort |
| `readonly database` / Errno 30 skills | 15:05 permissions |
| `NameError: n` in deploy_high | 15:07 f-string |
| Schedules gone after destroy | 10:45 shared cron |
| Busy / `/busy` tip on Zalo | 08:45 FIFO + noise filter; 08:25 multi-task cron |
| Only last numbered item answered | 12:45 inline split |
| Daily 06:00 â†’ tomorrow at 05:58 | 07:15 schedule_tz today |
| Simple chat >5s still â€œpassâ€ | 07:45 SLO 5s |
| stack-watch restart loop / compound not split | 07:35 backoff + multi_request |
| Inbound queue backlog | 09:34 queue max 3 |
| zalo-api crash `schedule_list` / Omni default | 09:25 image + Omni |
| Lab force Omni/Grafana on | 07:50 deploy_high defaults |
| Destroy without backup stamp | 17 Aug 17:55 |
| Notify/AV still up after disable | 17 Aug 15:05 drop profile containers |
| Judge CLEAN allowed scan | 17 Aug 14:15 isolation |
| `/oev/null` / check-medium broken | 17 Aug 12:15 corruption |
| No `:29119` on HermesÃ—2 | 17 Aug 12:05 Traefik probe |
| Gateway open / docker.sock on zalo-api | 17 Aug 11:50 P0 |
| `/sethome` spam | 17 Aug 07:25 auto-sethome |
| Restore missing Traefik/Zalo; SSE 0 | 17 Aug 07:15 DR profiles |
| Backup DROP ROLE / fat tar | 16 Aug 20:10 |
| Hermes ports vanish every ~2 min | 16 Aug stack-watch scale |
| Dual Zalo SSE / silent bot after restore | 16 Aug Zalo owner lock |
| Replica exits `gateway` not found | 16 Aug 11:57 entrypoint |
| Traefik miss after scale | 16 Aug 11:25 API bind |
| Watch restart storm | 16 Aug 08:15 |
| Skill learn empty / embedding | 15 Aug ONNX fallback |
| PDF silently becomes `.txt` | 15 Aug 16:10 office |
| Wrong default combo after first-setup | 15 Aug 14:55 |
| Disk full on Hermes extract | 15 Aug 14:20 |
| No entries 12â€“14 Aug | note under 18 Aug 07:50 block |

## 2026-09-04 20:52 +07 — topic-specific image composition created future gaps

See `history/2026-09-04/README.md` section “Generic image composition replaces fixed render families”.
## 2026-09-04 21:04 +07 — update guidance referenced a missing helper

See `history/2026-09-04/README.md` section “Production update guidance points to the real entrypoint”.
## 2026-09-05 03:30 +07 — update/watchdog lock and transient secret loading

### Symptom

An update could remove enabled optional services or race the watchdog while
Compose was recreating containers. Secrets scrubbed from disk could also be
missing from the next consumer recreate.

### Root cause

Several update branches recognized only literal `1`, while the supported value
is also `active`. The updater and watchdog had no shared exclusion lock, and
Compose interpolation depended on secrets being written back to repository env.

### Fix and prevention

Use `_env_active` for option decisions, hold the shared stack-maintenance lock
for update, have stack-watch exit when the lock is held, and export OpenBao's
mode-0600 transient file into the current shell before Compose. Recreate the
declared consumers, then scrub both disk locations. Tests must verify rotation
without printing the rotated value.
## 2026-09-05 12:45 +07 — scheduled media reclassified or split at fire

### Symptom

A delayed search-to-image request stored successfully but was classified again,
split into unrelated workflow jobs, or delivered a generated background with
competing labels. A separate half-open SSE connection could report one client
while accepting bridge injections that never reached Hermes.

### Root cause

The scheduler copied its plan only for one concrete map representation. Coarse
classifier hints could override explicit media task types, and the diffusion
prompt still inherited classifier prose about the overlay. SSE reads had no
deadline despite a 15-second bridge heartbeat.

### Fix and prevention

Forward the stored plan as an opaque JSON value, execute schedule fires with the
persisted structural render contract, and let grounded composition author a clean
background brief plus overlay plan. Treat explicit media/image fields as stronger
than broad artifact hints. Keep SSE read timeout at three heartbeat intervals so
half-open connections reconnect. Regression tests cover all four boundaries.
## 2026-09-05 13:47 +07 — priority media skills and single-deliverable office output

Completed the existing Omni media combo shells through classifier and mounted
skills, migrated selected combo strategies without changing member order, and
made visual office assets opt-in with one visible document title. See
`history/2026-09-05/README.md` for root-cause detail and verification gates.

## 2026-09-05 15:30 +07 — rendered office artifact gate

The Zalo visual-document lab now uses the exact configurable fixture, discovers
active dispatcher/Hermes instances, rejects new sibling images, and allows the
long-running office workflow budget. Release evaluation must extract text and
inspect the rendered pages for scope, source time, language, unsupported copy,
overflow, and page balance. Injection immediately after a replica restart is
invalid until the bridge health endpoint reports an active SSE subscriber.
## 2026-09-05 18:10 +07 — Zalo owner failover without replica restart

See `history/2026-09-05/README.md` section “Filesystem Zalo owner election
required replica restarts”.

## 2026-09-05 22:30 +07 — live outage fallback verification

An OmniRoute stop test exposed two silent fallback gaps: numeric enabled values
did not activate local embeddings, and SearXNG infobox-only responses were
dropped. Core services now normalize the documented flag forms and preserve
knowledge-panel search records. Future outage gates must exercise live service
endpoints with OmniRoute stopped.

## 2026-09-05 22:55 +07 — preserve multipart media through Model Router

The generic proxy no longer feeds non-JSON bodies through chat normalization.
Multipart image-edit uploads retain their original bytes and boundary instead
of being replaced by a synthetic stream-only JSON object.

## 2026-09-05 23:25 +07 — print-safe office authoring constraints

Office HTML guidance now keeps factual content in normal flow, rejects risky
overlap/clipping techniques, bounds decorative icons, and requires deliberate
one-page vertical balance plus rendered-output evaluation.

## 2026-09-05 23:40 +07 — office renderers in the media worker

The dispatcher build now includes headless Writer, Calc, and Impress so VPS
release tests can render DOCX, XLSX, and PPTX outputs before assigning a visual
verdict.

## 2026-09-05 23:55 +07 — native Office tables from authored Markdown

The shared Office renderer now strips inline Markdown chrome and converts pipe
tables into native Word and spreadsheet cells. Spreadsheet output also adds a
chart when a table exposes a usable numeric series; tests reject regressions
that leak source markers into delivered documents. Word preserves source block
order and explicitly resets heading indents for reliable LibreOffice rendering.

## 2026-09-06 00:10 +07 — exclude repository-only Office skills at runtime

Hermes replicas no longer register local PDF, Word, or spreadsheet maintenance
toolkits. Removing every root and categorized runtime copy prevents late skill
cloning from recreating ambiguous lookups; chat creation remains on `file-gen`.
