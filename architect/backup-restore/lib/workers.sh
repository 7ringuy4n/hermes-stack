#!/usr/bin/env bash
# Worker activation. Core is always on: Hermes, Memory, Model Router, Traefik local, watchdog.
# Optional workers are inactive unless WORKER_*=active (or ENABLE_*=active; legacy 1 still accepted via migrate).
# Bundled ENABLE_* for a worker live with that worker — not in default setup.
set -euo pipefail

_env_active() {
  case "$(printf '%s' "${1:-}" | tr '[:upper:]' '[:lower:]')" in
    active|1|true|yes|on) return 0 ;;
  esac
  return 1
}

assistant_migrate_enable_active() {
  # Canonical on/off for feature toggles: active | inactive (never 1/0).
  local k v
  for k in \
    ENABLE_OMNIROUTER ENABLE_JOBS ENABLE_SEARXNG \
    ENABLE_ZALO ENABLE_TELEGRAM ENABLE_SECURITY ENABLE_NOTIFY ENABLE_MONITOR \
    ENABLE_SCHEDULE ENABLE_MEDIA_FILE ENABLE_MESSAGE ENABLE_GRAFANA \
    ENABLE_PROMETHEUS ENABLE_LOKI ENABLE_ALLOY ENABLE_ANTIVIRUS ENABLE_AUTHZ \
    ENABLE_SIEM ENABLE_POLICY ENABLE_OPENBAO ENABLE_OPENBAO_AGENT ENABLE_TRAEFIK \
    ENABLE_API_GATEWAY ENABLE_MODEL_ROUTER ENABLE_CLOUDDRIVE ENABLE_OPENVPN \
    ENABLE_LOG_ARCHIVE OFFICE_FILE_GEN OMNIROUTER_ENABLE_MEMORY \
    ENABLE_LLM_JUDGE SECURITY_SANDBOX SECURITY_YARA SECURITY_FAIL_CLOSED \
    SECURITY_LLM_JUDGE IMAGE_ALLOW_PILLOW ZALO_INBOUND_QUEUE \
    ZALO_HISTORY_POSTGRES TRAEFIK_ACME_ENABLED ENABLE_QWEN ENABLE_QWEN_THINKING
  do
    v="$(eval "printf '%s' \"\${${k}:-}\"")"
    case "$(printf '%s' "$v" | tr '[:upper:]' '[:lower:]')" in
      1|true|yes|on) eval "export ${k}=active" ;;
      0|false|no|off) eval "export ${k}=inactive" ;;
    esac
  done
}

_worker_active() {
  local worker_val="${1:-inactive}"
  local enable_val="${2:-inactive}"
  case "$(printf '%s' "$worker_val" | tr '[:upper:]' '[:lower:]')" in
    active) return 0 ;;
  esac
  case "$(printf '%s' "$enable_val" | tr '[:upper:]' '[:lower:]')" in
    active) return 0 ;;
    # Legacy ENABLE_*=1 still accepted until migrate rewrites .env to active.
    1) return 0 ;;
  esac
  return 1
}

