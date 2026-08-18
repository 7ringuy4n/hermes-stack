# Change history

## 2026-08-18 09:30 +07 — copy: user-facing lịch/schedule (not cron) + queue docs

- Skills/zalo-api: user-facing text uses **lịch** / **schedule**; avoid **cron** / **cron job** in Zalo replies and admin schedule list.
- `messages/README.md`: documents `queue.full` default and `ZALO_INBOUND_QUEUE_MAX=20` cap behavior.

## 2026-08-18 09:25 +07 — feat: Low/Medium OmniRouter default + !zalo schedule list

- `profile.sh`: `ENABLE_OMNIROUTER` default **1** on **Low** and **Medium**; **High** stays **0** (opt-in via `.env`).
- Zalo admin: `!zalo schedule list` (alias `!zalo cron list`) runs `hermes cron list` in Hermes and shows user jobs (filters internal optimize/session crons; cap `ZALO_SCHEDULE_LIST_LIMIT`).
- Tests: `defaults_profile_unit.py`, `schedule_list_unit.py`. Docs: `DEFAULTS.md`, `06-model-routing.md`, case 21.
- zalo-api Docker image includes `schedule_list.py` (fixes crash loop after first deploy).

## 2026-08-18 09:10 +07 — fix: compound queue — `Đã xong.` only after last part

- Multi-part Zalo (image + prices, etc.): media turn sends the file **only**; `Đã xong.` / `Done.` is deferred until **after the last queued part** (not between parts).
- Removed remaining “banter OK” tone from temp `common-rules`; aligns with `communication/friendly-response`.
- Copy: `messages/ux.json` → `media.done`. Skills/media-out + zalo-channel updated.

## 2026-08-18 09:05 +07 — feat: default friendly-response + Vietnamese people-terms skills

- Mounted as default request/response: `communication/friendly-response` (no banter/insults/blame; result → next step) and `communication/vi-people-terms` (context for người / đàn ông / phụ nữ / con / thằng / đứa; full dictionary in `reference.md`).
- Wired from SOUL, answering, chat-style, zalo-channel, translation, and zalo-api response policy (replaces “banter is OK”).
- Sources: hermes plan docs *AI Agent — Friendly User Response Skill* and *Vietnamese Semantic Dictionary — People, Gender, and Human References*.

## 2026-08-18 08:57 +07 — ops: rolling deploy Valkey inbound FIFO + busy-interrupt filter

- Backup verified, source synced, zalo-api rebuilt, Hermes replicas restarted (no destroy).
- Hermes reaches 9router and model-router. On-host files `inbound_queue.py` present.

## 2026-08-18 08:45 +07 — feat: Valkey inbound FIFO for compound + rate-limited Zalo

- Compound and follow-up Zalo turns enqueue on Valkey (`gate_valkey` list per thread). A drain task runs **one Hermes turn at a time** so overlapping `handle_message` cannot inject busy-interrupt UX.
- Rate-limit: user gets the queued notice **once**, the message is **kept** and processed later (not dropped). Cap `ZALO_INBOUND_QUEUE_MAX` (default 20). Valkey down → fail-open sequential in-process turns.
- Copy lives in `hermes/main/messages/ux.json` `queue.*` (env override). Daily numbered lists still stay **one cron job**; immediate 3-item lists split onto the FIFO (case 23).
- Tests: `inbound_queue_unit.py` (separate process from case 16).

## 2026-08-18 08:25 +07 — fix: drop Zalo busy-interrupt UX; multi-task cron runs every item

- Hermes gateway “Interrupting current task” / First-time `/busy` tips are dropped on Zalo (`gateway_noise.py`). They are not in this repo’s source — they come from upstream Hermes when a new turn starts mid-run.
- Immediate compound still splits, but the adapter waits until the current part has actually sent (then a short gap) before the next `handle_message`, and holds the answering slot for the whole sequence.
- Numbered **daily/cron** lists stay **one job** (wakeup + weather image + fuel in one payload). Skills require completing every item after media; do not register parallel crons at the same clock.
- Tests: `gateway_noise_unit.py` + schedule keep-whole fixture in case 16 unit; new case `22-zalo-busy-cron-multi`.

## 2026-08-18 08:17 +07 — ops: rolling deploy numbered Zalo split + zalo-api policy

- Backup verified, source synced, zalo-api rebuilt, Hermes replicas restarted (no destroy).
- On-host unit: numbered `1 …` / `2.Sau đó` split PASS. Hermes reaches 9router and model-router; Traefik recovered after restart (brief 503 while replicas came up).

## 2026-08-18 08:10 +07 — fix: numbered Zalo lists (`1 …` / `2.Sau đó`) + media-out vs compound

- Splitter missed live style `yêu cầu:` + `1 vẽ…` + `2.Sau đó …` (no `1.` / no space after `2.`), so one Hermes turn ran **image + fuel**.
- `media-out` / response policy “after a file, one short line, no recap” then dropped request 2. **Not** the summarization skill (`tóm tắt`) — it was the file-result policy on an unsplit turn.
- Splitter now accepts numbered lines `1 task` / `2.Sau đó` (indexes 1–20, must include 1 and 2). Skills/SOUL/zalo-api: media-out applies **per turn** after split. Unit fixture added (case 16).

## 2026-08-18 07:50 +07 — ops: High lab deploy matches profile defaults (Omni/Grafana off)

- `test/scripts/deploy_high.py` no longer force-enables OmniRouter, Grafana, Prometheus, Loki, or Alloy. Defaults are **0** (same as `profile.sh`). Opt in with `ENABLE_OMNIROUTER=1` / `ENABLE_GRAFANA=1` (Grafana pairs Prometheus; Loki pairs Alloy).
- No Hermes fire-and-forget memory/log rewrite.

