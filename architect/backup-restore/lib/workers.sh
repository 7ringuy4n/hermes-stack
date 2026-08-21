#!/usr/bin/env bash
# Worker activation. Core is always on: Hermes, Memory, Router Worker, Traefik local, watchdog.
# Optional workers are inactive unless WORKER_*=active (or ENABLE_*=1 for compatibility).
# Bundled ENABLE_* for a worker live with that worker — not in default setup.
set -euo pipefail

_worker_active() {
  local worker_val="${1:-inactive}"
  local enable_val="${2:-0}"
  case "$(printf '%s' "$worker_val" | tr '[:upper:]' '[:lower:]')" in
    active|on|1|true|yes) return 0 ;;
  esac
  [[ "${enable_val}" == "1" ]]
}

assistant_workers_apply() {
  # Default setup: optional workers inactive
  export WORKER_SCHEDULE="${WORKER_SCHEDULE:-inactive}"
  export WORKER_MEDIA_FILE="${WORKER_MEDIA_FILE:-inactive}"
  export WORKER_SECURITY="${WORKER_SECURITY:-inactive}"
  export WORKER_NOTIFY="${WORKER_NOTIFY:-inactive}"
  export WORKER_MESSAGE="${WORKER_MESSAGE:-inactive}"
  export WORKER_MONITOR="${WORKER_MONITOR:-inactive}"

  if _worker_active "${WORKER_SCHEDULE}" "${ENABLE_SCHEDULE:-0}"; then
    export WORKER_SCHEDULE=active
    export ENABLE_SCHEDULE=1
    export SCHEDULE_URL="${SCHEDULE_URL:-http://schedule-worker:8110}"
    export SCHEDULE_WORKER=1
  else
    export WORKER_SCHEDULE=inactive
    export ENABLE_SCHEDULE=0
    export SCHEDULE_URL=""
    export SCHEDULE_WORKER=0
  fi

  if _worker_active "${WORKER_MEDIA_FILE}" "${ENABLE_MEDIA_FILE:-0}"; then
    export WORKER_MEDIA_FILE=active
    export ENABLE_MEDIA_FILE=1
    # Media|File Worker bundled flags (worker defaults, not default-setup)
    export ENABLE_OCR="${ENABLE_OCR:-1}"
    export ENABLE_JOBS="${ENABLE_JOBS:-1}"
    export OFFICE_FILE_GEN="${OFFICE_FILE_GEN:-1}"
    export ENABLE_SEARXNG="${ENABLE_SEARXNG:-1}"
    [[ -n "${WEB_BACKENDS:-}" ]] || export WEB_BACKENDS=tavily,firecrawl,searxng
    [[ -n "${IMAGE_BACKENDS:-}" ]] || export IMAGE_BACKENDS=llm,vendor,comfy-cpu,comfy-gpu
  else
    export WORKER_MEDIA_FILE=inactive
    export ENABLE_MEDIA_FILE=0
    export ENABLE_OCR="${ENABLE_OCR:-0}"
    export ENABLE_JOBS="${ENABLE_JOBS:-0}"
    export OFFICE_FILE_GEN="${OFFICE_FILE_GEN:-0}"
  fi

  if _worker_active "${WORKER_SECURITY}" "${ENABLE_SECURITY:-0}"; then
    export WORKER_SECURITY=active
    export ENABLE_SECURITY=1
    # Bundled with Security Worker (compose profile "security")
    export ENABLE_OPENBAO="${ENABLE_OPENBAO:-1}"
    export ENABLE_AUTHZ="${ENABLE_AUTHZ:-1}"
    export ENABLE_SIEM="${ENABLE_SIEM:-1}"
    export ENABLE_POLICY="${ENABLE_POLICY:-1}"
  else
    export WORKER_SECURITY=inactive
    export ENABLE_SECURITY=0
    # Force off so leftover .env ENABLE_*=1 does not keep security intent
    export ENABLE_OPENBAO=0
    export ENABLE_OPENBAO_AGENT=0
    export ENABLE_AUTHZ=0
    export ENABLE_SIEM=0
    export ENABLE_POLICY=0
  fi

  if _worker_active "${WORKER_NOTIFY}" "${ENABLE_NOTIFY:-0}"; then
    export WORKER_NOTIFY=active
    export ENABLE_NOTIFY=1
  else
    export WORKER_NOTIFY=inactive
    export ENABLE_NOTIFY=0
  fi

  if _worker_active "${WORKER_MESSAGE}" "${ENABLE_MESSAGE:-0}"; then
    export WORKER_MESSAGE=active
    export ENABLE_MESSAGE=1
    export ENABLE_ZALO=1
  else
    export WORKER_MESSAGE=inactive
    export ENABLE_MESSAGE=0
    export ENABLE_ZALO="${ENABLE_ZALO:-0}"
  fi

  if _worker_active "${WORKER_MONITOR}" "${ENABLE_MONITOR:-0}"; then
    export WORKER_MONITOR=active
    export ENABLE_MONITOR=1
    export ENABLE_GRAFANA=1
    export ENABLE_PROMETHEUS=1
    export ENABLE_LOKI=1
    export ENABLE_ALLOY=1
  else
    export WORKER_MONITOR=inactive
    export ENABLE_MONITOR=0
    export ENABLE_GRAFANA="${ENABLE_GRAFANA:-0}"
    export ENABLE_PROMETHEUS="${ENABLE_PROMETHEUS:-0}"
    export ENABLE_LOKI="${ENABLE_LOKI:-0}"
    export ENABLE_ALLOY="${ENABLE_ALLOY:-0}"
  fi

  # Single-replica Zalo: SSE through socat fork breaks; use host bridge directly.
  if [[ "${HERMES_REPLICAS:-1}" == "1" && "${ENABLE_ZALO:-0}" == "1" ]]; then
    if [[ -z "${ZALO_PLUGIN_URL:-}" || "${ZALO_PLUGIN_URL:-}" == "http://zalo-proxy:8787" ]]; then
      export ZALO_PLUGIN_URL="http://host.docker.internal:8787"
    fi
  fi

  export ENABLE_SEARXNG="${ENABLE_SEARXNG:-0}"  # overridden active when media worker on
  export ENABLE_CLOUDDRIVE="${ENABLE_CLOUDDRIVE:-0}"
  # OpenBao / authz / SIEM / policy: set above from WORKER_SECURITY; keep agent flag default off
  export ENABLE_OPENBAO_AGENT="${ENABLE_OPENBAO_AGENT:-0}"
  export ENABLE_ANTIVIRUS="${ENABLE_ANTIVIRUS:-0}"
  export ENABLE_TELEGRAM="${ENABLE_TELEGRAM:-0}"
  export ENABLE_OPENVPN="${ENABLE_OPENVPN:-0}"
  export ENABLE_WHATSAPP=0
  export ENABLE_VAULT=0
  export SECURITY_SANDBOX="${SECURITY_SANDBOX:-0}"
  export SECURITY_LLM_JUDGE="${SECURITY_LLM_JUDGE:-0}"
  export ENABLE_LLM_JUDGE="${ENABLE_LLM_JUDGE:-0}"
  export SECURITY_YARA="${SECURITY_YARA:-0}"
  export SECURITY_FAIL_CLOSED="${SECURITY_FAIL_CLOSED:-0}"

  # Core (always on)
  export ENABLE_TRAEFIK="${ENABLE_TRAEFIK:-1}"
  export ENABLE_API_GATEWAY="${ENABLE_API_GATEWAY:-1}"
  export TRAEFIK_MODE="${TRAEFIK_MODE:-local}"
  export TRAEFIK_ACME_ENABLED="${TRAEFIK_ACME_ENABLED:-0}"
  export ENABLE_9ROUTER="${ENABLE_9ROUTER:-0}"
  export ENABLE_OMNIROUTER="${ENABLE_OMNIROUTER:-1}"
  export OMNIROUTER_ENABLE_MEMORY="${OMNIROUTER_ENABLE_MEMORY:-1}"
  export ENABLE_MODEL_ROUTER="${ENABLE_MODEL_ROUTER:-1}"
  export WEB_SEARCH_MAX_RESULTS="${WEB_SEARCH_MAX_RESULTS:-3}"
  export ENABLE_LOG_ARCHIVE="${ENABLE_LOG_ARCHIVE:-1}"
  export LOG_RETENTION_DAYS="${LOG_RETENTION_DAYS:-30}"
  export HERMES_REPLICAS="${HERMES_REPLICAS:-1}"
  export ZALO_INBOUND_QUEUE="${ZALO_INBOUND_QUEUE:-1}"
  export GATEWAY_SKIP_RL_PATHS="${GATEWAY_SKIP_RL_PATHS:-/coding,/v1/coding,/skills/coding,/schedule,/v1/schedule,/skills/schedule,/v1/schedules}"
  export VALKEY_URL="${VALKEY_URL:-redis://valkey:6379/0}"

  if [[ "${ENABLE_SEARXNG}" == "1" ]]; then
    [[ -n "${WEB_BACKENDS:-}" ]] || export WEB_BACKENDS=tavily,firecrawl,searxng
  fi
  if [[ "${ENABLE_9ROUTER:-0}" != "1" ]]; then
    export N9ROUTER_BASE_URL=""
  fi

  if [[ "${SECURITY_SANDBOX:-0}" == "1" ]]; then
    export SECURITY_DOCKER_HOST="${SECURITY_DOCKER_HOST:-tcp://docker-socket-proxy:2375}"
  fi

  if [[ "${ENABLE_TRAEFIK}" == "1" && "${ENABLE_API_GATEWAY}" == "1" ]]; then
    export GATEWAY_UPSTREAM_URL="${GATEWAY_UPSTREAM_URL:-http://traefik:80}"
  fi

  export GATEWAY_REQUIRE_AUTH="${GATEWAY_REQUIRE_AUTH:-1}"
  export GATEWAY_TRUST_FORWARDED="${GATEWAY_TRUST_FORWARDED:-0}"
  export GATEWAY_RL_FAIL_CLOSED="${GATEWAY_RL_FAIL_CLOSED:-1}"
  if [[ "${ENABLE_API_GATEWAY}" == "1" && "${GATEWAY_REQUIRE_AUTH}" == "1" ]]; then
    if [[ -z "${GATEWAY_API_KEYS:-}" ]]; then
      echo "WARN: ENABLE_API_GATEWAY=1 but GATEWAY_API_KEYS is empty — gateway will refuse to start until keys are set (or GATEWAY_REQUIRE_AUTH=0 for isolated lab)." >&2
    fi
  fi
}

