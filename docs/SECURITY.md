# Security notes (v0.5.3+)

Hardening for **VPN / localhost** stacks. Production is VPN-only: keep host publishes on `127.0.0.1`, leave `TRAEFIK_MODE=local`, and do **not** enable ACME unless you intentionally expose 80/443.

The LLM judge is **risk detection, not isolation**. An LLM can be manipulated by adversarial content (prompt injection in PDFs, etc.).

## Isolation vs heuristic

```text
file
 → size / MIME / archive limits     isolation (must pass)
 → YARA + static                    isolation (must pass)
 → ClamAV (opt-in)                  isolation (must pass when enabled)
 → sandbox (opt-in, not recommended) isolation (must pass when enabled)
 → LLM judge (opt-in, default off)  heuristic — may add RISK only
 → allow only if isolation passed
```

`LLM says CLEAN` is **ignored**. It cannot allow a file. Judge outages also cannot allow or block.

## Defaults (Security worker)

| Flag | Default | Role |
|------|---------|------|
| `SECURITY_YARA` | **1** | Isolation |
| `ENABLE_ANTIVIRUS` | **0** | Isolation when opted in |
| `SECURITY_SANDBOX` | **0** | Off — no Docker API on security-manager |
| `SECURITY_LLM_JUDGE` / `ENABLE_LLM_JUDGE` | **0** | Off until you opt into RISK-only heuristic |
| `SECURITY_FAIL_CLOSED` | **1** | Isolation outages → RISK. **Never** applied to the LLM judge |
| `TRAEFIK_MODE` | **local** | VPN/localhost. `public` + ACME is explicit opt-in |

## Fixed / mitigated

| Issue | Mitigation |
|-------|------------|
| `docker.sock` on zalo-api | **Removed** — Hermes restarts via host `stack-watch` / `zalo-watch` |
| `docker.sock` on security-manager | **None by default.** Socket proxy only if `SECURITY_SANDBOX=1` (compose profile `sandbox`) |
| LLM `CLEAN` treated as a passed gate | Judge is RISK-only; default **off** |
| `scan-url` SSRF | Block private/metadata IPs; no auto-follow redirects; re-validate each hop |
| Gateway auth optional | `GATEWAY_REQUIRE_AUTH=1` + startup fail without `GATEWAY_API_KEYS` |
| Client RL header bypass | **Removed** (`x-assistant-skill` ignored) |
| Spoofable RL identity | Default: API key hash or `request.client.host`; `GATEWAY_TRUST_FORWARDED=0` |
| RL Valkey fail-open | Fail closed → small **local** per-process limiter |
| OpenBao on the internet | Host bind `127.0.0.1:8200`. Container `0.0.0.0` is Docker-internal only. No Traefik route |

## Still lab-only / P1

- OpenBao still runs **`-dev`** when Security/OpenBao is installed. Production needs non-dev storage + AppRole.
- Alloy monitor profile still mounts docker.sock **read-only** for log discovery.
- Image tags may use `:latest` — pin digests for production.
- Secrets still fan out via compose env — prefer OpenBao per-service credentials later.
- Flat `internal` Docker network — segment edge / agent / data later.
- `SECURITY_SANDBOX=1` still uses `docker-socket-proxy` (create/start containers). Prefer a dedicated sandbox broker / gVisor later — not Docker-from-an-AI-facing service.

## Operator checklist

1. Set `GATEWAY_API_KEYS` in `.env` before `ENABLE_API_GATEWAY=1`.
2. Keep host publishes on `127.0.0.1`; use SSH tunnels or VPN.
3. Leave `TRAEFIK_MODE=local` and `TRAEFIK_ACME_ENABLED=0` for production.
4. Leave `GATEWAY_TRUST_FORWARDED=0` unless Traefik is the only client of the gateway.
5. Opt-in only when needed: `ENABLE_ANTIVIRUS=1`, `SECURITY_LLM_JUDGE=1` (RISK-only), `SECURITY_SANDBOX=1` (not recommended).
6. For isolated lab without gateway keys: `GATEWAY_REQUIRE_AUTH=0` (not for shared networks).

## Related

- [docs/05-edge-networking.md](./05-edge-networking.md)
- [architect/gateway/README.md](../architect/gateway/README.md)
- [architect/security/README.md](../architect/security/README.md)
- [docs/MULTI_NODE.md](./MULTI_NODE.md)