## 2026-08-18 07:45 +07 — test: Grafana pairing + router defaults; simple-chat SLO 5s

- **Grafana (when on):** case `20-grafana-component-integration` — Prometheus jobs + `assistant_service_up` for each deployed target; 9Router via **TCP** (UI `/health` 404); Omni scrape only if OmniRouter is on. Stack-exporter + High compose `HEALTH_TARGETS` include `9router`.
- **Defaults:** case `21-defaults-routers-connected` — 9Router always on; `ENABLE_MODEL_ROUTER` default 1; `ENABLE_OMNIROUTER` / Grafana default **0**. `deploy_high.py` no longer forces Omni/Grafana on (opt-in env flags).
- **Latency:** simple host-side chat **> 5s is FAIL** (case 17). Previous lab p95 ~9s is an improvement ticket, not a pass.
- Docs: `DEFAULTS.md` matches `profile.sh` (Low Traefik default on; Medium Hermes×1; High OmniRouter default off). Monitor + model-routing docs point at cases 20–21.

## 2026-08-18 07:35 +07 — ops: rolling VPS deploy + SSH labs 15–19

- Backup stamp `20260818_072647` verified, then rolling sync (no destroy): zalo-api rebuilt, Hermes replicas restarted, skills/plugins/SOUL bind-mounts live.
- Labs (separate processes): 15 TZ unit PASS; 16 compound split PASS; 17 chat p50 ~4s / p95 ~9s PASS; 18 search backend=searxng (Tavily/Firecrawl keys unset) PASS; 19 YARA RISK + ClamAV BLOCKED PASS. Ingest `SECURITY_URL` still unset (documented gap).
- Case 19 lab polls av-gateway session ready (async SCANNING is not a false clean).

## 2026-08-18 07:15 +07 — fix: Zalo schedule TZ, compound messages, stack-watch backoff, lab cases 15–19

- **Schedule TZ:** `architect/tools/schedule_tz.py` — at 05:58 local, daily 06:00 is **today** not tomorrow; skill `core/scheduling` + zalo-api response policy.
- **Zalo compound messages:** `hermes/main/plugins/zalo/multi_request.py` splits `tin nhắn 1:` / `tin nhắn 2:` (including mid-sentence); adapter runs each part sequentially.
- **Zalo safety:** skills `communication/zalo-channel`, `core/safety`, `SOUL.md`, zalo-api policy — user errors only `Phiên làm việc bị gián đạn…`; no `/help`, channel dumps, or host secret scans.
- **stack-watch:** exponential backoff (90s→3600s), degraded after 5 fails, optional `NOTIFY_URL` alert — no infinite restart loop.
- **Tests:** cases `15-schedule-timezone` … `19-file-pipeline-security`; unit scripts for TZ/multi-request/web-search; SSH labs for latency SLO and file/AV matrix. `test/RULES.md` §13–15 updated.
- **Web search default:** Medium/High `WEB_BACKENDS=tavily,firecrawl` round-robin; **SearXNG always appended** as fallback (`architect/models/dispatcher/app.py`).
- **File security matrix:** Zalo inbound → AV only; dispatcher outbound → security-manager when `SECURITY_URL` set; ingest scan not wired (documented in case 19).

## 2026-08-17 18:00 +07 — release: v0.5.4

- P0 skills + exact text-poster; local ONNX embedding fallback; learn unique by path.
- Backup+verify required before destroy / switch-profile / add-components / update.
- Skills lab cases 12–14; High Notify + OmniRouter + monitor.

## 2026-08-17 17:55 +07 — ops: backup+verify before destroy / upgrade / downgrade

- `run.sh destroy`, `switch-profile`, `add-components`, and `update` run `backup` then `verify` and abort if either fails.
- Lab deploy scripts no longer swallow `destroy` failure (`|| true`).
- `verify` live-checks Postgres/Valkey when those containers are running.

## 2026-08-17 17:48 +07 — ops: High deploy with Notify + OmniRouter + monitor

- Lab helper `test/scripts/deploy_high.py`: destroy current profile, High up with Notify, OmniRouter, Grafana/Loki/Prometheus/Alloy.
- Isolation stays default off (AV / sandbox / LLM judge). Zalo off unless requested.
- Prune stale `created`/`dead` containers before `up` (compose missing-container race).

## 2026-08-17 17:35 +07 — test: skills lab PASS (cases 12–14)

- Medium lab: 52 skill docs learned into Qdrant; local ONNX embedding fallback.
- Case 13 text-poster: `backend=text-poster`, n=10, empty prompt HTTP 400.
- `test/scripts/skills_lab.py`: Windows console UTF-8 safe output.

## 2026-08-17 16:50 +07 — embedding: local ONNX fallback for skill learn

- Embedding service uses local `BAAI/bge-small-en-v1.5` (fastembed) when 9Router has no embedding credentials/models.
- Ingest recreates `knowledge_chunks` if vector size changes.
- Skills lab rebuilds embedding on Medium destroy/redeploy.

## 2026-08-17 16:20 +07 — ingest: learn unique docs by path

- `learn/scan` no longer treats every `SKILL.md` as the same document; skip/index keys use relative path.
- Markdown/text files are read as UTF-8 during learn (not OCR-only).
- post-ready-learn mirrors skills under `docs/skills/<relative-folder>/`.

## 2026-08-17 16:10 +07 — test: skills lab (Medium auto-learn + text-poster)

