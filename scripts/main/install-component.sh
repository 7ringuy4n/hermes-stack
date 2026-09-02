#!/usr/bin/env bash
# Resolve short component names → .env KEY=VAL pairs for run.sh install / uninstall.
# Catalog mirrors .env.example section D (optional workers + attachable flags).
# Feature toggles use active|inactive (never 1/0).
#
# Usage:
#   bash scripts/main/install-component.sh list
#   bash scripts/main/install-component.sh resolve openbao schedule zalo
#   bash scripts/main/install-component.sh unresolve openbao
set -euo pipefail

cmd="${1:-list}"
shift || true

_install_pairs() {
  # Workers (WORKER_*=active bundles ENABLE_* via workers.sh)
  case "$1" in
    schedule|sched)
      echo WORKER_SCHEDULE=active
      echo ENABLE_SCHEDULE=active
      ;;
    media|media-file|file)
      echo WORKER_MEDIA_FILE=active
      echo ENABLE_MEDIA_FILE=active
      echo ENABLE_JOBS=active
      echo ENABLE_SEARXNG=active
      echo OFFICE_FILE_GEN=active
      ;;
    security|sec)
      echo WORKER_SECURITY=active
      echo ENABLE_SECURITY=active
      echo ENABLE_AUTHZ=active
      echo ENABLE_SIEM=active
      echo ENABLE_POLICY=active
      ;;
    openbao|bao)
      # OpenBao requires Security worker overlay (workers.sh forces ENABLE_OPENBAO=inactive otherwise).
      echo WORKER_SECURITY=active
      echo ENABLE_SECURITY=active
      echo ENABLE_AUTHZ=active
      echo ENABLE_SIEM=active
      echo ENABLE_POLICY=active
      echo ENABLE_OPENBAO=active
      ;;
    notify|notification)
      echo WORKER_NOTIFY=active
      echo ENABLE_NOTIFY=active
      ;;
    message|zalo)
      echo WORKER_MESSAGE=active
      echo ENABLE_MESSAGE=active
      echo ENABLE_ZALO=active
      ;;
    monitor|mon)
      echo WORKER_MONITOR=active
      echo ENABLE_MONITOR=active
      echo ENABLE_GRAFANA=active
      echo ENABLE_PROMETHEUS=active
      echo ENABLE_LOKI=active
      echo ENABLE_ALLOY=active
      ;;
    # Attachable flags (section D ENABLE_*)
    searxng|search)
      echo ENABLE_SEARXNG=active
      ;;
    jobs)
      echo WORKER_MEDIA_FILE=active
      echo ENABLE_JOBS=active
      ;;
    grafana)
      echo ENABLE_GRAFANA=active
      echo ENABLE_PROMETHEUS=active
      ;;
    prometheus|prom)
      echo ENABLE_PROMETHEUS=active
      ;;
    loki)
      echo ENABLE_LOKI=active
      echo ENABLE_ALLOY=active
      ;;
    alloy)
      echo ENABLE_ALLOY=active
      ;;
    antivirus|av|clamav)
      echo ENABLE_ANTIVIRUS=active
      ;;
    clouddrive|cloud-drive|rclone)
      echo ENABLE_CLOUDDRIVE=active
      ;;
    openvpn|vpn)
      echo ENABLE_OPENVPN=active
      ;;
    traefik|edge)
      echo ENABLE_TRAEFIK=active
      ;;
    gateway|api-gateway|api_gateway)
      echo ENABLE_API_GATEWAY=active
      ;;
    *)
      echo "ERROR: unknown install name: $1 (run: bash run.sh install list)" >&2
      return 1
      ;;
  esac
}