assistant_append_monitor_profiles() {
  local -n _amp_profiles="$1"
  local g="${ENABLE_GRAFANA:-0}" p="${ENABLE_PROMETHEUS:-0}" l="${ENABLE_LOKI:-0}" a="${ENABLE_ALLOY:-0}"
  local want_prom=0 want_loki=0
  [[ "$g" == "1" || "$p" == "1" ]] && want_prom=1
  [[ "$l" == "1" || "$a" == "1" ]] && want_loki=1
  if [[ "$g" == "1" ]]; then
    _amp_profiles+=(--profile grafana)
  fi
  if [[ "$want_prom" == "1" ]]; then
    _amp_profiles+=(--profile prometheus)
  fi
  if [[ "$want_loki" == "1" ]]; then
    _amp_profiles+=(--profile loki --profile alloy)
  fi
  if [[ "$want_prom" == "1" && "${ENABLE_OMNIROUTER:-0}" == "1" ]]; then
    _amp_profiles+=(--profile omni-exporter)
  fi
}

assistant_disabled_monitor_containers() {
  local g="${ENABLE_GRAFANA:-0}" p="${ENABLE_PROMETHEUS:-0}" l="${ENABLE_LOKI:-0}" a="${ENABLE_ALLOY:-0}"
  local want_prom=0 want_loki=0
  [[ "$g" == "1" || "$p" == "1" ]] && want_prom=1
  [[ "$l" == "1" || "$a" == "1" ]] && want_loki=1
  [[ "$g" == "1" ]] || echo grafana
  if [[ "$want_prom" != "1" ]]; then
    echo prometheus
    echo nine-exporter
    echo node-exporter
    echo stack-exporter
  fi
  if [[ "$want_loki" != "1" ]]; then
    echo loki
    echo alloy
  fi
  if [[ "$want_prom" != "1" || "${ENABLE_OMNIROUTER:-0}" != "1" ]]; then
    echo omni-exporter
  fi
}

