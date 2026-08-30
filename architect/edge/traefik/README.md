# edge / traefik

## Purpose

**Traefik** terminates internal HTTP and load-balances to healthy Hermes instances. Bind host ports to **127.0.0.1** (or VPN interface) only — no public inbound.

## Enable

```env
ENABLE_TRAEFIK=active
# Optional Let's Encrypt (HTTP-01 — needs public 80/443 or use staging first):
TRAEFIK_ACME_ENABLED=inactive
TRAEFIK_ACME_EMAIL=admin@example.com
TRAEFIK_ACME_DOMAIN=assistant.example.com
# TRAEFIK_ACME_CA_SERVER=https://acme-staging-v02.api.letsencrypt.org/directory
```

`run.sh` adds compose profile `traefik` (HTTP/LAN) or `traefik-acme` (Let's Encrypt) from `docker-compose.edge.yml`.

## Functions

| Piece | Role |
|-------|------|
| EntryPoint `:80` | HTTP (LAN) or ACME HTTP-01 + redirect |
| EntryPoint `:443` | HTTPS when `TRAEFIK_ACME_ENABLED=active` |
| Let's Encrypt | `certificatesResolvers.letsencrypt` + `acme.json` volume |
| File provider | `dynamic/hermes.yml` or rendered `dynamic-acme/hermes.yml` |
| Hermes upstream | `http://hermes:8642` |
| Future × N | Add more `servers.url` entries |

## Let's Encrypt notes

- **HTTP-01** needs Let's Encrypt to reach your host on **80/443**. Default LAN bind (`127.0.0.1`) cannot obtain certs — set `TRAEFIK_BIND=0.0.0.0` (and firewall) when enabling ACME.
- While product policy is **no public inbound**, keep `TRAEFIK_ACME_ENABLED=inactive` and terminate TLS on VPN or a reverse proxy elsewhere.
- Use **staging CA** first to avoid rate limits.

## Related

- [../README.md](../README.md)
- [docs/05-edge-networking.md](../../../docs/05-edge-networking.md)
