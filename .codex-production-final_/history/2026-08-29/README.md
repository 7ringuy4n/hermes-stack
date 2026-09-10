# 2026-08-29

19 incident(s). Times are UTC+7.

## 07:45 — Weather PDF ask: SOUL blocked; reportlab path; no file

### Symptom

A request to design a PDF with current Ho Chi Minh weather (with attractive icons/images) produced chat weather text and/or Hermes default `/help` intro instead of a PDF. Logs showed SOUL blocked and local `pdf` skill collisions / reportlab attempts.

### Root cause

SOUL.md contained the literal jailbreak phrase scanned by Hermes `threat_patterns` as `prompt_injection`, so the entire SOUL context was dropped every turn. Without SOUL, the agent used default persona and tried ambiguous local pdf skills instead of Dispatcher `file-gen` / office-file (compound search+PDF also skipped the host office shortcut).

### AI decision

Backfilled from legacy log. At fix time: prioritize durable core change over VPS hotpatch; align classify/skills when intent routing was involved.

### Fix (core)

Reword SOUL and related safety/classify text to preserve untrusted-content policy without matching Hermes injection patterns. Expand the SOUL unit for `prompt_injection`. Harden classify + file-gen + answering so chat PDF create-and-send stays on Dispatcher office-file (never pip/reportlab / `skill_view pdf`).

### Todo list

- Reproduce
- Fix core
- Regression test
- Verify on lab/VPS

### Prevent recurrence

Keep SOUL free of classic injection literals; bake/classify must not reintroduce them. Chat office create always routes through file-gen.

## 08:00 — Attractive weather PDF became a menu + plain text file

### Symptom

User asked for a designed PDF of live Ho Chi Minh weather with icons/images. Bot replied with session-restore text and numbered options (retry image / PDF without images / supply API key). Delivered PDFs were plain one-line dumps.

### Root cause

Classify/Hermes treated “icons/images” as a hard `/v1/image` dependency. Image backends returned 502; the agent narrated internals and asked for keys. Dispatcher `office-file` PDF writer only drew monospaced text lines — no layout.

### AI decision

Backfilled from legacy log. At fix time: prioritize durable core change over VPS hotpatch; align classify/skills when intent routing was involved.

### Fix (core)

Styled PDF renderer in office-file (header band, vector icon, fact card) driven by TITLE/ICON/fact lines from file-gen. Classify: visual weather PDF stays search + pdf — no decorative image job. Harden skills so image failure never becomes an API-key / recovery menu; deliver the styled PDF instead.

### Todo list

- Reproduce
- Fix core
- Regression test
- Verify on lab/VPS

### Prevent recurrence

Never block a PDF deliverable on image-backend health. Keep decorative visuals inside office-file for document asks.

## 08:15 — Weather card Vietnamese diacritics became tofu boxes

### Symptom

Attractive weather/info visuals rendered Vietnamese with missing diacritics (white squares). Plain PDFs also risked incomplete glyph coverage.

### Root cause

Diffusion image backends bake text into pixels without a Unicode font. Overlay/poster/PDF font lists preferred incomplete paths or fell back to bitmap defaults.

### AI decision

Backfilled from legacy log. At fix time: prioritize durable core change over VPS hotpatch; align classify/skills when intent routing was involved.

### Fix (core)

Ship Noto Sans with the Dispatcher image; shared `fonts.py` picks a TTF that covers Vietnamese samples (cached). New Pillow `info-card` image mode for dashboards; office PDF/overlay/text-poster share the resolver. Local concurrent media smoke (no LLM).

### Todo list

- Reproduce
- Fix core
- Regression test
- Verify on lab/VPS

### Prevent recurrence

Never ask diffusion to paint Vietnamese labels for dashboards — use info-card or office-file with bundled Noto.

## 08:40 — Designed weather PDF became chat text only

### Symptom

User asked for an attractive PDF of live Ho Chi Minh weather with icons. Bot replied with chat weather (and sometimes a text “card”) and no `share.file` PDF.

