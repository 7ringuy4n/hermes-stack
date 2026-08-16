# Change history

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
