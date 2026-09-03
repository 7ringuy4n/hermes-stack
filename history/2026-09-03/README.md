# 2026-09-03

2 incident(s). Times are UTC+7.

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
