# 2026-09-02

23 incident(s). Times are UTC+7.

## 07:30 — router-worker URL; reasoning_effort; labeled weather-on-image

### Symptom

Compound asks (weather update + draw city with facts on image) went silent; short follow-ups ("ê") ignored prior turns; `model-router` hostname lingered after rename to `router-worker`.

### Root cause

1. Search+image plans with two instructions but no `task_details` search marker failed `_plan_has_search` gate.
2. Ultra-short classify bypass treated contextual nudges as fresh hello.
3. Image shortcuts stored empty assistant turns — session hydrate had no assistant history.
4. Info-card path blocked the event loop without ack.

### AI decision

Backfilled from legacy log. At fix time: prioritize durable core change over VPS hotpatch; align classify/skills when intent routing was involved.

### Fix (core)

`router-worker` URL defaults; classify `reasoning_effort`; prompt hardening for labeled weather-on-image and prior-turn recap; `_plan_has_search` contract detection; info-card asyncio + ack; session `append_turn` records image delivery.

### Todo list

- Reproduce
- Fix core
- Regression test
- Verify on lab/VPS

### Prevent recurrence

Search+labeled-scene combos must pass host gate without `task_details` alone; never store blank assistant turns after delivered images.

## 08:45 — first-setup: Pollinations Flux image head; drop setup smokes

### Symptom

`first-setup-omnirouter` aborted on VPS when AI Horde head diffusion exceeded setup timeout; `IMAGE_GEN_HEAD_MEMBER` pinned slow Horde instead of free Flux.

### Root cause

Setup smoke-tested `/images/generations` against the ranked head (AI Horde ICBINP when no AI Box); Horde workers routinely exceed any sane first-setup timeout.

### AI decision

Backfilled from legacy log. At fix time: prioritize durable core change over VPS hotpatch; align classify/skills when intent routing was involved.

### Fix (core)

Pollinations provider is created when missing (`POLLINATIONS_API_KEY` or anonymous placeholder); Flux slug is ranked first and pinned as `IMAGE_GEN_HEAD_MEMBER`. Pollinations chat/community paths are excluded from image combo membership. Setup smoke probes removed.

### Todo list

- Reproduce
- Fix core
- Regression test
- Verify on lab/VPS

### Prevent recurrence

Do not hard-fail first-setup on free diffusion latency; pin a fast free Flux head instead of Horde for scenic delivery.

## 09:00 — first-setup: catalog-only media combos; drop vendor hardcoding

### Symptom

First-setup carried AI Box whitelists, Horde/namespace filters, obsolete env scrubbing, and remapped image/vision routes to `hermes` when media worker was inactive.

### Root cause

Setup script duplicated operator concerns (vendor model lists, combo member surgery) that belong in Omni UI or runtime, not first-run wiring.

### AI decision

Backfilled from legacy log. At fix time: prioritize durable core change over VPS hotpatch; align classify/skills when intent routing was involved.

### Fix (core)

Media combos seed from `/v1/models` image/vision/embed signals only when empty; `pin_media_combos` pins combo names when media is active without hermes fallback; removed `ensure_aibox_image_models` and related hardcoded filters.

### Todo list

- Reproduce
- Fix core
- Regression test
- Verify on lab/VPS

### Prevent recurrence

First-setup wires providers and empty combos — never maintain vendor-specific model allowlists in setup code.

## 09:15 — vision-ocr combo: priority (fallback) strategy

### Symptom

Vision OCR combo used global round-robin, rotating across multimodal members instead of exhausting the ranked head before failover.

### Root cause

`ensure_media_combos` did not pass a per-combo strategy for `vision-ocr`; only chat combos inherited `OMNIROUTER_COMBO_STRATEGY=round-robin`.

### AI decision

Backfilled from legacy log. At fix time: prioritize durable core change over VPS hotpatch; align classify/skills when intent routing was involved.

### Fix (core)

`VISION_OCR_COMBO_STRATEGY=priority` (env `OMNIROUTER_VISION_OCR_COMBO_STRATEGY`); `_put_or_create_combo` preserves member order when fixing strategy on an existing combo.

