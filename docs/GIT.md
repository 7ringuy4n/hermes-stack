# Recommended Git workflow (hermes-stack)

English rules for branches and merge requests (GitHub PRs). Agents follow the same rules via `.cursor/rules/git.mdc`.

---

## Core rule

| Branch | Meaning |
|--------|---------|
| **`develop`** | Everything currently being integrated / tested |
| **`main`** | Production-ready / stable **only** |
| **`release/*`** | The **specific set** of features selected for the next production release |

```text
feature/* ──MR──> develop ──> release/* ──MR──> main
                     │
                     ├── Feature A ✅
                     ├── Feature B ✅
                     ├── Feature C ✅
                     ├── Feature D 🧪
                     └── Feature E 🧪
```

### Merging to `main` — mandatory merge request

**Always create a GitHub Pull Request (merge request) into `main`. Never land production commits by direct push or local-only merge to `main`.**

| Allowed | Forbidden |
|---------|-----------|
| `gh pr create --base main …` then review / `gh pr merge` | `git push origin main` with new commits (no PR) |
| MR from `release/vX.Y.Z` → `main` (`[RELEASE] …`) | Merging `develop` straight into `main` without an MR |
| MR from `hotfix/*` → `main` (`[HOTFIX][…] …`) | `git merge` on a local `main` checkout and force-push |
| Agent / operator merges **only via the open PR** | Closing the PR and pushing the same commits to `main` by hand |

Release path reminder:

1. Create `release/vX.Y.Z` from `main` (or update it with selected commits).  
2. Push the release branch.  
3. **Open MR** `release/vX.Y.Z` → `main` with title `[RELEASE] Release vX.Y.Z`.  
4. Merge **through that MR** after checks/review.  
5. Optionally sync `main` back into `develop` (also via MR preferred).

---

## 1. Branch types

| Branch | Purpose |
|--------|---------|
| `main` | Production / stable only |
| `develop` | Integration branch; may contain features still under testing |
| `feature/*` | New feature development |
| `fix/*` | Normal bug fixes |
| `hotfix/*` | Urgent production fixes (usually from `main`) |
| `release/*` | Selected features being prepared for production |

### Feature / fix naming (layer in path)

Prefer `feature/<layer>/<slug>` or `fix/<layer>/<slug>`:

| Layer (path) | Title tag | Examples |
|--------------|-----------|----------|
| `memory` | `MEMORY` | Memory Manager, Postgres memories |
| `session` | `SESSION` | Valkey session, thread state |
| `worker` | `WORKER` | OCR, jobs, image workers |
| `zalo` | `ZALO` | Bridge, proxy, zalo-watch |
| `gateway` | `GATEWAY` | API gateway, rate limit |
| `arch` | `ARCH` | Traefik, OpenVPN, edge |
| `hermes` | `HERMES` | Hermes runtime / health |
| `docs` | `DOCS` | Documentation only |
| `security` | `SECURITY` | Authz, secret probe, AV |
| `monitor` | `MONITOR` | Grafana, Loki, metrics |

Examples:

```text
feature/memory/add-memory-manager
feature/session/concurrent-session-handling
fix/session/session-isolation
feature/arch/traefik-openvpn-gateway-stubs
hotfix/gateway/rate-limit-outage
release/v1.5.0
```

Rules:

- Branch **`feature/*`** and **`fix/*`** from **`develop`** (unless hotfix).
- Branch **`hotfix/*`** from **`main`**; merge back to `main` and cherry-pick / MR into `develop`.
- One MR = one concern. Do not mix unrelated layers.
- Do not push to a VPS / production host unless the operator explicitly allows it.

---

## 2. Your exact release scenario

A, B, C are production-ready; D/E are still testing on `develop`:

```text
develop
 ├── A ✅
 ├── B ✅
 ├── C ✅
 ├── D 🧪
 └── E 🧪
```

### Create the release branch

1. Create **`release/v1.5.0` from `main`** (clean production baseline).
2. Bring **only A / B / C** into `release/v1.5.0` (cherry-pick or MR the selected commits/MRs — **not** the whole `develop` tip if D/E must stay out).

