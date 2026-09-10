# 2026-08-21

9 incident(s). Times are UTC+7.

## 16:53 — Omni owns search; Router Worker proxies

### Symptom

Request â€œcreate MR then merge to develop **and** mainâ€ while sitting on `develop` with mixed temp files.

### Root cause

[`docs/GIT.md`](../docs/GIT.md): **never** merge `develop` straight into `main`. Feature/fix â†’ `develop`; `release/*` â†’ `main`. Temp reports / `_tmp_*` probes must not ship.

### AI decision

Backfilled from legacy log. At fix time: prioritize durable core change over VPS hotpatch; align classify/skills when intent routing was involved.

### Fix (core)

1. Branch `fix/zalo/workflow-schedule-reliability` from current work.
2. Stage product files only (workflow service, Zalo adapter, compose, docs, unit/VPS scripts). Leave `test/reports/**` and `test/scripts/_tmp_*`.
3. Fetch + rebase onto `origin/develop`.
4. PR [#40](https://github.com/7ringuy4n/hermes-stack/pull/40) â†’ merge into `develop`.
5. `release/v0.5.6` from `origin/main`, cherry-pick the fix commit, PR [#41](https://github.com/7ringuy4n/hermes-stack/pull/41) â†’ merge into `main`.
6. Fast-forward local `develop` / `main`; delete local fix/release branches.

### Todo list

- Reproduce
- Fix core
- Regression test
- Verify on lab/VPS

### Prevent recurrence

Do not `gh pr create --base main` from `develop`. Do not commit `_tmp_` probes.

---

## Quick index (symptom â†’ section)

| You saw | Go to |
|---------|--------|
| Lá»‹ch saved, no run today (same minute) | 13:55 same-minute grace |
| Lá»‹ch saved, only first Zalo message | 15:27 fail_job; 16:20 turn wait; 16:40 session isolation |
| `[response interrupted]` | 15:00 9router abort |
| `readonly database` / Errno 30 skills | 15:05 permissions |
| `NameError: n` in deploy_high | 15:07 f-string |
| Schedules gone after destroy | 10:45 shared cron |
| Busy / `/busy` tip on Zalo | 08:45 FIFO + noise filter; 08:25 multi-task cron |
| Only last numbered item answered | 12:45 inline split |
| Daily 06:00 â†’ tomorrow at 05:58 | 07:15 schedule_tz today |
| Simple chat >5s still â€œpassâ€ | 07:45 SLO 5s |
| stack-watch restart loop / compound not split | 07:35 backoff + multi_request |
| Inbound queue backlog | 09:34 queue max 3 |
| zalo-api crash `schedule_list` / Omni default | 09:25 image + Omni |
| Lab force Omni/Grafana on | 07:50 deploy_high defaults |
| Destroy without backup stamp | 17 Aug 17:55 |
| Notify/AV still up after disable | 17 Aug 15:05 drop profile containers |
| Judge CLEAN allowed scan | 17 Aug 14:15 isolation |
| `/oev/null` / check-medium broken | 17 Aug 12:15 corruption |
| No `:29119` on HermesÃ—2 | 17 Aug 12:05 Traefik probe |
| Gateway open / docker.sock on zalo-api | 17 Aug 11:50 P0 |
| `/sethome` spam | 17 Aug 07:25 auto-sethome |
| Restore missing Traefik/Zalo; SSE 0 | 17 Aug 07:15 DR profiles |
| Backup DROP ROLE / fat tar | 16 Aug 20:10 |
| Hermes ports vanish every ~2 min | 16 Aug stack-watch scale |
| Dual Zalo SSE / silent bot after restore | 16 Aug Zalo owner lock |
| Replica exits `gateway` not found | 16 Aug 11:57 entrypoint |
| Traefik miss after scale | 16 Aug 11:25 API bind |
| Watch restart storm | 16 Aug 08:15 |
| Skill learn empty / embedding | 15 Aug ONNX fallback |
| PDF silently becomes `.txt` | 15 Aug 16:10 office |
| Wrong default combo after first-setup | 15 Aug 14:55 |
| Disk full on Hermes extract | 15 Aug 14:20 |
| No entries 12â€“14 Aug | note under 18 Aug 07:50 block |

## 17:55 — Weather search soft-fail: Hermes tool used SearXNG only

### Symptom

Zalo weather ask got a soft failure about the search tool being broken.

### Root cause

Hermes native `web_search` (toolset `web`) ignores `WEB_SEARCH_URL` /
Router Worker. With only `SEARXNG_URL` set and no `TAVILY_API_KEY` in the
Hermes container, SearXNG returned unusable results and the model apologized.

Also: two skills named `web-search` caused cron skill load collisions.

### AI decision

Backfilled from legacy log. At fix time: prioritize durable core change over VPS hotpatch; align classify/skills when intent routing was involved.

### Fix (core)

- Compose: inject `TAVILY_API_KEY` / `FIRECRAWL_API_KEY` into Hermes.
- Rename knowledge skill frontmatter to `web-search-strategy`.
- Recreate Hermes on lab; verify native `web_search_tool`.

### Todo list

- Reproduce
- Fix core
- Regression test
- Verify on lab/VPS

### Prevent recurrence

Any provider key required by Hermes built-in tools must be on the Hermes
service env, not only on router-worker / Omni.

## 18:05 — Native Hermes search ignored Omni / Router Worker

### Symptom

Zalo weather query answered with search-tool technical failure.

### Root cause

Hermes toolset `web` calls `SEARXNG_URL/search` (or Tavily with
`TAVILY_API_KEY`). `WEB_SEARCH_URL` is unused by the native tool. Lab Hermes
only had raw SearXNG; Omni Tavily key cannot be read unmasked from Omni API.

### AI decision

Backfilled from legacy log. At fix time: prioritize durable core change over VPS hotpatch; align classify/skills when intent routing was involved.

### Fix (core)

- `GET /v1/searxng-compat/search` on Router Worker wraps Omni search.
- Hermes `SEARXNG_URL=http://model-router:8096/v1/searxng-compat`.
- Keep Router Worker `SEARXNG_URL` as real SearXNG for direct adapter fallback.

### Todo list

- Reproduce
- Fix core
- Regression test
- Verify on lab/VPS

### Prevent recurrence

Never assume Hermes env `WEB_SEARCH_URL` feeds the native web tool; wire
`SEARXNG_URL` / `TAVILY_API_KEY` explicitly.

## 18:20 — Web search hang locked next Zalo message

### Symptom

A web-search turn hung on Hermes; the next user message got no reply (queue
appeared stuck).

### Root cause

Per-thread inbound FIFO drain awaited `handle_message` with no hard timeout.
`_as_queue_kick` refused to start another drain while that task was still
running, so later messages sat in Valkey. Search provider HTTP timeouts were
also long (60s/90s), so failover waited the sum of worst cases.

### AI decision

Backfilled from legacy log. At fix time: prioritize durable core change over VPS hotpatch; align classify/skills when intent routing was involved.

### Fix (core)

- Wrap queued turn in `asyncio.wait_for` (`ZALO_QUEUE_TURN_TIMEOUT_S=150`);
  on timeout send UX line, `compound_end`, continue drain.
- Cap drain age (`ZALO_QUEUE_DRAIN_MAX_S`); cancel stuck drain so kick can restart.
- Omni providers default Tavily → Firecrawl → SearXNG; per-provider timeout 20s.

### Todo list

- Reproduce
- Fix core
- Regression test
- Verify on lab/VPS

### Prevent recurrence

Never let one Hermes turn hold the Zalo FIFO without a hard deadline. Keep
search provider timeouts short enough that failover finishes inside the turn budget.

## 18:50 — PDF/txt “created” but never sent on Zalo

### Symptom

User asked to create a PDF and a text file with content `1`. Bot replied that
files were created; Zalo never received an attachment.

### Root cause

1. Hermes tried ambiguous skill name `pdf` (3 collisions) then `pip`/`uv`
   install of `pypdf` failed (externally managed Python). No file in `media/out`.
2. Model still answered as if creation succeeded.
3. Omni combos were filled with OpenCode Free by first-setup (unwanted; 503s).

### AI decision

Backfilled from legacy log. At fix time: prioritize durable core change over VPS hotpatch; align classify/skills when intent routing was involved.

### Fix (core)

- Skills `file-gen` / `documents` / `media-out`: use Dispatcher
  `POST /v1/office-file` only; never local pdf skill / pip.
- Compose default `OFFICE_FILE_GEN=1`; empty Zalo caption on office deliver.
- first-setup clears `hermes` and `classifier` to empty member lists.

### Todo list

- Reproduce
- Fix core
- Regression test
- Verify on lab/VPS

### Prevent recurrence

Office create must go through Media Worker office API. Never claim success
without `"ok":true` / autosend. Do not auto-populate OpenCode into chat combos.

## 19:30 — PDF claim + gpt-oss-120b request storm

### Symptom

User: “tạo 1 file pdf và điền vào số 1”. Bot: “Đây là file PDF… (File được
gửi kèm)” but Zalo had no attachment. OmniRouter showed many
`openrouter/openai/gpt-oss-120b` (and groq) turns with huge tool lists.

### Root cause

1. Three skills still registered as `name: pdf` (SoT + official + Hermes
   `productivity/` clone). `skill_view('pdf')` refused (ambiguous).
2. Agent fell back to local pdf scripts → missing `reportlab` → pip/uv
   install loops. Each failure = another chat.completions call (~20+ tools
   in the body) → Omni “plenty of requests” to gpt-oss-120b.
3. Model narrated success without `"ok":true` / file in `media/out`.
4. `file-gen` already pointed at Dispatcher office-file, but the skill
   index still advertised “Create… PDF files” under name `pdf`.

### AI decision

Backfilled from legacy log. At fix time: prioritize durable core change over VPS hotpatch; align classify/skills when intent routing was involved.

### Fix (core)

- Rename office SoT skills to `pdf-tools-local` / `docx-tools-local` /
  `xlsx-tools-local` (and `official-*`); descriptions defer to `file-gen`.
- `hermes-replica-entry.sh` deletes category clones under
  `productivity|documents/{pdf,docx,xlsx}` after skill overlay.
- Unit `office_skill_collision_unit.py` forbids reserved names `pdf|docx|xlsx`.

### Todo list

- Reproduce
- Fix core
- Regression test
- Verify on lab/VPS

### Prevent recurrence

Never ship multiple skills with the same frontmatter `name`. Chat
create-and-send must only go through Dispatcher `/v1/office-file`. Do not
claim delivery without `"ok":true` or autosend of a real `media/out` file.

## 19:55 — SOUL blocked; empty session; wrong PDF/image content

### Symptom

After Hermes recreate: canned “Chào bạn /help” intro (forgot chat). PDF “điền
số 1” contained the instruction sentence. “5 dòng hello” image was an unrelated
photo (sana diffusion), not five lines of hello.

### Root cause

1. Hermes threat scan matched SOUL “do not tell the user…” → `deception_hide`
   → entire SOUL replaced with a BLOCKED placeholder.
2. Gateway transcript lived under per-replica `sessions.json`; recreate →
   msgs:0. Valkey session service was not hydrating the next turn.
3. `parse_office` missed `chứa số 1`; agent-rewritten prompts became the PDF
   body. Text-poster left “hello và gửi cho tôi”; agent skipped poster mode
   and called diffusion.

### AI decision

Backfilled from legacy log. At fix time: prioritize durable core change over VPS hotpatch; align classify/skills when intent routing was involved.

### Fix (core)

- Rewrite SOUL without the deception trigger phrase.
- Zalo `session_memory`: hydrate inbound + append outbound via `SESSION_URL`.
- Harden office/text-poster parsers; Zalo `media_shortcuts` for clear create
  intents (Dispatcher only).

### Todo list

- Reproduce
- Fix core
- Regression test
- Verify on lab/VPS

### Prevent recurrence

Never put “do not tell the user” in SOUL. Short-term chat SoT is Session/Valkey.
Exact text posters and simple office creates must not depend on the LLM
rewriting the prompt.

## 20:25 — Đặt lịch no reply (classifier 503 + queue timeout)

### Symptom

User: “đặt lịch chạy một lần lúc 20:07/20:17 với nội dung…”. No Zalo reply;
schedule never stored (`jobs.json` empty / no new rows).

### Root cause

1. Omni combo `classifier` returned 503 “all upstream accounts are inactive”
   (~50ms) but was **not** skipped (only 401/403/404/429 were).
2. Failover to `hermes` hit ReadTimeout (classify `timeout_s=60`).
3. Hermes turn then hit Zalo queue turn timeout (150s) → no useful reply;
   Valkey `gate:ans` / `gate:qwork` could stay occupied.
4. Schedule heuristic explicitly returned `None` for “đặt lịch”, so LLM failure
   did not fall back to a storeable cron plan.

### AI decision

Backfilled from legacy log. At fix time: prioritize durable core change over VPS hotpatch; align classify/skills when intent routing was involved.

### Fix (core)

- Skip classify combos on 502/503; shorten classify timeout to 15s.
- Deterministic schedule heuristic for once/daily `lúc HH:MM` (early + fallback).
- Ops: clear stuck answering/queue keys for the thread when applying.

### Todo list

- Reproduce
- Fix core
- Regression test
- Verify on lab/VPS

### Prevent recurrence

Dead Omni classify combos must not burn the full Zalo turn budget. Clocked
“đặt lịch” must store via heuristic when LLM classify is unavailable.

## 20:40 — Classifier 400: CF models want prompt/text/audio

### Symptom

Classify `model=classifier` with OpenAI `messages` returned CF AiError 400:
required `prompt` / `text` / `audio`. Logs showed Cloudflare AI, not Codex chat.

### Root cause

1. Combo `classifier` members were (or remapped to) Workers AI models that are
   not chat/completions-capable; Omni RR tried several and each 400’d.
2. Our classify only skipped 401/403/502/503 — not 400 — so it waited on the
   dead combo longer than needed.
3. Valkey `[Prior conversation]` was prepended before classify, so the current
   ask (and schedule wording) was buried under older PDF/image turns.

### AI decision

Backfilled from legacy log. At fix time: prioritize durable core change over VPS hotpatch; align classify/skills when intent routing was involved.

### Fix (core)

- Skip classify combo on HTTP 400 and AiError schema bodies; failover to `hermes`.
- `strip_prior_for_classify` before LLM/heuristic.

### Todo list

- Reproduce
- Fix core
- Regression test
- Verify on lab/VPS

### Prevent recurrence

Keep only **chat** models in the `classifier` combo (same class as `hermes`).
Do not add CF translation / ASR / vision-only / prompt-only models.
