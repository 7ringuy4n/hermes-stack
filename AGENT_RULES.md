# Agent operations rules (hermes-stack)

**Audience:** Cursor agents and human operators working on this repo.  
**Source of truth:** this file at the repo root. Lab methodology: [`test/RULES.md`](./test/RULES.md).  
**Do not** hardcode these rules into application runtime messages or adapters.  
**Related:** [`docs/GIT.md`](./docs/GIT.md) (branch/MR workflow), [`docs/CHANGELOG.md`](./docs/CHANGELOG.md).

---

## Role

You are an AI/DevOps/Developer with 10+ years experience across AI Agent and automation projects. Your role is to rebuild and optimize the current architecture for long-term production/enterprise use: memory-efficient, high performance, fast response, fault tolerant, and able to handle many concurrent requests, files, and threads.

---

## Operator rules

| # | Rule |
|---|------|
| 1 | Fixing CRLF from multi-line SSH here-strings breaks remote bash (`/tmp\r`). Prefer a **single-line** SSH command and fail on non-zero exit. |
| 2 | Fix PowerShell parse errors from bad escaping and special characters in step blocks. |
| 3 | **Do not** send scripts to the VPS to test without explicit permission. |
| 4 | Make/update a history note for what changed, with timestamp. |
| 5 | Prefer the PowerShell helper `scripts/main/Update-StackRemote.ps1` to sync code, apply sudo, normalize LF, and scrub configured bad words before remote ops. |
| 6 | Code must follow best practices; prefer `switch`/`case` over deep `if`/`else` trees when branching on enums/modes. |
| 7 | Handle special characters correctly (Vietnamese UTF-8; files may contain UTF-8). |
| 8 | Docs must be written in **English**. |
| 10 | Features must be **components** that can be enabled/disabled later and reused across projects. |
| 11 | **Do not hardcode** platform logic when a third party already solves it (e.g. Valkey for session cache/retention, rate-limit, queues). |
| 12 | If a requirement can be solved by an **agent skill**, implement a skill — do not invent new application code for that case. |
| 13 | Before moving/deleting code or functions, ensure runtime will not break from missing symbols. |
| 14 | Knowledge list/find/cite: return **top 5** results only and report how many remain. |
| 15 | Improve fragile logic such as: Ingest down causing cite intercept to bypass Hermes. |
| 16 | Prefer reusable designs; always consider better options before coding. |
| 17 | **Do not hardcode** user-facing messages (notifications, secret-probe, etc.). Put them in editable message/config files (e.g. `hermes/main/messages/`). |
| 18 | Use named **constants** for reused values. |
| 19 | Keyword lists (secret-probe, bad-words, cite triggers): prefer a **skill** or editable config over large hardcoded trigger lists. |
| 20 | Do not patch one bug in a way that regresses other features. |
| 21 | Docs must be human-readable and describe each feature in detail (data stores, short-term vs long-term memory, when data moves, etc.). |
| 22 | **Do not** push or create a merge request on any branch without explicit permission. |
| 23 | **Do not** deploy to the VPS without explicit permission. |
| 24 | Always switch to branch **`develop`** before implementing new requirements (then open `feature/*` from `develop`). |
| 25 | Merge requests to `main` and `develop` must follow [GIT.md](./docs/GIT.md). |
| 26 | Same as (1): CRLF crashes remote bash — convert to LF; single-line SSH; fail on non-zero exit. |
| 27 | Same as (2): PowerShell escaping / special characters. |
| 28 | After installation, report current admin credentials (from env/docs — never invent secrets). |
| 29 | While deploying, if an error is caused by source, fix and update the source. |
| 30 | Verify all services before finishing installation; Hermes must connect to **OmniRouter** (default) or **9Router** when that optional component is enabled. |
| 31 | Avoid Hermes crash-loops and edge ports going down. |
| 32 | Make/update history notes with timestamps in `docs/CHANGELOG.md`. |
| 33 | **No lab identity in product source.** Committed files under `scripts/`, `test/`, `docs/`, and the rest of the tree must not contain VPS IPs, hostnames, login names, or server secrets. Use env vars (`ASSISTANT_SSH_*`) and generic placeholders (`USER@HOST`). |
| 34 | **VPS / lab test scripts belong in gitignored temp.** When testing a host, write probes/deploys under `scripts/temp/` or `hermes/temp/` — never `scripts/main/` or committed `test/scripts/` with real host details. |
| 35 | **Source on `develop` / `main` must stay production-ready.** No lab defaults for SSH host, user, or password in product entrypoints. |
| 36 | **LLM-first content processing. Do not implement natural-language understanding, intent classification, semantic parsing, entity extraction, or user-request interpretation in application code. Let the appropriate LLM/Model Router handle content understanding and return structured output. Do not use split(), join(), substring matching, regex, keyword dictionaries, hardcoded phrases, or language-specific rules to interpret user content. Application code should consume structured LLM output and handle only deterministic responsibilities such as validation, authorization, persistence, queueing, scheduling, rate limiting, locking, serialization, and execution. String operations are allowed only for known deterministic data/protocol formats. LLM understands; code validates and executes. |
| 37 | **Always update and add test cases to fit the current architecture. For every new or changed feature, create/update tests that reflect the actual production flow and include realistic end-user requests, not only unit-level or synthetic inputs. For social platforms such as Zalo, if an authenticated/login session is already available, use it to run real end-to-end test cases against the actual integration. Keep test data safe and generic; never commit real credentials, secrets, personal data, or production identifiers. |
| 38 | **Zalo and zalo-api are one component.** `ENABLE_ZALO=1` must start **both** `zalo-proxy` (bridge) and `zalo-api` (channel admin: allowlists, `!zalo`, sole admin DM). Do not treat a logged-in host bridge as enough. Health checks and stack-watch must fail if zalo-api is missing or unhealthy while Zalo is enabled. |
| 39 | **LLM Intent Classification** — Do not hardcode large keyword lists or strict phrase matching in gateways, routers, plugins, or schedulers to determine user intent. Use an LLM/intent-classification layer to understand natural-language requests, including multilingual variations, paraphrases, and new expressions.
* Gateway logic should perform only lightweight, deterministic routing/validation.
* Before adding keyword-based detection, check existing scripts/components for similar logic and consolidate it.
* When a request can be handled by an existing Agent Skill, check the relevant skills first and let the skill/LLM determine intent.
* Schedule requests must be classified by temporal intent and recurrence semantics, not fixed keywords.
* Knowledge/citation requests must be classified by intent, not words such as `tài liệu`, `kiến thức`, `cite`, or `find`.
* Do not add keyword exceptions to fix individual false positives; improve the classifier, prompt, skill, or intent schema instead.
* When classification is ambiguous, return structured uncertainty and ask for clarification rather than guessing.
* Keep deterministic keyword rules only for explicit commands, security boundaries, protocol markers, or cases where exact matching is intentionally required.
* When changing intent classification, test both **false positives and false negatives**, including natural-language, multilingual, paraphrased, and unrelated requests.
| 40 | **Zalo Testing — All Zalo test cases must simulate real user requests sent through the Zalo Bridge, rather than directly calling internal services or bypassing the Zalo integration path.
| 41 | Restore Defaults — After testing is complete, revert all test-specific source/configuration values to their original/default values and verify no test-only changes remain.
| 42 | Async Workflows — Workflows must be asynchronous and non-blocking by default; do not force sequential execution unless ordering or data dependency explicitly requires it.
| 43 | Router Timeout — Do not use overly strict request timeouts. Free-model routers may need additional time to switch, retry, or find an available model. Use configurable, fault-tolerant timeouts with appropriate retry/grace periods, while still preventing indefinite hangs.
| 44 | Temporary Files — Always add temporary/test-environment folders and generated temporary artifacts to .gitignore; never commit them to the source repository.
| 45 | Abnormal Test Behavior — If abnormal tasks or operations are discovered during testing, update the affected logic to handle them correctly without rearchitecting the existing system unless explicitly required.
| 46 | Classification Testing — Test classification in detail for every supported request type and task_hint, including correct routing and false classifications. Test cases must contain no secrets, no chit-chat, and no summaries. Classification output must return JSON only and include only the fields required by the current requirements.
| 47| Test Integrity & Architecture Alignment — NEVER cheat by changing test cases only to obtain a passing result. Every test must represent the CURRENT architecture, component responsibilities, APIs, workflows, security boundaries, concurrency model, and realistic user behavior. Before modifying a test, inspect the current implementation and architecture. If the architecture intentionally changed, update the test accordingly; otherwise, fix the implementation instead of weakening the test. Never remove assertions, reduce coverage, bypass validation, mock away the behavior under test, skip real integration paths, or change expected results without architectural justification. Tests must prove that the system works according to its intended architecture, not that the implementation can satisfy an artificially modified test.
| 48 | Test Cases Must Follow the Current Architecture — After any rearchitecture, refactoring, component replacement, workflow change, responsibility change, or API change, review ALL affected test cases and update them to match the CURRENT architecture. Do not preserve outdated test assumptions, obsolete component paths, deprecated APIs, old worker responsibilities, or previous request flows merely to keep tests passing. Tests must validate the system as it is architected now. When a test is no longer applicable, replace it with an equivalent test that validates the intended behavior through the current architecture rather than simply deleting it. Re-run the updated tests and ensure they still represent realistic user requests and end-to-end behavior.
| 49 | Social-App Test Routing — When a supported social app such as **Zalo** is available and already authenticated/configured, ALL applicable end-to-end test cases MUST simulate requests through that real social-app channel (e.g., Zalo → bridge/proxy → Hermes) rather than bypassing the social-app layer. Tests must use realistic user requests, message types, attachments, and interaction flows supported by the current architecture. If the social app is unavailable, not authenticated, or not configured, simulate the request directly against Hermes while preserving the same expected user behavior. Never modify or weaken test cases simply to avoid using the available social-app integration.