```text
main ────────────────────────┐
                             │
                             ↓
                       release/v1.5.0
                         ↑   ↑   ↑
                         A   B   C
                             │
                             ↓
                            main
```

```text
develop
 ├── A
 ├── B
 ├── C
 ├── D 🧪
 └── E 🧪
```

3. After A/B/C pass final release testing: **MR `release/v1.5.0` → `main`**.
4. D/E stay on **`develop`** and ship in a later release.

Optional: after release, merge `main` back into `develop` (or cherry-pick release fixes) so develop stays aligned with production.

---

## 3. MR (pull request) naming

**Format:** `[TYPE][LAYER] Short imperative summary`  
**Release:** `[RELEASE] Release vX.Y.Z`

### Examples

```text
[FEATURE][MEMORY] Add memory manager
[FEATURE][SESSION] Add concurrent session handling
[FIX][SESSION] Fix session isolation
[REFACTOR][WORKER] Separate heavy workers from Hermes
[FEATURE][ARCH] Add Traefik, OpenVPN, and API Gateway stubs
[FIX][ZALO] Prevent Hermes restart storm from watch timers
[DOCS][DOCS] Add git workflow rules
[RELEASE] Release v1.5.0
```

| TYPE | Use for |
|------|---------|
| `FEATURE` | New capability |
| `FIX` | Bug fix (`fix/*` or corrective MR) |
| `REFACTOR` | Structure / no intended behavior change |
| `SECURITY` | Auth, secrets, hardening |
| `DOCS` | Documentation only |
| `HOTFIX` | Urgent production fix |
| `RELEASE` | Release branch → `main` |

| Default MR base | From branch |
|-----------------|-------------|
| `develop` | `feature/*`, `fix/*` |
| `main` | `release/*`, `hotfix/*` (also sync `develop`) |

---

## 4. Commit messages

Prefer the **same title line** as the MR when the commit is the whole change:

```text
[FEATURE][MEMORY] Add memory manager

Optional body: why, flags, follow-ups.
```

- UTF-8 OK (Vietnamese in docs/messages).
- No secrets in commits.
- Amend / force-push only when the operator explicitly asks (`--force-with-lease`).
- Do not skip hooks unless explicitly requested.

---

## 5. Changelog

Every ops/product change updates `docs/CHANGELOG.md` at the top with a timestamp:

```markdown
## YYYY-MM-DD HH:MM +07 — short title

- Bullet: why / what / verify
```

---

## 6. Auth and push

- Push only when GitHub auth is the repo owner for this project (`7ringuy4n` for `github.com/7ringuy4n/hermes-stack`).
- If the active account is wrong, stop and ask.

```bash
git push -u origin develop
git push -u origin feature/<layer>/<slug>
git push -u origin release/v1.5.0
```

```bash
# feature → develop
gh pr create --base develop --head feature/<layer>/<slug> \
  --title "[FEATURE][<LAYER>] <Summary>" --body "..."

# release → main (REQUIRED — never push commits to main without this PR)
gh pr create --base main --head release/v1.5.0 \
  --title "[RELEASE] Release v1.5.0" --body "..."
# After review: gh pr merge <number>   (do not git push to main instead)
```

---

## 7. What not to commit

- `.env`, secrets, keys  
- `scripts/temp/**` (except README)  
- `hermes/temp/**`  
- Editor folders (`.idea/`) unless agreed  

See root `.gitignore`.

---

## 8. Quick checklist

- [ ] Right branch type (`feature` / `fix` / `hotfix` / `release`)
- [ ] Features/fixes from `develop`; hotfixes from `main`; releases from `main` + selected commits
- [ ] MR title `[TYPE][LAYER] …` or `[RELEASE] Release vX.Y.Z`
- [ ] Feature/fix MR base = `develop`; release/hotfix to `main` as appropriate
- [ ] **Any change to `main` goes through an open MR — no direct push to `main`**
- [ ] CHANGELOG updated when needed
- [ ] Auth account correct before push
- [ ] No VPS deploy without explicit permission
- [ ] Release MR includes **only** production-ready items (leave 🧪 work on `develop`)