### Todo list

- Reproduce
- Fix core
- Regression test
- Verify on lab/VPS

### Prevent recurrence

Media combos that need head-first failover must declare their own strategy constant, not rely on the global round-robin default.

## 09:30 — combo priority failover: classifier, embedding, web-search

### Symptom

Classifier, embedding, and web-search combos inherited global round-robin; `web-search` combo was missing on fresh installs so Router search had no Omni failover chain.

### Root cause

Only image-gen had an explicit per-combo strategy; web-search creation was deferred to manual Omni UI.

### AI decision

Backfilled from legacy log. At fix time: prioritize durable core change over VPS hotpatch; align classify/skills when intent routing was involved.

### Fix (core)

`FALLBACK_COMBO_STRATEGY=priority` for classifier, embedding, vision-ocr, image-gen, and web-search; `ensure_web_search_omni_combo` seeds Tavily -> Firecrawl -> SearXNG when empty.

### Todo list

- Reproduce
- Fix core
- Regression test
- Verify on lab/VPS

### Prevent recurrence

Any stack combo that must exhaust a ranked head before failover needs an explicit priority strategy in first-setup, not the global round-robin default.

## 09:45 — setup-zalo: headless Node.js install (no apt hang)

### Symptom

`setup-zalo.sh` stopped after "core ready for QR" on fresh VPS; `apt install` stuck in stopped state (`T+`); no QR because Node was never installed.

### Root cause

`zalo_need_node` ran NodeSource `setup_20.x` via curl|bash, which spawned nested apt jobs that hung on headless SSH when debconf/readline waited on a background TTY.

### AI decision

Backfilled from legacy log. At fix time: prioritize durable core change over VPS hotpatch; align classify/skills when intent routing was involved.

### Fix (core)

Direct NodeSource apt repo add + `DEBIAN_FRONTEND=noninteractive` install; `zalo_wait_apt_lock`; Node preflight in `setup-zalo` before QR phase; clearer QR browser instructions.

### Todo list

- Reproduce
- Fix core
- Regression test
- Verify on lab/VPS

### Prevent recurrence

Never pipe NodeSource setup scripts into bash on headless VPS; use explicit apt repo + noninteractive flags and apt-lock waits for any setup-zalo package installs.

## 10:00 — setup-zalo: print Zalo QR in terminal

### Symptom

`setup-zalo` waited silently after npm install; users expected a scannable QR in the SSH console, not only `http://127.0.0.1:8787/qr.png`.

### Root cause

`hermes-zalo-plugin login` ran in the background with stderr discarded; upstream only renders ASCII QR when stdout is a TTY. The systemd bridge also logs QR to a file path, not the terminal.

### AI decision

Backfilled from legacy log. At fix time: prioritize durable core change over VPS hotpatch; align classify/skills when intent routing was involved.

### Fix (core)

Stop the bridge, run login CLI in the foreground (TTY), then restart bridge and verify `/health`.

### Todo list

- Reproduce
- Fix core
- Regression test
- Verify on lab/VPS

### Prevent recurrence

Do not background Zalo login helpers during setup; interactive QR requires a foreground process attached to the user's terminal.

## 10:15 — setup-zalo: show QR/logs during health capture

### Symptom

After `core ready for QR`, setup-zalo printed nothing — no logs, no ASCII QR — until timeout or Ctrl+C.

### Root cause

`setup-zalo` captures stdout via `health_json="$(zalo_qr_login_phase)"`, swallowing all `zalo_log` output and login CLI QR. Inside `$(...)`, `[[ -t 1 ]]` is false so console QR path was skipped.

### AI decision

Backfilled from legacy log. At fix time: prioritize durable core change over VPS hotpatch; align classify/skills when intent routing was involved.

### Fix (core)

`zalo_log` → stderr; QR instructions → stderr; detect TTY via `/dev/tty`; run `hermes-zalo-plugin login` with stdin/stdout on `/dev/tty`.

### Todo list

- Reproduce
- Fix core
- Regression test
- Verify on lab/VPS

