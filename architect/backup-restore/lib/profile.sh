#!/usr/bin/env bash
# Expand ASSISTANT_PROFILE into optional ENABLE_* (Must services need no ENABLE_*).
# v0.5.0: Traefik default all profiles; replicas 1 (High=2); optionals allowed if enabled.
set -euo pipefail

ASSISTANT_PROFILE="${ASSISTANT_PROFILE:-${PROFILE:-low}}"
ASSISTANT_PROFILE="$(printf '%s' "$ASSISTANT_PROFILE" | tr '[:upper:]' '[:lower:]')"

assistant_profile_apply() {
  case "$ASSISTANT_PROFILE" in
    low|medium|high) ;;
    *)
      echo "WARN: unknown ASSISTANT_PROFILE=${ASSISTANT_PROFILE}; using low" >&2
      ASSISTANT_PROFILE=low
      ;;
  esac
  export ASSISTANT_PROFILE

  # Optionals: default 0; any profile may set ENABLE_*=1 in .env
  export ENABLE_OCR="${ENABLE_OCR:-0}"
  export ENABLE_SEARXNG="${ENABLE_SEARXNG:-0}"
  export ENABLE_JOBS="${ENABLE_JOBS:-0}"
  export ENABLE_GRAFANA="${ENABLE_GRAFANA:-0}"
  export ENABLE_LOKI="${ENABLE_LOKI:-0}"
  export ENABLE_PROMETHEUS="${ENABLE_PROMETHEUS:-0}"
  export ENABLE_ALLOY="${ENABLE_ALLOY:-0}"
  export ENABLE_CLOUDDRIVE="${ENABLE_CLOUDDRIVE:-0}"
  export ENABLE_OPENBAO="${ENABLE_OPENBAO:-0}"
  export ENABLE_OPENBAO_AGENT="${ENABLE_OPENBAO_AGENT:-0}"
  export ENABLE_ANTIVIRUS="${ENABLE_ANTIVIRUS:-0}"
  export ENABLE_SECURITY="${ENABLE_SECURITY:-0}"
  export ENABLE_NOTIFY="${ENABLE_NOTIFY:-0}"
  export ENABLE_SIEM="${ENABLE_SIEM:-0}"
  export ENABLE_POLICY="${ENABLE_POLICY:-0}"
  export ENABLE_AUTHZ="${ENABLE_AUTHZ:-0}"
  export ENABLE_ZALO="${ENABLE_ZALO:-0}"
  export ENABLE_TELEGRAM="${ENABLE_TELEGRAM:-0}"
  export ENABLE_OPENVPN="${ENABLE_OPENVPN:-0}"
  export ENABLE_OMNIROUTER="${ENABLE_OMNIROUTER:-0}"
  export ENABLE_MODEL_ROUTER="${ENABLE_MODEL_ROUTER:-1}"
  export ENABLE_LOG_ARCHIVE="${ENABLE_LOG_ARCHIVE:-1}"
  export LOG_RETENTION_DAYS="${LOG_RETENTION_DAYS:-30}"
  export ENABLE_WHATSAPP=0
  export ENABLE_VAULT=0

  # Traefik: default ON; mode local (VPN/localhost). public/ACME is explicit opt-in.
  export ENABLE_TRAEFIK="${ENABLE_TRAEFIK:-1}"
  export ENABLE_API_GATEWAY="${ENABLE_API_GATEWAY:-1}"
  export TRAEFIK_MODE="${TRAEFIK_MODE:-local}"
  export TRAEFIK_ACME_ENABLED="${TRAEFIK_ACME_ENABLED:-0}"
  # Hermes scale: default 1; High = 2 (one node). Medium stays 1.
  export HERMES_REPLICAS="${HERMES_REPLICAS:-1}"

  case "$ASSISTANT_PROFILE" in
    low)
      export OFFICE_FILE_GEN="${OFFICE_FILE_GEN:-0}"
      export HERMES_REPLICAS=1
      export ENABLE_OMNIROUTER="${ENABLE_OMNIROUTER:-1}"
      ;;
    medium)
      export ENABLE_OCR="${ENABLE_OCR:-1}"
      export ENABLE_SEARXNG="${ENABLE_SEARXNG:-1}"
      export ENABLE_JOBS="${ENABLE_JOBS:-1}"
      export OFFICE_FILE_GEN="${OFFICE_FILE_GEN:-1}"
      [[ -n "${WEB_BACKENDS:-}" ]] || export WEB_BACKENDS=tavily,firecrawl
      [[ -n "${IMAGE_BACKENDS+x}" ]] || export IMAGE_BACKENDS=llm,vendor,comfy-cpu,comfy-gpu
      export HERMES_REPLICAS=1
      export ENABLE_OMNIROUTER="${ENABLE_OMNIROUTER:-1}"
      ;;
    high)
      export ENABLE_OCR="${ENABLE_OCR:-1}"
      export ENABLE_SEARXNG="${ENABLE_SEARXNG:-1}"
      export ENABLE_JOBS="${ENABLE_JOBS:-1}"
      export OFFICE_FILE_GEN="${OFFICE_FILE_GEN:-1}"
      [[ -n "${WEB_BACKENDS:-}" ]] || export WEB_BACKENDS=tavily,firecrawl
      [[ -n "${IMAGE_BACKENDS+x}" ]] || export IMAGE_BACKENDS=llm,vendor,comfy-cpu,comfy-gpu
      # Monitor optional (allowed if enabled); lab often sets 0
      export ENABLE_GRAFANA="${ENABLE_GRAFANA:-0}"
      export ENABLE_LOKI="${ENABLE_LOKI:-0}"
      export ENABLE_PROMETHEUS="${ENABLE_PROMETHEUS:-0}"
      export ENABLE_ALLOY="${ENABLE_ALLOY:-0}"
      export ENABLE_CLOUDDRIVE="${ENABLE_CLOUDDRIVE:-0}"
      export ENABLE_OPENBAO="${ENABLE_OPENBAO:-1}"
      export ENABLE_OPENBAO_AGENT="${ENABLE_OPENBAO_AGENT:-0}"
      export ENABLE_SECURITY="${ENABLE_SECURITY:-1}"
      export ENABLE_NOTIFY="${ENABLE_NOTIFY:-0}"
      export ENABLE_SIEM="${ENABLE_SIEM:-1}"
      export ENABLE_POLICY="${ENABLE_POLICY:-1}"
      export ENABLE_AUTHZ="${ENABLE_AUTHZ:-1}"
      # Isolation defaults: YARA on; AV/sandbox/LLM judge off (judge is heuristic-only if enabled)
      export ENABLE_ANTIVIRUS="${ENABLE_ANTIVIRUS:-0}"
      export SECURITY_SANDBOX="${SECURITY_SANDBOX:-0}"
      export SECURITY_LLM_JUDGE="${SECURITY_LLM_JUDGE:-0}"
      export ENABLE_LLM_JUDGE="${ENABLE_LLM_JUDGE:-0}"
      export SECURITY_YARA="${SECURITY_YARA:-1}"
      export SECURITY_FAIL_CLOSED="${SECURITY_FAIL_CLOSED:-1}"
      # OmniRouter optional; High enables model-router layer by default
      # zalo-api follows ENABLE_ZALO (compose profile zalo), not High alone
      export ENABLE_OMNIROUTER="${ENABLE_OMNIROUTER:-0}"
      export ENABLE_MODEL_ROUTER="${ENABLE_MODEL_ROUTER:-1}"
      export HERMES_REPLICAS="${HERMES_REPLICAS:-2}"
      ;;
  esac

  if [[ "${SECURITY_SANDBOX:-0}" == "1" ]]; then
    export SECURITY_DOCKER_HOST="${SECURITY_DOCKER_HOST:-tcp://docker-socket-proxy:2375}"
  fi

  if [[ "${ENABLE_TRAEFIK}" == "1" && "${ENABLE_API_GATEWAY}" == "1" ]]; then
    export GATEWAY_UPSTREAM_URL="${GATEWAY_UPSTREAM_URL:-http://traefik:80}"
  fi

  export ENABLE_TRAEFIK="${ENABLE_TRAEFIK:-1}"
  export ENABLE_API_GATEWAY="${ENABLE_API_GATEWAY:-1}"
  export HERMES_REPLICAS="${HERMES_REPLICAS:-1}"
  export GATEWAY_REQUIRE_AUTH="${GATEWAY_REQUIRE_AUTH:-1}"
  export GATEWAY_TRUST_FORWARDED="${GATEWAY_TRUST_FORWARDED:-0}"
  export GATEWAY_RL_FAIL_CLOSED="${GATEWAY_RL_FAIL_CLOSED:-1}"
  if [[ "${ENABLE_API_GATEWAY}" == "1" && "${GATEWAY_REQUIRE_AUTH}" == "1" ]]; then
    if [[ -z "${GATEWAY_API_KEYS:-}" ]]; then
      echo "WARN: ENABLE_API_GATEWAY=1 but GATEWAY_API_KEYS is empty — gateway will refuse to start until keys are set (or GATEWAY_REQUIRE_AUTH=0 for isolated lab)." >&2
    fi
  fi
}