*(Number 9 is intentionally unused in the operator list.)*

---

## Rules (numbered)

Existing lab cases: [`test/cases/`](./test/cases/) (procedure: [`test/RULES.md`](./test/RULES.md)). This section only lists cases **not** to run.

exclude:
| Skills mount + auto-learn (Medium+) | `test/cases/12-skills-auto-learn.md` |
| Exact text poster (text-poster backend) | `test/cases/13-image-text-poster.md` |
| Internal docs knowledge-first | `test/cases/14-knowledge-internal-rag.md` |

---

## How Cursor should apply this

1. Load this document (via `.cursor/rules/agent-ops.mdc` and/or skill `agent-ops`).
2. Treat **22 / 23 / 24 / 25 / 32 / 33 / 34 / 35 / 36 / 38 / 40 / 41** as hard gates every turn.
3. Prefer skills + editable config over new hardcoded keyword tables (12, 17, 19).
4. When syncing to a host, use `Update-StackRemote.ps1` only after the operator grants deploy/test permission (3, 5, 23).
5. Lab procedure and case index: [`test/RULES.md`](./test/RULES.md).

---

## Editable companions

| Path | Purpose |
|------|---------|
| `docs/GIT.md` | Branch / MR workflow |
| `docs/CHANGELOG.md` | Timestamped change history |
| `test/RULES.md` | Deployment and profile test procedure (links here) |
| `hermes/main/messages/` | User-facing strings (admin-editable) |
| `config/agent/bad-words.txt` | Words/phrases scrubbed by the update script |
| `scripts/main/Update-StackRemote.ps1` | Safe remote sync helper (LF + sudo + scrub) |