### Prevent recurrence

Functions whose stdout is machine-readable JSON must log and render UI on stderr or `/dev/tty`, not stdout.

## 10:45 — first-setup: image-gen from catalog metadata only

### Symptom

`image-gen` combo routed chat models to `/images/generations` (401/empty); some members were chat-only under image-looking ids.

### Root cause

First-setup used hardcoded provider prefixes and model-name whitelists that drift when Omni renames namespaces.

### AI decision

Backfilled from legacy log. At fix time: prioritize durable core change over VPS hotpatch; align classify/skills when intent routing was involved.

### Fix (core)

Select and rank image-gen members from catalog `supportedEndpoints` / `apiFormat` / `type` / `capabilities`; register/repair provider custom models via `images-generations` provider-nodes only.

### Todo list

- Reproduce
- Fix core
- Regression test
- Verify on lab/VPS

### Prevent recurrence

Never gate image-gen on id prefixes or fixed model lists; use Omni catalog fields and provider-node `apiType`.

## 11:00 — first-setup: vision-ocr rejects blind supportsVision models

### Symptom

Vision OCR returned garbage ("crn ae maa") — model replied "I don't see any image attached" despite image in request.

### Root cause

`vision-ocr` combo included OpenCode models with `supportsVision` but no image-input modality (e.g. qwen3.7-plus).

### AI decision

Backfilled from legacy log. At fix time: prioritize durable core change over VPS hotpatch; align classify/skills when intent routing was involved.

### Fix (core)

Filter vision-ocr members by catalog image-input capability; refill combo when blind members present.

### Todo list

- Reproduce
- Fix core
- Regression test
- Verify on lab/VPS

### Prevent recurrence

Do not trust `supportsVision` alone for vision-ocr; require image-input modality or explicit vision capability.

## 11:30 — Zalo: quote local image path + weather-on-image silent turns

### Symptom

(1) Quote-reply with embedded image path + đọc hình → no Zalo response. (2) Weather update + draw HCMC with weather text on image → no response.

### Root cause

Quote media extraction only accepted HTTP URLs; local `/opt/data/media/...` paths in quoted bot text were ignored. Workflow submit returned True after a no-op media shortcut, swallowing the turn. Weather+labeled-image asks without `RENDER:` marker missed the info-card host gate.

### AI decision

Backfilled from legacy log. At fix time: prioritize durable core change over VPS hotpatch; align classify/skills when intent routing was involved.

### Fix (core)

Resolve local media paths from quote payloads; `_download_media` uses existing staged files. Return shortcut consumed status; announce workflow start. Classify parts + host gate for labeled weather-on-image.

### Todo list

- Reproduce
- Fix core
- Regression test
- Verify on lab/VPS

### Prevent recurrence

Quote media must accept shared-volume paths; never return True from workflow submit unless the turn was consumed or dispatched.

## 11:45 — Zalo: search+image workflow split + image-gen single-provider fail

### Symptom

Compound weather+image ask delivered a generic Hermes greeting plus a scenic image without weather labels; image-gen logged Pollinations 401; quote-image vision returned garbage.

### Root cause

Classify search+image plans expose two `instructions[]` entries — workflow treated them as separate async jobs (Hermes chat + diffusion). Host diffusion called only `IMAGE_GEN_HEAD_MEMBER` (Pollinations) with no combo failover. Pollinations without API key still appeared in image-gen catalog head selection.

### AI decision

Backfilled from legacy log. At fix time: prioritize durable core change over VPS hotpatch; align classify/skills when intent routing was involved.

### Fix (core)

`plan_is_search_then_image_turn` blocks workflow FIFO split; adapter routes unified search+image to host media shortcut. Diffusion tries combo `image-gen` then head member. first-setup skips Pollinations image members when unkeyed; repairs API key ACL when stack combos drop.

### Todo list

- Reproduce
- Fix core
- Regression test
- Verify on lab/VPS

### Prevent recurrence

Dual-instruction search+image plans must never enqueue separate Hermes workflow jobs; image-gen must use combo failover, not a single pinned provider.

