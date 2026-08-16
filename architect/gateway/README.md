# gateway / api-gateway

## Purpose

VPN/LAN **HTTP entry** in front of Traefik (or Hermes). Enforces **global rate limits** in **Valkey** so limits do not multiply with Hermes replicas.

## Enable

```env
ENABLE_API_GATEWAY=1
# Prefer Traefik when both are on:
GATEWAY_UPSTREAM_URL=http://traefik:80
# Or direct Hermes (no LB):
# GATEWAY_UPSTREAM_URL=http://hermes:8642
```

## Functions

| Function | Detail |
|----------|--------|
| `GET /health` | Liveness for compose/ops |
| Proxy `/*` | Forwards method/path/query/body to upstream |
| Valkey RL | Key `rate:gw:user:{id}` or `rate:gw:ip:{ip}`; window + max from env |
| Skip RL | Path prefixes in `GATEWAY_SKIP_RL_PATHS` **or** header `X-Assistant-Skill: coding` (coding skills — no rate-limit) |
| Messages | Admin-editable UTF-8 JSON: `messages/en.json` (429 / 503 text) |

## What this does **not** do

- Does **not** sit in front of Zalo SSE (bridge → proxy → Hermes stays internal).
- Does **not** replace High authz; auth can be added later as another component.
- Does **not** run OCR/coding workers — only HTTP front door.

## Env (non-secret defaults)

| Variable | Default | Meaning |
|----------|---------|---------|
| `GATEWAY_PORT` | `8088` | Container listen port |
| `GATEWAY_RATE_LIMIT_REQUESTS` | `60` | Max requests per window |
| `GATEWAY_RATE_LIMIT_WINDOW_S` | `60` | Window seconds |
| `GATEWAY_SKIP_RL_PATHS` | `/coding,/v1/coding,/skills/coding` | No RL |
| `GATEWAY_PROXY_TIMEOUT_S` | `120` | Upstream timeout (bounds hung waits) |

## Related

- [architect/edge/README.md](../../edge/README.md)
- [docs/05-edge-networking.md](../../../docs/05-edge-networking.md)