### Root cause

Classify correctly emitted search + file_processing(pdf). Host `plan_skips_media_shortcut` blocked the plain office shortcut for any search sibling. Hermes completed search then answered in chat and never called Dispatcher office-file.

### AI decision

Backfilled from legacy log. At fix time: prioritize durable core change over VPS hotpatch; align classify/skills when intent routing was involved.

### Fix (core)

Host `plan_allows_search_then_office` + `run_search_then_office` (model-router `/v1/search` → styled `/v1/office-file`). Classify media part + answering: never rewrite a file ask into chat-only weather. Unit covers gates and body assembly.

### Todo list

- Reproduce
- Fix core
- Regression test
- Verify on lab/VPS

### Prevent recurrence

Never rely on Hermes to finish search→PDF after the host skipped the office shortcut. Keep search+file in classify so the host gate matches.

## 09:00 — Weather PDF UI: create-verb title + SERP junk rows

### Symptom

PDF files arrived, but the card showed create-instruction text as the title and raw search-result page titles (site chrome, truncated words) instead of clean weather facts.

### Root cause

Host body assembly treated the whole file instruction as TITLE when markers were mid-line, and appended SERP titles verbatim. `TITLE:` substring matching also stole values from `SUBTITLE:`. Styled PDF clipped long lines with no label/value layout.

### AI decision

Backfilled from legacy log. At fix time: prioritize durable core change over VPS hotpatch; align classify/skills when intent routing was involved.

### Fix (core)

Safe contract-marker extraction; SERP noise filter; prefer answer/snippets; infer icon from facts; richer office-file card (wrap, hero temperature, label/value). Classify media part: PDF instruction is TITLE/SUBTITLE/ICON only — no create-verb wrapper.

### Todo list

- Reproduce
- Fix core
- Regression test
- Verify on lab/VPS

### Prevent recurrence

Never dump search page titles into the PDF body. Keep TITLE: parsing from mistaking SUBTITLE:.

## 09:10 — Weather PDF still showed JSON dumps and fake hero temp

### Symptom

Delivered weather PDFs included raw `{'location': ...}` API text, markdown section headers, and used wind bearings like `246°WSW` as the large header temperature.

### Root cause

Search snippets often embed weather-API JSON or Python dict dumps. The host body builder pasted them as fact lines. Hero-temp scanned any token with `°`, so compass bearings won over Celsius.

### AI decision

Backfilled from legacy log. At fix time: prioritize durable core change over VPS hotpatch; align classify/skills when intent routing was involved.

### Fix (core)

Filter JSON/dict/markdown/label-only noise; parse valid weather JSON into labeled fact rows; hero temperature only from °C / temperature-labeled values. Classify: never paste raw JSON into the PDF body.

### Todo list

- Reproduce
- Fix core
- Regression test
- Verify on lab/VPS

### Prevent recurrence

Never render search payload serialization on the card. Keep wind bearings out of the hero metric.

## 09:20 — Attractive weather PDF still looked sparse (few icons)

### Symptom

Asks for a weather PDF “with full attractive images and icons” delivered a clean but plain card — one header glyph and text rows, no image panel.

### Root cause

Prior hardening blocked diffusion decoration (502 menus / Vietnamese tofu) and left office-file with a single vector icon. Skills told Hermes not to call image-gen for PDF decoration, so no visual banner was produced either.

### AI decision

Backfilled from legacy log. At fix time: prioritize durable core change over VPS hotpatch; align classify/skills when intent routing was involved.

### Fix (core)

Rich styled PDF: badge strip, companion icons, per-fact glyphs, embedded Pillow info-card banner (Unicode-safe). Classify/file-gen/image-gen: keep visual weather as one office-file PDF with internal visuals; optional scenic image-gen only for standalone photos, never block PDF delivery.

### Todo list

- Reproduce
- Fix core
- Regression test
- Verify on lab/VPS

### Prevent recurrence

Do not equate “no diffusion” with “no images” — use info-card + vectors inside the PDF.

