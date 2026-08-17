# Docker Compose layouts (project root = repo root)

Compose YAML lives here so the repo root stays clean. **`run.sh` always passes
`--project-directory <repo-root>`**, so volume paths like `./architect/...` and
`./config/...` still resolve from the repository root.

| File | Role |
|------|------|
| `docker-compose.yml` | Must / Low base |
| `docker-compose.medium.yml` | Medium (+ OCR, SearXNG, Jobs, Comfy CPU, …) |
| `docker-compose.high.yml` | High (+ security, SIEM, OpenBao, optional **monitor**) |
| `docker-compose.edge.yml` | Traefik / API Gateway / OpenVPN |
| `docker-compose.hermes-hostports.yml` | Host `:28642` / `:29119` when `HERMES_REPLICAS=1` |

## Profiles (components)

| Profile | Enable via |
|---------|------------|
| `zalo` | `ENABLE_ZALO=1` |
| `monitor` | any of `ENABLE_GRAFANA` / `ENABLE_LOKI` / `ENABLE_PROMETHEUS` / `ENABLE_ALLOY` = `1` |
| `notify` / `antivirus` / `sandbox` / `clouddrive` / `comfy-gpu` | matching `ENABLE_*` / `SECURITY_SANDBOX` / `COMFYUI_HAS_GPU` |
| `traefik` / `gateway` / `openvpn` | `ENABLE_TRAEFIK` / `ENABLE_API_GATEWAY` / `ENABLE_OPENVPN` |

High without Loki/Prometheus/Grafana:

```bash
export ASSISTANT_PROFILE=high
export ENABLE_GRAFANA=0 ENABLE_LOKI=0 ENABLE_PROMETHEUS=0 ENABLE_ALLOY=0
bash run.sh up
```

Sizing: [docs/HARDWARE.md](../docs/HARDWARE.md). DR: [architect/backup-restore/README.md](../architect/backup-restore/README.md).
