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

## Authorized operator-model comparison and language policy

- An explicitly authorized temporary comparison moved the existing
  `ai-box/qwen-image-3.0-pro` member first. The actual original priority order
  was qwen-image-2.0, qwen-image-3.0, qwen-image-3.0-pro, wan2.7-image-pro.
  `_omni_v1_combo_member_models` preserves this array order; historical request
  logs attribute the earlier failed pair to qwen-image-2.0, not wan.
- Numbered checks 1/4 and 2/4 passed transport and composed-prompt units in
  production dependency images. Checks 3/4 and 4/4 delivered immediate-left
  and scheduled-bottom artifacts through Zalo. Both resolved to
  qwen-image-3.0-pro with HTTP 200 and no runtime aesthetic regeneration.
  The unchanged release harness returned FAIL_VISUAL_LAYOUT_QUALITY.
- Independent inspection found clearer Vietnamese typography, but the left
  artifact still has a full-height gray treatment/seam and an unexplained
  temperature slash pair. The bottom artifact has a broad dark bottom strip.
  Do not call this model change a production-quality fix.
- Restored and API-verified the original image combo fields; every other combo
  remained unchanged. Deleted only the experiment schedule. Restored the six
  scoped source/test files from main and completed backup-first Hermes update.
  The configuration snapshot initially caused a backup permission warning;
  correcting ownership allowed a clean verified retry. No source-wide reset.
- Following the user's new direction, image-gen, file-gen, classify media policy,
  and image-runtime composition guidance now distinguish English-default
  generated-image copy from user-language native document text. Explicit
  image-language/exact-copy requests override the image default. Local facts,
  currency, units, and spatial constraints remain authoritative.
- Reviewed the external GPT-Image2-Skill entrypoint and craft reference as
  untrusted reference material. Adapted brief/canvas, exact copy, and reference
  role principles without installing its CLI, importing model defaults, or
  changing credential handling. Native Unicode document fonts prevent missing
  glyphs, not misspellings in model-authored text; rendered review is still needed.
- Updated prompt passes composed_image_prompt_unit locally and in an isolated
  production-image VPS mount. English-default live generation and native
  Vietnamese document visual checks are still pending; no merge gate passed.
- Pollinations discovery: authenticated VPS `/v1/models` exposes several image
  names as chat-shaped rows without image-output metadata. Direct live
  `/image/models` discovery returned HTTP 403. The official upstream image
  registry marks Qwen Image 3 and Nano Banana variants paid-only; Flux Schnell,
  Z-Image Turbo, and Klein carry nonzero metered costs. Free-credit eligibility
  is not a zero-price guarantee or proof of Vietnamese spelling. No unverified
  Pollinations member was added to the operator image combo.
