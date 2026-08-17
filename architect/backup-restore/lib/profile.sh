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

  # Traefik: default ON all profiles; mode public with fail-soft to local in run.sh
  export ENABLE_TRAEFIK="${ENABLE_TRAEFIK:-1}"
  export ENABLE_API_GATEWAY="${ENABLE_API_GATEWAY:-1}"
  export TRAEFIK_MODE="${TRAEFIK_MODE:-public}"
  export TRAEFIK_ACME_ENABLED="${TRAEFIK_ACME_ENABLED:-0}"
  # Hermes scale: default 1; High = 2 (one node). Medium stays 1.
  export HERMES_REPLICAS="${HERMES_REPLICAS:-1}"

  case "$ASSISTANT_PROFILE" in
    low)
      export OFFICE_FILE_GEN="${OFFICE_FILE_GEN:-0}"
      export HERMES_REPLICAS=1
      ;;
    medium)
      export ENABLE_OCR="${ENABLE_OCR:-1}"
      export ENABLE_SEARXNG="${ENABLE_SEARXNG:-1}"
      export ENABLE_JOBS="${ENABLE_JOBS:-1}"
      export OFFICE_FILE_GEN="${OFFICE_FILE_GEN:-1}"
      [[ -n "${WEB_BACKENDS:-}" ]] || export WEB_BACKENDS=tavily,firecrawl
      [[ -n "${IMAGE_BACKENDS+x}" ]] || export IMAGE_BACKENDS=llm,vendor,comfy-cpu,comfy-gpu
      export HERMES_REPLICAS=1
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
      export ENABLE_ANTIVIRUS="${ENABLE_ANTIVIRUS:-0}"
      export ENABLE_SECURITY="${ENABLE_SECURITY:-1}"
      export ENABLE_NOTIFY="${ENABLE_NOTIFY:-0}"
      export ENABLE_SIEM="${ENABLE_SIEM:-1}"
      export ENABLE_POLICY="${ENABLE_POLICY:-1}"
      export ENABLE_AUTHZ="${ENABLE_AUTHZ:-1}"
      # OmniRouter optional; High enables model-router layer by default
      # zalo-api follows ENABLE_ZALO (compose profile zalo), not High alone
      export ENABLE_OMNIROUTER="${ENABLE_OMNIROUTER:-0}"
      export ENABLE_MODEL_ROUTER="${ENABLE_MODEL_ROUTER:-1}"
      export HERMES_REPLICAS="${HERMES_REPLICAS:-2}"
      ;;
  esac

  if [[ "${ENABLE_TRAEFIK}" == "1" && "${ENABLE_API_GATEWAY}" == "1" ]]; then
    export GATEWAY_UPSTREAM_URL="${GATEWAY_UPSTREAM_URL:-http://traefik:80}"
  fi

  export ENABLE_TRAEFIK="${ENABLE_TRAEFIK:-1}"
  export ENABLE_API_GATEWAY="${ENABLE_API_GATEWAY:-1}"
  export HERMES_REPLICAS="${HERMES_REPLICAS:-1}"
}

assistant_profile_summary() {
  echo "ASSISTANT_PROFILE=${ASSISTANT_PROFILE}"
  echo "ASSISTANT_DATA_DIR=${ASSISTANT_DATA_DIR:-/data/assistant}"
  echo "BACKUP_DIR=${BACKUP_DIR:-/data/assistant/backups}"
  echo "TRAEFIK_MODE=${TRAEFIK_MODE:-public} TRAEFIK_ACME=${TRAEFIK_ACME_ENABLED:-0}"
  echo "optional OCR=${ENABLE_OCR:-0} SEARXNG=${ENABLE_SEARXNG:-0} JOBS=${ENABLE_JOBS:-0} OFFICE_FILE_GEN=${OFFICE_FILE_GEN:-0} WEB_BACKENDS=${WEB_BACKENDS:-} OPENBAO=${ENABLE_OPENBAO:-0} CLOUDDRIVE=${ENABLE_CLOUDDRIVE:-0} ANTIVIRUS=${ENABLE_ANTIVIRUS:-0} NOTIFY=${ENABLE_NOTIFY:-0} ZALO=${ENABLE_ZALO:-0} TRAEFIK=${ENABLE_TRAEFIK:-0} API_GATEWAY=${ENABLE_API_GATEWAY:-0} OPENVPN=${ENABLE_OPENVPN:-0} OMNIROUTER=${ENABLE_OMNIROUTER:-0} MODEL_ROUTER=${ENABLE_MODEL_ROUTER:-1} LOG_ARCHIVE=${ENABLE_LOG_ARCHIVE:-1} HERMES_REPLICAS=${HERMES_REPLICAS:-1}"
}
