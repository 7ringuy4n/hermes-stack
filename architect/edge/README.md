# architect / edge

## System architecture

| | |
|--|--|
| **Sits between** | Operators / LAN clients ↔ Hermes |
| **Owns** | Traefik LB, API Gateway (Valkey RL), optional OpenVPN |
| **Does not own** | Zalo SSE (host bridge → zalo-proxy → Hermes) |

<table style="width:100%;border-collapse:collapse;font-size:13px;">
  <tr>
    <td style="padding:12px;background:#f5f5f5;border:1px solid #ddd;text-align:center;width:28%;">LAN / SSH · VPN opt</td>
    <td style="padding:8px;background:#eee;text-align:center;width:4%;">→</td>
    <td style="padding:14px;background:#2563eb;color:#fff;text-align:center;border:3px solid #fbbf24;width:36%;"><b>Gateway → Traefik</b></td>
    <td style="padding:8px;background:#eee;text-align:center;width:4%;">→</td>
    <td style="padding:12px;background:#e8f4ea;border:1px solid #c5e0c8;text-align:center;width:28%;">Hermes ×1|×2</td>
  </tr>
</table>

## Purpose

**Edge networking** for TLS/LB (Traefik), private admin VPN (OpenVPN), and an API Gateway with shared Valkey rate limits.

## Profile (v0.5.0)

| Flag | Compose profile | Default |
|------|-----------------|--------|
| `ENABLE_TRAEFIK=1` | `traefik` | **1** (all profiles) |
| `ENABLE_API_GATEWAY=1` | `gateway` | **1** (all profiles) |
| `ENABLE_OPENVPN=1` | `openvpn` | 0 |
| `TRAEFIK_MODE` | — | **`local`** (VPN/localhost). `public` + ACME is opt-in |

Merged via `docker-compose.edge.yml` when any flag is on (`run.sh up`). Set `ENABLE_TRAEFIK=0` / `ENABLE_API_GATEWAY=0` to disable.

## Sub-packages

| Package | Function |
|---------|----------|
| [../gateway](../gateway/README.md) | HTTP entry: optional API keys, Valkey global rate limit, proxy to Traefik/Hermes |
| [traefik/](./traefik/README.md) | Load balancer across Hermes (×1 or ×2 on one node) |
| [openvpn/](./openvpn/README.md) | Private admin / LAN path |

## Traffic rules (product decisions)

```text
LAN / SSH tunnel    →  API Gateway (Valkey RL) → Traefik → Hermes ×1|×2
OpenVPN (optional)  →  same Gateway path
Zalo (local)        →  host bridge → zalo-proxy → Hermes   (bypass Gateway)
Coding skill path   →  no Gateway rate-limit (MUST)
```

Heavy OCR/image work stays on **jobs / dispatcher** (async + timeouts), not inside Hermes.

## Related

- [docs/05-edge-networking.md](../../docs/05-edge-networking.md)
- [docs/MULTI_NODE.md](../../docs/MULTI_NODE.md)
- [referrence/hermes-production-scalability-architecture.md](../../referrence/hermes-production-scalability-architecture.md)
