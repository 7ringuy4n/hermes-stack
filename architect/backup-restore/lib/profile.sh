#!/usr/bin/env bash
# Expand ASSISTANT_PROFILE into optional ENABLE_* only (Must services need no ENABLE_*).
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
  export ENABLE_ADMIN_API="${ENABLE_ADMIN_API:-0}"
  export ENABLE_ZALO="${ENABLE_ZALO:-0}"
  export ENABLE_TELEGRAM="${ENABLE_TELEGRAM:-0}"
  # OpenVPN stays opt-in everywhere; Traefik/Gateway set per profile below
  export ENABLE_OPENVPN="${ENABLE_OPENVPN:-0}"
  export TRAEFIK_ACME_ENABLED="${TRAEFIK_ACME_ENABLED:-0}"
  export ENABLE_WHATSAPP=0
  export ENABLE_VAULT=0

  case "$ASSISTANT_PROFILE" in
    low)
      # Must-only: no web / file-gen / image even if leftover keys in .env
      export WEB_BACKENDS=
      export OFFICE_FILE_GEN=0
      export IMAGE_BACKENDS=
      export ENABLE_TRAEFIK=0
      export ENABLE_API_GATEWAY=0
      export TRAEFIK_ACME_ENABLED=0
      export HERMES_REPLICAS=1
      ;;
    medium)
      export ENABLE_OCR=1
      export ENABLE_SEARXNG=1
      export ENABLE_JOBS=1
      export OFFICE_FILE_GEN="${OFFICE_FILE_GEN:-1}"
      [[ -n "${WEB_BACKENDS:-}" ]] || export WEB_BACKENDS=tavily,firecrawl
      # Image: llm (OpenAI/Gemini/DeepSeek) → vendor (fal/…) → ComfyUI CPU → GPU
      [[ -n "${IMAGE_BACKENDS:-}" ]] || export IMAGE_BACKENDS=llm,vendor,comfy-cpu,comfy-gpu
      # Edge on by default for Medium (set ENABLE_TRAEFIK=0 in .env to disable)
      export ENABLE_TRAEFIK="${ENABLE_TRAEFIK:-1}"
      export ENABLE_API_GATEWAY="${ENABLE_API_GATEWAY:-1}"
      export HERMES_REPLICAS="${HERMES_REPLICAS:-2}"
      if [[ "${ENABLE_TRAEFIK}" == "1" && "${ENABLE_API_GATEWAY}" == "1" ]]; then
        export GATEWAY_UPSTREAM_URL="${GATEWAY_UPSTREAM_URL:-http://traefik:80}"
      fi
      ;;
    high)
      export ENABLE_OCR=1
      export ENABLE_SEARXNG=1
      export ENABLE_JOBS=1
      export OFFICE_FILE_GEN="${OFFICE_FILE_GEN:-1}"
      [[ -n "${WEB_BACKENDS:-}" ]] || export WEB_BACKENDS=tavily,firecrawl
      [[ -n "${IMAGE_BACKENDS:-}" ]] || export IMAGE_BACKENDS=llm,vendor,comfy-cpu,comfy-gpu
      # Observability defaults ON for High; set ENABLE_GRAFANA=0 (etc.) in .env to skip
      export ENABLE_GRAFANA="${ENABLE_GRAFANA:-1}"
      export ENABLE_LOKI="${ENABLE_LOKI:-1}"
      export ENABLE_PROMETHEUS="${ENABLE_PROMETHEUS:-1}"
      export ENABLE_ALLOY="${ENABLE_ALLOY:-1}"
      export ENABLE_CLOUDDRIVE="${ENABLE_CLOUDDRIVE:-0}"
      export ENABLE_OPENBAO=1
      export ENABLE_OPENBAO_AGENT="${ENABLE_OPENBAO_AGENT:-0}"
      # ClamAV / av-gateway opt-in — default OFF on High (compose profile antivirus)
      export ENABLE_ANTIVIRUS="${ENABLE_ANTIVIRUS:-0}"
      export ENABLE_SECURITY=1
      # Notify opt-in (channel thread required) — default OFF on High
      export ENABLE_NOTIFY="${ENABLE_NOTIFY:-0}"
      export ENABLE_SIEM=1
      export ENABLE_POLICY=1
      export ENABLE_AUTHZ=1
      export ENABLE_ADMIN_API=1
      export ENABLE_TRAEFIK="${ENABLE_TRAEFIK:-1}"
      export ENABLE_API_GATEWAY="${ENABLE_API_GATEWAY:-1}"
      export HERMES_REPLICAS="${HERMES_REPLICAS:-2}"
      if [[ "${ENABLE_TRAEFIK}" == "1" && "${ENABLE_API_GATEWAY}" == "1" ]]; then
        export GATEWAY_UPSTREAM_URL="${GATEWAY_UPSTREAM_URL:-http://traefik:80}"
      fi
      ;;
  esac
  # Defaults if profile did not set (unknown → low already remapped)
  export ENABLE_TRAEFIK="${ENABLE_TRAEFIK:-0}"
  export ENABLE_API_GATEWAY="${ENABLE_API_GATEWAY:-0}"
  export HERMES_REPLICAS="${HERMES_REPLICAS:-1}"
}

assistant_profile_summary() {
  echo "ASSISTANT_PROFILE=${ASSISTANT_PROFILE}"
  echo "ASSISTANT_DATA_DIR=${ASSISTANT_DATA_DIR:-/data/assistant}"
  echo "BACKUP_DIR=${BACKUP_DIR:-/data/assistant/backups}"
  echo "optional OCR=${ENABLE_OCR:-0} SEARXNG=${ENABLE_SEARXNG:-0} JOBS=${ENABLE_JOBS:-0} OFFICE_FILE_GEN=${OFFICE_FILE_GEN:-0} WEB_BACKENDS=${WEB_BACKENDS:-} OPENBAO=${ENABLE_OPENBAO:-0} CLOUDDRIVE=${ENABLE_CLOUDDRIVE:-0} ANTIVIRUS=${ENABLE_ANTIVIRUS:-0} NOTIFY=${ENABLE_NOTIFY:-0} ZALO=${ENABLE_ZALO:-0} TRAEFIK=${ENABLE_TRAEFIK:-0} API_GATEWAY=${ENABLE_API_GATEWAY:-0} OPENVPN=${ENABLE_OPENVPN:-0} HERMES_REPLICAS=${HERMES_REPLICAS:-1}"
}