- Cases `12-skills-auto-learn`, `13-image-text-poster`, `14-knowledge-internal-rag`.
- Script `test/scripts/skills_lab.py`: destroy Medium, sync skills, post-ready-learn, mount/catalog/poster probes.
- `test/RULES.md` §13 fail events + §15 case index updated.

## 2026-08-17 16:00 +07 — skills: P0 sources + exact text posters

- **Image:** dispatcher `text-poster` path (Pillow) for quoted text / N lines — skips LLM refine and diffusion; `image-gen` skill updated.
- **Skills:** vendored Anthropic skill-creator, obra superpowers (debug/TDD/git/verify), Trail of Bits audit plugins; Hermes wrappers under `core/`, `knowledge/`, `coding/`, `communication/`.
- **Not vendored:** `canvas-design` (art-first; breaks exact text). Kodus/VoltAgent remain catalogs.
- `post-ready-learn` ingests category subfolders; `vendor/CATALOG.md` updated.

## 2026-08-17 15:25 +07 — release: v0.5.3

- Isolation boundary: sandbox/LLM judge/AV off by default; judge CLEAN cannot allow; VPN-only Traefik; socket-proxy only with sandbox profile.
- Ops: `switch-profile` / `add-components` (archive first); drop disabled-profile containers on up.
- Tests: run-05 two-pass; cases 09–11 (Zalo mixed media delay, isolation risks, profile upgrade/downgrade).

## 2026-08-17 15:20 +07 — test: run-05 two-pass (profile switch + mixed media)

- Pass 1: High/Zalo deploy; case 11 upgrade/downgrade + add/remove notify; mixed media fail-event N=8 (text 503).
- Pass 2: Quick start only; isolation PASS; profile dry-run; mixed media N=2 ok / N=4 one text timeout.
- Reports: `test/reports/run-05-two-pass/SUMMARY.md`. `RULES.md` §5/§14–15.

## 2026-08-17 15:05 +07 — fix: drop disabled-profile containers on up

- `run.sh up`/`update` now `docker rm` notify/alert-watch (and other off profiles). Compose `--remove-orphans` does not stop services that were started with `--profile` and later disabled.
- first-setup-llm recreate: remove leftover `hexprefix_*hermes*` names that collide on `--force-recreate`. Do **not** pass `--remove-orphans` here (that compose set omits edge YAML and would drop Traefik/Gateway).

## 2026-08-17 14:55 +07 — test: profile switch case 11

- Case `11-profile-switch`: existing options, add/remove `ENABLE_NOTIFY`, High↔Medium, bogus-tier fail event; script `test/scripts/profile_switch.py`.
- `test/RULES.md` §13–15.

## 2026-08-17 14:50 +07 — ops: switch-profile / add-components archive first

- All tiers can upgrade or downgrade. `bash run.sh switch-profile <low|medium|high>` dumps current options, stamps a DR backup, writes `ASSISTANT_PROFILE`, then `up --remove-orphans`.
- `bash run.sh add-components KEY=VAL` same archive-then-apply for optional flags (Zalo, OCR, …).
- Stamp includes `config/profile-options.env` + `change-intent.txt`; undo via `restore` of `BACKUP_DIR/PRE_CHANGE`.
- Docs: `docs/00-profiles.md`, `docs/02-commands.md`.

## 2026-08-17 14:45 +07 — test: run-04 two-pass lab complete

- Pass 1: sync+deploy High/Zalo; fixes post-ready-learn/stack-watch Traefik `/health`, mixed-media auth (Traefik+`API_SERVER_KEY`), AV/sandbox env precedence.
- Pass 2: README Quick start only (no source edits); isolation risks PASS; mixed media N≤4 all-success with delay tables.
- Reports: `test/reports/run-04-two-pass/SUMMARY.md`; `cases/09` + `RULES.md` §5/§13/§14 updated for Traefik text path and run-04 findings.
- `lab_two_pass.py`: Traefik probe uses `/health` (root `/` is 404).

## 2026-08-17 14:20 +07 — test: Zalo mixed media concurrent + isolation risks

- New cases `09-zalo-concurrent-media` (text+image gen, delay p50/p95/max) and `10-security-isolation-risks` (no sock, judge/sandbox off, VPN-only, EICAR via YARA).
- `test/RULES.md` §5/§7/§13–15; lab two-pass defaults sandbox/judge off; README Traefik `local`.

## 2026-08-17 14:15 +07 — security: isolation boundary (sandbox/judge off, VPN-only)

- High defaults: `SECURITY_SANDBOX=0`, `SECURITY_LLM_JUDGE=0`, `ENABLE_ANTIVIRUS=0`; YARA + size/static remain isolation.
- LLM judge (if enabled) may only add RISK; CLEAN / skip / errors never allow and never fail-closed.
- docker-socket-proxy only with compose profile `sandbox` (`SECURITY_SANDBOX=1`); security-manager has no Docker API by default.
- Edge default `TRAEFIK_MODE=local` (VPN/localhost). Public/ACME remains explicit opt-in.
- Docs: `docs/SECURITY.md`.
- README Traefik default wording: `local` (VPN-only), matching `profile.sh`.
- post-ready-learn / stack-watch probe Traefik `/health` (root `/` is 404 by design).
- stack-watch: product `.env` wins over leftover `/data/assistant/.env` (stops AV/sandbox flags resurrecting).

## 2026-08-17 12:00 +07 — release: v0.5.2

- Security P0 hardening (gateway auth, SSRF, docker.sock/proxy, fail-closed).
- Ops: Hermes×2 Traefik/Gateway probes; check-medium restore; Zalo concurrent lab tests.