## Test case if required in REQUIREMENT

| Case | File |
|------|------|
| Basic health | `test/cases/01-basic-health.md` |
| Media disabled | `test/cases/02-media-disabled.md` |
| High 10-type concurrency | `test/cases/03-high-concurrency.md` |
| Web search | `test/cases/04-web-search.md` |
| Security / policy | `test/cases/05-security-policy.md` |
| Backup / restore | `test/cases/06-backup-restore.md` |
| Fail events + auto-heal | `test/cases/07-fail-events.md` |
| Zalo concurrent text | `test/cases/08-zalo-concurrent.md` |
| Zalo concurrent text + media gen + delay | `test/cases/09-zalo-concurrent-media.md` |
| Isolation risks (sock, judge, VPN-only) | `test/cases/10-security-isolation-risks.md` |
| Worker add/remove | `test/cases/11-worker-switch.md` |
| Schedule TZ (today vs tomorrow) | `test/cases/15-schedule-timezone.md` |
| Zalo compound multi-request | `test/cases/16-zalo-multi-request.md` |
| Zalo latency SLO | `test/cases/17-zalo-latency-slo.md` |
| Web search backend chain | `test/cases/18-web-search-backends.md` |
| File/OCR/YARA/AV matrix | `test/cases/19-file-pipeline-security.md` |
| Grafana component integration | `test/cases/20-grafana-component-integration.md` |
| Default 9Router / OmniRouter connected | `test/cases/21-defaults-routers-connected.md` |
| Zalo busy interrupt + multi-task cron | `test/cases/22-zalo-busy-cron-multi.md` |
| Zalo inbound FIFO (plenty of requests) | `test/cases/23-zalo-inbound-queue.md` |
| Plenty-in-one + same/different-time cron | `test/cases/24-workflow-multi-cron-channels.md` |
| Zalo special four (hello + image + fuel + video) | `test/cases/25-zalo-special-four.md` |
| Zalo weather+fuel infographic (one picture) | `test/cases/26-zalo-weather-fuel-poster.md` |
| Daily schedule of one weather+fuel infographic | `test/cases/27-zalo-weather-fuel-daily.md` |
| Zalo media gen + schedule delivery (video send, leftover claim, quiet) | `test/cases/28-zalo-media-cron-delivery.md` |
| Zalo once-schedule numbered tasks (no cite intercept) | `test/cases/29-zalo-once-numbered-nocite.md` |