_uninstall_pairs() {
  case "$1" in
    schedule|sched)
      echo WORKER_SCHEDULE=inactive
      echo ENABLE_SCHEDULE=inactive
      ;;
    media|media-file|file)
      echo WORKER_MEDIA_FILE=inactive
      echo ENABLE_MEDIA_FILE=inactive
      echo ENABLE_JOBS=inactive
      echo ENABLE_SEARXNG=inactive
      echo OFFICE_FILE_GEN=inactive
      ;;
    security|sec|openbao|bao)
      echo WORKER_SECURITY=inactive
      echo ENABLE_SECURITY=inactive
      echo ENABLE_OPENBAO=inactive
      echo ENABLE_AUTHZ=inactive
      echo ENABLE_SIEM=inactive
      echo ENABLE_POLICY=inactive
      ;;
    notify|notification)
      echo WORKER_NOTIFY=inactive
      echo ENABLE_NOTIFY=inactive
      ;;
    message|zalo)
      echo WORKER_MESSAGE=inactive
      echo ENABLE_MESSAGE=inactive
      echo ENABLE_ZALO=inactive
      ;;
    monitor|mon|grafana)
      echo WORKER_MONITOR=inactive
      echo ENABLE_MONITOR=inactive
      echo ENABLE_GRAFANA=inactive
      echo ENABLE_PROMETHEUS=inactive
      echo ENABLE_LOKI=inactive
      echo ENABLE_ALLOY=inactive
      ;;
    searxng|search)
      echo ENABLE_SEARXNG=inactive
      ;;
    jobs)
      echo ENABLE_JOBS=inactive
      ;;
    prometheus|prom)
      echo ENABLE_PROMETHEUS=inactive
      ;;
    loki)
      echo ENABLE_LOKI=inactive
      echo ENABLE_ALLOY=inactive
      ;;
    alloy)
      echo ENABLE_ALLOY=inactive
      ;;
    antivirus|av|clamav)
      echo ENABLE_ANTIVIRUS=inactive
      ;;
    clouddrive|cloud-drive|rclone)
      echo ENABLE_CLOUDDRIVE=inactive
      ;;
    openvpn|vpn)
      echo ENABLE_OPENVPN=inactive
      ;;
    traefik|edge)
      echo ENABLE_TRAEFIK=inactive
      ;;
    gateway|api-gateway|api_gateway)
      echo ENABLE_API_GATEWAY=inactive
      ;;
    *)
      echo "ERROR: unknown uninstall name: $1 (run: bash run.sh install list)" >&2
      return 1
      ;;
  esac
}

_list_catalog() {
  cat <<'EOF'
Optional workers + attachable flags (default inactive in .env.example section D).

Workers:
  schedule          WORKER_SCHEDULE=active
  media             WORKER_MEDIA_FILE=active (+ Jobs, SearXNG)
  security          WORKER_SECURITY=active (OpenBao, authz, SIEM, policy)
  openbao           WORKER_SECURITY=active + ENABLE_OPENBAO=active
  notify            WORKER_NOTIFY=active
  message | zalo    WORKER_MESSAGE=active + ENABLE_ZALO=active
  monitor           WORKER_MONITOR=active (+ Grafana, Prometheus, Loki, Alloy)

Attachable (section D ENABLE_*):
  jobs              media worker + ENABLE_JOBS=active
  searxng           ENABLE_SEARXNG=active
  grafana           ENABLE_GRAFANA=active + Prometheus
  prometheus        ENABLE_PROMETHEUS=active
  loki              ENABLE_LOKI=active + Alloy
  alloy             ENABLE_ALLOY=active
  antivirus         ENABLE_ANTIVIRUS=active
  clouddrive        ENABLE_CLOUDDRIVE=active
  openvpn           ENABLE_OPENVPN=active
  traefik           ENABLE_TRAEFIK=active
  gateway           ENABLE_API_GATEWAY=active

Examples:
  bash run.sh install openbao
  bash run.sh install schedule media message zalo
  bash run.sh install monitor --no-up    # write .env only; then bash run.sh up
  bash run.sh install schedule media security notify monitor antivirus --update
  bash run.sh uninstall zalo traefik
  bash run.sh uninstall schedule media security notify monitor antivirus --update
EOF
}

_dedupe_pairs() {
  # Last KEY= wins when a bundle repeats keys (e.g. openbao + security).
  python3 - "$@" <<'PY'
import sys
order: list[tuple[str, str]] = []
seen: dict[str, str] = {}
for raw in sys.argv[1:]:
    if "=" not in raw:
        continue
    k, v = raw.split("=", 1)
    seen[k] = v
for k, v in seen.items():
    print(f"{k}={v}")
PY
}

_resolve_many() {
  local name rc=0
  local -a raw=()
  for name in "$@"; do
    while IFS= read -r line; do
      [[ -n "$line" ]] && raw+=("$line")
    done < <(_install_pairs "$name") || rc=1
  done
  ((${#raw[@]})) || return "${rc:-1}"
  _dedupe_pairs "${raw[@]}"
  return "$rc"
}

_unresolve_many() {
  local name rc=0
  local -a raw=()
  for name in "$@"; do
    while IFS= read -r line; do
      [[ -n "$line" ]] && raw+=("$line")
    done < <(_uninstall_pairs "$name") || rc=1
  done
  ((${#raw[@]})) || return "${rc:-1}"
  _dedupe_pairs "${raw[@]}"
  return "$rc"
}

case "$cmd" in
  list|-l|--list)
    _list_catalog
    ;;
  resolve)
    ((${#@})) || { echo "usage: $0 resolve NAME [NAME…]" >&2; exit 2; }
    _resolve_many "$@"
    ;;
  unresolve)
    ((${#@})) || { echo "usage: $0 unresolve NAME [NAME…]" >&2; exit 2; }
    _unresolve_many "$@"
    ;;
  *)
    echo "usage: $0 list | resolve NAME… | unresolve NAME…" >&2
    exit 2
    ;;
esac