assistant_workers_apply() {
  assistant_migrate_enable_active

  # Default setup: optional workers inactive
  export WORKER_SCHEDULE="${WORKER_SCHEDULE:-inactive}"
  export WORKER_MEDIA_FILE="${WORKER_MEDIA_FILE:-inactive}"
  export WORKER_SECURITY="${WORKER_SECURITY:-inactive}"
  export WORKER_NOTIFY="${WORKER_NOTIFY:-inactive}"
  export WORKER_MESSAGE="${WORKER_MESSAGE:-inactive}"
  export WORKER_MONITOR="${WORKER_MONITOR:-inactive}"

  # Migrate legacy ENABLE_MEDIA_FILE=1|true|yes|on → active (media flag is active-only).
  case "$(printf '%s' "${ENABLE_MEDIA_FILE:-}" | tr '[:upper:]' '[:lower:]')" in
    1|true|yes|on) export ENABLE_MEDIA_FILE=active ;;
  esac

  if _worker_active "${WORKER_SCHEDULE}" "${ENABLE_SCHEDULE:-0}"; then
    export WORKER_SCHEDULE=active
    export ENABLE_SCHEDULE=active
    export SCHEDULE_URL="${SCHEDULE_URL:-http://schedule-worker:8110}"
    export SCHEDULE_WORKER=active
  else
    export WORKER_SCHEDULE=inactive
    export ENABLE_SCHEDULE=inactive
    export SCHEDULE_URL=""
    export SCHEDULE_WORKER=inactive
  fi

  if _worker_active "${WORKER_MEDIA_FILE}" "${ENABLE_MEDIA_FILE:-inactive}"; then
    export WORKER_MEDIA_FILE=active
    export ENABLE_MEDIA_FILE=active
    # Media|File Worker bundled flags (worker defaults, not default-setup)
    export ENABLE_JOBS="${ENABLE_JOBS:-active}"
    export OFFICE_FILE_GEN="${OFFICE_FILE_GEN:-active}"
    export ENABLE_SEARXNG="${ENABLE_SEARXNG:-active}"
    # Web search runs on model-router via Omni combo web-search only
    [[ -n "${IMAGE_GEN_COMBO:-}" ]] || export IMAGE_GEN_COMBO=image-gen
    [[ -n "${OCR_MODEL:-}" ]] || export OCR_MODEL=vision-ocr
    [[ -n "${EMBED_MODEL:-}" ]] || export EMBED_MODEL=embedding
  else
    export WORKER_MEDIA_FILE=inactive
    export ENABLE_MEDIA_FILE=inactive
    export ENABLE_JOBS="${ENABLE_JOBS:-inactive}"
    export OFFICE_FILE_GEN="${OFFICE_FILE_GEN:-inactive}"
  fi

  if _worker_active "${WORKER_SECURITY}" "${ENABLE_SECURITY:-0}"; then
    export WORKER_SECURITY=active
    export ENABLE_SECURITY=active
    # Bundled with Security Worker (compose profile "security")
    export ENABLE_OPENBAO="${ENABLE_OPENBAO:-active}"
    export ENABLE_AUTHZ="${ENABLE_AUTHZ:-active}"
    export ENABLE_SIEM="${ENABLE_SIEM:-active}"
    export ENABLE_POLICY="${ENABLE_POLICY:-active}"
  else
    export WORKER_SECURITY=inactive
    export ENABLE_SECURITY=inactive
    # OpenBao is core (secrets SoT) — independent of full Security worker stack.
    export ENABLE_OPENBAO="${ENABLE_OPENBAO:-active}"
    export ENABLE_OPENBAO_AGENT=inactive
    export ENABLE_AUTHZ=inactive
    export ENABLE_SIEM=inactive
    export ENABLE_POLICY=inactive
  fi

  if _worker_active "${WORKER_NOTIFY}" "${ENABLE_NOTIFY:-0}"; then
    export WORKER_NOTIFY=active
    export ENABLE_NOTIFY=active
  else
    export WORKER_NOTIFY=inactive
    export ENABLE_NOTIFY=inactive
  fi

  if _worker_active "${WORKER_MESSAGE}" "${ENABLE_MESSAGE:-0}"; then
    export WORKER_MESSAGE=active
    export ENABLE_MESSAGE=active
    export ENABLE_ZALO=active
  else
    export WORKER_MESSAGE=inactive
    export ENABLE_MESSAGE=inactive
    export ENABLE_ZALO="${ENABLE_ZALO:-inactive}"
  fi

  if _worker_active "${WORKER_MONITOR}" "${ENABLE_MONITOR:-0}"; then
    export WORKER_MONITOR=active
    export ENABLE_MONITOR=active
    export ENABLE_GRAFANA=active
    export ENABLE_PROMETHEUS=active
    export ENABLE_LOKI=active
    export ENABLE_ALLOY=active
  else
    export WORKER_MONITOR=inactive
    export ENABLE_MONITOR=inactive
    export ENABLE_GRAFANA="${ENABLE_GRAFANA:-inactive}"
    export ENABLE_PROMETHEUS="${ENABLE_PROMETHEUS:-inactive}"
    export ENABLE_LOKI="${ENABLE_LOKI:-inactive}"
    export ENABLE_ALLOY="${ENABLE_ALLOY:-inactive}"
  fi

  # Single-replica Zalo: SSE through socat fork breaks; use host bridge directly.
  if [[ "${HERMES_REPLICAS:-1}" == "1" ]] && _env_active "${ENABLE_ZALO:-}"; then
    if [[ -z "${ZALO_PLUGIN_URL:-}" || "${ZALO_PLUGIN_URL:-}" == "http://zalo-proxy:8787" ]]; then
      export ZALO_PLUGIN_URL="http://host.docker.internal:8787"
    fi
  fi

  export ENABLE_SEARXNG="${ENABLE_SEARXNG:-inactive}"  # overridden active when media worker on
  export ENABLE_CLOUDDRIVE="${ENABLE_CLOUDDRIVE:-inactive}"
  # OpenBao / authz / SIEM / policy: set above from WORKER_SECURITY; keep agent flag default off
  export ENABLE_OPENBAO_AGENT="${ENABLE_OPENBAO_AGENT:-inactive}"
  export ENABLE_ANTIVIRUS="${ENABLE_ANTIVIRUS:-inactive}"
  export ENABLE_TELEGRAM="${ENABLE_TELEGRAM:-inactive}"
  export ENABLE_OPENVPN="${ENABLE_OPENVPN:-inactive}"
  export ENABLE_WHATSAPP=inactive
  export ENABLE_VAULT=inactive
  export SECURITY_SANDBOX="${SECURITY_SANDBOX:-inactive}"
  export SECURITY_LLM_JUDGE="${SECURITY_LLM_JUDGE:-inactive}"
  export ENABLE_LLM_JUDGE="${ENABLE_LLM_JUDGE:-inactive}"
  export SECURITY_YARA="${SECURITY_YARA:-inactive}"
  export SECURITY_FAIL_CLOSED="${SECURITY_FAIL_CLOSED:-inactive}"

  # Core (always on)
  export ENABLE_TRAEFIK="${ENABLE_TRAEFIK:-active}"
  export ENABLE_API_GATEWAY="${ENABLE_API_GATEWAY:-active}"
  export TRAEFIK_MODE="${TRAEFIK_MODE:-local}"
  export TRAEFIK_ACME_ENABLED="${TRAEFIK_ACME_ENABLED:-inactive}"
  export ENABLE_OMNIROUTER="${ENABLE_OMNIROUTER:-active}"
  export OMNIROUTER_ENABLE_MEMORY="${OMNIROUTER_ENABLE_MEMORY:-active}"
  export ENABLE_MODEL_ROUTER="${ENABLE_MODEL_ROUTER:-active}"
  export WEB_SEARCH_MAX_RESULTS="${WEB_SEARCH_MAX_RESULTS:-3}"
  export ENABLE_LOG_ARCHIVE="${ENABLE_LOG_ARCHIVE:-active}"
  export LOG_RETENTION_DAYS="${LOG_RETENTION_DAYS:-30}"
  export HERMES_REPLICAS="${HERMES_REPLICAS:-1}"
  export ZALO_INBOUND_QUEUE="${ZALO_INBOUND_QUEUE:-active}"
  export GATEWAY_SKIP_RL_PATHS="${GATEWAY_SKIP_RL_PATHS:-/coding,/v1/coding,/skills/coding,/schedule,/v1/schedule,/skills/schedule,/v1/schedules}"
  export VALKEY_URL="${VALKEY_URL:-redis://valkey:6379/0}"

  if _env_active "${SECURITY_SANDBOX:-}"; then
    export SECURITY_DOCKER_HOST="${SECURITY_DOCKER_HOST:-tcp://docker-socket-proxy:2375}"
  fi

  if _env_active "${ENABLE_TRAEFIK:-}" && _env_active "${ENABLE_API_GATEWAY:-}"; then
    export GATEWAY_UPSTREAM_URL="${GATEWAY_UPSTREAM_URL:-http://traefik:80}"
  fi

  export GATEWAY_REQUIRE_AUTH="${GATEWAY_REQUIRE_AUTH:-active}"
  export GATEWAY_TRUST_FORWARDED="${GATEWAY_TRUST_FORWARDED:-inactive}"
  export GATEWAY_RL_FAIL_CLOSED="${GATEWAY_RL_FAIL_CLOSED:-active}"
  if _env_active "${ENABLE_API_GATEWAY:-}" && _env_active "${GATEWAY_REQUIRE_AUTH:-}"; then
    if [[ -z "${GATEWAY_API_KEYS:-}" ]] && ! _env_active "${ENABLE_OPENBAO:-}"; then
      echo "WARN: ENABLE_API_GATEWAY=active but GATEWAY_API_KEYS is empty — gateway will refuse to start until keys are set (or GATEWAY_REQUIRE_AUTH=inactive for isolated lab)." >&2
    elif [[ -z "${GATEWAY_API_KEYS:-}" ]]; then
      echo "INFO: GATEWAY_API_KEYS will be loaded from OpenBao for runtime use." >&2
    fi
  fi
}