## 16:45 — image-gen: Omni provider-models sync; combo-only diffusion

### Symptom

Omni `image-gen` combo listed custom-provider models (e.g. `ai-box/qwen-image-2.0`) but `/v1/images/generations` returned `No images-capable targets in combo "image-gen"`. Host diffusion fell back to slow Horde head; Zalo showed "Đang vẽ hình…" before scenic delivery.

### Root cause

Combo members used catalog ids without matching `provider-models` on an `images-generations` provider node. Chat-only provider nodes (`apiType=chat`) do not route `/images/generations`. Legacy `IMAGE_GEN_HEAD_MEMBER` bypassed combo failover.

### AI decision

Backfilled from legacy log. At fix time: prioritize durable core change over VPS hotpatch; align classify/skills when intent routing was involved.

### Fix (core)

`ensure_images_generations_nodes` uses Omni provider-nodes API (chat → images-generations sibling). `ensure_provider_image_models` syncs from `/api/providers/{id}/models` onto images-generations provider-models. Combo members = wired prefix/model ids only. Host diffusion uses combo `image-gen` only. Obsolete env keys cleared via session temp script — not in first-setup.

### Todo list

- Reproduce
- Fix core
- Regression test
- Verify on lab/VPS

### Prevent recurrence

Custom image providers must be wired through OmniRoute provider-nodes + provider-models; do not parse provider prefixes in setup scripts. Do not embed obsolete env key cleanup in durable setup scripts.

## 17:15 — image-gen: custom provider wiring + host combo failover

### Symptom

Direct `prefix/model` image routes worked; `model=image-gen` returned `No images-capable targets` for custom providers (e.g. ai-box).

### Root cause

Omni `executeImageCombo` filters targets via built-in image registry only — custom `provider-models` are invisible to combo execution. Prefix/model routing resolves via provider-nodes to the chat provider node id.

model=image-gen still returns No images-capable targets because Omni’s executeImageCombo only accepts targets in the built-in image registry — custom provider-models are ignored (OmniRoute v3.8.50).

### AI decision

Backfilled from legacy log. At fix time: prioritize durable core change over VPS hotpatch; align classify/skills when intent routing was involved.

### Fix (core)

`first-setup-omnirouter`: `POST sync-models`, register provider-models on prefix-resolved provider node from admin/`/v1/combos` image-gen members. Host diffusion (`media_shortcuts`) fails over to `/v1/combos` members as direct routes when combo name fails.

Register provider-models on _prefix_resolved_provider_node_id() from provider-nodes API (same rule as Omni’s imageRouteModel.ts)

### Todo list

- Reproduce
- Fix core
- Regression test
- Verify on lab/VPS

### Prevent recurrence

Do not parse provider prefixes in setup scripts; use provider-nodes + provider-models + combo APIs. Do not rely on Omni combo name alone for custom image providers until image-combo supports custom registry entries.

## 17:45 — zalo: image-gen failover helper had broken signature

### Symptom

Zalo inbound message (scenic/image shortcut) got no reply; Hermes logged `SyntaxError: '(' was never closed` importing `media_shortcuts`, so the host turn threw before classification/execution.

### Root cause

Failover refactor left `_omni_request_image_blob_once` with an unterminated `def (` signature; module import failed on every inbound message, aborting the whole media shortcut path.

### AI decision

Backfilled from legacy log. At fix time: prioritize durable core change over VPS hotpatch; align classify/skills when intent routing was involved.

### Fix (core)

Restored the complete keyword-only signature on `_omni_request_image_blob_once`. Added regression tests asserting combo→member failover order and `/v1/combos` member parsing.

### Todo list

- Reproduce
- Fix core
- Regression test
- Verify on lab/VPS

### Prevent recurrence

Keep image-gen helpers import-safe; unit tests import the module (which fails fast on syntax errors) and cover the failover call order.

## 19:15 — zalo: image-gen 5m timeout; Hermes image path; schedule ack

### Symptom

Combo image-gen member attempts timed out around 60s; captioned image analyze hit OCR-worker vision-ocr (Omni queue saturation) instead of Hermes multimodal; relative remind schedule stored/fired but user saw no saved ack or fire text when a prior turn had delivered media.

