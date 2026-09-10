# 2026-09-04

## 21:04 — Production update guidance points to the real entrypoint

### Symptom

The operations rules recommended a remote-update helper that was not present in
the repository, leaving the final deployment step ambiguous.

### Root cause

The documented helper name survived after the update workflow consolidated in
the root lifecycle script.

### Technical detail

- **Entrypoint:** `run.sh::do_update()` performs a verified backup before any
  rebuild and synchronizes classifier and Zalo source-of-truth assets.
- **Branch gate:** production updates must fast-forward a clean checkout to
  verified `origin/main` before invoking the update entrypoint.

### AI decision

The rule now references the existing backup-first lifecycle command instead of
adding another wrapper with overlapping ownership.

### Fix (core)

- Replaced both stale helper references in the operations rules.
- Kept the authorization and main-only deployment gates explicit.

### Todo list

- [x] Resolve the documented helper path.
- [x] Inspect the current update implementation.
- [x] Point the rule and companion table to the source-owned entrypoint.

### Prevent recurrence

Documentation must resolve every named operational script before it is merged.

## 20:52 — Generic image composition replaces fixed render families

### Symptom

Information images were routed through several topic- and layout-shaped modes,
and runtime Python embedded fixed scene and fact-extraction instructions. New
subjects or visual styles could therefore miss the intended path or inherit a
design that did not fit the request.

### Root cause

Classification mixed semantic intent with presentation templates, while the
host owned both prompt copy and a fixed bottom-left card. Prompt policy,
content selection, visual design, and deterministic rendering were not cleanly
separated.

### Technical detail

- **Protocol:** `RENDER: composed-image` is the single classifier marker for a
  generated background plus grounded information.
- **Prompt asset:** `hermes/main/skills/classify/parts/image-runtime.json`
  contains the generic scene and structured composition contracts.
- **Functions:** `media_shortcuts::_synthesize_overlay_plan()` obtains title,
  facts, emphasis, and design; `_safe_overlay_design()` validates the bounded
  vocabulary; dispatcher `overlay::apply_overlay()` selects a quiet region,
  derives contrast, and renders role-specific typography.
- **API fields:** `/v1/overlay` accepts optional `overlay_design` alongside
  structural `overlay` lines; unrecognized design values fall back safely.
- **Timing:** `OMNI_IMAGE_GEN_TIMEOUT_S` defaults to and is capped at 300
  seconds per image-combo member.

### AI decision

The architecture assigns semantic and aesthetic choices to the LLM, keeps
editable instructions outside application code, and limits Python to protocol
parsing, validation, I/O, and rendering. A growing set of aliases or
topic-specific templates was rejected because it would reproduce the same gap.

### Fix (core)

- Collapsed live and labeled image modes into the generic composed-image path.
- Removed runtime prompt prose and fixed photographic styling from the Zalo
  shortcut code.
- Added adaptive placement, theme, alignment, accent, density, and font-role
  rendering with Inter and Unicode-capable fallbacks.
- Rebuilt the classifier fallback from English-only semantic parts and added a
  cross-platform source-of-truth sync command.
- Replaced obsolete mode tests with generic contract and adaptive-render tests.

### Todo list

- [x] Inspect classifier, shortcut, dispatcher, skills, and existing tests.
- [x] Externalize runtime prompts and remove fixed render aliases.
- [x] Add structured design validation and adaptive rendering.
- [x] Update operational rules and project history.
- [x] Run local syntax, classifier, routing, timeout, and rendering tests.
- [x] Keep VPS access outside the explicitly authorized scope.

### Prevent recurrence

Classifier parts are required to remain English-only and semantic. New image
subjects use the existing composed-image protocol; they must not add a new
topic mode. Unit coverage verifies prompt loading, mode gating, timeout bounds,
design fallback, content roles, and real Pillow output.

## 20:05 — Scheduled live-scene intent survives storage and fire

### Symptom

A delayed live-facts image request could run immediately, lose its inner search/media work during schedule storage, or fire later as plain chat without producing the composed image.

### Root cause

The classifier prompt did not make outer timing precedence explicit, provider output could serialize the scheduled process body as chat-shaped JSON, and the Zalo media gates treated every schedule context—including a due schedule fire—as ineligible.

### Technical detail