assistant_append_monitor_profiles() {
  local -n _amp_profiles="$1"
  local want_prom=0 want_loki=0
  if _env_active "${ENABLE_GRAFANA:-}" || _env_active "${ENABLE_PROMETHEUS:-}"; then
    want_prom=1
  fi
  if _env_active "${ENABLE_LOKI:-}" || _env_active "${ENABLE_ALLOY:-}"; then
    want_loki=1
  fi
  if _env_active "${ENABLE_GRAFANA:-}"; then
    _amp_profiles+=(--profile grafana)
  fi
  if [[ "$want_prom" == "1" ]]; then
    _amp_profiles+=(--profile prometheus)
  fi
  if [[ "$want_loki" == "1" ]]; then
    _amp_profiles+=(--profile loki --profile alloy)
  fi
  if [[ "$want_prom" == "1" ]] && _env_active "${ENABLE_OMNIROUTER:-}"; then
    _amp_profiles+=(--profile omni-exporter)
  fi
}

assistant_disabled_monitor_containers() {
  local want_prom=0 want_loki=0
  if _env_active "${ENABLE_GRAFANA:-}" || _env_active "${ENABLE_PROMETHEUS:-}"; then
    want_prom=1
  fi
  if _env_active "${ENABLE_LOKI:-}" || _env_active "${ENABLE_ALLOY:-}"; then
    want_loki=1
  fi
  _env_active "${ENABLE_GRAFANA:-}" || echo grafana
  if [[ "$want_prom" != "1" ]]; then
    echo prometheus
    echo node-exporter
    echo stack-exporter
  fi
  if [[ "$want_loki" != "1" ]]; then
    echo loki
    echo alloy
  fi
  if [[ "$want_prom" != "1" ]] || ! _env_active "${ENABLE_OMNIROUTER:-}"; then
    echo omni-exporter
  fi
}