# Observability compose profiles. Exporters start only with the component they scrape.
#   Grafana ↔ Prometheus + nine-exporter + node-exporter (host hardware) + stack-exporter
#   Loki ↔ Alloy
#   OmniRouter ↔ omni-exporter (only when Prometheus is also on)
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

assistant_profile_summary() {
  echo "ASSISTANT_PROFILE=${ASSISTANT_PROFILE}"
  echo "ASSISTANT_DATA_DIR=${ASSISTANT_DATA_DIR:-/data/assistant}"
  echo "BACKUP_DIR=${BACKUP_DIR:-/data/assistant/backups}"
  echo "TRAEFIK_MODE=${TRAEFIK_MODE:-local} TRAEFIK_ACME=${TRAEFIK_ACME_ENABLED:-0}"
  echo "optional OCR=${ENABLE_OCR:-0} SEARXNG=${ENABLE_SEARXNG:-0} JOBS=${ENABLE_JOBS:-0} OFFICE_FILE_GEN=${OFFICE_FILE_GEN:-0} WEB_BACKENDS=${WEB_BACKENDS:-} OPENBAO=${ENABLE_OPENBAO:-0} CLOUDDRIVE=${ENABLE_CLOUDDRIVE:-0} ANTIVIRUS=${ENABLE_ANTIVIRUS:-0} SANDBOX=${SECURITY_SANDBOX:-0} LLM_JUDGE=${SECURITY_LLM_JUDGE:-0} NOTIFY=${ENABLE_NOTIFY:-0} ZALO=${ENABLE_ZALO:-0} TRAEFIK=${ENABLE_TRAEFIK:-0} API_GATEWAY=${ENABLE_API_GATEWAY:-0} OPENVPN=${ENABLE_OPENVPN:-0} OMNIROUTER=${ENABLE_OMNIROUTER:-0} GRAFANA=${ENABLE_GRAFANA:-0} PROMETHEUS=${ENABLE_PROMETHEUS:-0} LOKI=${ENABLE_LOKI:-0} ALLOY=${ENABLE_ALLOY:-0} MODEL_ROUTER=${ENABLE_MODEL_ROUTER:-1} LOG_ARCHIVE=${ENABLE_LOG_ARCHIVE:-1} HERMES_REPLICAS=${HERMES_REPLICAS:-1}"
}