## 09:30 — Weather PDF still looked cluttered (badge strip)

### Symptom

After the “rich icons” update, PDFs still looked poor: a row of Nắng/Mây/Mưa/… labels, duplicated temperature, and busy panels instead of a polished weather card.

### Root cause

ReportLab composition stacked too many decorations (badge strip + banner + fact rows) without a single visual hierarchy. No post-render layout check caught the clutter.

### AI decision

Backfilled from legacy log. At fix time: prioritize durable core change over VPS hotpatch; align classify/skills when intent routing was involved.

### Fix (core)

Pillow full-page weather sheet (sky band, one hero temp, one condition icon, 2-column metric tiles). `verify_styled_pdf_layout` rejects badge-strip clutter; fallback is a minimal clean card. Ship `weather_sheet.py` in the Dispatcher image.

### Todo list

- Reproduce
- Fix core
- Regression test
- Verify on lab/VPS

### Prevent recurrence

Prefer one weather-app composition over stacking strips. Always verify layout after write.

## 10:00 — Visual office classify was weather/fuel-locked

### Symptom

Attractive live-data PDF asks outside the weather/fuel wording risked weak classify guidance because prompts named weather-app sheets, specific VN phrases, and fixed ICON enums.

### Root cause

Media classify / file-gen / image-gen treated one product family as the rule instead of a generic visual + live-facts office pattern.

### AI decision

Backfilled from legacy log. At fix time: prioritize durable core change over VPS hotpatch; align classify/skills when intent routing was involved.

### Fix (core)

Rewrite to generic VISUAL / ATTRACTIVE OFFICE FILE rules: markers TITLE/SUBTITLE/ICON, search sibling when live facts are needed, office-file owns in-document visuals, no decorative media_generation, no chat-only when a file was asked. Reassemble classify bake. Keep schedule/split examples as families only.

### Todo list

- Reproduce
- Fix core
- Regression test
- Verify on lab/VPS

### Prevent recurrence

Do not hardcode topic dictionaries into classify media policy; keep examples illustrative.

## 10:45 — Place visual PDFs needed overview/background

### Symptom

When the ask named a place/city in the visual PDF title, the sheet still showed metrics only — no place intro or atmosphere/background.

### Root cause

Classify/file-gen contract stopped at TITLE/ICON/facts. Renderer and host body builder had no OVERVIEW/BACKGROUND path.

### AI decision

Backfilled from legacy log. At fix time: prioritize durable core change over VPS hotpatch; align classify/skills when intent routing was involved.

### Fix (core)

Classify PLACE SUBJECT rule (intent-based, no city dictionary). file-gen requires OVERVIEW/BACKGROUND for place titles. Host extracts/fills those markers from search prose. Styled sheet renders overview/background panels.

### Todo list

- Reproduce
- Fix core
- Regression test
- Verify on lab/VPS

### Prevent recurrence

Keep place context as contract markers, not hardcoded place names.

## 11:45 — Weather info image: greeting + empty broken card

### Symptom

User asked for a beautiful image with current city weather. Bot replied with a default AI/`/help` intro; the delivered card showed a truncated English scene prompt as the title and “(no details)”.

### Root cause

Labeled live-data **image** asks had no host search→info-card path (unlike PDF), so Hermes often fell through under rate-limit/persona defaults. Hermes/`refine` passed an English scene sentence into info-card without TITLE markers or fact lines; overlay was ignored; layout clipped a single long title.

### AI decision

Backfilled from legacy log. At fix time: prioritize durable core change over VPS hotpatch; align classify/skills when intent routing was involved.

### Fix (core)

Classify LABELED INFO IMAGE (search + media_generation, markers only). Host `plan_allows_search_then_image` / `run_search_then_info_card`. Info-card: reject scene-prompt dumps, merge overlay, wrap title, OVERVIEW/BACKGROUND, never “(no details)”. Auto-route TITLE: prompts to info-card without refine.

### Todo list

- Reproduce
- Fix core
- Regression test
- Verify on lab/VPS

