# architect / edge

## Purpose

Optional **edge networking** for production-style access: TLS/LB (Traefik), private admin VPN (OpenVPN), and an API Gateway with shared Valkey rate limits. All default **off** on Low.

## Profile

| Flag | Compose profile | Default |
|------|-----------------|--------|
| `ENABLE_TRAEFIK=1` | `traefik` | 0 |
| `ENABLE_API_GATEWAY=1` | `gateway` | 0 |
| `ENABLE_OPENVPN=1` | `openvpn` | 0 |

Merged via `docker-compose.edge.yml` when any flag is on (`run.sh up`).

## Sub-packages

| Package | Function |
|---------|----------|
| [../gateway/api-gateway](../gateway/api-gateway/README.md) | HTTP entry: auth stub, Valkey global rate limit, proxy to Traefik/Hermes |
| [traefik/](./traefik/README.md) | Load balancer across Hermes (ready for × N) |
| [openvpn/](./openvpn/README.md) | Private admin / LAN path (no public inbound) |

## Traffic rules (product decisions)

```text
Public Internet     →  blocked (no public bind for edge)
OpenVPN / LAN       →  API Gateway (Valkey RL) → Traefik → Hermes × N
Zalo (local)        →  host bridge → zalo-proxy → Hermes   (bypass Gateway)
Coding skill path   →  no Gateway rate-limit (MUST)
```

Heavy OCR/image work stays on **dispatcher workers** (async + timeouts), not inside Hermes.

## Related

- [docs/05-edge-networking.md](../../docs/05-edge-networking.md)
- [referrence/hermes-production-scalability-architecture.md](../../referrence/hermes-production-scalability-architecture.md)
