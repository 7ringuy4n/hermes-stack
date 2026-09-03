# 2026-08-31

12 incident(s). Times are UTC+7.

## 07:10 — image-gen empty; scenic ask refused; search combo naming

### Symptom

Scenic image asks failed with “image-gen has no image-capable targets”; Omni key could block stack combos when `allowedCombos` was empty; web-search combo naming/backends were inconsistent with Tavily→Firecrawl→SearXNG failover.

### Root cause

`image-gen` accepted any `aihorde/*` id including aphrodite chat workers; Omni treats empty `allowedCombos` as deny-all for combo names; web-search SoT still used legacy `websearch` / Omni-only backends.

### AI decision

Backfilled from legacy log. At fix time: prioritize durable core change over VPS hotpatch; align classify/skills when intent routing was involved.

### Fix (core)

Require image modality (reject aphrodite/non-diffusion) when filling `image-gen`; pin API key `allowedCombos` for stack combos; rename/align combo `web-search` with Omni→direct adapter failover and skill docs; refill `embedding` with embed-capable catalog models and smoke `/v1/embeddings`.

### Todo list

- Reproduce
- Fix core
- Regression test
- Verify on lab/VPS

### Prevent recurrence

Never classify AI Horde LLM workers as diffusion; always pin key combo allowlists after creating stack combos; keep web-search backends Omni-first with direct fallbacks.

## 07:40 — Media defaults not OpenCode-first; invented aerial SCENE

### Symptom

Vision/embedding first-setup preferred non-OpenCode providers; scenic classify/examples still steered toward aerial/top-down phrasing even when the user did not ask for that viewpoint.

### Root cause

Capability-matched media fill ranked Gemini/OpenRouter ahead of OpenCode; scenic examples and fixtures reused aerial wording from older weather cases.

### AI decision

Backfilled from legacy log. At fix time: prioritize durable core change over VPS hotpatch; align classify/skills when intent routing was involved.

### Fix (core)

OpenCode-first for vision-ocr and embedding defaults; keep image-gen on diffusion-capable members; classify/image-gen and lab fixtures stop inventing aerial viewpoints; image attachment instructions require scene summary plus text extract.

### Todo list

- Reproduce
- Fix core
- Regression test
- Verify on lab/VPS

### Prevent recurrence

Default combo fills for chat/vision/embed start with OpenCode; only add aerial/top-down SCENE text when the user asks for that viewpoint.

## 08:15 — Pillow image layout retired; diffusion labeled stills

### Symptom

Labeled/weather images used hardcoded Pillow info-card and overlay layout; NSFW censor recovery used fixed retry prompts in dispatcher code; vision-ocr kimi returned empty `content`.

### Root cause

Dispatcher owned layout modules (`info_card`, `overlay`) instead of diffusion; image_backends retried with hardcoded cityscape templates; OCR vision parser read only `message.content`.

### AI decision

Backfilled from legacy log. At fix time: prioritize durable core change over VPS hotpatch; align classify/skills when intent routing was involved.

### Fix (core)

Remove layout modules; host/classify route labeled and weather stills through Omni combo `image-gen` with facts in SCENE; NSFW/SFW guidance in classify/image-gen skills; OCR reads `reasoning_content` fallback; `RENDER: weather-scene` / `labeled-scene` gates.

### Todo list

- Reproduce
- Fix core
- Regression test
- Verify on lab/VPS

### Prevent recurrence

No new Pillow layout for informational stills; strengthen classify SCENE prompts instead of Python retry templates.

## 16:20 — active|inactive env flags; web-search cascade

### AI decision

Backfilled from legacy log. At fix time: prioritize durable core change over VPS hotpatch; align classify/skills when intent routing was involved.

### Todo list

- Reproduce
- Fix core
- Regression test
- Verify on lab/VPS

## 17:00 — strict active|inactive; web-search combo routing

### Symptom

Legacy truthy env values (`1`, `true`, `yes`, `on`) still enabled features; search provider cascade duplicated between env and router JSON; image-gen first-setup hardcoded model/style lists.

### Root cause

Gradual active|inactive migration left read-time legacy acceptance in Python; `OMNIROUTER_SEARCH_PROVIDERS` bypassed operator Omni combo `web-search`.

### AI decision

Backfilled from legacy log. At fix time: prioritize durable core change over VPS hotpatch; align classify/skills when intent routing was involved.

### Fix (core)

`env_active()` accepts only `active`/`inactive`; web-search uses combo env chain + JSON `omni_providers`; image-gen fill from catalog only; first-setup verifies `web-search` combo on API key ACL.

### Todo list

- Reproduce
- Fix core
- Regression test
- Verify on lab/VPS

### Prevent recurrence

New toggles use active|inactive only; search failover order owned by combo JSON + Omni UI, not host env lists.

## 18:00 — image-gen HD canvas 1920x1080

### Symptom

Scenic diffusion still used square 1024 canvas while operator docs described Full HD landscape output.

### Root cause

Skill and Zalo host shortcut hardcoded `1024x1024` after the combo-only migration.

### AI decision

Backfilled from legacy log. At fix time: prioritize durable core change over VPS hotpatch; align classify/skills when intent routing was involved.

### Fix (core)

image-gen skill and host `_omni_generate_still` default to `1920x1080` (16:9); dispatcher comment aligned.

### Todo list

- Reproduce
- Fix core
- Regression test
- Verify on lab/VPS

### Prevent recurrence

