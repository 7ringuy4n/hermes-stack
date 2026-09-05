# OmniRoute integration

The directory and environment prefix retain `omni-router` / `OMNIROUTER_*` for
upgrade compatibility. The deployed product is **OmniRoute**.

| Property | Value |
|---|---|
| Upstream caller | model-router and stack-owned direct capability clients |
| Downstream | provider accounts selected by named priority combos |
| Image | `${OMNIROUTER_IMAGE:-diegosouzapw/omniroute:latest}` |
| Host UI/API bind | `127.0.0.1:${OMNIROUTER_HOST_PORT:-20129}` by default |
| Compose profile | `omnirouter` (compatibility name) |
| Persistent state | `omni_router_data` plus backup export |

`scripts/main/first-setup-omnirouter.py` is setup-only and idempotent. It may
create required combo shells but must preserve operator-managed AI Box/provider
members, order, and strategy on updates.

The active combo contract is documented in
[docs/06-model-routing.md](../../../docs/06-model-routing.md). Monitoring uses
`omni-exporter` when Prometheus/Grafana is enabled.
