# 2026-09-03

6 incident(s). Times are UTC+7.

## 19:40 — Classify blocked asyncio; weather image silent (499 hedge)

### Symptom

User weather+image ask got no Zalo reply. OmniRoute showed many `499` / Request aborted on `classifier` and `qwen3.8-flash`; Hermes exited watchdog code 75; no `weather-scene` output.

### Root cause

Host media-shortcut called sync `classify_text` (urllib) on the asyncio event loop. OmniRoute `classifier` combo hedged multiple upstream members and stalled (~90s). Liveness probes failed → gateway kill before search/image-gen. Multi-model rows are combo hedge + model-router fallback to chat combo `hermes`, not parallel Hermes chat jobs.

### Technical detail

- **Function:** `adapter.py::_as_run_host_media_shortcut` — sync `classify_text` → `classify_text_async` / `asyncio.to_thread`.
- **Function:** `classify_client.py::classify_text_async` — offload HTTP; client timeout `45s`, attempts `2`.
- **Function:** `model-router/classify.py` — on `httpx.TimeoutException` / connect errors `_mark_classify_model_bad` then next candidate.
- **Config:** `hermes/main/skills/classify/classify.json` — `timeout_s` `90`→`35`, `retry` `2`→`1` (baked copy synced).
- **Prompt:** `parts/media.txt` — omit empty `Label:` weather bullets when values unknown.
- **Lines:** `adapter.py` media shortcut / workflow submit / image-analyze / sheet follow-up / AV refuse paths.
- **Key:** OmniRoute combo `classifier` members race → client abort `499` / `hedge-cancelled` when Hermes disconnects.

### AI decision

Keep one classify hop; never block the event loop; shorten classify budget and prefer chat fallback after timeout; evaluate delivered media via OCR (AGENT_RULES §29.2).

### Fix (core)

Async offload for classify on inbound paths; tighter classify timeouts; mark bad combo on timeout; prompt omit empty overlay bullets; AGENT_RULES §29.2 artifact self-eval.

### Todo list

- Offload classify / office / poster from event loop
- Tighten classify.json + mark-bad on timeout
- Prompt empty-bullet rule
- AGENT_RULES §29.2 + VPS Tn OCR eval

### Prevent recurrence

Watchdog must not see classify on the loop; unit/lab must OCR rate deliverables, not assert-only.

## 07:15 — OmniRouter setup vs update split; history/ root-cause log

### Symptom

Every `run.sh up` re-ran full `first-setup-omnirouter`, resetting default combos and minting/overwriting API key behavior operators did not want.

### Root cause

Single script mixed first-install bootstrap with ongoing combo refill, provider sync, and router-worker recreation.

### Technical detail

- **Function:** `first-setup-omnirouter.py::main()` — always ran full combo refill path on every invoke (including `run.sh` post-up hook).
- **Function:** `ensure_media_combos()`, `ensure_opencode_combo()`, `_put_or_create_combo()` — `setup_only=False` (default) rewrote combo members and env pins each run.
- **Function:** `set_env_key()` — overwrote `.env` keys; no `set_env_key_if_missing()` guard for `OMNIROUTER_API_KEY`.
- **Lines:** `run.sh:L654–L670` (`do_post_up_hooks` calls first-setup unconditionally); `first-setup-omnirouter.py:L2162–L2165` (routing split).
- **Key:** `OMNIROUTER_API_KEY` — behavior: re-mint risk on full path → core path uses existing key only (`ensure_api_key_allows_combos` + missing-key branch).
- **Key:** combo env pins (`OMNI_IMAGE_GEN_TIMEOUT_S`, `IMAGE_GEN_HEAD_MEMBER`, etc.) — full `run_update()` rewrote via `set_env_key`; core path uses `set_env_key_if_missing` only.
- **CLI:** `--update` flag → `run_update()`; default → `setup_core()` (`L2016`, `L2080`).

### AI decision

Split responsibilities: default path = idempotent core setup only; explicit `update-omnirouter` for repair/sync. Add dated `history/` per AGENT_RULES §4.1 so root-cause reasoning is preserved outside the append-only ops log.

### Fix (core)

