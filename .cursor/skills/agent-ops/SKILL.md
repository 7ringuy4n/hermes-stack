---
name: agent-ops
description: >-
  Production/enterprise agent and DevOps rules for hermes-stack: permissions
  (no VPS/MR without ask), develop-first branches, CHANGELOG, skills-first,
  editable messages, LF/SSH safety, reusable components. Use whenever coding,
  documenting, deploying, or operating this repo.
---

# Agent ops

## Source of truth

Read and follow **`docs/AGENT_RULES.md`** (full numbered rules + role).  
Git/MR workflow: **`docs/GIT.md`**.

Do **not** copy those rules into application runtime code or user-facing bot replies. Keep them in docs/rules/skills so admins can edit them.

## When this skill applies

- Starting any new requirement
- Deploy, VPS, SSH, sync, or install work
- Adding triggers/keywords, notifications, or probe messages
- Knowledge cite / list / find behavior
- Choosing skill vs new code vs third-party service

## Decision shortcuts

| Situation | Action |
|-----------|--------|
| New feature request | Checkout `develop` → `feature/<layer>/<slug>` |
| Deploy / test on VPS | Ask permission first; then `Update-StackRemote.ps1` if syncing |
| Push / open MR | Ask permission first; follow `docs/GIT.md` |
| Lab run finished | Restore product defaults (rule 41); do not leave test-only config |
| Keyword triggers / copy | Skill or `hermes/main/messages/` / `config/agent/*` — not hardcoded lists in adapters |
| Can Valkey/queue/3rd party do it? | Use that component (enable/disable via profile/env) |
| Can a skill solve it? | Add/update skill; skip app code |
| Done with ops/product change | Prepend `docs/CHANGELOG.md` with timestamp (`YYYY-MM-DD HH:mm +07`) |

## Remote update script

`scripts/main/Update-StackRemote.ps1` — normalizes LF, optional bad-word scrub from `config/agent/bad-words.txt`, sudo-aware copy. **Only run when the operator allows remote work.**