## 2026-08-17 12:15 +07 — fix: restore check-medium.sh corruption

- `scripts/main/check-medium.sh` had systematic `d`→`o` corruption (`/dev/null` → `/oev/null`, dispatcher → oispatcher); restored. Blocks Medium smoke / Zalo setup gate.

## 2026-08-17 12:05 +07 — fix: post-ready-learn probes Traefik when Hermes×2

- High (HERMES_REPLICAS≠1) has no host `:29119`; post-ready-learn and stack-watch now probe Traefik/API Gateway instead of the missing dashboard port.

## 2026-08-17 11:50 +07 — security: P0 hardening (gateway, SSRF, docker.sock)

- Gateway: require GATEWAY_API_KEYS; drop client header RL bypass; do not trust XFF by default; RL fail-closed with local limiter.
- security-manager: SSRF-safe scan-url; SECURITY_FAIL_CLOSED on High; sandbox via docker-socket-proxy (no raw sock on security-manager).
- zalo-api: remove docker.sock mount (host watches restart Hermes).
- Docs: docs/SECURITY.md.

## 2026-08-17 11:40 +07 — release: v0.5.1

- Docs/ops patch: zalo-api cutover, HTML architecture panels, Valkey/SPOF docs.

## 2026-08-17 11:35 +07 — docs/ops: zalo-api rename + HTML architecture panels

- Product rename: admin-api to zalo-api (compose profile zalo with ENABLE_ZALO). Legacy ADMIN_API_* env aliases kept in Hermes/plugin/zalo-api.
- Removed architect/admin-api; High no longer starts a separate admin-api. Docs/scripts/health probes updated.
- Architecture diagrams: mermaid replaced with HTML table panels (README + architect layer READMEs).

## 2026-08-17 11:20 +07 — docs: README navigability + architect system design

