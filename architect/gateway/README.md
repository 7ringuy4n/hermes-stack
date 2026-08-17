# gateway / api-gateway

## System architecture

| | |
|--|--|
| **Sits between** | LAN / SSH clients ↔ Traefik (or Hermes) |
| **Owns** | Global Valkey rate limits, optional API-key gate, proxy |
| **Does not own** | Zalo SSE path; High authz ACL |

<table style="width:100%;border-collapse:collapse;font-size:13px;">
  <tr>
    <td style="padding:12px;background:#f5f5f5;border:1px solid #ddd;text-align:center;width:28%;">Client</td>
    <td style="padding:8px;background:#eee;text-align:center;width:4%;">→</td>
    <td style="padding:14px;background:#2563eb;color:#fff;text-align:center;border:3px solid #fbbf24;width:36%;"><b>api-gateway + Valkey RL</b></td>
    <td style="padding:8px;background:#eee;text-align:center;width:4%;">→</td>
    <td style="padding:12px;background:#e8f4ea;border:1px solid #c5e0c8;text-align:center;width:28%;">Traefik → Hermes</td>
  </tr>
</table>

## Purpose

VPN/LAN **HTTP entry** in front of Traefik (or Hermes). Enforces **global rate limits** in **Valkey** so limits do not multiply with Hermes replicas. Default **on** in v0.5.0 with Traefik (`ENABLE_API_GATEWAY=1`).

**Auth:** `GATEWAY_REQUIRE_AUTH=1` (default) — set `GATEWAY_API_KEYS` or the gateway process refuses to start. See [docs/SECURITY.md](../../docs/SECURITY.md).

**Rate limit:** keyed by API-key hash (preferred) or peer IP. Client `X-Forwarded-For` / `x-user-id` are **not** trusted unless `GATEWAY_TRUST_FORWARDED=1`. Header `x-assistant-skill` no longer bypasses RL.

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
| Valkey RL | Key `rate:gw:key:{sha256[:16]}` or `rate:gw:ip:{peer}`; window + max from env |
| Skip RL | Path prefixes in `GATEWAY_SKIP_RL_PATHS` only (after auth). **No** client header bypass |
| Messages | Admin-editable UTF-8 JSON: `messages/en.json` (401 / 429 / 503 text) |

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

- [edge/README.md](../edge/README.md)
- [docs/05-edge-networking.md](../../docs/05-edge-networking.md)
- [docs/MULTI_NODE.md](../../docs/MULTI_NODE.md)