### Root cause

Default host diffusion timeout was below operator budget; captioned images always ran OCR worker (vision combo) before Hermes; `_as_job_file_sent` muted later text sends including schedule ack/fire in the same thread.

### AI decision

Backfilled from legacy log. At fix time: prioritize durable core change over VPS hotpatch; align classify/skills when intent routing was involved.

### Fix (core)

Pin/default `OMNI_IMAGE_GEN_TIMEOUT_S=300` in first-setup and host diffusion. Skip OCR worker for captioned images; empty bare-image OCR prompt routes Hermes multimodal. Clear job-file-sent mute on new inbound; exempt schedule/gate sends from post-media text drop. Harden classify schedule/media parts.

### Todo list

- Reproduce
- Fix core
- Regression test
- Verify on lab/VPS

### Prevent recurrence

Unit tests for 300s timeout default, once_after remind body timing, and existing combo failover import safety.

## 19:45 — zalo: classify strips attachment recall for schedule

### Symptom

Relative remind schedule (`N phút nữa nhắc tôi: …`) stored 0 rows when thread memory had recent attachments; logs showed `attach_followup` without `schedule stored`.

### Root cause

Host injected `[Recent attachments…]` into inbound text before classify; router received the full blob (not user line only), so timed intent was drowned by prior file context.

### AI decision

Backfilled from legacy log. At fix time: prioritize durable core change over VPS hotpatch; align classify/skills when intent routing was involved.

### Fix (core)

`strip_prior_for_classify` drops attachment-recall blocks; classify HTTP payload sends stripped user line. Schedule classify part: recall must not downgrade remind-with-body creates.

### Todo list

- Reproduce
- Fix core
- Regression test
- Verify on lab/VPS

### Prevent recurrence

Unit test locks strip of attachment recall before schedule classify.

## 20:15 — zalo: image analyze Hermes chat (not txt file / OCR garbage)

### Symptom

Captioned image ask (`đây là hình gì`) delivered a `.txt` file whose body was the classify instruction template. Bare image returned OCR garbage (`crn ae maa`) as the only reply.

### Root cause

Classify mis-tagged image analyze as async `file_processing` with `output_type=txt`, so workflow/file-gen wrote instructions as file content. Bare-image host-ack sent raw OCR noise without Hermes multimodal.

### AI decision

Backfilled from legacy log. At fix time: prioritize durable core change over VPS hotpatch; align classify/skills when intent routing was involved.

### Fix (core)

`plan_is_image_analyze_chat` blocks async workflow when an image is attached; coerce plan to interactive Hermes. Disable image host-ack; filter short OCR noise before prompt. Harden classify media part: image analyze never emits file output_type.

### Todo list

- Reproduce
- Fix core
- Regression test
- Verify on lab/VPS

### Prevent recurrence

Unit test for txt misclassify coercion and OCR noise filter.

## 20:45 — model-router: preserve multimodal image parts

### Symptom

Zalo `hình gì đây` + Saigon skyline photo returned hallucinated text (GitHub repo page, cybernetic brain) instead of describing the attached image.

### Root cause

`architect/models/model-router/chat_norm.sanitize_chat_payload` flattened every message to text via `parts_to_text`, dropping `image_url` parts. Hermes `vision_analyze` and combo chat saw only the Vietnamese prompt — models invented content from session prior turns.

### AI decision

Backfilled from legacy log. At fix time: prioritize durable core change over VPS hotpatch; align classify/skills when intent routing was involved.

### Fix (core)

`normalize_message_content` keeps multimodal lists when vision parts are present. Remove erroneous `OCR_URL=127.0.0.1` stack pin; Hermes config: `image_input_mode: native`, `auxiliary.vision` → `vision-ocr` via router-worker. OCR container `OPENAI_BASE_URL` → router-worker.

### Todo list

- Reproduce
- Fix core
- Regression test
- Verify on lab/VPS

### Prevent recurrence

`test/scripts/model_router_chat_norm.py` vision preserve case.

