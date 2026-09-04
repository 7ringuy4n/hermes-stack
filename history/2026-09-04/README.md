# 2026-09-04

2 incident(s). Times are UTC+7.

## 07:05 — sync-model-router-skills PermissionError on classify.json

### Symptom

`bash run.sh update` / `bash scripts/main/sync-model-router-skills.sh` printed `PermissionError: … classify.json` and `WARN: sync-model-router-skills failed` while updating from `main`.

### Root cause

Bake file `architect/models/model-router/config/classify.json` was left `root:root` (mode 644) after a root/sudo sync, while the config directory stayed operator-owned. Later non-root `tn` runs could not overwrite the file.

### Technical detail

- **Script:** `scripts/main/sync-model-router-skills.sh` — Python `Path.write_text` directly onto `classify.json`.
- **Path:** `/opt/assistant/architect/models/model-router/config/classify.json` — `root:root 644`; dir `tn:tn`.
- **Fix:** assemble to temp under the config dir, then `_install_file` removes a non-writable dst (via `sudo` when needed), `mv`, and `chown` to the directory owner.

### AI decision

Treat ownership restoration as part of durable sync, not a one-off VPS chown.

### Fix (core)

Atomic install + chown-to-dir-owner in `sync-model-router-skills.sh`.

### Todo list

- Reproduce ownership mismatch
- Core sync fix
- VPS chown + re-sync
- MR after operator approval

### Prevent recurrence

Never leave bake `classify.json` root-owned after sync; always match config directory owner.

## 06:50 — Weather overlay missing live metrics (title+timestamp only)

### Symptom

Weather-on-image deliverable showed a scenic city still with bottom-left badge `Thời tiết` + `Cập nhật: …` but no temperature, humidity, sky, or wind lines the user asked for.

### Root cause

Host overlay facts came only from classify `- Label: value` bullets and search `answer`. Omni web-search often returns rich `results[].content` with live conditions while `answer` is null. Classify correctly omits empty bullets when values are unknown at classify time. Weather shortcut then painted header+timestamp with `facts=[]`.

### Technical detail

- **Function:** `media_shortcuts.py::_collect_host_facts` — bullets + `_search_answer_lines` only; no use of result content.
- **Function:** `media_shortcuts.py::run_search_then_weather_scene` — `if not facts: facts = []` left overlay empty of metrics.
- **Function:** `model-router/websearch.py::_omni_search` — proxied Omni hit without `include_answer`.
- **New:** `_search_notes_blob`, `_synthesize_overlay_facts`, `_parse_label_value_lines` — chat combo synthesizes 3–4 Label: value lines from search notes when answer/bullets empty.
- **Prompt:** `classify/parts/media.txt` — host must paint metrics when search has condition data.
- **Key:** Omni search `answer` null; `results[].content` holds live weather prose.

### AI decision

Keep host free of weather keyword maps; let chat combo own Label:value extraction from search notes. Prefer durable shortcut path over waiting for classify-time filled bullets (classify runs before search on host shortcut).

### Fix (core)

Synthesize overlay facts after search when needed; request `include_answer` on Omni search; unit coverage for notes blob + Label:value parse.

### Todo list

- Reproduce empty-answer search on VPS
- Core synthesize path
- Unit + Tn OCR eval
- Merge after PASS

### Prevent recurrence

Weather overlay PASS requires OCR evidence of at least one metric line (temperature / humidity / sky / wind), not title+timestamp alone.
