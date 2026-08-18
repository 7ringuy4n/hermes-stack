# config/

Host-mounted non-secret config snippets for optional services.

| Path | Profile | Used by |
|---|---|---|
| `searxng/settings.yml` | Medium+ | `searxng` container (`/etc/searxng`) |
| `openbao/config.hcl` | High | OpenBao (`ui = true`, localhost `:8200`) |
| `monitor/loki-config.yaml` | High + Loki | Loki (pairs with Alloy) |
| `monitor/prometheus.yml` | High + Prometheus/Grafana | Prometheus (scrapes paired exporters) |
| `monitor/config.alloy` | High + Loki/Alloy | Alloy |
| `monitor/grafana/` | High + Grafana | Grafana provisioning + dashboards (Hardware needs node-exporter) |
