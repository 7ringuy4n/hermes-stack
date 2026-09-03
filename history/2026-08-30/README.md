# 2026-08-30

16 incident(s). Times are UTC+7.

## 08:00 — Drop ComfyUI; route image/OCR/embed via router combos

### Symptom

Stack depended on ComfyUI checkpoints and host API keys (FAL/Flux/Pollinations/dall-e defaults) for image gen; OCR/embed combo names were not first-class.

### Root cause

Media worker pinned `IMAGE_BACKENDS=comfy-cpu,…` and optional paid keys in `.env.example`; skills pointed Hermes at Comfy.

### AI decision

Backfilled from legacy log. At fix time: prioritize durable core change over VPS hotpatch; align classify/skills when intent routing was involved.

### Fix (core)

Dispatcher omni→n9 with `IMAGE_GEN_COMBO=image-gen`; remove Comfy compose services; OCR `vision-ocr`; embed `embedding`; first-setup creates combo shells; refuse music/audio/URL transcripts; skills + classify media policy updated.

### Todo list

- Reproduce
- Fix core
- Regression test
- Verify on lab/VPS

### Prevent recurrence

Never reintroduce ComfyUI or host image vendor keys — operators fill Omni/9Router combo members in the router UI.

## 08:30 — Legacy Comfy aliases and stub skills left behind

### Symptom

Dispatcher still accepted `comfy-cpu` aliases; `comfyui` skill folders and first-setup Qwen/Ollama cleanup helpers remained after the Omni combo cutover.

### Root cause

Incomplete removal after media combo migration.

### AI decision

Backfilled from legacy log. At fix time: prioritize durable core change over VPS hotpatch; align classify/skills when intent routing was involved.

### Fix (core)

Delete Comfy skill trees/workflows/ensure script; simplify `image_backends`; drop first-setup cleanup helpers; inactive media pins `hermes`; OCR Paddle→vision-ocr for all scanned docs.

### Todo list

- Reproduce
- Fix core
- Regression test
- Verify on lab/VPS

### Prevent recurrence

Do not leave disabled stubs for removed engines — delete the code and skills.

## 08:40 — Omni combo shells image-gen / vision-ocr / embedding missing

### Symptom

After media combo cutover, OmniRoute UI only showed `hermes` and `classifier` — dedicated media combos never appeared.

### Root cause

`ensure_combo_shell` POSTed `models: []`; Omni rejects empty combos. `http_json` raised HTTP 400 so the stub retry never ran.

### AI decision

Backfilled from legacy log. At fix time: prioritize durable core change over VPS hotpatch; align classify/skills when intent routing was involved.

### Fix (core)

Create media combo shells with one OpenCode stub member; do not overwrite existing operator-owned members.

### Todo list

- Reproduce
- Fix core
- Regression test
- Verify on lab/VPS

### Prevent recurrence

Never create Omni combos with an empty models list.

## 08:50 — Dispatcher still documented Low profile search; media combos were stubs

### Symptom

Dispatcher README still described Low/Medium/High and `POST /v1/search` on the media worker; media Omni combos had a single stub instead of OpenCode members like hermes.

### Root cause

Stale profile-tier docs after search moved to model-router; media ensure used a one-model shell path.

### AI decision

Backfilled from legacy log. At fix time: prioritize durable core change over VPS hotpatch; align classify/skills when intent routing was involved.

### Fix (core)

Rewrite dispatcher README; office-file comments follow Media worker flags; `ensure_media_combos` uses OpenCode fill (`refill_if_below=3`).

### Todo list

- Reproduce
- Fix core
- Regression test
- Verify on lab/VPS

### Prevent recurrence

Do not document profile Low/Med/High on dispatcher; media combos share the hermes OpenCode ensure path.

## 09:00 — Aerial image fail; bare photo OCR skipped vision-ocr

### Symptom

Scenic image asks returned the media-out failure line; bare photo replies said OCR found no clear text. Combo `image-gen` / `vision-ocr` were not used.

### Root cause