- **Functions:** `architect/models/model-router/classify.py::assemble_classify_system()` prepends hard priority rules; schedule normalization at `architect/models/model-router/classify.py:L930–L985` rebuilds `message` from ordered `instructions`; request construction at `L1088–L1102` pins classifier reasoning effort.
- **Lines:** `hermes/main/plugins/zalo/adapter.py:L2318–L2327` and `L2715–L2724` allow media only for `schedule_fire` or a non-schedule plan, preventing create-time execution while enabling due work.
- **Fields:** `task_hint=schedule`, `task_type=create_schedule`, `schedule_form=once_after`, `delay_seconds=<integer seconds>`, `schedule_delivery=process`, and `task_details=[search, media_generation]` are preserved as one job; `message` is plain joined instruction text.
- **Config:** `hermes/main/skills/classify/classify.json` uses `timeout_s=60`, `max_tokens=3072`, and `retry=1`; router payload uses `reasoning_effort=low` so hidden reasoning does not consume the structured JSON budget.

### AI decision

The fix keeps intent classification in the prompt and limits host code to schema normalization and lifecycle state. A VPS-only patch, phrase scan, or immediate shortcut fallback was rejected because each would bypass the source-of-truth schedule contract and could duplicate work.

### Fix (core)

- Hardened the classify source prompt and regenerated the router bake.
- Normalized process schedule messages from the classifier-owned instruction list.
- Made both Zalo media gates schedule-fire aware without enabling media during schedule creation.
- Replaced LLM cooldowns in the real-channel lab with schedule and artifact condition polling.

### Todo list

- [x] Reproduce immediate/missing scheduled media behavior.
- [x] Harden classifier timing and process-delivery contracts.
- [x] Add structural normalization and both adapter gate regressions.
- [x] Verify a real delayed Zalo request stores once and fires once.
- [x] Monitor schedule, Hermes dependencies, router, Omni, dispatcher, Zalo API, and bridge logs.

### Prevent recurrence

`test/scripts/classify_parts_assemble_unit.py` asserts the assembled priority contract and process message shape. `test/scripts/media_shortcut_gate_unit.py` covers create-time exclusion and fire-time inclusion at both adapter sites. The real-channel lab requires a newly modified artifact rather than accepting a stale path.

## 20:10 — One renderer owns live-scene text

### Symptom

Generated live-scene images could contain a correct overlay card plus duplicated headings, timestamps, or malformed text burned into the scenic background.

### Root cause

Search-derived label/value facts were passed into the diffusion prompt and then rendered again by Pillow. The overlay also appended its own authoritative update time without excluding an update time already present in the fact list.

### Technical detail

- **Functions:** `hermes/main/plugins/zalo/media_shortcuts.py::overlay_heading_from_instruction()` (`L454–L461`) reads the classifier marker; `_is_renderer_timestamp_fact()` (`L477–L491`) identifies source timestamp fields by structural label; `_live_overlay_lines()` (`L494–L519`) emits one heading/card/timestamp; `_live_scene_visual_prompt()` (`L574–L588`) builds a text-free background prompt.
- **Fields:** `OVERLAY_HEADING` is the sole card title input; source labels `Updated`, `Last Updated`, `Update Time`, `Timestamp`, `Cập nhật`, and `Thời gian cập nhật` are omitted because the renderer appends one `Updated` line.
- **Prompt boundary:** factual label/value rows are no longer copied into the diffusion `prompt`; they remain inputs only to the deterministic `/v1/overlay` stage.
- **Artifact gate:** `test/scripts/zalo_tn_weather_dalat_inject.py:L22–L27` normalizes managed `ID | label` entries, and `L114–L151` accepts only the newest image whose mtime exceeds the pre-test value.

### AI decision

The deterministic renderer was chosen as the only owner of visible facts. Repeatedly asking the image model not to render labels was insufficient while its prompt still contained those labels; OCR cleanup or pixel patching would be nondeterministic and would hide rather than remove the cause.

### Fix (core)

- Added a classifier-owned English heading marker and stopped deriving headings from a first fact label.
- Removed source update-time rows before appending the renderer timestamp.
- Removed factual label/value data from scenic diffusion prompts and strengthened the clean-background/no-UI contract.
- Added overlay, prompt-boundary, target-normalization, and real artifact checks.

### Todo list

- [x] Visually inspect the failed image and confirm duplicated generated text.
- [x] Make Pillow the sole factual-text renderer.
- [x] Add unit coverage for duplicate timestamps and fact-free diffusion prompts.
- [x] Re-run the delayed request through the real Zalo bridge.
- [x] OCR/rate the artifact; treat an empty free-model OCR response as a skipped model case and perform direct visual evaluation.

### Prevent recurrence

`test/scripts/weather_overlay_unit.py` asserts one update line, a distinct English heading, and absence of fact values in the diffusion prompt. VPS validation checks dimensions, direct visual hierarchy, schedule fire count, self-photo delivery count, and queue-drop/error metrics before merge.