`first-setup-omnirouter.py`: `setup_core()` (login, API key if missing, empty combo shells) vs `run_update()` (`--update`). New `scripts/main/update-omnirouter.py`; `run.sh update-omnirouter`. Backfill `history/` from 2026-08-01 via `backfill-root-history.py`.

### Todo list

- Refactor setup vs update in first-setup script
- Wire run.sh command
- Document in CHANGELOG + 02-commands
- Backfill history folders

### Prevent recurrence

AGENT_RULES §4.1 mandates dated history notes on future root-cause fixes; post-up hook stays on core-only setup.

## 07:00 — Weather Pillow overlay; ingest PDF/zip read

### Symptom

Weather-on-image showed garbled Vietnamese from diffusion text. Bare PDF and zip inner files returned empty extract or member listing only.

### Root cause

Labeled facts were baked into image-gen SCENE (models corrupt diacritics). Hermes read PDF locally without pymupdf; archive temp dir deleted before durable member read.

### Technical detail

- **Function:** `media_shortcuts.py::run_search_then_weather_scene()` — embedded Vietnamese fact labels in diffusion SCENE prompt instead of post-render overlay.
- **Function:** `media_shortcuts.py::_omni_request_image_blob_once()` — 5xx failover before per-member timeout budget exhausted.
- **Function:** ingest `_read_member_text()` / PDF path — no pymupdf text layer; zip members lost when temp dir removed before persist.
- **Lines:** `media_shortcuts.py:L1138–L1205` (weather SCENE); `L701` (`POST /v1/overlay`); `L819` (`OMNI_IMAGE_GEN_TIMEOUT_S` read); `adapter.py:L1634–L1719` (weather shortcut dispatch).
- **Key:** `OMNI_IMAGE_GEN_TIMEOUT_S` — `60` (implicit/default) → `300` pinned on image-gen combo (`first-setup-omnirouter.py:L1330`, `L1361`).
- **Field:** `ImageReq.prompt` (`dispatcher/app.py:L173`) — required → optional default `""` (overlay-only POST returned 422).
- **Route:** `POST /v1/overlay` (`dispatcher/app.py:L940`) — 404 until `overlay.py` added to `dispatcher/Dockerfile` COPY line 13.
- **Path:** `media/extracted/` — archive inner files now persisted before temp cleanup (ingest).

### AI decision

Prioritize durable core change over VPS hotpatch; restore Pillow Unicode overlay instead of trusting diffusion for diacritics; route Zalo PDF reads through ingest extract API.

### Fix (core)

Restore dispatcher `overlay.py` + `/v1/overlay` (bottom-left Noto badge). `run_search_then_weather_scene` applies overlay after scenic gen. Ingest adds pymupdf PDF layer + persisted `media/extracted/` members. Zalo PDF → ingest `/v1/extract-text` first. Image-gen waits 300s with 5xx retry before combo failover.

### Todo list

- Reproduce
- Fix core
- Regression test
- Verify on lab/VPS

### Prevent recurrence

`test/scripts/weather_overlay_unit.py`; `test/scripts/zalo_tn_pdf_zip_weather_inject.py` for Tn inject lab.

## 08:45 — Visual weather PDF bad layout / SERP dump

### Symptom

Zalo Tn request for attractive HCM weather PDF returned plain SERP chrome (district lists, PM stubs, create-sentence title) or a sparse card without city hero image / with markdown table leftovers.

### Root cause

Host search→office previously scraped SERP result snippets into the PDF body. After Hermes composition, `write_pdf_styled` used a minimal single-column layout, did not full-bleed `IMAGE:`, and did not skip markdown table separators; classify/file-gen did not hard-require city image-gen before office-file.

### Technical detail

- **Function:** `media_shortcuts.py::build_office_body_from_search()` — must use classify bullets + search `answer` only (no `results[]` scrape).
- **Function:** `office_file.py::write_pdf_styled()` — L126+ — flat fact rows → full-bleed hero + 2-column cards; `_skip_structural_junk` drops `|---|` rows.
- **Function:** `classify_client.py::_office_body_trivial_for_host_shortcut()` — removed topic keyword list; structural + `process_original_message` gate only.
- **Lines:** `office_file.py:L98–L280` (styled render); `media.txt` VISUAL PDF block; `file-gen/SKILL.md` visual workflow.
- **Field:** office-file `prompt` markdown — require `#` / `##` / `IMAGE:` / `- Label: value`.
- **Key:** N/A — infra-only image path `/opt/data/media/out/` for hero stills.

