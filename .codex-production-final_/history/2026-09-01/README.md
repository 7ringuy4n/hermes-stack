# 2026-09-01

12 incident(s). Times are UTC+7.

## 07:15 — Quote-reply image; AI Box in image-gen combo; analyze path

### Symptom

Quote-reply to a photo in Zalo did not download/analyze the quoted image. Inbound image analyze still routed to `vision-ocr`. AI Box image generators were excluded from combo `image-gen` after the prior chat-junk fix.

### Root cause

Quote media merge ran after the group mention gate, so quoted images were invisible to buffered-media logic. `_as_vision_scene_text` forced `image-gen` → `vision-ocr`. first-setup excluded all `img-gen/*` models, including whitelisted AI Box image generators.

### AI decision

Backfilled from legacy log. At fix time: prioritize durable core change over VPS hotpatch; align classify/skills when intent routing was involved.

### Fix (core)

`merge_inbound_quote_media` before mention gate; bridge `quoted` alias + attachment quote forward; first-setup whitelists four AI Box image models with Horde fallback; OCR_MODEL pins to image-gen combo; neutral multimodal summary prompt.

### Todo list

- Reproduce
- Fix core
- Regression test
- Verify on lab/VPS

### Prevent recurrence

Run first-setup after AI Box provider changes; keep quote media extraction ahead of gates; do not blanket-exclude `img-gen/` — only chat junk.

## 11:10 — AI Box custom image-model repair; neutral image analyze; slim acks

### Symptom

AI Box image generators never returned an image from combo `image-gen`: `/v1/images/generations` silently skipped them. Image acks still appended a fixed "summarize / translate / save knowledge" footer, and the host adapter still hardcoded image/vision prompts plus timing helpers.

### Root cause

The AI Box custom model `qwen-image-2.0` was registered with `supportedEndpoints: ["chat"]`, not `["images"]`; the other three whitelisted models were absent as active custom models. OmniRoute only routes a custom model through `/v1/images/generations` when `supportedEndpoints` includes `images`. The host adapter owned natural-language prompt/timing concerns that belong to the LLM/OCR worker.

### AI decision

Backfilled from legacy log. At fix time: prioritize durable core change over VPS hotpatch; align classify/skills when intent routing was involved.

### Fix (core)

first-setup registers/repairs the four AI Box image models on their `images-generations` provider node via `/api/provider-models` (POST add / PUT fix) with `apiFormat=images-generations` + `supportedEndpoints=["images"]`. Zalo image/file acks drop the fixed footer; OCR keeps only a "Đã đọc chữ:" header. Host-side scene-text and timing helpers removed; OCR worker owns multimodal summarization through `image-gen`.

### Todo list

- Reproduce
- Fix core
- Regression test
- Verify on lab/VPS

### Prevent recurrence

After adding an AI Box provider, run first-setup so its image models get the correct image endpoint tags; keep image analysis prompting in the OCR worker, not the host adapter.

## 11:25 — OCR vision on vision-ocr; image-gen diffusion-only

### Symptom

Inbound image analyze routed `OCR_MODEL=image-gen`, but the `image-gen` combo holds diffusion-only models (AI Box qwen-image, AI Horde) that reject `/chat/completions` with HTTP 400/502 — so every image analyze failed.

### Root cause

The OCR worker's vision path posts `/v1/chat/completions` with `model=OCR_MODEL`; pointing it at a diffusion combo cannot produce a text description. The earlier "route image analyze through image-gen" decision conflated diffusion (`/images/generations`) with multimodal chat.

### AI decision

Backfilled from legacy log. At fix time: prioritize durable core change over VPS hotpatch; align classify/skills when intent routing was involved.

### Fix (core)

`pin_media_combos` sets `OCR_MODEL` from `OMNIROUTER_VISION_COMBO` (`vision-ocr`); OCR worker default `MODEL` and its docstring reverted to `vision-ocr`. Combo `image-gen` remains diffusion-only.

### Todo list

- Reproduce
- Fix core
- Regression test
- Verify on lab/VPS

### Prevent recurrence

Keep image generation (`/images/generations`) and image analyze (`/chat/completions` multimodal) on separate combos: `image-gen` vs `vision-ocr`.

## 16:30 — image-gen priority fallback; scenic-vs-OCR classification guard

### Symptom

Scenic "vẽ hình …" asks intermittently returned either "Hiện chưa tạo được file này" (media-out failure) or "mình không thấy hình ảnh nào được gửi kèm" (image-analyze misroute).

### Root cause

1. The `image-gen` combo used `round-robin` across 8 members (AI Box + free AI Horde). Round-robin cycles evenly, so free Horde workers — which hang or return censored placeholders — served many scenic requests, failing host delivery.
2. The classifier `media` part still referenced `combo image-gen` for the OCR handoff, and did not explicitly reject draw/paint asks with no attachment; weaker classifier members in rotation drifted to image-analyze.

### AI decision

Backfilled from legacy log. At fix time: prioritize durable core change over VPS hotpatch; align classify/skills when intent routing was involved.

