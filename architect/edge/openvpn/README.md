# edge / openvpn

## Purpose

**OpenVPN** gives administrators a private path into the host/stack. Public traffic must not reach Postgres, Qdrant, Valkey, Docker, or admin UIs.

## Enable

```env
ENABLE_OPENVPN=1
```

Compose profile `openvpn` starts a stub container. **You must initialize PKI/config before it stays healthy** (see below).

## Functions

| Step | Action |
|------|--------|
| 1 | Create host volume / data dir for OpenVPN config |
| 2 | Generate CA + server certs (image docs / `ovpn_genconfig` + `ovpn_initpki`) |
| 3 | Set `ENABLE_OPENVPN=1` and `bash run.sh up` |
| 4 | Issue client profiles; connect; reach Gateway/Traefik on LAN IPs |

## Security

- Publish UDP only on a **VPN/LAN** interface or `127.0.0.1` for local testing — never `0.0.0.0` on a public VPS without firewall rules.
- Zalo bridge stays on the host; it does not require OpenVPN for end users.

## Related

- [../README.md](../README.md)
- [docs/05-edge-networking.md](../../../docs/05-edge-networking.md)