### AI decision

Fix durable renderer + classify/skill contract; keep LLM-authored content; no domain SERP noise lists.

### Fix (core)

Upgrade styled PDF layout; strengthen classify/file-gen for city IMAGE path; case 39 + `zalo_tn_visual_weather_pdf_inject.py`.

### Todo list

- Reproduce from VPS PDFs
- Core renderer + prompt
- Unit + Tn inject
- Merge after PASS

### Prevent recurrence

`test/cases/39-zalo-tn-visual-weather-pdf.md`; unit assert skips `|---|` in extracted PDF text.

## 18:30 — Weather-on-image placeholders / empty PPTX

### Symptom

Weather facts on HCM photo showed unfilled `<value after search>`, misspelled Vietnamese labels, and `SAFE-FOR-WORK` as on-image header. PPTX weather ask produced a near-empty deliverable (topic line only).

### Root cause

Classify routed weather-on-image to `labeled-scene` with diffusion-burned boards and template fact bullets. Host info-card path baked those bullets into Omni SCENE. SCENE policy token `safe-for-work` leaked as overlay/diffusion text. Office-file had no `pptx` writer (`output_type` remapped/fell through).

### Technical detail

- **Function:** `media_shortcuts.py::_labeled_scene_prompt` / `run_search_then_info_card` — diffusion info board → scenic still + `_apply_weather_overlay`.
- **Function:** `media_shortcuts.py::_skip_structural_junk` / `_weather_overlay_lines` / `_overlay_header` — drop placeholders/SFW; never use SCENE as badge title.
- **Function:** `office_file.py::write_pptx_styled` + `_KIND_EXT["pptx"]`; `_hero_metric` short temp token.
- **Lines:** `classify/parts/media.txt` WEATHER ON IMAGE → `RENDER: weather-scene`; OFFICE CREATE includes pptx.
- **Key:** `python-pptx` on dispatcher requirements.
- **Field:** classify `output_type=pptx` in `_OUTPUT_TYPES`.

### AI decision

Keep Vietnamese facts on Pillow `/v1/overlay` only; strengthen classify contract; add durable PPTX render — no hotpatch.

### Fix (core)

Prompt + host overlay path + pptx writer; case 40 inject script.

### Todo list

- Core fix
- Unit tests
- VPS Tn inject
- MR after PASS

### Prevent recurrence

`test/cases/40-zalo-tn-weather-overlay-pptx.md`; `weather_overlay_unit.py` rejects placeholders/SFW.

## 18:45 — ReportLab PDF layout removed; HTML→PDF

### Symptom

Attractive PDF asks still looked like rigid card templates with truncated metrics (host ReportLab `write_pdf_styled`).

### Root cause

Dispatcher owned page layout in Python (fonts, hero band, two-column cards) instead of letting the LLM author HTML/PDF and converting.

### Technical detail

- **Removed:** `write_pdf_styled`, `_pdf_font`, `_pdf_font_bold`, `_hero_metric`, `_pdf_wrap_line`, `_register_font`, `reportlab_font_name`.
- **Function:** `office_file.py::write_pdf` / `write_pdf_from_html` — HTML or raw/`PDF_BASE64` → WeasyPrint or PyMuPDF Story.
- **Deps:** drop `reportlab`; add `weasyprint`; Dockerfile pango/gdk libs.
- **Skills:** `file-gen` + classify `media.txt` require HTML for PDF bodies.

### AI decision

LLM owns visual layout via HTML; worker only converts.

### Fix (core)

Rewrite PDF path; update classify/file-gen contracts; unit coverage via HTML fixtures.

### Todo list

- Remove ReportLab layout
- HTML convert path
- Prompt/skills
- Units

### Prevent recurrence

`test/scripts/office_pptx_unit.py` / `office_poster_session_unit.py` assert HTML→`%PDF`.
