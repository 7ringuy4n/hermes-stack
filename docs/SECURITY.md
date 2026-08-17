# Security notes (v0.5.2+)

Hardening applied for LAN/VPN lab stacks. **Do not** expose High to the public Internet without reviewing this file.

## Fixed / mitigated (P0)

| Issue | Mitigation |
|-------|------------|
| `docker.sock` on zalo-api | **Removed** — Hermes restarts via host `stack-watch` / `zalo-watch` |
| `docker.sock` on security-manager | **Replaced** with `docker-socket-proxy` (limited container APIs) + `DOCKER_HOST` |
| `scan-url` SSRF | Block private/metadata IPs; no auto-follow redirects; re-validate each hop |
| Gateway auth optional | `GATEWAY_REQUIRE_AUTH=1` + startup fail without `GATEWAY_API_KEYS` |
| Client RL header bypass | **Removed** (`x-assistant-skill` ignored) |
| Spoofable RL identity | Default: API key hash or `request.client.host`; `GATEWAY_TRUST_FORWARDED=0` |
| RL Valkey fail-open | Fail closed → small **local** per-process limiter |
| Security fail-open | High: `SECURITY_FAIL_CLOSED=1` — enabled controls that error → RISK |
| Sandbox off | High default `SECURITY_SANDBOX=1` via socket proxy |

## Still lab-only / P1

- OpenBao still runs **`-dev`** on High (localhost bind). Production needs non-dev storage + AppRole.
- Alloy monitor profile still mounts docker.sock **read-only** for log discovery.
- Image tags may use `:latest` — pin digests for production.
- Secrets still fan out via compose env — prefer OpenBao per-service credentials later.
- Flat `internal` Docker network — segment edge / agent / data later.

## Operator checklist

1. Set `GATEWAY_API_KEYS` in `.env` before `ENABLE_API_GATEWAY=1`.
2. Keep host publishes on `127.0.0.1`; use SSH tunnels.
3. Leave `GATEWAY_TRUST_FORWARDED=0` unless Traefik is the only client of the gateway.
4. For isolated lab without gateway keys: `GATEWAY_REQUIRE_AUTH=0` (not for shared networks).

## Related

- [docs/05-edge-networking.md](./05-edge-networking.md)
- [architect/gateway/README.md](../architect/gateway/README.md)
- [docs/MULTI_NODE.md](./MULTI_NODE.md)