assistant_workers_summary() {
  echo "workers SCHEDULE=${WORKER_SCHEDULE} MEDIA_FILE=${WORKER_MEDIA_FILE} SECURITY=${WORKER_SECURITY} NOTIFY=${WORKER_NOTIFY} MESSAGE=${WORKER_MESSAGE} MONITOR=${WORKER_MONITOR}"
  echo "core TRAEFIK=${ENABLE_TRAEFIK:-1} GATEWAY=${ENABLE_API_GATEWAY:-1} OMNI=${ENABLE_OMNIROUTER:-1} N9=${ENABLE_9ROUTER:-0} ROUTER=${ENABLE_MODEL_ROUTER:-1} REPLICAS=${HERMES_REPLICAS:-1} QUEUE=${ZALO_INBOUND_QUEUE:-1}"
  echo "ASSISTANT_DATA_DIR=${ASSISTANT_DATA_DIR:-/data/assistant}"
  echo "BACKUP_DIR=${BACKUP_DIR:-/data/assistant/backups}"
  echo "TRAEFIK_MODE=${TRAEFIK_MODE:-local} TRAEFIK_ACME=${TRAEFIK_ACME_ENABLED:-0}"
}

# Compat name used by run.sh / backup until callers switch
assistant_profile_summary() { assistant_workers_summary; }

