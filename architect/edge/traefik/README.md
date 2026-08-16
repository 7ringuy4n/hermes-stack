# edge / traefik

## Purpose

**Traefik** terminates internal HTTP and load-balances to healthy Hermes instances. Bind host ports to **127.0.0.1** (or VPN interface) only — no public inbound.

## Enable

```env
ENABLE_TRAEFIK=1
```

`run.sh` adds compose profile `traefik` from `docker-compose.edge.yml`.

## Functions

| Piece | Role |
|-------|------|
| EntryPoint `:80` | Internal only (Docker network + optional localhost publish) |
| File provider | `dynamic/hermes.yml` — router + service + health check |
| Hermes upstream | `http://hermes:8642` (gateway port inside container) |
| Future × N | Add more `servers.url` entries or Docker provider labels |

## Health

Traefik should stop routing to instances that fail health checks. Hermes live/ready split can be tightened later; stub uses a simple path check.

## Related

- [../README.md](../README.md)
- [docs/05-edge-networking.md](../../../docs/05-edge-networking.md)
