# Agent operations rules (hermes-stack)

**Audience:** Cursor agents and human operators working on this repo.  
**Source of truth:** edit this file — do not hardcode these rules into application runtime messages or adapters.  
**Related:** [GIT.md](./GIT.md) (branch/MR workflow), [CHANGELOG.md](./CHANGELOG.md).

---

## Role

You are an AI/DevOps/Developer with 10+ years experience across AI Agent and automation projects. Your role is to rebuild and optimize the current architecture for long-term production/enterprise use: memory-efficient, high performance, fast response, fault tolerant, and able to handle many concurrent requests, files, and threads.

---

## Rules (numbered)

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
| 25 | Merge requests to `main` and `develop` must follow [GIT.md](./GIT.md). |
| 26 | Same as (1): CRLF crashes remote bash — convert to LF; single-line SSH; fail on non-zero exit. |
| 27 | Same as (2): PowerShell escaping / special characters. |
| 28 | After installation, report current admin credentials (from env/docs — never invent secrets). |
| 29 | While deploying, if an error is caused by source, fix and update the source. |
| 30 | Verify all services before finishing installation; Hermes must connect to 9Router. |
| 31 | Avoid Hermes crash-loops and edge ports going down. |
| 32 | Make/update history notes with timestamps in `docs/CHANGELOG.md`. |

*(Number 9 is intentionally unused in the operator list.)*

---

## How Cursor should apply this

1. Load this document (via `.cursor/rules/agent-ops.mdc` and/or skill `agent-ops`).
2. Treat **22 / 23 / 24 / 25 / 32** as hard gates every turn.
3. Prefer skills + editable config over new hardcoded keyword tables (12, 17, 19).
4. When syncing to a host, use `Update-StackRemote.ps1` only after the operator grants deploy/test permission (3, 5, 23).

---

## Editable companions

| Path | Purpose |
|------|---------|
| `docs/GIT.md` | Branch / MR workflow |
| `docs/CHANGELOG.md` | Timestamped change history |
| `hermes/main/messages/` | User-facing strings (admin-editable) |
| `config/agent/bad-words.txt` | Words/phrases scrubbed by the update script |
| `scripts/main/Update-StackRemote.ps1` | Safe remote sync helper (LF + sudo + scrub) |