## 18:10 — Privileged OpenBao refresh preserves runtime ownership

### Symptom

Running the OpenBao export refresh with elevated privileges could leave the generated compose secret export owned by root, preventing later stack operations by the normal runtime-data owner.

### Root cause

The loader enforced secret file permissions after writing but did not restore ownership when the process effective user differed from the owner of the persistent data directory.

### Technical detail

- **Function:** `scripts/main/load-openbao-env.py::match_export_owner()` (`L204–L224`) applies the data directory UID/GID and falls back to the invoking sudo user only when directory stat/chown fails.
- **Call site:** `scripts/main/load-openbao-env.py:L264–L274` writes `.env.openbao`, keeps mode `0600`, then restores ownership before refilling compose keys.
- **Ownership:** `.env.openbao` changes from a possible privileged-process owner to the UID/GID of `ASSISTANT_DATA_DIR`; `SUDO_USER` is a guarded fallback, not a configured owner override.
- **Key:** file contents and OpenBao key names are unchanged; this fix changes only filesystem owner metadata while retaining permission value `0o600`.

### AI decision

Ownership is derived from the existing data directory because it is the durable source of truth for the deployment operator. Hard-coding a username, relaxing permissions, or applying a one-off VPS chown was rejected as environment-specific and non-durable.

### Fix (core)

- Added owner restoration to the core OpenBao export path.
- Added a platform-safe unit using the actual data-directory stat values and a mocked chown call.
- Verified a privileged loader run on the VPS keeps both the host env and generated export owned by the stack operator with restrictive modes.

### Todo list

- [x] Reproduce/inspect ownership after a privileged refresh.
- [x] Implement ownership restoration in the source loader.
- [x] Add unit coverage without requiring root privileges.
- [x] Run the unit locally and on the VPS.
- [x] Run the real loader with sudo and verify owner/mode afterward.

### Prevent recurrence

`test/scripts/openbao_common_unit.py:L48–L62` asserts that `match_export_owner()` calls chown with the data-directory UID/GID. Future privileged refresh paths must continue using the core loader rather than shell ownership patches.

## Omni maxWaitMs reset on update

### Technical detail
- **Symptom:** Jobs still dropped at `maxWaitMs=15000` after stack update.
- **Root cause:** Omni recreate resets resilience defaults; `run.sh update` did not re-apply `/api/resilience`.
- **Fix:** Default 24h clamp; force PATCH every setup/update; `run.sh update` → `update-omnirouter` (keeps combo members).
- **Verify:** Cookie-session `GET /api/resilience` shows `maxWaitMs=86400000`; live chat has no 15000 drop string.

## Obsolete env key cleanup

### Technical detail
- **Symptom:** Empty `ADMIN_API_TOKEN` and `WEB_BACKENDS=omni` lingered on VPS after combo-only search / OpenBao scrub.
- **Root cause:** Scrub cleared secret values but did not delete retired KEY lines.
- **Fix:** `cleanup-obsolete-env.py` + `OBSOLETE_ENV_KEYS`; scrub + load-openbao; filter OpenBao export; `.env.example` drops `WEB_BACKENDS`.
- **Verify:** Lab seeds retired pins then asserts they are gone; classifier/Omni smoke still HTTP 200.

## Omni requestQueue maxWaitMs

### Technical detail
- **Symptom:** Omni drops slow free-model jobs at `maxWaitMs=15000` (Bottleneck execution expiration; legacy name “queue budget”).
- **Root cause:** Default resilience setting; `/api/settings` does not persist nested `resilienceSettings`.
- **Fix:** `scripts/main/first-setup-omnirouter.py` → `ensure_request_queue_max_wait` → `PATCH /api/resilience` with `requestQueue.maxWaitMs` (env `OMNIROUTER_REQUEST_QUEUE_MAX_WAIT_MS`, default `600000`).
- **Verify:** `GET /api/resilience` shows raised `maxWaitMs`; chat smoke with free members no longer returns the 15s drop string.

## Hermes non-owner Zalo adapter ERROR

### Technical detail
- **Symptom:** Non-owner Hermes replica ERROR `Platform 'zalo' … adapter creation failed`.
- **Root cause:** Shared `config.yaml` still enabled `gateway.platforms.zalo` + `zalo-platform` after `ZALO_PLUGIN_URL` cleared.
- **Fix:** `hermes/main/docker/hermes-replica-entry.sh` → local config for non-owners with Zalo disabled; owner keeps shared symlink.
- **Verify:** After recreate, non-owner logs have no zalo adapter ERROR; Zalo bridge health still OK; owner keeps `zalo_url`.