Canvas size lives in image-gen skill only — no `.env` size pins.

## 18:30 — Zalo bare image skipped vision-ocr combo

### Symptom

Random image from Zalo got OCR-only failure line even when the photo had visible subjects; Omni logs showed classifier/hermes but not vision-ocr.

### Root cause

Host-ack path treated all `ocr` attachments (including images) as deterministic OCR ack and returned before classify; empty Paddle text never triggered adapter vision fallback.

### AI decision

Backfilled from legacy log. At fix time: prioritize durable core change over VPS hotpatch; align classify/skills when intent routing was involved.

### Fix (core)

Vision-ocr combo call when OCR text empty; host-ack only for bare images with OCR/vision content; captioned or empty-after-vision images fall through to classify/Hermes with media kept.

### Todo list

- Reproduce
- Fix core
- Regression test
- Verify on lab/VPS

### Prevent recurrence

Do not put image attachments in the same host-ack bucket as office/text PDF extract; vision-ocr must run before OCR-only user messaging.

## 19:00 — Combo-only web-search; low-quality image-gen guard

### Symptom

Omni logs showed `tavily-search` instead of combo `web-search`; Zalo-delivered scenic images were blurry low-res stubs.

### Root cause

Router Worker fell through to provider-specific Omni search bodies after combo attempt; diffusion workers returned tiny/censor placeholders that host still saved and sent.

### AI decision

Backfilled from legacy log. At fix time: prioritize durable core change over VPS hotpatch; align classify/skills when intent routing was involved.

### Fix (core)

Omni search uses `{ combo: web-search }` only; image-gen rejects sub-HD/tiny blobs before Zalo send.

### Todo list

- Reproduce
- Fix core
- Regression test
- Verify on lab/VPS

### Prevent recurrence

Do not hardcode provider failover lists in repo JSON — operator combo members live in Omni UI; validate pixel size before delivering generated stills.

## 20:00 — Omni-only web-search; drop direct adapter chain

### AI decision

Backfilled from legacy log. At fix time: prioritize durable core change over VPS hotpatch; align classify/skills when intent routing was involved.

### Todo list

- Reproduce
- Fix core
- Regression test
- Verify on lab/VPS

## 21:00 — Host scenic image-gen shortcut; security-safe delivery

### Symptom

Hermes image-gen skill attempted `curl | python` to plain HTTP OmniRouter; Tirith/security blocked the turn. Scenic-only classify path set `process_original_message true` but adapter had no host shortcut despite `plan_allows_scene_image`.

### Root cause

Scenic-only diffusion was delegated to Hermes shell one-liners; host already had `_omni_generate_still` via urllib but no `run_scene_image` wiring. Low-quality AI Horde stubs still passed the 48KB guard.

### AI decision

Backfilled from legacy log. At fix time: prioritize durable core change over VPS hotpatch; align classify/skills when intent routing was involved.

### Fix (core)

`run_scene_image` host shortcut + classify `process_original_message false` for scenic-only; image-gen skill documents non-shell Omni path; quality guard 960×540 / 80KB; first-setup photoreal-first image-gen combo ordering.

### Todo list

- Reproduce
- Fix core
- Regression test
- Verify on lab/VPS

### Prevent recurrence

Never route scenic-only diffusion through bash curl pipes; keep classify host-owned media families on internal HTTP shortcuts.

## 22:00 — image-gen combo polluted with AI Box chat models

### Symptom

Omni combo `image-gen` round-robin hit AI Box `image-gen/qwen-image-2.0` and `image-gen/deepseek-v4-flash`; `/images/generations` returned no image (`No images-capable targets in combo`).

### Root cause

AI Box chat endpoints share the `image-gen/` model namespace (colliding with combo name `image-gen`). Catalog lacks image modalities for AI Horde workers, so first-setup never refilled after operator added AI Box members.

### AI decision

Backfilled from legacy log. At fix time: prioritize durable core change over VPS hotpatch; align classify/skills when intent routing was involved.

### Fix (core)

first-setup treats `aihorde/*` and OpenRouter Flux/image as diffusion targets, excludes `image-gen/*` chat models, force-refills bad combos; load_env expands literal `\n` in corrupted one-line `.env` templates.

### Todo list

- Reproduce
- Fix core
- Regression test
- Verify on lab/VPS

### Prevent recurrence

Never pin AI Box chat models into combo `image-gen`; run first-setup after Omni provider changes to restore aihorde diffusion members.

## 23:00 — Hermes execute_code blocked on image-gen key probe

### Symptom

Image ask got no attachment; Hermes tried `execute_code` to read replica `.env` / config for API keys — security denied; user saw no image.

### Root cause

Host `_omni_generate_still` only read process env; replica/shared `.env` often lacked synced `OMNIROUTER_API_KEY`. Classify sometimes kept `process_original_message true`, so Hermes image-gen skill hunted keys via scripts instead of failing cleanly.

### AI decision

Backfilled from legacy log. At fix time: prioritize durable core change over VPS hotpatch; align classify/skills when intent routing was involved.

### Fix (core)

`omni_env.resolve_omni_api_key()` reads stack/shared env files; patch-hermes writes Omni keys into `/opt/data/.env` and non-symlink replica copies; skills forbid execute_code secret scans.

### Todo list

- Reproduce
- Fix core
- Regression test
- Verify on lab/VPS

### Prevent recurrence

Never probe `.env`/replica paths from Hermes for diffusion; host owns scenic delivery with synced stack keys.