### Prevent recurrence

Never send English scene prose alone to info-card. Prefer host search→info-card for live labeled images.

## 12:15 — Weather info image on disk but no Zalo reply

### Symptom

User asked for a labeled live weather image; the PNG was created under media/out but the chat stayed silent.

### Root cause

`/v1/image` info-card mode wrote the file and returned ok without honoring `send_zalo`. The host shortcut set `send_zalo=false` and relied on late autosend, which often missed shortcut-created files (turn dest not remembered before late watch).

### AI decision

Backfilled from legacy log. At fix time: prioritize durable core change over VPS hotpatch; align classify/skills when intent routing was involved.

### Fix (core)

Info-card path sends via bridge when `send_zalo=true` (file still kept for autosend if send fails). Host search→info-card enables send. Adapter calls `_as_autosend_remember_turn` before late autosend on media shortcuts.

### Todo list

- Reproduce
- Fix core
- Regression test
- Verify on lab/VPS

### Prevent recurrence

Treat labeled info images like office-file: write + deliver, with autosend as fallback only.

## 14:00 — Sheet follow-up lost workbook memory

### Symptom

User asked what sheet 2 describes after an Excel extract; chat stayed silent or the bot claimed no file was attached and asked for a re-upload.

### Root cause

Attachment recall TTL was short; large workbook extracts truncated away sheet inventory; ingest headers lacked 1-based indices; media shortcuts/Hermes treated the ask as a missing file.

### AI decision

Backfilled from legacy log. At fix time: prioritize durable core change over VPS hotpatch; align classify/skills when intent routing was involved.

### Fix (core)

Ingest: `Workbook sheets:` inventory + `## Sheet N (title)`. Longer recall TTL; prefer inventory when truncating. Classify WORKBOOK/SHEET FOLLOW-UP with `SHEET_REF:`. Host answers from remembered extract; skip media shortcuts on Recent attachments. Answering skill: never ask re-send when extract is present.

### Todo list

- Reproduce
- Fix core
- Regression test
- Verify on lab/VPS

### Prevent recurrence

Keep sheet inventory durable in recall; resolve sheet asks via classify SHEET_REF + host memory, not re-upload prompts.

## 17:00 — Aerial city vs weather picture vs info-card

### Symptom

“Draw aerial HCMC” and “draw current HCMC weather picture” both produced the same metrics info-card dashboard instead of a scenic photo or city+overlay weather image.

### Root cause

Classify and host treated all live-data image asks as LABELED INFO IMAGE → info-card. No separate scenic-only or weather-scene+overlay contract.

### AI decision

Backfilled from legacy log. At fix time: prioritize durable core change over VPS hotpatch; align classify/skills when intent routing was involved.

### Fix (core)

Classify: WEATHER SCENE IMAGE (`RENDER: scene-overlay`, `SCENE:`, search), SCENE IMAGE (scenic `SCENE:` only), LABELED INFO IMAGE (`RENDER: info-card` / TITLE). Host: `run_search_then_weather_scene`, `run_scene_image`, `run_search_then_info_card` gates.

### Todo list

- Reproduce
- Fix core
- Regression test
- Verify on lab/VPS

### Prevent recurrence

Never route scenic or weather-picture asks to info-card unless the user wants a metrics dashboard card.

## 18:00 — Scenic image shortcut fail → /help intro

### Symptom

Aerial HCMC image ask returned backend-unavailable prose plus a first-meeting `/help` greeting instead of a file or a single failure line.

### Root cause

Host `run_scene_image` returned `None` on diffusion 502; adapter only short-circuited on success, so Hermes handled the turn and produced persona/backend recovery chatter.

### AI decision

Backfilled from legacy log. At fix time: prioritize durable core change over VPS hotpatch; align classify/skills when intent routing was involved.

### Fix (core)

`plan_media_shortcut_gate` + `shortcut_consumed` contract: failed host shortcuts send media-out failure line and return (no Hermes). Weather-scene falls back to Pillow info-card when diffusion is down. Classify: `process_original_message false` on host-owned image paths.

