# 05 — Edge networking (Traefik, API Gateway, OpenVPN)

Human-readable guide for the optional **edge** layer. Default is **off** on Low. All host ports bind to **127.0.0.1**. Production is **VPN-only** (`TRAEFIK_MODE=local`, `TRAEFIK_ACME_ENABLED=0`). There is **no public inbound** unless you opt into ACME.

Related code: `docker-compose.edge.yml`, `architect/edge/`, `architect/gateway/`.

---

## 1. Why this exists

Production target (see `referrence/hermes-production-scalability-architecture.md`):

1. **API Gateway** — controlled HTTP entry, shared Valkey rate limits  
2. **Traefik** — load balance Hermes chat replicas  
3. **OpenVPN** — private admin access  
4. **Zalo** — local bridge only (does **not** use the Gateway)

Heavy OCR/image work stays on **dispatcher workers** (async + timeouts) so Hermes does not hang on long jobs.

---

## 2. How to enable

In `.env` (copy from `.env.example` or `docs/config/edge.env.snippet`):

```env
# Medium/High: leave unset → profile.sh defaults Traefik + API Gateway ON, TRAEFIK_MODE=local
# Low: forced OFF in profile.sh
# ENABLE_TRAEFIK=0
# ENABLE_API_GATEWAY=0
TRAEFIK_MODE=local
ENABLE_OPENVPN=0
```

Set a flag to `0` on Medium/High only when you want to disable edge. Then:

```bash
bash run.sh up
```

`run.sh` merges `docker-compose.edge.yml` and adds compose profiles `traefik` / `gateway` / `openvpn` as needed.

| Combination | Typical use |
|-------------|-------------|
| Traefik only | LB in front of Hermes on `127.0.0.1:8080` |
| Gateway only | Rate-limited proxy → Hermes (`GATEWAY_UPSTREAM_URL=http://hermes:8642`) |
| Gateway + Traefik | Set `GATEWAY_UPSTREAM_URL=http://traefik:80` |
| OpenVPN | Admin VPN stub — initialize PKI first (see OpenVPN README) |

---

## 3. Traefik (load balancer)

**Functions**

| Function | Detail |
|----------|--------|
| Listen | Container `:80`, host `${TRAEFIK_BIND:-127.0.0.1}:${TRAEFIK_HOST_PORT:-8080}` (LAN mode) |
| Route | All paths → service `hermes-gw` |
| Upstream | `http://hermes:8642` (Hermes gateway inside Docker) |
| Health | Periodic check; unhealthy instances drop from LB |
| Scale later | Add more `servers` in `architect/edge/traefik/dynamic/hermes.yml` for Hermes × N |

Config files: `architect/edge/traefik/traefik.yml` + `dynamic/hermes.yml`.

### Let's Encrypt (optional)

```env
ENABLE_TRAEFIK=1
TRAEFIK_ACME_ENABLED=1
TRAEFIK_ACME_EMAIL=admin@example.com
TRAEFIK_ACME_DOMAIN=assistant.example.com
# Optional staging:
# TRAEFIK_ACME_CA_SERVER=https://acme-staging-v02.api.letsencrypt.org/directory
TRAEFIK_BIND=0.0.0.0
TRAEFIK_HTTP_PORT=80
TRAEFIK_HTTPS_PORT=443
```

| Function | Detail |
|----------|--------|
| Profile | `traefik-acme` (chosen by `run.sh` when ACME enabled) |
| HTTP→HTTPS | EntryPoint redirect + middleware |
| Cert resolver | `letsencrypt` → `/letsencrypt/acme.json` volume |
| Host rule | Rendered from `hermes.tls.yml.template` via `scripts/main/render-traefik-acme.sh` |
| Challenge | **HTTP-01** on entryPoint `web` (default) |

**Conflict with “no public inbound”:** HTTP-01 needs Let's Encrypt to reach ports **80/443**. Keep `TRAEFIK_ACME_ENABLED=0` for VPN/LAN-only. Enable ACME only when you intentionally expose those ports (or terminate TLS elsewhere).

When ACME is on and Gateway is on, prefer:

```env
GATEWAY_UPSTREAM_URL=http://traefik:80
```

(or reach Hermes on the internal Docker network; TLS is for external clients).

---

## 4. API Gateway (HA entry + global rate limit)

**Functions**

| Function | Detail |
|----------|--------|
| `GET /health` | Process liveness |
| Proxy | Forwards HTTP to `GATEWAY_UPSTREAM_URL` |
| Valkey rate limit | Shared counters `rate:gw:user:*` / `rate:gw:ip:*` (does not multiply with Hermes replicas) |
| Skip rate limit | Coding skill paths (`GATEWAY_SKIP_RL_PATHS`) or header `X-Assistant-Skill: coding` |
| Messages | Edit `architect/gateway/api-gateway/messages/en.json` (UTF-8) — no hardcoded operator strings in logic |
| Timeout | `GATEWAY_PROXY_TIMEOUT_S` bounds how long Gateway waits (helps ISSUE: long hang) |

**Zalo:** bridge `:8787` → `zalo-proxy` → Hermes on the Docker network. Do **not** send Zalo SSE through the API Gateway.

**Coding:** no rate-limit on coding skill paths (product MUST). Other HTTP still uses global Valkey RL.

---

## 5. OpenVPN (private admin)

**Functions**

| Function | Detail |
|----------|--------|
| Stub service | `kylemanna/openvpn` under profile `openvpn` |
| Data dir | `OPENVPN_DATA_DIR` (certs/config) |
| Host port | `127.0.0.1:${OPENVPN_HOST_PORT:-1194}/udp` for local tests |

Initialize PKI before expecting a healthy VPN. Steps: `architect/edge/openvpn/README.md`.

---

## 6. Request concurrency (chat / coding / OCR)

| Request | Path | Concurrent? |
|---------|------|-------------|
| Chat | Gateway → Traefik → Hermes × N | Yes, across Hermes |
| Coding (skills) | Same Hermes pool; **no** Gateway RL | Yes, as chat turns |
| OCR / image | Dispatcher → Valkey/RQ workers | Separate queue; should not block Hermes if async |

---

## 7. Operator checklist

- [ ] `.env` flags set intentionally (default all `0`)  
- [ ] Ports only on localhost / VPN (`TRAEFIK_MODE=local`, ACME off)  
- [ ] If Gateway + Traefik: `GATEWAY_UPSTREAM_URL=http://traefik:80`  
- [ ] Edit rate-limit / 503 messages in `messages/en.json` if needed  
- [ ] Zalo still uses bridge path  
- [ ] OpenVPN PKI initialized before production use  

PowerShell helper (local pack / optional remote apply **only with permission**):  
`scripts/main/Apply-EdgeUpdate.ps1`
