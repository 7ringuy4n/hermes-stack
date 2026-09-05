# edge / openvpn

## Purpose

**OpenVPN** gives administrators a private path into the host/stack from **any OS** (Windows, macOS, Linux, Android, iOS). Public traffic must not reach Postgres, Qdrant, Valkey, Docker, or admin UIs — including OmniRoute.

## Enable

```env
ENABLE_OPENVPN=active
```

Compose profile `openvpn` starts a stub container. **You must initialize PKI/config before it stays healthy** (see below).

## Functions

| Step | Action |
|------|--------|
| 1 | Create host volume / data dir for OpenVPN config |
| 2 | Generate CA + server certs (image docs / `ovpn_genconfig` + `ovpn_initpki`) |
| 3 | Set `ENABLE_OPENVPN=active` and `bash run.sh up` |
| 4 | Issue `.ovpn` client profiles; import in any OpenVPN-compatible client |
| 5 | Connect VPN, then reach OmniRoute / Gateway on the VPN host address |

## OmniRoute from any OS (via OpenVPN)

Omni UI/API defaults to **localhost-only** publish (`OMNIROUTER_BIND=127.0.0.1`, port `20129`).

**Recommended (safest) — SSH tunnel over VPN**

1. Connect OpenVPN from Windows / macOS / Linux / mobile.
2. From the client: `ssh -L 20129:127.0.0.1:20129 USER@VPN_HOST_IP`
3. Open `http://127.0.0.1:20129` in the browser (any OS).

**Optional — publish Omni on the VPN path**

1. Set in `.env`: `OMNIROUTER_BIND=0.0.0.0` (compose republishes `:20129`).
2. Firewall-allow **only** the OpenVPN client subnet (never world `0.0.0.0/0` on a public VPS).
3. After VPN connect, open `http://VPN_HOST_IP:20129` from any OS browser.
4. Keep `OMNIROUTE_DISABLE_CREDENTIAL_HEALTH_CHECK=true` so Omni does not spam provider connection tests.

## Client apps (any OS)

| OS | Client |
|----|--------|
| Windows | OpenVPN GUI / OpenVPN Connect |
| macOS | Tunnelblick / OpenVPN Connect |
| Linux | `openvpn` / NetworkManager OpenVPN |
| Android / iOS | OpenVPN Connect |

Import the issued `.ovpn` profile; no stack change is required per OS.

## Security

- Publish UDP only on a **VPN/LAN** interface or `127.0.0.1` for local testing — never `0.0.0.0` on a public VPS without firewall rules.
- Zalo bridge stays on the host; it does not require OpenVPN for end users.
- Prefer SSH tunnel to Omni over exposing `OMNIROUTER_BIND=0.0.0.0` unless the VPN CIDR is locked down.

## Related

- [../README.md](../README.md)
- [docs/05-edge-networking.md](../../../docs/05-edge-networking.md)