- Root README: New here?, Use cases, architecture panels, profile why, resilience/SPOF pointers, clickable doc links; Valkey (not Redis) wording.
- Each architect/*/README.md: System architecture (sits between / owns / HTML flow). Edge defaults corrected for v0.5.0 (Traefik + Gateway on).
- docs/03-architecture.md brief view: edge + model-router. docs/MULTI_NODE.md SPOF table. Env REDIS_URL documented as Valkey-compatible name.

## 2026-08-17 10:20 +07 — release: v0.5.0

- Bundle Model Router / optional OmniRouter, Traefik default all profiles, jobs contract, session locks, fail-event tests, log-archive 30d, Zalo/Hermes crash auto-heal.

## 2026-08-17 09:45 +07 — zalo: auto-start stopped proxy

- `zalo-watch` starts `zalo-proxy` when the container is exited. Host bridge `/health` can stay up while the proxy hop is down, which previously skipped heal.

## 2026-08-17 09:40 +07 — test: HTML summaries + fail-event rules

- Profile×mode SUMMARY tables are HTML. RULES.md §13: infected AV (EICAR), concurrency ramp until first fail, Hermes/Zalo auto-heal.
- stack-watch now restarts **exited/dead/unhealthy** Hermes replicas (crash recovery). Probe-fail still does not bounce healthy Hermes.

## 2026-08-17 09:20 +07 — test: profile matrix reports (no host/account)

- `test/` layout: cases, fixtures, scripts, reports/run-01 and run-02 per RULES.md.
- Reports omit hostnames, IPs, and account names. High profile is the stack left running after the matrix.

## 2026-08-17 09:10 +07 — ops: post-restore memory reconnect + log-archive timer

- Restore now restarts Postgres clients (memory/ingest/embedding) after stack up so pooled connections survive `pg_terminate_backend`.
- Memory pool uses `ConnectionPool.check_connection`. Daily `assistant-log-archive.timer` (01:15, retention `LOG_RETENTION_DAYS=30`).

## 2026-08-17 08:45 +07 — ops: short alerts for disabled media/policy/AV/VPN

- hermes/main/messages/ops-alerts.json + dispatcher messages/en.json for admin-editable short errors.
- Image gen empty backends returns editable 503 text (not hardcoded only).

## 2026-08-17 08:20 +07 — arch: v0.5.0 router layer (OmniRouter optional, profiles, jobs)

- Model Router: hybrid coding/general routing → 9router / OmniRouter / fallback pool; clear `no_model_available`.
- OmniRouter optional (`ENABLE_OMNIROUTER`, compose profile `omnirouter`); Traefik default all profiles with `TRAEFIK_MODE` public→fail-soft local.
- Hermes replicas: default 1, High=2 (one node); Medium=1. Session Valkey locks; jobs OCR/embed/filegen + idempotency/DLQ marker.
- Gateway API key auth + body limit when `GATEWAY_API_KEYS` set. Log archive 30d; OpenVPN client `.ovpn` export to home.
- Docs: `docs/06-model-routing.md`, `docs/MULTI_NODE.md`.

## 2026-08-17 07:30 +07 — release: v0.4.1

- Ship Mem0 purge leftovers, Zalo SSE heal after restore, stack-watch Hermes scale preserve, Zalo silent auto-sethome.

## 2026-08-17 07:25 +07 — zalo: silent auto-sethome (stop /sethome spam)

- First chat no longer gets Hermes “📬 No home channel… /sethome” when home is unset.
- Zalo adapter silently claims `ZALO_HOME_CHANNEL` from the first allowed DM (`ZALO_AUTO_SETHOME=1` default; DM-only by default).
- Set `ZALO_AUTO_SETHOME=0` to require manual `/sethome` or a pre-set `ZALO_HOME_CHANNEL`.

## 2026-08-17 07:15 +07 — backup-restore: lab retest + compose profiles on restore

- VPS lab stamp `20260817_070637`: backup → verify → restore + canary OK.
- Pre-restore Zalo had `sseClients=0`; post-restore `heal-zalo-sse` restored `sseClients=1` / loggedIn.
- Volume restore stops Traefik; restore compose now passes the same `--profile` flags as `run.sh` so Traefik/gateway/Zalo come back.
- **stack-watch:** `compose up` now keeps `--scale hermes=$HERMES_REPLICAS` (was collapsing Hermes×2 →×1 every 2 min and killing Zalo SSE). Skip Grafana probe when monitor off; skip host `:29119` probe when replicas≠1.

## 2026-08-17 07:05 +07 — memory: purge Mem0 leftovers; Zalo SSE heal after restore

- Deleted architect/memory/mem0; scrubbed Mem0 from docs, monitor health targets, and Grafana queries.
- Session metrics now scan conversation_active:* (Valkey session store).
- Backup excludes zalo_owner*; restore clears lock and runs scripts/main/heal-zalo-sse.sh.
- zalo-watch: on sseClients=0, clear owner lock and restart proxy/Hermes (fixes silent bot after DR).

## 2026-08-16 20:15 +07 — release: v0.4.0

- Cut 
elease/v0.4.0 from main + current develop (compose under docker/, High DR + Zalo singleton, hardware docs, Deploy-High, agent-ops).

## 2026-08-16 20:15 +07 — docs: hardware specs + backup/restore test notes (MR-ready)

- Added docs/HARDWARE.md: lab-tested High (Ubuntu 24.04, 4 vCPU / 16 GiB / ~200 GB) and recommended minimum/comfortable sizes per profile.
- architect/backup-restore/README.md: restore behavior + successful round-trip matrix (stamp 20260816_195940).
- Linked from root README, docs/README.md, docs/00-profiles.md, docs/02-commands.md, docs/04-component-flows.md, docker/README.md.

## 2026-08-16 20:10 +07 — backup-restore: VPS round-trip + High path fixes

- Restored corrupted backup.sh; defaults BACKUP_DIR=/data/assistant/backups, HERMES_DATA_DIR=/data/assistant.
- Restore uses compose (not missing generate/deploy); Postgres skips DROP/CREATE ROLE for session user; Qdrant per-collection snaps.
- Hermes scale-aware; exclude backups/ + replicas/ from hermes tar; schedules enable only existing timers.
- VPS test stamp 20260816_195940: backup + verify + restore OK; Hermes x2 up.

## 2026-08-16 20:05 +07 — docs: recommend fail2ban on clean Ubuntu

- README: host-hardening note + install snippet for fail2ban (SSH jail) on fresh Ubuntu VPS.

## 2026-08-16 20:00 +07 — zalo: stale owner reclaim (entry + adapter)

- If the Zalo-owner Hermes replica dies, leftover zalo_owner blocked SSE (sseClients=0).
- Entrypoint scrubs unreachable owners before election; adapter can reclaim the lock when owner DNS is gone.

## 2026-08-16 19:58 +07 — zalo: owner lock enforced in adapter (survive s6 env)

- Compose/s6 can restore ZALO_PLUGIN_URL on every replica after entrypoint clears it.
- Adapter connects only when hostname matches HERMES_SHARED_DATA/zalo_owner.

## 2026-08-16 19:55 +07 — zalo: empty ZALO_PLUGIN_URL disables adapter (no default bridge)

- Explicit empty env no longer falls back to a default bridge URL (prevents dual SSE on Hermes x2).

## 2026-08-16 19:50 +07 — hermes: Zalo singleton lock (no bare hermes DNS)

- Do not treat bare Compose DNS alias hermes as Zalo owner when scaled.

## 2026-08-16 19:45 +07 — ops: High VPS redeploy (no monitor; Hermes x2)

- Destroyed prior medium stack; deployed High with monitor flags off; Traefik + API Gateway; image smoke + gateway concurrency.

## 2026-08-16 19:40 +07 — arch: compose under docker/; High without monitor; Deploy-High

- Moved all docker-compose*.yml into docker/ (run.sh uses --project-directory).
- Observability gated by compose profile monitor; Deploy-High.ps1 + deploy_high_vps.py for phased SSH.

## 2026-08-16 11:58 +07 — release: v0.3.0

- Cut `release/v0.3.0` from `main` + current `develop` (Mem0 removal, edge defaults, Hermes scale 2, per-replica home + Zalo singleton, MR-to-main workflow).

## 2026-08-16 11:57 +07 — hermes: fix replica entrypoint (gateway run via dispatch)

- `hermes-replica-entry.sh` now execs image `entrypoint-dispatch.sh` with `gateway run` (raw `/init gateway run` → exit 127; empty args → interactive CLI exit).
- Resolve Compose service name from `/etc/hosts` so Zalo SSE stays on `*-hermes-1` when hostname is the container id.

## 2026-08-16 11:35 +07 — hermes: per-replica home for scale 2 + Zalo singleton

- `hermes-replica-entry.sh`: each scaled container uses `/opt/data/replicas/<hostname>` (avoids `gateway.lock` race).
- Zalo adapter only on `*-hermes-1` (other replicas clear `ZALO_PLUGIN_URL`).
- Includes API bind fix (`API_SERVER_HOST=0.0.0.0`) for Traefik after scale.

## 2026-08-16 11:25 +07 — edge: Hermes API bind for Traefik after scale

- Hermes `API_SERVER_HOST=0.0.0.0` + `API_SERVER_KEY` so Traefik can reach `hermes:8642` (upstream default was loopback-only).
- Traefik health check path `/health`.

## 2026-08-16 09:35 +07 — hermes: default scale 2 on medium|high

- `HERMES_REPLICAS` default **2** on medium/high, **1** on low (`profile.sh` + `run.sh --scale`).
- Removed fixed `container_name: hermes`; host ports only when replicas=1 (`docker-compose.hermes-hostports.yml`).
- Traefik continues to use service DNS `http://hermes:8642` (LB across replicas). Watch scripts restart all matching hermes containers.

## 2026-08-16 09:30 +07 — memory: remove Mem0; edge on Med/High; coding skills

- **Removed Mem0** from Must compose; LTM = Memory Manager + Postgres (+ optional Qdrant). Compact no longer calls mem0.
- **Traefik + API Gateway** default **ON** for `medium`/`high`, forced **OFF** on `low` (set `ENABLE_*=0` in `.env` to disable on Med/High).
- **Coding skills** vendored (skills-only, no coding worker): `hermes/main/skills/coding` + `vendor/mattpocock/*` + `vendor/ui-ux-pro-max/*` with LICENSE/ATTRIBUTION.
- No VPS auto-deploy from this change.

## 2026-08-16 09:25 +07 — docs: require MR for all merges to main

- `docs/GIT.md` + `.cursor/rules/git.mdc`: never push/merge directly to `main`; always open a PR (`release/*` or `hotfix/*` → `main`).

## 2026-08-16 09:20 +07 — docs: git workflow release model

- `docs/GIT.md`: `feature/*` → `develop` → `release/*` → `main`; `fix/*` / `hotfix/*`.
- Release from `main`, cherry-pick only production-ready features; MR titles `[TYPE][LAYER]` / `[RELEASE]`.
- Updated `.cursor/rules/git.mdc`.

## 2026-08-16 09:15 +07 — edge: Traefik Let's Encrypt (optional ACME)

- `TRAEFIK_ACME_ENABLED=1` selects compose profile `traefik-acme` (HTTP-01, `:443`, redirect).
- Requires `TRAEFIK_ACME_EMAIL` + `TRAEFIK_ACME_DOMAIN`; render via `scripts/main/render-traefik-acme.sh`.
- Default remains LAN/`127.0.0.1` without ACME (no public inbound). Staging CA supported.

## 2026-08-16 09:05 +07 — edge: Traefik, API Gateway, OpenVPN stubs

- Optional `docker-compose.edge.yml` via `ENABLE_TRAEFIK` / `ENABLE_API_GATEWAY` / `ENABLE_OPENVPN` (default **0**; VPN/LAN bind `127.0.0.1` only).
- API Gateway: Valkey global rate limit; coding paths/header skip RL; admin messages in `messages/en.json`.
- Traefik file provider LB → `hermes:8642` (ready for Hermes × N server list).
- OpenVPN compose stub + PKI docs; Zalo still bypasses Gateway.
- Docs: `docs/05-edge-networking.md`; reference copy under `referrence/`; `Apply-EdgeUpdate.ps1`.

## 2026-08-16 08:25 +07 — docs: git workflow rules

- Added `docs/GIT.md`: branch layout (`main` → `develop` → `feature/<layer>/<slug>`), PR title `[KIND][LAYER][TYPE]`, commit/changelog/push rules.
- Added `.cursor/rules/git.mdc` (always apply) pointing at `docs/GIT.md`.

## 2026-08-16 08:15 +07 — zalo/stack-watch: stop Hermes restart storm

- **Cause:** `assistant-zalo-watch` restarted Hermes when `sseClients==0` (miss limit too low); `stack-watch` also bounced Hermes on probe fail / post-boot flicker → multi-hour restart loops.
- **zalo-watch.sh:** default `ZALO_WATCH_RESTART_HERMES=0` (bridge-only on sse=0); SSE miss≥15; cooldown 1800s; writable `/watch` state (sudo/chown fallback).
- **stack-watch.sh:** default `STACK_WATCH_RESTART_HERMES=0`; boot grace 600s; heal 9router/dispatcher without thrashing Hermes; project/label fallbacks for lab compose names.
- Opt-in old behavior: set `ZALO_WATCH_RESTART_HERMES=1` / `STACK_WATCH_RESTART_HERMES=1`.

## 2026-08-15 17:25 +07 — skills: new+docs/web/comfy in main; live-matched in temp

- Compared to ighthawk-lab/hermes_backup/skills\.
- **main:** documents/markdown/pdf/docx/xlsx/file-gen, comfyui, tavily/firecrawl/searxng (+ official + vendor packs).
- **temp:** live-matched Must/Medium skills (chat, research, mode-router, …).

## 2026-08-15 17:20 +07 — default main/; live skills parked in hermes/temp

- SCRIPTS_DIR / HERMES_DIR default to scripts/main and hermes/main.
- Live-server skill set moved: hermes/main/skills/* → hermes/temp/skills/ (gitignored). Main keeps _example only until promote.

## 2026-08-15 17:15 +07 — hermes main/temp + rename llm/vendor

- `hermes/main/` product (skills, plugins, messages, config); `hermes/temp/` local drafts (gitignored).
- Image backends renamed: **paid1 → llm**, **paid2 → vendor** (`IMAGE_BACKENDS=llm,vendor,comfy-cpu,comfy-gpu`).
- `IMAGE_LLM_PROVIDER`: openai | gemini | deepseek | custom. Legacy `IMAGE_PAID1_*` / `paid1` still accepted.

## 2026-08-15 17:00 +07 — paid2 providers + official skills

- `IMAGE_VENDOR_PROVIDER` (was PAID2): `fal` | `pollinations` | `fluxai` | `openai` | `http`.
- Hermes skills under `hermes/main/skills/`: official pdf/docx/xlsx/comfyui/searxng-search; routers documents/tavily/firecrawl/searxng.

## 2026-08-15 16:45 +07 — /v1/image fallback (llm → vendor → ComfyUI)

- Dispatcher chain: **llm** → **vendor** → **comfy-cpu** → **comfy-gpu** (when `COMFYUI_HAS_GPU=1`).
- Medium compose: `comfyui-cpu` always; `comfyui-gpu` via profile `comfy-gpu`.
- Workflows: `architect/models/dispatcher/comfy_workflows/`. Low forces `IMAGE_BACKENDS` empty.

## 2026-08-15 16:35 +07 — post-ready learn skills|docs (all profiles)

- After Hermes + 9Router ready (`run.sh up` / `update` / `first-setup-llm`): if `hermes/main/skills` has real skills, sync markdown → `$ASSISTANT_DATA_DIR/docs/` and ingest `learn/scan`.
- Ingest: `LEARN_DOCS_ROOT=/data/assistant/docs`; `LEARN_REQUIRE_APPROVE=0` auto-ingests on scan (no approve).
- Optional inbox: `hermes/main/setup/`, extra docs: `hermes/main/docs/`. Command: `bash run.sh post-ready-learn`.

## 2026-08-15 16:10 +07 — office PDF (reportlab + DejaVu)

- Dispatcher can create real `.pdf` / `.docx` / `.xlsx` (not silent `.txt` fallback).
- Adds `reportlab`, `openpyxl`, `python-docx`; image installs `fonts-dejavu-core` for Vietnamese PDF.
- Synced from verified assistant fix; Low still defaults `OFFICE_FILE_GEN=0`.

## 2026-08-15 15:40 +07 — rename GDrive → CloudDrive (rclone)

- `ENABLE_CLOUDDRIVE`, `CLOUDDRIVE_*`, service `clouddrive-sync`, command `backup-sync-clouddrive`; mirror `/data/clouddrive`. Still rclone under the hood.

## 2026-08-15 15:35 +07 — High profile compose + OpenBao

- Added `docker-compose.high.yml`: OpenBao UI `:8200`, ClamAV/AV, security-manager, SIEM, authz, policy, admin-api, Grafana/Prom/Loki/Alloy, exporters; optional `notify` / `CloudDrive` compose profiles.
- `profile.sh` High: `ENABLE_NOTIFY` default **0**; OpenBao on; CloudDrive flag on.
- `scripts/main/first-setup-openbao.py` seeds API keys → `secret/assistant/api-keys` + `.env.openbao`; auto on `up`/`update`.
- `bash run.sh check-high`. Docs: README High, 00-profiles, DEFAULTS, NEXT.

## 2026-08-15 15:25 +07 — Medium timers auto on up/update

- `run.sh up` / `update` call `ensure_profile_timers` for `medium|high` (auto-learn, backup, compact). No separate `install-timers` step.

## 2026-08-15 15:20 +07 — Medium profile compose + smoke

- Added `docker-compose.medium.yml` (SearXNG, OCR, Jobs, jobs-worker); `run.sh` merges it for `medium|high`.
- `profile.sh`: Medium sets `WEB_BACKENDS` / `OFFICE_FILE_GEN`; Low forces web + file-gen off.
- Dispatcher: empty `WEB_BACKENDS` disables search (no accidental Low web); SearXNG fallback only when backends enabled.
- `scripts/main/check-medium.sh` + `bash run.sh check-medium`. Docs: README Medium, DEFAULTS, 00-profiles.

## 2026-08-15 15:05 +07 — split scripts/main vs scripts/temp

- Product ops → `scripts/main/` (`install-docker`, `first-setup-9router-hermes`); one-off deploy/probes → `scripts/temp/` (gitignored except README).
- `run.sh` paths updated.

## 2026-08-15 15:00 +07 — `run.sh update` after git pull

- Added `bash run.sh update`: rebuild/recreate compose from current tree, refresh 9Router→Hermes first-setup, prune disk. Workflow: `git pull` then `bash run.sh update`.

## 2026-08-15 14:55 +07 — combo round-robin + post-setup cleanup

- First-setup sets 9Router `comboStrategy` / `comboStrategies.hermes` to **`round-robin`** (`comboStickyRoundRobinLimit=1` = rotate each request).
- After successful first-setup: `docker builder/image/container prune` + clear `/tmp/assistant*` to free disk. (Code only — not pushed.)

## 2026-08-15 14:50 +07 — default 9Router combo renamed to `hermes`

- First-setup creates/updates combo **`hermes`** with all current OpenCode Free (`oc/*`) models; Hermes default model id = `hermes`.

## 2026-08-15 14:45 +07 — default LLM = OpenCode Free combo

- First-setup builds/updates 9Router combo with all current `oc/*` models (big-pickle first).
- Hermes default model id uses that combo (fallback). No OpenRouter key required for Low chat.

## 2026-08-15 14:40 +07 — first-setup: Docker install + 9Router Default Key → Hermes

- Added `scripts/install-docker.sh` (official `docker-ce` apt, `systemctl enable`, add user to `docker` group + `getent` verify).
- Added `scripts/first-setup-9router-hermes.py` — login 9Router, copy **Default Key** into `.env` / Hermes, default model `openrouter/auto` via `http://9router:20128/v1`.
- `deploy-test-low.py` installs Docker if missing, then runs first-setup after Hermes is up.
- Compose: `N9ROUTER_API_KEY` optional at interpolate time (`:-`) so first boot can fill Default Key after 9Router starts.

## 2026-08-15 14:20 +07 — deploy Hermes + 9Router on Low test host

- Synced compose to `[internal-host]`; extended root LV 13.5→27G (disk full blocked Hermes extract).
- Up: `9router` `:20128`, `hermes` gateway `:28642` + dashboard `:29119` (HTTP 302). Embedding `has_key=true`; dispatcher `n9router=true`.

## 2026-08-15 13:35 +07 — Low Must: Hermes + 9Router in compose

- Wired `9router` (`decolua/9router`, host `20128`) and `hermes` (`nousresearch/hermes-agent`, gateway `28642`, dashboard `29119`) as always-on Must services (no Traefik, no Zalo `depends_on`).
- Hermes → dispatcher OpenAI path; embedding/dispatcher get `N9ROUTER_API_KEY`; Low defaults `WHISPER_ENABLED=0`.
- Mounts: `HERMES_DATA_DIR` → `/opt/data`; repo `hermes/main/skills` + `messages` read-only.

## 2026-08-15 13:20 +07 — Low profile test deploy

- Synced tree to `/opt/assistant`, `.env` with test secrets, `ASSISTANT_PROFILE=low`.
- Stack up: postgres, redis, qdrant, memory, mem0, session, embedding, ingest, dispatcher.
- Slimmed dispatcher Dockerfile (no ffmpeg) + requirements (no faster-whisper) for Low; `WHISPER_ENABLED=0` in host `.env`.
- Health OK on 8090/8094/8095/8096/8099/8107 (Hermes/9Router wired in later same day).

## 2026-08-15 11:35 +07 — copy Zalo adapter (mention gate) into hermes/main/plugins

- Copied edited plugin from lab `hermes_backup/plugins/zalo` → `hermes/main/plugins/zalo/` (`adapter.py` with `ASSISTANT_MENTION_GATE_v1`, `gate_valkey.py`, `plugin.yaml`, `__init__.py`).
- Did **not** copy PowerShell push scripts.

## 2026-08-15 11:20 +07 — root README expanded

- Rewrote `README.md` (reference-style): product pitch, quick start, profiles, layout, commands, architecture brief, docs map, design rules. Still points at `docs/` for detail.

## 2026-08-15 10:55 +07 — brief views as HTML architecture panels

- `03-architecture.md` / `04-component-flows.md`: **Brief view** = styled HTML layer boxes (THIS = gold border); **Workflow** stays Mermaid.

## 2026-08-15 10:40 +07 — brief system architect + workflow per section

- `03-architecture.md`: each workflow has **Brief system architect** then **Workflow** (Mermaid).
- `04-component-flows.md`: each component has **Brief system architect** (THIS highlight) then **Internal workflow**.

## 2026-08-15 10:15 +07 — system architecture & component flowcharts

- Added `docs/03-architecture.md` (whole-system architecture, chat/knowledge/Medium/High/ops/memory Mermaid workflows).
- Added `docs/04-component-flows.md` (flowchart per hermes surface + each architect layer).
- Linked from `docs/README.md`, `docs/01-workflow.md`, `architect/README.md`.

## 2026-08-15 10:12 +07 — profile matrix as Excel-style HTML tables

- `02-components-and-commands.md` uses HTML tables with column widths, row padding, and section header rows (Must / Medium+ / High).

## 2026-08-15 10:10 +07 — components & commands doc rewritten for readability

- Replaced wide profile matrices in `02-components-and-commands.md` with Low / Medium / High sections, plain lists, and "I want to…" cheat sheet.

## 2026-08-15 10:05 +07 — components & commands by profile (one doc)

- Added `docs/02-components-and-commands.md`: Must/Med/High component matrix + `run.sh` command matrix + timers + cheat-sheets.
- Docs index points here first for operators. `02-commands.md` kept as commands-only detail.

## 2026-08-15 10:00 +07 — commands by profile (backup, auto-learn, compact)

- Added `docs/02-commands.md`: full command matrix for Low / Medium / High.
- `run.sh` supports: backup|restore|verify|migrate, auto-learn|learn-status, compact|optimize-memory (Med+), install-timers, backup-sync-clouddrive (High), channel-status.
- Compact refused on Low; auto-learn available on all profiles. No VPS push.

## 2026-08-15 09:55 +07 — detailed architect/hermes docs + example skill

- Added per-component READMEs under `architect/**` and `hermes/**` (purpose, profile, functions, how it works).
- Added `hermes/main/skills/_example/SKILL.md` template from current skill style (`common-rules` / `knowledge-learn`).
- Docs index links component indexes. No VPS push.

## 2026-08-15 09:45 +07 — clean rebuild of assistant

- Wiped prior scaffold clone. New clean tree: `architect/` (layers) + `hermes/` (skills, messages, plugins, config).
- Seeded Must Low `docker-compose.yml`, `run.sh`, `ASSISTANT_PROFILE` via `architect/backup-restore/lib/profile.sh`.
- Docs: `00-profiles.md`, `01-workflow.md` (Low only), `DEFAULTS.md`. Fresh changelog (lab history stays in `assistant`).
- Copied service code into layers from lab (memory, tools, models, …) without hotfix push scripts / OpenVPN / Traefik product path.
- **Action for operators:** copy `.env.example` → `.env` and set all `CHANGE_ME` secrets before `bash run.sh up`.
- No VPS deploy in this change.