assistant_options_dump() {
  cat <<EOF
WORKER_SCHEDULE=${WORKER_SCHEDULE:-inactive}
WORKER_MEDIA_FILE=${WORKER_MEDIA_FILE:-inactive}
WORKER_SECURITY=${WORKER_SECURITY:-inactive}
WORKER_NOTIFY=${WORKER_NOTIFY:-inactive}
WORKER_MESSAGE=${WORKER_MESSAGE:-inactive}
WORKER_MONITOR=${WORKER_MONITOR:-inactive}
HERMES_REPLICAS=${HERMES_REPLICAS:-1}
TRAEFIK_MODE=${TRAEFIK_MODE:-local}
TRAEFIK_ACME_ENABLED=${TRAEFIK_ACME_ENABLED:-0}
ENABLE_TRAEFIK=${ENABLE_TRAEFIK:-0}
ENABLE_API_GATEWAY=${ENABLE_API_GATEWAY:-0}
ENABLE_OCR=${ENABLE_OCR:-0}
ENABLE_SEARXNG=${ENABLE_SEARXNG:-0}
ENABLE_JOBS=${ENABLE_JOBS:-0}
OFFICE_FILE_GEN=${OFFICE_FILE_GEN:-0}
WEB_BACKENDS=${WEB_BACKENDS:-}
IMAGE_BACKENDS=${IMAGE_BACKENDS:-}
ENABLE_GRAFANA=${ENABLE_GRAFANA:-0}
ENABLE_LOKI=${ENABLE_LOKI:-0}
ENABLE_PROMETHEUS=${ENABLE_PROMETHEUS:-0}
ENABLE_ALLOY=${ENABLE_ALLOY:-0}
ENABLE_CLOUDDRIVE=${ENABLE_CLOUDDRIVE:-0}
ENABLE_OPENBAO=${ENABLE_OPENBAO:-0}
ENABLE_OPENBAO_AGENT=${ENABLE_OPENBAO_AGENT:-0}
ENABLE_ANTIVIRUS=${ENABLE_ANTIVIRUS:-0}
ENABLE_SECURITY=${ENABLE_SECURITY:-0}
ENABLE_NOTIFY=${ENABLE_NOTIFY:-0}
ENABLE_SIEM=${ENABLE_SIEM:-0}
ENABLE_POLICY=${ENABLE_POLICY:-0}
ENABLE_AUTHZ=${ENABLE_AUTHZ:-0}
ENABLE_ZALO=${ENABLE_ZALO:-0}
ENABLE_TELEGRAM=${ENABLE_TELEGRAM:-0}
ENABLE_OPENVPN=${ENABLE_OPENVPN:-0}
ENABLE_SCHEDULE=${ENABLE_SCHEDULE:-0}
ENABLE_MEDIA_FILE=${ENABLE_MEDIA_FILE:-0}
ENABLE_MESSAGE=${ENABLE_MESSAGE:-0}
ENABLE_MONITOR=${ENABLE_MONITOR:-0}
ENABLE_OMNIROUTER=${ENABLE_OMNIROUTER:-1}
ENABLE_9ROUTER=${ENABLE_9ROUTER:-0}
OMNIROUTER_ENABLE_MEMORY=${OMNIROUTER_ENABLE_MEMORY:-1}
WEB_SEARCH_MAX_RESULTS=${WEB_SEARCH_MAX_RESULTS:-3}
ENABLE_MODEL_ROUTER=${ENABLE_MODEL_ROUTER:-1}
ENABLE_LOG_ARCHIVE=${ENABLE_LOG_ARCHIVE:-1}
SECURITY_SANDBOX=${SECURITY_SANDBOX:-0}
SECURITY_LLM_JUDGE=${SECURITY_LLM_JUDGE:-0}
ENABLE_LLM_JUDGE=${ENABLE_LLM_JUDGE:-0}
SECURITY_YARA=${SECURITY_YARA:-1}
SECURITY_FAIL_CLOSED=${SECURITY_FAIL_CLOSED:-0}
COMFYUI_HAS_GPU=${COMFYUI_HAS_GPU:-0}
VALKEY_URL=${VALKEY_URL:-redis://valkey:6379/0}
EOF
}

assistant_option_key_ok() {
  case "$1" in
    WORKER_SCHEDULE|WORKER_MEDIA_FILE|WORKER_SECURITY|WORKER_NOTIFY|WORKER_MESSAGE|WORKER_MONITOR|HERMES_REPLICAS|TRAEFIK_MODE|TRAEFIK_ACME_ENABLED|ENABLE_TRAEFIK|ENABLE_API_GATEWAY|ENABLE_OCR|ENABLE_SEARXNG|ENABLE_JOBS|OFFICE_FILE_GEN|WEB_BACKENDS|WEB_SEARCH_MAX_RESULTS|IMAGE_BACKENDS|ENABLE_GRAFANA|ENABLE_LOKI|ENABLE_PROMETHEUS|ENABLE_ALLOY|ENABLE_CLOUDDRIVE|ENABLE_OPENBAO|ENABLE_OPENBAO_AGENT|ENABLE_ANTIVIRUS|ENABLE_SECURITY|ENABLE_NOTIFY|ENABLE_SIEM|ENABLE_POLICY|ENABLE_AUTHZ|ENABLE_ZALO|ENABLE_TELEGRAM|ENABLE_OPENVPN|ENABLE_OMNIROUTER|ENABLE_9ROUTER|OMNIROUTER_ENABLE_MEMORY|ENABLE_MODEL_ROUTER|ENABLE_LOG_ARCHIVE|ENABLE_SCHEDULE|ENABLE_MEDIA_FILE|ENABLE_MESSAGE|ENABLE_MONITOR|SECURITY_SANDBOX|SECURITY_LLM_JUDGE|ENABLE_LLM_JUDGE|SECURITY_YARA|SECURITY_FAIL_CLOSED|COMFYUI_HAS_GPU|VALKEY_URL)
      return 0
      ;;
    *)
      return 1
      ;;
  esac
}

# Back-compat for callers still using the old function name
assistant_profile_apply() { assistant_workers_apply; }