## 21:00 — zalo: image-analyze host reply via OCR vision-ocr

### Symptom

`hình gì đây` + Saigon skyline returned unrelated scenes (dog on sofa, girl in meadow) despite native vision attach and router multimodal fix.

### Root cause

Hermes `hermes` combo still hallucinates on inline vision; probe showed `vision-ocr` via OCR `/v1/ocr` describes skyline correctly.

### AI decision

Backfilled from legacy log. At fix time: prioritize durable core change over VPS hotpatch; align classify/skills when intent routing was involved.

### Fix (core)

`_as_try_image_analyze_vision_reply`: classify `plan_is_image_analyze_chat` → OCR worker with Vietnamese describe prompt → host Zalo reply; bypass Hermes chat turn. Hooked in enqueue + queue drain before `handle_message`.

### Todo list

- Reproduce
- Fix core
- Regression test
- Verify on lab/VPS

### Prevent recurrence

`attachment.image_analyze_vision_*` helpers + unit tests in `image_analyze_chat_unit.py`.

## 21:15 — OCR worker: vision-ocr only (remove paddle/tesseract)

### Symptom

Image describe still wrong or empty: Paddle returned glyph noise and skipped vision; large photos refused or hallucinated on vision-ocr.

### Root cause

Media OCR worker ran pymupdf → PaddleOCR → vision-ocr → tesseract. Paddle short-circuit blocked vision; tesseract added unreliable fallback.

### AI decision

Backfilled from legacy log. At fix time: prioritize durable core change over VPS hotpatch; align classify/skills when intent routing was involved.

### Fix (core)

`architect/tools/ocr/app.py` v2: pymupdf PDF text layer → vision-ocr combo only. Large images downscaled (`OCR_VISION_MAX_PX`). Removed `paddle_engine.py`, tesseract deps, paddle compose env/volume. Skills/classify/media.txt aligned.

### Todo list

- Reproduce
- Fix core
- Regression test
- Verify on lab/VPS

### Prevent recurrence

`test/scripts/vision_ocr_policy_unit.py` locks vision-only app policy.

## 22:00 — Remove OCR worker container entirely

### Symptom

Separate OCR container still ran legacy paddle health on VPS; duplicate hop vs shared vision lib.

### Root cause

OCR worker was retired in code but compose/service/skills still referenced `ocr:8091`.

### AI decision

Backfilled from legacy log. At fix time: prioritize durable core change over VPS hotpatch; align classify/skills when intent routing was involved.

### Fix (core)

Deleted `architect/tools/ocr/`. Ingest/jobs/dispatcher/Zalo call `vision_read` / `vision_read_path`. Removed `ocr` service, `OCR_URL`, `ENABLE_OCR`, monitor health probes, paddle test case.

### Todo list

- Reproduce
- Fix core
- Regression test
- Verify on lab/VPS

### Prevent recurrence

`test/scripts/vision_ocr_policy_unit.py` fails if `architect/tools/ocr` exists.

## 22:40 — router-worker stripped image_url; kimi saw text only

### Symptom

Direct Omni `ai-box/kimi-k3` described the DSLR correctly; same payload via `router-worker` / `vision-ocr` returned “chưa nhận được ảnh” or invented cafe scenes.

### Root cause

Container `chat_norm.sanitize_chat_payload` still flattened every message with `parts_to_text`, dropping `image_url`. Blind text models then hallucinated scenic Vietnamese cafe replies.

### AI decision

Backfilled from legacy log. At fix time: prioritize durable core change over VPS hotpatch; align classify/skills when intent routing was involved.

### Fix (core)

Ship `normalize_message_content` that keeps vision parts; do not force `model=hermes` on vision payloads. Zalo adds structural prompt-echo gate and media path/base64 describe path.

### Todo list

- Reproduce
- Fix core
- Regression test
- Verify on lab/VPS

### Prevent recurrence

`test/scripts/model_router_chat_norm.py` asserts multimodal lists survive sanitize; VPS must rebuild/restart `router-worker` after router code changes (image bake, not Hermes bind-mount alone).