# Non-secret option snapshot (restore later via stamp config/env.sealed + this file).
assistant_options_dump() {
  cat <<EOF
ASSISTANT_PROFILE=${ASSISTANT_PROFILE:-low}
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
ENABLE_OMNIROUTER=${ENABLE_OMNIROUTER:-0}
ENABLE_MODEL_ROUTER=${ENABLE_MODEL_ROUTER:-1}
ENABLE_LOG_ARCHIVE=${ENABLE_LOG_ARCHIVE:-1}
SECURITY_SANDBOX=${SECURITY_SANDBOX:-0}
SECURITY_LLM_JUDGE=${SECURITY_LLM_JUDGE:-0}
ENABLE_LLM_JUDGE=${ENABLE_LLM_JUDGE:-0}
SECURITY_YARA=${SECURITY_YARA:-1}
SECURITY_FAIL_CLOSED=${SECURITY_FAIL_CLOSED:-0}
COMFYUI_HAS_GPU=${COMFYUI_HAS_GPU:-0}
EOF
}

assistant_option_key_ok() {
  case "$1" in
    ASSISTANT_PROFILE|HERMES_REPLICAS|TRAEFIK_MODE|TRAEFIK_ACME_ENABLED|ENABLE_TRAEFIK|ENABLE_API_GATEWAY|ENABLE_OCR|ENABLE_SEARXNG|ENABLE_JOBS|OFFICE_FILE_GEN|WEB_BACKENDS|IMAGE_BACKENDS|ENABLE_GRAFANA|ENABLE_LOKI|ENABLE_PROMETHEUS|ENABLE_ALLOY|ENABLE_CLOUDDRIVE|ENABLE_OPENBAO|ENABLE_OPENBAO_AGENT|ENABLE_ANTIVIRUS|ENABLE_SECURITY|ENABLE_NOTIFY|ENABLE_SIEM|ENABLE_POLICY|ENABLE_AUTHZ|ENABLE_ZALO|ENABLE_TELEGRAM|ENABLE_OPENVPN|ENABLE_OMNIROUTER|ENABLE_MODEL_ROUTER|ENABLE_LOG_ARCHIVE|SECURITY_SANDBOX|SECURITY_LLM_JUDGE|ENABLE_LLM_JUDGE|SECURITY_YARA|SECURITY_FAIL_CLOSED|COMFYUI_HAS_GPU)
      return 0
      ;;
    *)
      return 1
      ;;
  esac
}
