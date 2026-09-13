# Quiet stored-note schedules and one-pass image typography

## Symptoms and cause

Grounded images consumed a vision call after each successful generation and
could generate again for an aesthetic rejection. The prior quality callback
also repeated an inline prompt. Generated copy sometimes used tiny or distorted
type, ambiguous paired temperatures, and inconsistent Vietnamese diacritics.
Scheduled research saved notes but announced results unless silence was explicit.

## Decision and technical detail

- `hermes/main/plugins/zalo/media_shortcuts.py:L825`,
  `_omni_request_image_blob`: remove `accept_blob` and the runtime visual-QA
  callback. Stop at the first valid image response. Transport, decode, and
  minimum-size failure still use the unchanged configured provider order.
- `media_shortcuts.py:L407`, `_synthesize_composition_plan`, and `:L654`,
  `_composition_image_prompt`: load typography guidance from the maintained
  `classify/parts/image-runtime.json` asset rather than inline runtime prose.
  Recommend the user's named font, otherwise Unicode Noto Sans; concise copy,
  regular body, bold key values, meaningful units, full diacritics, readable
  spacing, and scene-preserving compact regions. Raster models approximate
  typography; this does not claim they load the shipped TTF files.
- `hermes/main/skills/classify/parts/schedule.txt`: newly classified stored-note
  background outcomes default `notify_on_fire: true -> false` unless the current
  user explicitly requests result delivery. Ordinary reminders and artifacts
  still default true. Existing stored schedules are not rewritten. Creation
  confirmation remains; execution starts only when due, never during creation.
- Mirror the typed contract in `schema.txt` and the schedule skill; rebuild
  Router Worker config with `scripts/main/sync_router_worker_skills.py`.
  Host silence/persistence guards remain unchanged. Untrusted fetched or quoted
  text cannot authorize background work.

## Verification and continuation

- PASS: media transport/unit regressions and composed prompt regressions locally.
- PASS: changed Python scripts compile.
- Skill validator not yet runnable locally because that runtime lacks PyYAML;
  validate in the production dependency environment before claiming completion.
- VPS backup completed before candidate testing. Live typography artifact review,
  one-pass generation evidence, silent note persistence, explicit-delivery
  compatibility, and monitored service health remain pending.
- New `zalo_silent_background_lab.py` checks numbered admission, useful titled
  source-bearing persistence, and zero fire deliveries. Flexible composition
  lab retains explicit release-test vision review including spelling and
  phone-readable typography. `test/RULES.md` now distinguishes quiet stored
  outcomes from explicit delivery and runtime OCR from release evaluation.
- No merge gate passed yet. Do not merge or declare production ready from unit
  checks alone. Operator router combos and existing user reports are preserved.
