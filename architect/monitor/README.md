# monitor

## Purpose

Observability for High: metrics, logs, dashboards. Access via **localhost or SSH tunnel** (Traefik/OpenVPN removed from product).

## Profile

High only (`ENABLE_GRAFANA` / Loki / Prometheus / Alloy).

## Sub-packages (from lab copy)

| Package | Function |
|---|---|
| `grafana/` | Dashboards |
| `alert-watch/` | Health / alert watcher |
| `stack-exporter/` / `nine-exporter/` | Exporters |

## How it works

```text
Services expose /health and metrics
    → Prometheus scrapes
    → Loki receives logs (via Alloy/agents)
    → Grafana dashboards on 127.0.0.1
```

Do not require monitor to run Low chat.

## Related

- [docs/00-profiles.md](../../docs/00-profiles.md)
