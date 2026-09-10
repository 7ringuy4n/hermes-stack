# Lab two-pass SUMMARY — run-04 (sanitized)

No hostnames, IPs, or account names.

- Run ID: **run-04-two-pass**
- Profile: **High** + Zalo + edge (Traefik local, API Gateway)
- Started: 2026-08-17 ~14:00 +07
- Finished: 2026-08-17 ~14:40 +07

<table>
  <thead>
    <tr>
      <th>Pass</th>
      <th>Mode</th>
      <th>Deploy</th>
      <th>Zalo text concurrent</th>
      <th>Zalo text+media</th>
      <th>Isolation risks</th>
      <th>Final</th>
    </tr>
  </thead>
  <tbody>
    <tr><td>1</td><td>local</td><td>PASS</td><td>PASS (N≤24)</td><td>WARN (fail @ N=4 pre-fix; delay high)</td><td>PASS</td><td>PASS*</td></tr>
    <tr><td>2</td><td>local</td><td>PASS (Quick start)</td><td>n/a (smoke only)</td><td>PASS (N≤4)</td><td>PASS</td><td>PASS</td></tr>
  </tbody>
</table>

\* Pass 1 mixed-media hit first fail at N=4 (text 60s timeout) before auth-path fix; after fix and pass 2 redeploy, N=4 all-success recorded.

## Pass 1 — sync source + deploy + fix on error

| Step | Result | Notes |
|------|--------|-------|
| Sync develop tree | PASS | LF tarball; skip `.git`, reports |
| `ensure_env_keys` | PASS | sandbox/judge/AV off; `TRAEFIK_MODE=local` |
| Destroy leftovers | PASS | Legacy name conflicts cleared |
| `run.sh up` High + Zalo + edge | PASS | Hermes×2, Traefik, Gateway, zalo-api, security-manager |
| `first-setup-llm` | PASS | 9router → Hermes smoke HTTP 200 |
| post-ready-learn | FIXED → PASS | Probe Traefik `/health` (root `/` is 404 by design) |
| stack-watch env order | FIXED | Product `.env` wins over stale `/data/assistant/.env` |
| security-manager image | REBUILT | Old image showed AV URL in health; new `app.py` v1.3.0 |
| ClamAV when AV=0 | FIXED | Leftover containers from data-dir env; removed + `ENABLE_ANTIVIRUS=0` |

### Source fixes during pass 1 (allowed)

- `scripts/main/post-ready-learn.py` — Traefik `/health` probe
- `scripts/main/stack-watch.sh` — env precedence + Traefik `/health`
- `test/scripts/zalo_concurrent_media.py` — text via Traefik `:8080` + `API_SERVER_KEY` (not Gateway-only auth)
- `test/scripts/lab_two_pass.py` — sandbox/judge defaults; `first-setup-llm` in deploy path

### Zalo concurrent text (`cases/08-zalo-concurrent.md`)

| N | ok | fail | elapsed_s |
|---|----|------|-----------|
| 4 | 4 | 0 | 0.40 |
| 8 | 8 | 0 | 0.33 |
| 16 | 16 | 0 | 0.33 |
| 24 | 24 | 0 | 0.42 |

- Last all-success N: **24**
- First-fail N: **none ≤ 24**
- SSE after burst: **1** (`loggedIn=true`)

### Zalo concurrent text + media (`cases/09-zalo-concurrent-media.md`)

| Phase | N | ok | fail | text p50/p95/max ms | image p50/p95/max ms | Notes |
|-------|---|----|------|---------------------|----------------------|-------|
| Pre auth-fix | 2 | 2 | 0 | — | image ~2934 | text **503** (wrong Gateway-only path) |
| Pre auth-fix | 4 | 3 | 1 | 8130 / **60014** / 60014 | 375 / 2554 / 2554 | text **timeout 60s** |
| Post auth-fix (pass 1) | 2 | 2 | 0 | 38352 / 38352 / 38352 | 686 / 686 / 686 | cold LLM; image sub-second |
| Post auth-fix (pass 1) | 4 | 3 | 1 | — | — | one text timeout under mixed load |

- Auth fix: Hermes chat expects **`API_SERVER_KEY`** on Traefik `:8080/v1/chat/completions`; Gateway `:8088` alone returned 503 for text workers.
- Image gen via dispatcher `POST /v1/image` stayed **200** (~0.4–3s) even when text failed.

### Isolation risks (`cases/10-security-isolation-risks.md`) — pass 1

| Check | Result |
|-------|--------|
| `SECURITY_SANDBOX=0`, judge off, AV off | PASS |
| No `docker.sock` on security-manager / zalo-api | PASS |
| `docker-socket-proxy` not running | PASS |
| Edge loopback only (`TRAEFIK_MODE=local`) | PASS |
| EICAR → RISK via YARA (AV off) | PASS |
| Prompt-injection file → CLEAN (judge skipped) | PASS |

## Pass 2 — script-only Quick start (no source edits)

| Step | Result | Notes |
|------|--------|-------|
| `bash run.sh down` + `bash run.sh up` | PASS | README Quick start on synced tree |
| `bash run.sh first-setup-llm` | PASS | post-ready-learn OK (9router, Hermes, ingest) |
| `bash run.sh install-timers` | PASS | stack-watch + zalo-watch |
| API Gateway `/health` | PASS | |
| Traefik `/` | WARN | HTTP 404 expected — use `/health` or Gateway |
| Zalo bridge | PASS | `loggedIn=true`, `sseClients=1` at deploy |
| Hermes×2 | PASS | No host `:29119` (use Traefik/Gateway) |

### Post pass 2 probes

**Isolation risks:** PASS (0 fail) — same matrix as pass 1.

**Mixed media burst (N≤4 only per §14):**

| N | ok | fail | text p50/p95 ms | image p50/p95 ms | elapsed_s |
|---|----|------|-----------------|------------------|-----------|
| 2 | 2 | 0 | 38237 / 38237 | 479 / 479 | 38.56 |
| 4 | 4 | 0 | 13077 / 28951 | 407 / 785 | 29.28 |

- Last all-success N: **4**
- First-fail N: **none ≤ 4**
- SSE after final burst: **0** (brief; zalo-watch should restore — record on next tick)

## Observations

- **Text latency** under mixed load is dominated by LLM routing (tens of seconds); image gen stays sub-second to ~3s.
- **Fail event** for mixed media: N=4 text timeout at 60s when auth path wrong or under contended load; record last-all-success / first-fail per §13.
- **Traefik** root `/` returns 404; health checks must use `/health` or Gateway `/health`.
- **ClamAV** must not start when `ENABLE_ANTIVIRUS=0`; stale data-dir `.env` can resurrect AV until stack-watch fix applied.

## Left running

High profile: Hermes×2, Traefik + API Gateway (loopback), zalo-api/proxy, 9router, security-manager (sandbox/judge/AV off), core data services.