assistant_rm_container_by_service() {
  assistant_rm_all_compose_service_containers "${1:-}"
}

assistant_rm_all_compose_service_containers() {
  local svc="${1:-}" id project="${COMPOSE_PROJECT_NAME:-assistant}" cname
  [[ -n "$svc" ]] || return 0
  while IFS= read -r id; do
    [[ -z "$id" ]] && continue
    cname="$(docker inspect -f '{{.Name}}' "$id" 2>/dev/null | sed 's|^/||' || echo "$id")"
    echo "==> remove compose worker container ${cname} (service=${svc})"
    docker rm -f "$id" 2>/dev/null || true
  done < <(docker ps -aq --filter "label=com.docker.compose.service=${svc}" \
    --filter "label=com.docker.compose.project=${project}" 2>/dev/null)
  docker rm -f "$svc" 2>/dev/null || true
  docker rm -f "${project}-${svc}-1" 2>/dev/null || true
}

assistant_rm_nonrunning_compose_service_containers() {
  local svc="${1:-}" id st project="${COMPOSE_PROJECT_NAME:-assistant}" cname
  [[ -n "$svc" ]] || return 0
  while IFS= read -r id; do
    [[ -z "$id" ]] && continue
    st="$(docker inspect -f '{{.State.Status}}' "$id" 2>/dev/null || echo unknown)"
    [[ "$st" == "running" ]] && continue
    cname="$(docker inspect -f '{{.Name}}' "$id" 2>/dev/null | sed 's|^/||' || echo "$id")"
    echo "==> remove stopped compose worker container ${cname} (service=${svc}, state=${st})"
    docker rm -f "$id" 2>/dev/null || true
  done < <(docker ps -aq --filter "label=com.docker.compose.service=${svc}" \
    --filter "label=com.docker.compose.project=${project}" 2>/dev/null)
}