### Todo list

- Reproduce
- Fix core
- Regression test
- Verify on lab/VPS

### Prevent recurrence

Any host media gate must consume the turn on failure — never fall through to Hermes for classified image shortcuts.

## 18:15 — Aerial image silent after attachment recall

### Symptom

`vẽ hình … nhìn từ trên cao` after earlier photos/files → complete silence (no image, no error line).

### Root cause

`_as_attachment_followup` injected `[Recent attachments…]`; media shortcut block skipped when recall present; workflow media-gate returned handled without sending anything.

### AI decision

Backfilled from legacy log. At fix time: prioritize durable core change over VPS hotpatch; align classify/skills when intent routing was involved.

### Fix (core)

Classify `user_text_before_attach` for media shortcuts (recall stays for Hermes only). Remove workflow swallow; `_as_gate_announce` for fail-line; sync-zalo-plugins overlays all replica plugin dirs.

### Todo list

- Reproduce
- Fix core
- Regression test
- Verify on lab/VPS

### Prevent recurrence

Never gate scenic/weather shortcuts on attachment-recall blocks — only sheet/office paths need that guard.

## 18:30 — Zalo plugins stale after git pull

### Symptom

After `git pull` + `run.sh update`, aerial image asks still got Hermes backend-error prose (not host media-out failure line).

### Root cause

Hermes mounts `/data/assistant/plugins/zalo`, not `hermes/main/plugins/zalo` from git. Only `setup-zalo.sh` copied plugins; `run.sh update` did not.

### AI decision

Backfilled from legacy log. At fix time: prioritize durable core change over VPS hotpatch; align classify/skills when intent routing was involved.

### Fix (core)

`sync-zalo-plugins.sh` on every update; restart Hermes replicas. Workflow submit skips host-owned media gates.

### Todo list

- Reproduce
- Fix core
- Regression test
- Verify on lab/VPS

### Prevent recurrence

Any plugin-only fix must ship via sync-zalo-plugins on update, not git pull alone.

## 19:00 — IMAGE_OMNI_MODEL default dall-e-3 with no OpenAI creds

### Symptom

Scenic image `POST /v1/image` failed: OmniRouter `No credentials for image provider: openai` while Comfy `/models/checkpoints` was `[]`.

### Root cause

Default `IMAGE_OMNI_MODEL=dall-e-3` in `.env.example` / compose; lab `.env` inherited it after pull.

### AI decision

Backfilled from legacy log. At fix time: prioritize durable core change over VPS hotpatch; align classify/skills when intent routing was involved.

### Fix (core)

Default to `aihorde/Flux.1-Schnell fp8 (Compact)` — works via OmniRouter without OpenAI. Quote value in `.env` when it contains spaces/parens.

### Todo list

- Reproduce
- Fix core
- Regression test
- Verify on lab/VPS

### Prevent recurrence

Never ship dall-e-3 as default unless OpenAI image creds are part of first-setup; document quote requirement in `.env.example`.

## 19:30 — IMAGE_BACKENDS omni-first in .env broke Comfy-first policy

### Symptom

`/health` showed `image_backends: ["omni","comfy-cpu","comfy-gpu"]`; scenic images skipped Comfy unless `provider` forced.

### Root cause

`.env` pinned Omni before Comfy; empty `IMAGE_BACKENDS=` in compose disabled dispatcher backends; health read raw env not resolved list.

### AI decision

Backfilled from legacy log. At fix time: prioritize durable core change over VPS hotpatch; align classify/skills when intent routing was involved.

### Fix (core)

`image_backends.py` canonical order + empty→default; compose/first-setup pin `comfy-cpu,comfy-gpu,omni`; health uses `image_backends()`.

### Todo list

- Reproduce
- Fix core
- Regression test
- Verify on lab/VPS

### Prevent recurrence

Never accept arbitrary backend list order — always canonicalize Comfy before Omni on dispatcher.
