# config/

Host-mounted non-secret config snippets for optional services.

| Path | Profile | Used by |
|---|---|---|
| `searxng/settings.yml` | Medium+ | `searxng` container (`/etc/searxng`) |
| `openbao/config.hcl` | High | OpenBao (`ui = true`, localhost `:8200`) |
| `monitor/loki-config.yaml` | High | Loki |
| `monitor/prometheus.yml` | High | Prometheus |
| `monitor/config.alloy` | High | Alloy |
| `monitor/grafana/` | High | Grafana provisioning + dashboards |