assistant_worker_legacy_container_names() {
  case "${1:-}" in
    schedule) printf '%s\n' schedule-worker ;;
    media) printf '%s\n' searxng jobs jobs-worker dispatcher ;;
    security) printf '%s\n' openbao security-manager authz siem policy-center docker-socket-proxy ;;
    notify) printf '%s\n' notify alert-watch ;;
    monitor) printf '%s\n' grafana prometheus loki alloy omni-exporter node-exporter stack-exporter ;;
    antivirus) printf '%s\n' clamav av-gateway ;;
    message|zalo) printf '%s\n' zalo-proxy zalo-api ;;
    clouddrive) printf '%s\n' clouddrive-sync ;;
    sandbox) printf '%s\n' docker-socket-proxy ;;
  esac
}

assistant_rm_compose_recreate_orphans() {
  # Compose recreate renames the old container to <hex>_<oldname>. A failed
  # `compose up` can leave that hex name taken → next up:
  #   Conflict: container name "/e207aa1eecb5_assistant-authz-1" is already in use
  # Drop those rename leftovers (and duplicate project service containers) before up.
  local id name project="${COMPOSE_PROJECT_NAME:-assistant}" svc kept
  while IFS= read -r id; do
    [[ -z "$id" ]] && continue
    name="$(docker inspect -f '{{.Name}}' "$id" 2>/dev/null | sed 's|^/||' || true)"
    [[ -z "$name" ]] && continue
    # Docker Compose anonymous rename: 8–64 hex chars + underscore + rest
    if [[ "$name" =~ ^[0-9a-fA-F]{6,64}_.+ ]]; then
      echo "==> remove compose recreate orphan ${name}"
      docker rm -f "$id" 2>/dev/null || true
    fi
  done < <(docker ps -aq 2>/dev/null)

  # Same project+service with >1 container: keep one running (newest), remove rest.
  while IFS= read -r svc; do
    [[ -z "$svc" ]] && continue
    kept=""
    while IFS= read -r id; do
      [[ -z "$id" ]] && continue
      if [[ -z "$kept" ]] \
        && [[ "$(docker inspect -f '{{.State.Running}}' "$id" 2>/dev/null || echo false)" == "true" ]]; then
        kept="$id"
        continue
      fi
      if [[ -z "$kept" ]]; then
        kept="$id"
        continue
      fi
      name="$(docker inspect -f '{{.Name}}' "$id" 2>/dev/null | sed 's|^/||' || echo "$id")"
      echo "==> remove duplicate compose container ${name} (service=${svc})"
      docker rm -f "$id" 2>/dev/null || true
    done < <(docker ps -aq --filter "label=com.docker.compose.project=${project}" \
      --filter "label=com.docker.compose.service=${svc}" 2>/dev/null)
  done < <(docker ps -a --filter "label=com.docker.compose.project=${project}" \
    --format '{{.Label "com.docker.compose.service"}}' 2>/dev/null | sort -u)
}

