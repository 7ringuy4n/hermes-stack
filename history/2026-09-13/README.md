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
- PASS: both updated skills validated with `quick_validate.py` in the production
  Dispatcher dependency environment (local bundled Python lacks PyYAML).
- PASS: 116/116 production-image unit matrix on source overlay `909a895`.
  The runner's base checkout SHA remains main; this record identifies the actual
  overlaid candidate rather than attributing changed source to that main commit.
- Verified VPS backup completed before candidate testing. Observed live results
  and the remaining typography/research quality gates are recorded below.
- New `zalo_silent_background_lab.py` checks numbered admission, useful titled
  source-bearing persistence, and zero fire deliveries. Flexible composition
  lab retains explicit release-test vision review including spelling and
  phone-readable typography. `test/RULES.md` now distinguishes quiet stored
  outcomes from explicit delivery and runtime OCR from release evaluation.
- FAIL: independent immediate-image review found visibly garbled Vietnamese
  labels despite full-bleed scene and requested left placement. Live Router
  Worker logs show two valid image generation calls for two requests, without
  automatic runtime vision or image retries. Prompt guidance alone has not yet
  met the typography gate with the unchanged operator image combo.
- Concurrent scheduled-note test exposed `ZaloAdapter.send`: transport media
  muting ran before `_as_persist_deferred_notes`, losing gathered notes after a
  prior image. Source correction moves note persistence before media muting,
  skips autosend for typed pending silent notes, and suppresses short silent
  status responses while keeping pending state. Three executed send-order
  regression scenarios pass locally. Corrected production-image matrix passes
  117/117 on source `5d7cdf8`. The live corrected scheduled-note rerun passes
  all three checks: no creation-time execution, six titled source-bearing notes
  persisted at fire, and zero fire-time deliveries. Test schedule was deleted.
- Four read-only live classification cases pass: three daily clocks retained in
  one cron, default-silent note gathering, explicit result-delivery override,
  ordinary reminder delivery, and quoted scheduling instructions treated as data.
  Reproduce with `ROUTER_WORKER_URL=http://127.0.0.1:8096 python3
  test/scripts/schedule_background_policy_lab.py` on the VPS candidate source.
- Self-evaluation of stored rows found overlong paragraph-like titles and
  questionable compound wind wording. Persistence/silence passes are not a
  claim that research or note-presentation quality is production ready. The six
  weather records are retained as test output rather than deleting broad user
  note ranges without precise provenance.
- Both generated image artifacts were independently inspected and failed
  Vietnamese spelling. The paid release evaluator also returned an evaluator
  failure; that is not treated as a quality pass or quota skip. No further
  image generation was made to conceal the failed artifacts.
- No open PRs found. Candidate improvements are preserved on
  `codex/fix/quiet-tasks-typography`; no PR/merge is authorized by a failed gate.
  Source and Router Worker/Hermes services were restored to `origin/main` after
  test cleanup; no tracked runtime-source diff remains on the VPS. Operator
  router combo configuration was never changed.
- No merge gate passed yet. Do not merge or declare production ready from unit
  checks alone. Operator router combos and existing user reports are preserved.