### Fix (core)

`IMAGE_GEN_COMBO_STRATEGY` defaults the `image-gen` combo to `priority` (OmniRoute's fallback: head model drains before the next). Classifier media part now routes image analyze through `combo vision-ocr` and hard-disambiguates a no-attachment draw/paint ask into `media_generation` + SCENE. Baked `config/classify.json` re-assembled from parts.

### Todo list

- Reproduce
- Fix core
- Regression test
- Verify on lab/VPS

### Prevent recurrence

Keep `image-gen` (diffusion) distinct from `vision-ocr` (multimodal); scenic diffusion combos must favor fast paid heads over free fallbacks via `priority`.

## 18:30 — scenic image-gen HD canvas; drop head-model env pin

### Symptom

Scenic asks still failed after priority combo rollout; troubleshooting asks routed to Hermes architecture essays. Legacy `IMAGE_GEN_HEAD_MODEL` env pin lingered in patch scripts.

### Root cause

1. Host scenic path used Full HD `1920x1080` / square `1024x1024` inconsistently; combo drains timed out on large canvases.
2. Classifier had no family for image-gen failure/status asks.
3. Obsolete per-member `IMAGE_GEN_HEAD_MODEL` pin conflicted with combo-only routing.

### AI decision

Backfilled from legacy log. At fix time: prioritize durable core change over VPS hotpatch; align classify/skills when intent routing was involved.

### Fix (core)

Host scenic path: HD `1280x720` default, configurable timeout, combo `image-gen` only, scaled quality guard. Drop `IMAGE_GEN_HEAD_MODEL` from patch-hermes; first-setup clears obsolete key. Classifier media part: image-gen diagnostic → host direct reply.

### Todo list

- Reproduce
- Fix core
- Regression test
- Verify on lab/VPS

### Prevent recurrence

Scenic diffusion stays on combo `image-gen` with `priority` strategy; no per-member env pins; diagnostic asks never open Hermes chat.

## 19:15 — host media shortcut owns scenic turns; classify retry

### Symptom

Scenic asks returned the media-out failure line while Hermes logs showed `execute_code` calling Omni `/v1/images/generations` with `NO_API_KEY` — bypassing the host `run_scene_image` path that resolves keys via `omni_env`.

### Root cause

1. When classify succeeded on enqueue but failed on first inbound pass, `_as_try_workflow_submit` created an async workflow for `media_generation` and the workflow worker sent the SCENE instruction to Hermes.
2. Queued drain called `handle_message` without re-running media shortcuts.
3. Single-shot classify HTTP had no retry on transient OmniRouter queue saturation.

### AI decision

Backfilled from legacy log. At fix time: prioritize durable core change over VPS hotpatch; align classify/skills when intent routing was involved.

### Fix (core)

Extract `_as_run_host_media_shortcut` and invoke it from inbound, workflow submit (before schedule/workflow), and queue drain. Block workflow creation when `plan_media_shortcut_gate` is set. Classify client: three attempts with backoff; normalize forces `process_original_message=false` for pure host media.

### Todo list

- Reproduce
- Fix core
- Regression test
- Verify on lab/VPS

### Prevent recurrence

Host-owned media (`plan_media_shortcut_gate`) must never open Hermes diffusion or async workflow; queue drain must re-check shortcuts before gateway.

## 19:30 — sync-zalo-plugins without sudo when deploy user owns overlay

### Symptom

After `git pull`, scenic asks still failed; host overlay `/data/assistant/plugins/zalo` stayed one revision behind SoT because `sync-zalo-plugins.sh` required `sudo` and exited without copying.

### Root cause

Deploy user `tn` owns `/data/assistant/plugins` but the sync script always invoked `sudo rm/cp`; non-interactive runs failed password prompt, leaving stale adapter on the host path.

### AI decision

Backfilled from legacy log. At fix time: prioritize durable core change over VPS hotpatch; align classify/skills when intent routing was involved.

### Fix (core)

When the deploy user can write the plugin parent directory, sync uses plain `rm`/`cp`; sudo remains only for root-owned paths.

### Todo list

- Reproduce
- Fix core
- Regression test
- Verify on lab/VPS

### Prevent recurrence

Always run `bash scripts/main/sync-zalo-plugins.sh` after plugin pulls; script must not require sudo on standard deploy-user layouts.

## 19:45 — image-gen AI Box head pin; drop Horde from combo

### Symptom

Classify and Hermes chat combos responded in seconds; scenic image asks timed out with media-out failure. Omni logs showed `image-gen` falling through to AI Horde (30s timeouts) while direct `wan2.7-image-pro` smoke passed.

### Root cause

1. Host `run_scene_image` posted `model=image-gen` (combo) — Omni priority drained into broken free Horde workers.
2. Obsolete `IMAGE_GEN_HEAD_MODEL` lingered in shared `/data/assistant/.env`.
3. Plugin overlay sync failed without sudo (fixed separately).

### AI decision

Backfilled from legacy log. At fix time: prioritize durable core change over VPS hotpatch; align classify/skills when intent routing was involved.

### Fix (core)

Pin `IMAGE_GEN_HEAD_MEMBER` to ranked AI Box head; media_shortcuts calls head directly. first-setup: AI Box-only combo when heads exist; clear obsolete pins on stack + shared `.env`.

### Todo list

- Reproduce
- Fix core
- Regression test
- Verify on lab/VPS

### Prevent recurrence

Scenic diffusion must not use combo names that include Horde when AI Box heads are registered; first-setup smoke uses the same head member as runtime.

## 20:15 — scenic image delivery: shared media/out + direct Zalo send

### Symptom

Classify succeeded and container `run_scene_image` returned OK (~26s), but Zalo users received no image — inbound messages logged with no outbound attachment.

### Root cause

1. Diffusion wrote under `/data/media/out` while Zalo autosend and bridge scan `/opt/data/media/out` first (`HERMES_SHARED_DATA`).
2. Autosend grace window (8s) expired before ~26s diffusion finished, so late files were never claimed.
3. Synchronous `run_scene_image` blocked the adapter event loop during generation.

### AI decision

Backfilled from legacy log. At fix time: prioritize durable core change over VPS hotpatch; align classify/skills when intent routing was involved.

### Fix (core)

`media_shortcuts._media_out_candidates()` prefers shared SoT; adapter acks, offloads diffusion to a worker thread, and direct-sends images on success; autosend roots include legacy `/data/media/out`. patch-hermes syncs head member and clears obsolete image pins on shared `.env`.

### Todo list

- Reproduce
- Fix core
- Regression test
- Verify on lab/VPS

### Prevent recurrence

Scenic output paths must match Zalo bridge scan order; long diffusion must not rely on autosend grace alone.

## 20:30 — scenic gate ack bypasses outbound filter

### Symptom

Classify and diffusion succeeded intermittently, but Zalo users saw no ack, no failure line, and sometimes no image — silent turn after classify.

### Root cause

1. `_as_gate_announce` sent scenic ack/fail lines through `send()` without `skip_outbound_filter`, so `gateway_noise.filter_outbound` / `/v1/outbound` could drop host-owned copy.
2. Media shortcut ran late in the inbound handler (after inflight drop) and workflow submit could return `True` on media gates without invoking the host shortcut on a secondary path.

### AI decision

Backfilled from legacy log. At fix time: prioritize durable core change over VPS hotpatch; align classify/skills when intent routing was involved.

### Fix (core)

Gate announces bypass outbound filter; early bare-text media shortcut before inflight; workflow media-gate path calls `_as_run_host_media_shortcut`. Omni image HTTP errors log status code.

### Todo list

- Reproduce
- Fix core
- Regression test
- Verify on lab/VPS

### Prevent recurrence

Host-owned gate lines (ack, fail, queue) must always set `skip_outbound_filter`.

## 21:00 — weather-scene visual-only diffusion; fix duplicate image send

### Symptom

Weather-scene asks (city + current conditions) delivered duplicate images; diffusion rendered misspelled Vietnamese text on-image; evening asks produced bright daytime scenes.

### Root cause

1. `_scene_prompt_with_facts` asked diffusion for a readable caption board with raw fact strings — models garble non-English text.
2. Prompt hardcoded `daytime outdoor scene` regardless of local clock.
3. Host direct `send_image_file` plus `_as_autosend_late_files` (and queue worker autosend) sent the same still twice.

### AI decision

Backfilled from legacy log. At fix time: prioritize durable core change over VPS hotpatch; align classify/skills when intent routing was involved.

### Fix (core)

`_weather_scene_visual_prompt` uses visual cues + `_local_lighting_hint()`; classify `media` part drops on-image caption for weather-scene; adapter skips autosend when direct image delivery succeeds.

### Todo list

- Reproduce
- Fix core
- Regression test
- Verify on lab/VPS

### Prevent recurrence

Weather-scene must not request readable text in diffusion; one delivery path per shortcut image.

## 21:30 — classify Local now for scene lighting; drop host lighting heuristics

### Symptom

Evening weather-scene asks still produced bright daytime diffusion when host-side hour buckets overrode or duplicated classify intent.

### Root cause

`_local_lighting_hint()` and `_weather_visual_cues()` in `media_shortcuts.py` hardcoded time-of-day and weather atmosphere in Python instead of letting the classifier read current local time.

### AI decision

Backfilled from legacy log. At fix time: prioritize durable core change over VPS hotpatch; align classify/skills when intent routing was involved.

### Fix (core)

Model-router classify injects `Local now: {local_now}` into the user template from timezone; `media` classify part instructs SCENE lighting from that line. Host weather-scene prompt uses classify SCENE plus search facts only (no readable on-image text).

### Todo list

- Reproduce
- Fix core
- Regression test
- Verify on lab/VPS

### Prevent recurrence

Scene lighting for diffusion must be decided at classify time from Local now — never re-derived in host Python heuristics.