`.env` pinned `IMAGE_GEN_COMBO=hermes` / `OCR_MODEL=hermes` because pin only checked `ENABLE_MEDIA_FILE` (not `WORKER_MEDIA_FILE=active`). `image-gen` members were chat models (not images-capable). Paddle returned glyph noise and short-circuited vision.

### AI decision

Backfilled from legacy log. At fix time: prioritize durable core change over VPS hotpatch; align classify/skills when intent routing was involved.

### Fix (core)

Pin media when worker is active; fill `image-gen` with AI Horde / image-output models and `vision-ocr` with supportsVision models; OCR noise → vision; Omni `IMAGE_OMNI_MODEL` fallback on dispatcher.

### Todo list

- Reproduce
- Fix core
- Regression test
- Verify on lab/VPS

### Prevent recurrence

Never put chat-only models in `image-gen`; never treat Media worker active as inactive for combo pins.

## 09:30 — Media toggles and hardcoded image model/size

### Symptom

Media flags mixed `1`/`true`/`active`; `.env` pinned `IMAGE_GEN_SIZE` and `IMAGE_OMNI_MODEL` so diffusion did not rely solely on type-based combos.

### Root cause

Compat truthy sets and first-setup/dispatcher fallbacks treated single-model and size as env SoT.

### AI decision

Backfilled from legacy log. At fix time: prioritize durable core change over VPS hotpatch; align classify/skills when intent routing was involved.

### Fix (core)

`ENABLE_MEDIA_FILE` / `WORKER_MEDIA_FILE` → `active` only (with legacy migrate); clear obsolete image env keys; dispatcher sends combo name only and optional request `size`; image-gen skill declares default HD `1024x1024`.

### Todo list

- Reproduce
- Fix core
- Regression test
- Verify on lab/VPS

### Prevent recurrence

Never pin a single Omni image model or canvas size in `.env`; never treat media `1` as the canonical on-value.

## 10:15 — Scenic image fail; ENABLE toggles still numeric

### Symptom

Aerial/scenic image asks returned the media-out failure line. Host feature flags still used 1/0. OpenBao retained retired image-vendor secrets; unused search skill trees lingered.

### Root cause

image-gen combo accepted multimodal chat models (Gemini) as image capable because modality checks treated input-image chat as diffusion. Intersection with those members kept a broken combo. Toggle SoT mixed numeric and active.

### AI decision

Backfilled from legacy log. At fix time: prioritize durable core change over VPS hotpatch; align classify/skills when intent routing was involved.

### Fix (core)

Strict diffusion detector + force refill + setup smoke for image-gen; canonical active/inactive migrate in workers/run/env; OpenBao obsolete-key purge; remove unused firecrawl/tavily/searxng skill trees from repo.

### Todo list

- Reproduce
- Fix core
- Regression test
- Verify on lab/VPS

### Prevent recurrence

Never put chat/vision models in image-gen; never leave ENABLE_*=1 as the documented on-value; purge retired secrets on each OpenBao seed.

## 10:30 — Scenic aerial still host-shortcut; prompt not LLM-owned

### Symptom

Scenic/aerial draw asks were owned by a host scene_image shortcut instead of Hermes image-gen, so the diffusion English prompt was not produced by the LLM skill path.

### Root cause

Classify SCENE IMAGE set process_original_message false and the adapter gated scene_image as a host-owned turn.

### AI decision

Backfilled from legacy log. At fix time: prioritize durable core change over VPS hotpatch; align classify/skills when intent routing was involved.

### Fix (core)

Remove scene_image host shortcut/gate; classify scenic-only as Hermes+image-gen with English SCENE: instructions; strengthen image-gen/answering skills accordingly.

### Todo list

- Reproduce
- Fix core
- Regression test
- Verify on lab/VPS

### Prevent recurrence

Never add a separate aerial skill or host shortcut for scenic-only diffusion; keep English SCENE prompts in classify + image-gen.

## 10:50 — Scenic Saigon image returned NSFW censor stub

### Symptom

Aerial cityscape asks using colloquial Saigon returned an image labeled as censored NSFW blocked content.

### Root cause

