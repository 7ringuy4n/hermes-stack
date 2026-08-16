# Git workflow rules

English rules for branches, commits, and pull requests on **hermes-stack**.
Follow this document for every change. Agents must follow the same rules (see `.cursor/rules/git.mdc`).

---

## 1. Branch layout

```text
main
  └── develop                          # integration branch
        └── feature/<layer>/<slug>     # work branch (one concern)
```

| Branch | Purpose |
|--------|---------|
| `main` | Stable / release line |
| `develop` | Default integration; merge feature PRs here first |
| `feature/<layer>/<slug>` | One task under a product layer |

### Layer names (second path segment)

Use the architecture layer (uppercase in PR titles, lowercase in branch paths):

| Layer (branch) | Layer (title tag) | Examples |
|----------------|-------------------|----------|
| `memory` | `MEMORY` | Memory Manager, Mem0, Postgres memories |
| `session` | `SESSION` | Valkey session, thread state |
| `worker` | `WORKER` | OCR, jobs, image, coding workers |
| `zalo` | `ZALO` | Bridge, proxy, zalo-watch, adapter |
| `gateway` | `GATEWAY` | API gateway, rate limit |
| `arch` | `ARCH` | Cross-cutting architecture / Traefik |
| `hermes` | `HERMES` | Hermes runtime / health |
| `docs` | `DOCS` | Documentation only |
| `security` | `SECURITY` | Authz, secret probe, AV |
| `monitor` | `MONITOR` | Grafana, Loki, metrics |

### Branch name examples

```text
feature/zalo/fix-cause-restart-hermes
feature/memory/concurrent-session-support
feature/worker/external-file-processing
feature/gateway/api-rate-limiting
feature/docs/add-git-rules
```

Rules:

- Create `develop` from `main` if missing; do not commit feature work directly on `main`.
- Branch features from **`develop`**, not from `main`.
- One PR = one concern. Do not mix unrelated layers in one branch.
- Do not push to a VPS / production host unless the operator explicitly allows it.

---

## 2. Pull request title format

**Required:** three bracket tags, then a short imperative summary.

```text
[<BRANCH_KIND>][<LAYER>][<CHANGE_TYPE>] <Summary>
```

| Tag position | Values | Meaning |
|--------------|--------|---------|
| 1 — Branch kind | `FEATURE` `REFACTOR` `SECURITY` `DOCS` `HOTFIX` | Family of work (usually matches `feature/…`) |
| 2 — Layer | `ZALO` `MEMORY` `SESSION` `WORKER` `GATEWAY` `ARCH` `HERMES` `DOCS` … | Same as §1 |
| 3 — Change type | `FIX` `FEATURE` `REFACTOR` `SECURITY` `DOCS` `PERF` | What this PR mainly does |

### Examples

```text
[FEATURE][MEMORY][FEATURE] Add concurrent session support
[FEATURE][WORKER][FEATURE] Add external file processing worker
[FEATURE][SESSION][FIX] Prevent cross-session context leakage
[FEATURE][ARCH][REFACTOR] Separate heavy workers from Hermes
[FEATURE][GATEWAY][SECURITY] Add API rate limiting
[FEATURE][ZALO][FIX] Prevent Hermes restart storm from watch timers
[FEATURE][DOCS][DOCS] Add git workflow rules
```

Base branch for feature PRs: **`develop`**.

---

## 3. Commit messages

Prefer the **same title line** as the PR when the commit is the whole change:

```text
[FEATURE][ZALO][FIX] Prevent Hermes restart storm from watch timers

Optional body: cause, what changed, opt-in flags, follow-ups.
```

- Use UTF-8; keep Vietnamese or other Unicode in messages/docs when needed.
- Do not put secrets in commits.
- Do not amend or force-push unless the operator explicitly asks (then prefer `--force-with-lease`).
- Do not skip hooks (`--no-verify`) unless explicitly requested.

---

## 4. Changelog

Every user-facing or ops-facing change updates `docs/CHANGELOG.md` **at the top**, with timestamp:

```markdown
## YYYY-MM-DD HH:MM +07 — short title

- Bullet: why / what / how to opt in or verify
```

Commit message may mirror the latest CHANGELOG entry title when that is the agreed style for the task.

---

## 5. Pull request body

Include at least:

1. **Summary** — problem and fix in plain English  
2. **Cause** (for fixes) — root cause in one short list  
3. **Changes** — files / flags / defaults  
4. **Test plan** — checkboxes an operator can run  

Do not deploy or SSH-apply scripts to remote hosts from a PR unless permission is given in the request.

---

## 6. Auth and push

- Push only when GitHub CLI / git is authenticated as the repo owner account for this project (`7ringuy4n` for `github.com/7ringuy4n/hermes-stack`).
- If the active account is wrong, stop and ask; do not push as another user.
- After creating branches locally, push with upstream tracking:

```bash
git push -u origin develop
git push -u origin feature/<layer>/<slug>
```

Open PR:

```bash
gh pr create --base develop --head feature/<layer>/<slug> \
  --title "[FEATURE][<LAYER>][<TYPE>] <Summary>" \
  --body "..."
```

---

## 7. What not to commit

- `.env`, secrets, keys, credentials  
- `scripts/temp/**` (except README) — gitignored hotfixes  
- `hermes/temp/**` — local drafts  
- Editor folders (`.idea/`, `.vscode/`) unless the team agrees  

See root `.gitignore`.

---

## 8. Quick checklist

- [ ] Branched from `develop` as `feature/<layer>/<slug>`
- [ ] CHANGELOG entry with timestamp
- [ ] Commit / PR title: `[KIND][LAYER][TYPE] Summary`
- [ ] PR base = `develop`
- [ ] Auth account is correct before push
- [ ] No VPS deploy without explicit permission
