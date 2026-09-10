# Lab two-pass SUMMARY (sanitized)

No hostnames, IPs, or account names.

## Pass 1 — update source + deploy

| Step | Result | Notes |
|------|--------|-------|
| Sync develop tree | PASS | LF-normalized tarball |
| Force-clean leftover containers | PASS | Name conflicts (zalo-proxy / legacy admin-api) |
| `run.sh up` High + Zalo + edge | PASS | Hermes×2, Traefik, API Gateway, zalo-api |
| 9router → Hermes smoke | PASS | first-setup-llm OK |
| post-ready-learn (initial) | FAIL then FIXED | Probed missing `:29119` on Hermes×2 |
| Source fix | PASS | `post-ready-learn` + `stack-watch` use Traefik/Gateway when replicas≠1 |
| `check-medium.sh` corruption | FIXED | `d`→`o` typos (`/dev/null`, dispatcher) restored |
| Zalo concurrent bursts | PASS | See below |

### Zalo concurrent (`cases/08-zalo-concurrent.md`)

| N | ok | fail | elapsed_s |
|---|----|------|-----------|
| 4 | 4 | 0 | 0.38 |
| 8 | 8 | 0 | 0.33 |
| 16 | 16 | 0 | 0.33 |
| 24 | 24 | 0 | 0.43 |

- Last all-success N: **24**
- First-fail N: **none ≤ 24**
- SSE single owner after burst: **yes** (`sseClients=1`, `loggedIn=true`)
- Hermes replicas after burst: **2 up**

## Pass 2 — script-only Quick start (no source edits)

| Step | Result | Notes |
|------|--------|-------|
| `bash run.sh down` + `bash run.sh up` | PASS | Existing VPS tree only |
| Timers reinstall | PASS | stack-watch + zalo-watch |
| post-ready-learn | PASS | Traefik/Gateway probe path |
| API Gateway `/health` | PASS | |
| Traefik `/` | WARN | HTTP 404 (service up; no dashboard root) |
| Hermes host `:29119` | N/A | Expected absent when replicas=2 — use Gateway `:8088` / Traefik `:8080` |
| Zalo bridge | PASS | loggedIn, sseClients=1 |

## Left running

High profile: Hermes×2, Traefik + API Gateway, zalo-api/proxy, Model Router, 9router, Valkey/Postgres/Qdrant, security-manager + docker-socket-proxy.

## Follow-ups (not blocking)

- Traefik root `/` returns 404 — tunnel Gateway or a Hermes path for dashboard UX.
- Dispatcher briefly restart-looped during heal windows; recovered healthy.
- `Apply-EdgeUpdate.ps1` still shows similar letter corruption locally — rewrite when needed (not used this lab).
- Antivirus containers present despite lab intent to keep AV off — verify `.env` `ENABLE_ANTIVIRUS`.