AI Horde safety filters false-positive on the colloquial place name Saigon even for SFW skyline prompts; official English Ho Chi Minh City does not trigger the stub.

### AI decision

Backfilled from legacy log. At fix time: prioritize durable core change over VPS hotpatch; align classify/skills when intent routing was involved.

### Fix (core)

Classify/image-gen SCENE guidance maps Saigon/Sài Gòn → Ho Chi Minh City for diffusion. Dispatcher sanitizes the same aliases and treats tiny censor placeholders as backend failure (retry/fail).

### Todo list

- Reproduce
- Fix core
- Regression test
- Verify on lab/VPS

### Prevent recurrence

Never put colloquial Saigon alone in diffusion prompts; prefer official English toponyms when safety filters are known to false-positive.

## 18:45 — Scenic aerial example bias; OCR extract-only prompt

### Symptom

Scenic examples pushed “Aerial view … from above” wording. Image OCR used an extract-only markdown prompt that skewed vision answers.

### Root cause

Hardcoded scenic examples and a shared OCR prompt that only asked to extract text as markdown.

### AI decision

Backfilled from legacy log. At fix time: prioritize durable core change over VPS hotpatch; align classify/skills when intent routing was involved.

### Fix (core)

Neutral scenic examples in image-gen/answering/classify; OCR callers and defaults use an analyze-file prompt that still preserves readable text as markdown.

### Todo list

- Reproduce
- Fix core
- Regression test
- Verify on lab/VPS

### Prevent recurrence

Do not hardcode aerial-view stock phrases in scenic examples; keep OCR prompts analysis-first for images.

## 18:55 — Scenic ask still got Comfy-era manim/PIL workflow hint

### Symptom

Scenic image asks still received a Hermes workflow suffix telling the agent to avoid manim/matplotlib/PIL via dispatcher only — leftover Comfy-era framing instead of Omni combo image-gen.

### Root cause

Zalo workflow job runner appended a fixed pre-Omni media hint; classify/image-gen still under-emphasized OmniRouter combo image-gen.

### AI decision

Backfilled from legacy log. At fix time: prioritize durable core change over VPS hotpatch; align classify/skills when intent routing was involved.

### Fix (core)

Replace the workflow suffix and strengthen image-gen/classify so still images use dispatcher → OmniRouter combo image-gen /images/generations.

### Todo list

- Reproduce
- Fix core
- Regression test
- Verify on lab/VPS

### Prevent recurrence

Never reintroduce ComfyUI or local drawing-script hints for scenic diffusion; keep Omni combo image-gen as the SoT path.

## 19:00 — Scenic ask still guided to dispatcher/Comfy-era path

### Symptom

Image-generation asks still followed a dispatcher/Comfy-era Hermes hint instead of OmniRouter combo image-gen /images/generations.

### Root cause

Workflow suffix and image-gen skill centered on dispatcher /v1/image (legacy stack framing).

### AI decision

Backfilled from legacy log. At fix time: prioritize durable core change over VPS hotpatch; align classify/skills when intent routing was involved.

### Fix (core)

image-gen skill, classify media, media-file, and Zalo workflow suffix call OmniRouter /v1/images/generations with model image-gen; Hermes env gets Omni URL/key and IMAGE_GEN_COMBO.

### Todo list

- Reproduce
- Fix core
- Regression test
- Verify on lab/VPS

### Prevent recurrence

Never route scenic diffusion through ComfyUI or local drawing scripts; keep Omni combo image-gen as the still-image SoT.

## 19:20 — Scenic Hermes still guided to dispatcher / manim path

### Symptom

After classify, still-image jobs still pointed at dispatcher `/v1/image` (or inactive-worker `model=hermes`) with legacy manim/matplotlib/PIL framing instead of Omni combo image-gen.

### Root cause

Workflow suffix and skills still treated dispatcher diffusion as the scenic API; inactive-worker policy reused chat combo hermes for stills.

### AI decision

Backfilled from legacy log. At fix time: prioritize durable core change over VPS hotpatch; align classify/skills when intent routing was involved.

### Fix (core)