assistant_remove_stale_worker_containers() {
  # Optional workers install via `bash run.sh install …`. Drop legacy fixed-name
  # orphans (searxng) and compose-scoped leftovers (assistant-searxng-1) from
  # failed partial installs or repo-wipe without `bash run.sh destroy`.
  # Set ASSISTANT_PURGE_WORKER_COMPOSE=1 (install/add-components) to force-remove
  # all compose worker containers before up, even when running.
  local -a workers=() w name purge="${ASSISTANT_PURGE_WORKER_COMPOSE:-0}"

  # Always clear recreate-name collisions first (authz Conflict on update).
  assistant_rm_compose_recreate_orphans

  if [[ "${WORKER_SCHEDULE:-inactive}" == "active" ]] || _env_active "${ENABLE_SCHEDULE:-}"; then
    workers+=(schedule)
  fi
  if [[ "${WORKER_MEDIA_FILE:-inactive}" == "active" || "${ENABLE_MEDIA_FILE:-inactive}" == "active" ]] \
    || _env_active "${ENABLE_JOBS:-}" || _env_active "${ENABLE_SEARXNG:-}"; then
    workers+=(media)
  fi
  if [[ "${WORKER_SECURITY:-inactive}" == "active" ]] || _env_active "${ENABLE_SECURITY:-}"; then
    workers+=(security)
  fi
  if [[ "${WORKER_NOTIFY:-inactive}" == "active" ]] || _env_active "${ENABLE_NOTIFY:-}"; then
    workers+=(notify)
  fi
  if [[ "${WORKER_MONITOR:-inactive}" == "active" ]] || _env_active "${ENABLE_MONITOR:-}"; then
    workers+=(monitor)
  fi
  _env_active "${ENABLE_ANTIVIRUS:-}" && workers+=(antivirus)
  if [[ "${WORKER_MESSAGE:-inactive}" == "active" ]] || _env_active "${ENABLE_ZALO:-}"; then
    workers+=(message)
  fi
  _env_active "${ENABLE_CLOUDDRIVE:-}" && workers+=(clouddrive)
  _env_active "${SECURITY_SANDBOX:-}" && workers+=(sandbox)
  [[ ${#workers[@]} -eq 0 ]] && return 0
  for w in "${workers[@]}"; do
    while IFS= read -r name; do
      [[ -z "$name" ]] && continue
      if docker ps -aq --filter "name=^/${name}$" 2>/dev/null | grep -q .; then
        echo "==> remove legacy worker container ${name} (${w}; run.sh install)"
        docker rm -f "$name" 2>/dev/null || true
      fi
      if [[ "$purge" == "1" ]]; then
        assistant_rm_all_compose_service_containers "$name"
      else
        assistant_rm_nonrunning_compose_service_containers "$name"
      fi
    done < <(assistant_worker_legacy_container_names "$w")
  done
}

assistant_workers_summary() {
  echo "workers SCHEDULE=${WORKER_SCHEDULE} MEDIA_FILE=${WORKER_MEDIA_FILE} SECURITY=${WORKER_SECURITY} NOTIFY=${WORKER_NOTIFY} MESSAGE=${WORKER_MESSAGE} MONITOR=${WORKER_MONITOR}"
  echo "core TRAEFIK=${ENABLE_TRAEFIK:-1} GATEWAY=${ENABLE_API_GATEWAY:-1} OMNI=${ENABLE_OMNIROUTER:-1} ROUTER=${ENABLE_MODEL_ROUTER:-1} REPLICAS=${HERMES_REPLICAS:-1} QUEUE=${ZALO_INBOUND_QUEUE:-1}"
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
ENABLE_SEARXNG=${ENABLE_SEARXNG:-0}
ENABLE_JOBS=${ENABLE_JOBS:-0}
OFFICE_FILE_GEN=${OFFICE_FILE_GEN:-0}
IMAGE_GEN_COMBO=${IMAGE_GEN_COMBO:-}
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
ENABLE_MEDIA_FILE=${ENABLE_MEDIA_FILE:-inactive}
ENABLE_MESSAGE=${ENABLE_MESSAGE:-0}
ENABLE_MONITOR=${ENABLE_MONITOR:-0}
ENABLE_OMNIROUTER=${ENABLE_OMNIROUTER:-1}
OMNIROUTER_ENABLE_MEMORY=${OMNIROUTER_ENABLE_MEMORY:-1}
WEB_SEARCH_MAX_RESULTS=${WEB_SEARCH_MAX_RESULTS:-3}
ENABLE_MODEL_ROUTER=${ENABLE_MODEL_ROUTER:-1}
ENABLE_LOG_ARCHIVE=${ENABLE_LOG_ARCHIVE:-1}
ZALO_INBOUND_QUEUE=${ZALO_INBOUND_QUEUE:-1}
SECURITY_SANDBOX=${SECURITY_SANDBOX:-0}
SECURITY_LLM_JUDGE=${SECURITY_LLM_JUDGE:-0}
ENABLE_LLM_JUDGE=${ENABLE_LLM_JUDGE:-0}
SECURITY_YARA=${SECURITY_YARA:-1}
SECURITY_FAIL_CLOSED=${SECURITY_FAIL_CLOSED:-0}

VALKEY_URL=${VALKEY_URL:-redis://valkey:6379/0}
EOF
}

assistant_option_key_ok() {
  case "$1" in
    WORKER_SCHEDULE|WORKER_MEDIA_FILE|WORKER_SECURITY|WORKER_NOTIFY|WORKER_MESSAGE|WORKER_MONITOR|HERMES_REPLICAS|TRAEFIK_MODE|TRAEFIK_ACME_ENABLED|ENABLE_TRAEFIK|ENABLE_API_GATEWAY|ENABLE_SEARXNG|ENABLE_JOBS|OFFICE_FILE_GEN|WEB_SEARCH_MAX_RESULTS|IMAGE_GEN_COMBO|ENABLE_GRAFANA|ENABLE_LOKI|ENABLE_PROMETHEUS|ENABLE_ALLOY|ENABLE_CLOUDDRIVE|ENABLE_OPENBAO|ENABLE_OPENBAO_AGENT|ENABLE_ANTIVIRUS|ENABLE_SECURITY|ENABLE_NOTIFY|ENABLE_SIEM|ENABLE_POLICY|ENABLE_AUTHZ|ENABLE_ZALO|ENABLE_TELEGRAM|ENABLE_OPENVPN|ENABLE_OMNIROUTER|OMNIROUTER_FAILOVER_MODELS|OMNIROUTER_ROTATE_ATTEMPTS|OMNIROUTER_ENABLE_MEMORY|ENABLE_MODEL_ROUTER|ENABLE_LOG_ARCHIVE|ENABLE_SCHEDULE|ENABLE_MEDIA_FILE|ENABLE_MESSAGE|ENABLE_MONITOR|SECURITY_SANDBOX|SECURITY_LLM_JUDGE|ENABLE_LLM_JUDGE|SECURITY_YARA|SECURITY_FAIL_CLOSED|IMAGE_GEN_COMBO|OCR_MODEL|EMBED_MODEL|VALKEY_URL|ZALO_INBOUND_QUEUE)
      return 0
      ;;
    *)
      return 1
      ;;
  esac
}

# Back-compat for callers still using the old function name
assistant_profile_apply() { assistant_workers_apply; }