Always Omni `/images/generations` model `image-gen` for still diffusion; retire dispatcher diffusion (HTTP 410); Pillow-only `/v1/info-card` and `/v1/text-poster`; host weather Omni + `/v1/overlay`. Container classify/websearch path resolution no longer assumes repo parents. Setup refills `image-gen` when chat-only (e.g. OpenCode) members displace AI Horde / Flux. Model-router enable flags accept `active` so classify candidates are not empty after the active/inactive toggle migration.

### Todo list

- Reproduce
- Fix core
- Regression test
- Verify on lab/VPS

### Prevent recurrence

Never reintroduce dispatcher `/v1/image` for scenic diffusion, Comfy/manim/PIL generation hints, or `model=hermes` for still images. Keep `image-gen` members image-capable only. Keep enable-flag parsers accepting `active`.

## 20:10 — Core scripts still wrote ENABLE_*=1|0

### Symptom

After the active/inactive toggle migration, install/resolve, Zalo setup, and security smoke paths still emitted or compared `ENABLE_*=1|0`, so new writes and checks could disagree with migrated `.env` values.

### Root cause

Writers and equality checks were not fully converted when canonical values became `active`/`inactive`.

### AI decision

Backfilled from legacy log. At fix time: prioritize durable core change over VPS hotpatch; align classify/skills when intent routing was involved.

### Fix (core)

`install-component.sh`, setup/restore/Zalo helpers, `stack-watch`, `check-security`, and related comments/docs now set and test `active`/`inactive`. Legacy `1`/`0` remains accepted via migrate/`_env_active`.

### Todo list

- Reproduce
- Fix core
- Regression test
- Verify on lab/VPS

### Prevent recurrence

Never write `ENABLE_*=1|0` from core install/setup paths; use `active`/`inactive` only.

## 20:25 — Backup/security still compared ENABLE_*=1 after migrate

### Symptom

With `.env` toggles already migrated to `active`/`inactive`, backup compose profile selection, security-manager gates, and several host helpers still compared against `1`/`0`, so optional profiles and AV/YARA paths could be skipped incorrectly.

### Root cause

Earlier writer conversion did not cover all readers/checkers in backup, workers, security-manager, OCR/office, and channel helpers.

### AI decision

Backfilled from legacy log. At fix time: prioritize durable core change over VPS hotpatch; align classify/skills when intent routing was involved.

### Fix (core)

Use `_env_active` / explicit `active` membership for ENABLE_* and related toggles across backup.sh, workers.sh, security-manager, model-router defaults, OCR, office_file, and Zalo/log/ovpn scripts; keep legacy `1`/`0` accepted.

### Todo list

- Reproduce
- Fix core
- Regression test
- Verify on lab/VPS

### Prevent recurrence

Any new ENABLE_* check must accept `active` (and migrate writers must emit only `active`/`inactive`).

## 20:55 — Image OCR blocked by AV-down; weather ask silent; cartoon stills

### Symptom

Inbound images for OCR were refused with antivirus-not-ready while ClamAV/av-gateway were down; live weather scene asks could end with no Zalo reply; Omni image-gen stills looked cartoonish.

### Root cause

Zalo AV gate treated `ENABLE_ANTIVIRUS=active` as hard-required even when the gateway was unreachable; antivirus containers were not healed by stack-watch; diffusion prompts/combo members under-emphasized photoreal photography.

### AI decision

Backfilled from legacy log. At fix time: prioritize durable core change over VPS hotpatch; align classify/skills when intent routing was involved.

### Fix (core)

Soft-fail AV when gateway/clamd are down (Security Manager fallback; hard refuse only with `AV_REQUIRED=active`); heal antivirus profile in stack-watch; strengthen weather/scenic classify + image-gen photoreal prompts; exclude cartoon/anime models from image-gen combo fill; raise classify retry.

### Todo list

- Reproduce
- Fix core
- Regression test
- Verify on lab/VPS

### Prevent recurrence

Never equate ENABLE_ANTIVIRUS with AV_REQUIRED; keep photoreal constraints in classify SCENE / image-gen skill; keep antivirus heal when the flag is active.
