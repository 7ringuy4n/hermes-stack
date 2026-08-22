#!/usr/bin/env bash
# Self-heal Docker stack: restart exited/unhealthy project containers and
# re-check core HTTP health endpoints. Silent recovery for operators/users.
#
# Hardening (2026-08-16):
#   - BOOT_GRACE_S: skip heals shortly after host boot (avoids false downs)
#   - Do NOT restart Hermes on failed probes (only 9router/dispatcher + bad ctrs)
#   - COMPOSE_PROJECT_NAME defaults can be overridden (lab: nighthawk-lab)
set -euo pipefail

ROOT="${STACK_ROOT:-$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)}"
# Data-dir .env first (lab leftovers); product ${ROOT}/.env wins.
# shellcheck disable=SC1091
[[ -f /data/assistant/.env ]] && set -a && source <(tr -d '\r' < /data/assistant/.env) && set +a
[[ -f "${ROOT}/.env" ]] && set -a && source <(tr -d '\r' < "${ROOT}/.env") && set +a
# shellcheck source=architect/backup-restore/lib/profile.sh
source "${ROOT}/architect/backup-restore/lib/profile.sh"

PROJECT="${COMPOSE_PROJECT_NAME:-assistant}"
PROFILE="${ASSISTANT_PROFILE:-low}"
HERMES_REPLICAS="${HERMES_REPLICAS:-1}"
if [[ -n "${ASSISTANT_DATA_DIR:-}" ]]; then
  _data_root="$ASSISTANT_DATA_DIR"
elif [[ -n "${HERMES_DATA_DIR:-}" ]]; then
  _data_root="$HERMES_DATA_DIR"
elif [[ -d /data/hermes ]]; then
  _data_root="/data/hermes"
else
  _data_root="/data/assistant"
fi
STATE_DIR="${_data_root}/watch"
COOLDOWN_FILE="${STATE_DIR}/stack-watch.cooldown"
FAIL_COUNT_FILE="${STATE_DIR}/stack-watch.fail_count"
DEGRADED_FILE="${STATE_DIR}/stack-watch.degraded"
BOOT_GRACE_S="${STACK_WATCH_BOOT_GRACE:-600}"
RESTART_HERMES_ON_PROBE="${STACK_WATCH_RESTART_HERMES:-0}"
STACK_WATCH_MAX_FAILS="${STACK_WATCH_MAX_FAILS:-5}"
STACK_WATCH_BASE_COOLDOWN="${STACK_WATCH_BASE_COOLDOWN:-90}"
STACK_WATCH_MAX_COOLDOWN="${STACK_WATCH_MAX_COOLDOWN:-3600}"
HERMES_CTR="${HERMES_CONTAINER:-hermes}"
if [[ "$(id -u)" -ne 0 ]]; then SUDO=sudo; else SUDO=; fi

if ! mkdir -p "$STATE_DIR" 2>/dev/null; then
  $SUDO mkdir -p "$STATE_DIR"
  $SUDO chown "$(id -u):$(id -g)" "$STATE_DIR" 2>/dev/null || true
fi
if [[ ! -w "$STATE_DIR" ]]; then
  $SUDO mkdir -p "$STATE_DIR"
  $SUDO chown -R "$(id -u):$(id -g)" "$STATE_DIR" 2>/dev/null \
    || $SUDO chmod 777 "$STATE_DIR" 2>/dev/null \
    || true
fi
log() { echo "$(date -Is) stack-watch: $*"; }

in_cooldown() {
  local sec="${1:-60}"
  [[ -f "$COOLDOWN_FILE" ]] || return 1
  local then now
  then="$(cat "$COOLDOWN_FILE" 2>/dev/null || echo 0)"
  now="$(date +%s)"
  [[ $((now - then)) -lt "$sec" ]]
}
mark_cooldown() {
  if [[ -w "$STATE_DIR" ]]; then
    date +%s >"$COOLDOWN_FILE"
  else
    date +%s | $SUDO tee "$COOLDOWN_FILE" >/dev/null
    $SUDO chown "$(id -u):$(id -g)" "$COOLDOWN_FILE" 2>/dev/null || true
  fi
}

read_fail_count() {
  [[ -f "$FAIL_COUNT_FILE" ]] || { echo 0; return; }
  cat "$FAIL_COUNT_FILE" 2>/dev/null || echo 0
}

write_fail_count() {
  local n="$1"
  if [[ -w "$STATE_DIR" ]]; then
    echo "$n" >"$FAIL_COUNT_FILE"
  else
    echo "$n" | $SUDO tee "$FAIL_COUNT_FILE" >/dev/null
    $SUDO chown "$(id -u):$(id -g)" "$FAIL_COUNT_FILE" 2>/dev/null || true
  fi
}

heal_cooldown_sec() {
  local fails="$1"
  local base="${STACK_WATCH_BASE_COOLDOWN}"
  local max="${STACK_WATCH_MAX_COOLDOWN}"
  if [[ "$fails" -le 2 ]]; then
    echo "$base"
    return
  fi
  local exp=$((fails - 2))
  local sec=$((base * (2 ** exp)))
  if [[ "$sec" -gt "$max" ]]; then
    sec="$max"
  fi
  echo "$sec"
}

mark_degraded() {
  log "degraded after ${STACK_WATCH_MAX_FAILS} heal failures — manual check advised"
  if [[ -w "$STATE_DIR" ]]; then
    date -Is >"$DEGRADED_FILE"
  else
    date -Is | $SUDO tee "$DEGRADED_FILE" >/dev/null
  fi
  if [[ -n "${NOTIFY_URL:-}" ]]; then
    curl -fsS -m 8 -X POST "${NOTIFY_URL}/v1/alert" \
      -H 'content-type: application/json' \
      -d '{"title":"stack-watch degraded","body":"Repeated heal failures — check stack health"}' \
      >/dev/null 2>&1 || true
  fi
}

boot_grace_active() {
  local up
  up="$(awk '{print int($1)}' /proc/uptime 2>/dev/null || echo 999999)"
  [[ "$up" -lt "$BOOT_GRACE_S" ]]
}

compose() {
  # Keep overlays + profiles aligned with run.sh so heal does not strip
  # edge/hostports/scale or --remove-orphans notify/sandbox/antivirus.
  assistant_profile_apply
  PROFILE="${ASSISTANT_PROFILE:-$PROFILE}"
  HERMES_REPLICAS="${HERMES_REPLICAS:-1}"
  local existing=(--project-directory "${ROOT}" -f "${ROOT}/docker/docker-compose.yml")
  if [[ "${ENABLE_OCR:-0}" == "1" || "${ENABLE_JOBS:-0}" == "1" || "${ENABLE_SEARXNG:-0}" == "1" || "${ENABLE_MEDIA_FILE:-0}" == "1" ]]; then
    [[ -f "${ROOT}/docker/docker-compose.media.yml" ]] && existing+=(-f "${ROOT}/docker/docker-compose.media.yml")
  fi
  if [[ "${ENABLE_SECURITY:-0}" == "1" || "${ENABLE_MONITOR:-0}" == "1" || "${ENABLE_NOTIFY:-0}" == "1" || "${ENABLE_OPENBAO:-0}" == "1" || "${ENABLE_SIEM:-0}" == "1" || "${ENABLE_AUTHZ:-0}" == "1" || "${ENABLE_CLOUDDRIVE:-0}" == "1" ]]; then
    [[ -f "${ROOT}/docker/docker-compose.security.yml" ]] && existing+=(-f "${ROOT}/docker/docker-compose.security.yml")
  fi
  case "${ENABLE_TRAEFIK:-0}${ENABLE_API_GATEWAY:-0}${ENABLE_OPENVPN:-0}" in
    *1*)
      [[ -f "${ROOT}/docker/docker-compose.edge.yml" ]] && existing+=(-f "${ROOT}/docker/docker-compose.edge.yml")
      ;;
  esac
  if [[ "${HERMES_REPLICAS}" == "1" ]]; then
    [[ -f "${ROOT}/docker/docker-compose.hermes-hostports.yml" ]] && existing+=(-f "${ROOT}/docker/docker-compose.hermes-hostports.yml")
  fi
  local profiles=()
  [[ "${ENABLE_ZALO:-0}" == "1" ]] && profiles+=(--profile zalo)
  [[ "${ENABLE_NOTIFY:-0}" == "1" ]] && profiles+=(--profile notify)
  [[ "${ENABLE_SECURITY:-0}" == "1" ]] && profiles+=(--profile security)
  [[ "${ENABLE_ANTIVIRUS:-0}" == "1" ]] && profiles+=(--profile antivirus)
  [[ "${SECURITY_SANDBOX:-0}" == "1" ]] && profiles+=(--profile sandbox)
  [[ "${ENABLE_CLOUDDRIVE:-0}" == "1" ]] && profiles+=(--profile clouddrive)
  [[ "${COMFYUI_HAS_GPU:-0}" == "1" ]] && profiles+=(--profile comfy-gpu)
  [[ "${ENABLE_SCHEDULE:-0}" == "1" ]] && profiles+=(--profile schedule)
  [[ "${ENABLE_MEDIA_FILE:-0}" == "1" || "${ENABLE_OCR:-0}" == "1" || "${ENABLE_JOBS:-0}" == "1" ]] && profiles+=(--profile media)
  assistant_append_monitor_profiles profiles
  if [[ "${ENABLE_TRAEFIK:-0}" == "1" ]]; then
    case "${TRAEFIK_ACME_ENABLED:-0}" in
      1) profiles+=(--profile traefik-acme) ;;
      *) profiles+=(--profile traefik) ;;
    esac
  fi
  [[ "${ENABLE_API_GATEWAY:-0}" == "1" ]] && profiles+=(--profile gateway)
  [[ "${ENABLE_OPENVPN:-0}" == "1" ]] && profiles+=(--profile openvpn)
  [[ "${ENABLE_OMNIROUTER:-0}" == "1" ]] && profiles+=(--profile omnirouter)
  $SUDO docker compose -p "$PROJECT" "${existing[@]}" "${profiles[@]}" "$@"
}

restart_bad_containers() {
  local names
  names="$($SUDO docker ps -a --filter "label=com.docker.compose.project=${PROJECT}" \
    --format '{{.Names}} {{.Status}}' 2>/dev/null || true)"
  # Lab often uses project nighthawk-lab while timer may set COMPOSE_PROJECT_NAME=nighthawk
  if [[ -z "$names" && "$PROJECT" != "nighthawk-lab" ]]; then
    names="$($SUDO docker ps -a --filter "label=com.docker.compose.project=nighthawk-lab" \
      --format '{{.Names}} {{.Status}}' 2>/dev/null || true)"
  fi
  [[ -n "$names" ]] || return 0
  local line name status
  while IFS= read -r line; do
    [[ -z "$line" ]] && continue
    name="${line%% *}"
    status="${line#* }"
    # Never thrash Hermes from "Restarting" flicker — only Exited/Dead/unhealthy
    if echo "$status" | grep -qiE 'Exited|Dead|unhealthy'; then
      # Crash recovery: restart exited Hermes replicas. Probe-fail path still
      # does not bounce healthy Hermes unless STACK_WATCH_RESTART_HERMES=1.
      log "restart ${name} (${status})"
      $SUDO docker restart "$name" >/dev/null 2>&1 || true
    fi
  done <<<"$names"
}

ensure_core_up() {
  # Always pass --scale so heal does not collapse Hermes×N back to 1 (destroys SSE owner).
  local scale="${HERMES_REPLICAS}"
  log "compose up -d --scale hermes=${scale} (ensure running)"
  compose up -d --remove-orphans --scale "hermes=${scale}" >/dev/null 2>&1 || true
}

probe() {
  local name="$1" url="$2"
  if curl -sf -m 4 "$url" >/dev/null 2>&1; then
    return 0
  fi
  log "DOWN ${name} ${url}"
  return 1
}

FAILED_NAMES=""

mark_failed() {
  case " ${FAILED_NAMES} " in
    *" $1 "*) ;;
    *) FAILED_NAMES="${FAILED_NAMES} $1" ;;
  esac
}

component_running() {
  $SUDO docker ps --format '{{.Names}}' 2>/dev/null | grep -qx "$1"
}

# 9router /v1/models is 401 without a key (process up). curl -f treated that as DOWN
# and restarted 9router on every stack-watch tick.
probe_9router() {
  local url="http://127.0.0.1:${N9ROUTER_HOST_PORT:-20128}/v1/models"
  local code
  code="$(curl -sS -m 4 -o /dev/null -w '%{http_code}' "$url" 2>/dev/null || echo 000)"
  case "$code" in
    200|401|307) return 0 ;;
  esac
  log "DOWN 9router ${url} http=${code}"
  return 1
}

heal_by_health() {
  local failed=0
  FAILED_NAMES=""
  # Only probe optional components this stack actually runs: a disabled 9Router
  # used to fail every tick, and the heal then bounced dispatcher every 2 min.
  if [[ "${ENABLE_9ROUTER:-0}" == "1" ]] || component_running 9router; then
    probe_9router || { failed=1; mark_failed 9router; }
  fi
  if [[ "${ENABLE_MEDIA_FILE:-0}" == "1" ]] || component_running dispatcher; then
    probe dispatcher "http://127.0.0.1:${DISPATCHER_PORT:-8090}/health" \
      || { failed=1; mark_failed dispatcher; }
  fi
  # Host-published Hermes dashboard only exists when replicas=1
  if [[ "${HERMES_REPLICAS}" == "1" ]]; then
    probe hermes_dash "http://127.0.0.1:${HERMES_DASHBOARD_PORT:-29119}/" || true
  else
    probe traefik "http://127.0.0.1:${TRAEFIK_HOST_PORT:-8080}/health" || true
    probe gateway "http://127.0.0.1:${GATEWAY_HOST_PORT:-8088}/health" || failed=1
  fi

  if [[ "${ENABLE_OCR:-0}" == "1" || "${ENABLE_MEDIA_FILE:-0}" == "1" ]] || component_running ocr; then
    probe ocr "http://127.0.0.1:${OCR_PORT:-8091}/health" || { failed=1; mark_failed ocr; }
  fi
  if [[ "${ENABLE_JOBS:-0}" == "1" ]] || component_running jobs; then
    probe jobs "http://127.0.0.1:${JOBS_PORT:-8104}/health" || { failed=1; mark_failed jobs; }
  fi
  if [[ "${ENABLE_GRAFANA:-0}" == "1" ]]; then
    probe grafana "http://127.0.0.1:${GRAFANA_HOST_PORT:-23000}/api/health" || failed=1
  fi
  if [[ "${ENABLE_ZALO:-0}" == "1" ]]; then
    if ! $SUDO docker ps --format '{{.Names}}' | grep -qx zalo-api; then
      log "zalo-api missing while ENABLE_ZALO=1 — starting zalo combo"
      compose up -d --no-deps zalo-api zalo-proxy >/dev/null 2>&1 || true
      failed=1
    fi
    probe zalo-api "http://127.0.0.1:${ZALO_API_PORT:-${ADMIN_API_PORT:-8100}}/health" \
      || { failed=1; mark_failed zalo-api; }
    local zport="${ZALO_PLUGIN_PORT:-8787}"
    if ! probe zalo-bridge "http://127.0.0.1:${zport}/health"; then
      log "zalo bridge :${zport} down — restart host unit"
      if [[ -f "${ROOT}/scripts/main/patch_zalo_bridge_inject.py" ]]; then
        ZALO_BRIDGE_FORCE_RESTART=1 $SUDO python3 "${ROOT}/scripts/main/patch_zalo_bridge_inject.py" \
          >/dev/null 2>&1 || true
      else
        systemctl --user try-restart com.hermes.zaloplugin.service 2>/dev/null \
          || systemctl --user try-restart assistant-zalo.service 2>/dev/null \
          || true
      fi
      failed=1
    fi
  fi

  if [[ "${ENABLE_QWEN:-0}" == "1" && -n "${OLLAMA_BASE_URL:-}" ]]; then
    if ! bash "${ROOT}/scripts/main/ensure-ollama.sh" >/dev/null 2>&1; then
      log "ollama down while ENABLE_QWEN=1 — ensure-ollama failed"
      failed=1
      mark_failed router-worker
    fi
  fi

  if [[ "$failed" -ne 0 ]]; then
    local fails cooldown_sec
    fails="$(read_fail_count)"
    fails=$((fails + 1))
    write_fail_count "$fails"
    cooldown_sec="$(heal_cooldown_sec "$fails")"
    if [[ "$fails" -ge "${STACK_WATCH_MAX_FAILS}" ]]; then
      mark_degraded
    fi
    if in_cooldown "$cooldown_sec"; then
      log "heal skipped (cooldown ${cooldown_sec}s, fail_count=${fails})"
    else
      log "healing after failed probes (fail_count=${fails}, hermes restart=${RESTART_HERMES_ON_PROBE})"
      ensure_core_up
      restart_bad_containers
      # Restart only what actually failed its own probe. A blanket restart of
      # 9router/dispatcher killed in-flight OCR and media jobs on every tick.
      local name
      for name in ${FAILED_NAMES}; do
        log "restart ${name} (probe failed)"
        $SUDO docker restart "$name" >/dev/null 2>&1 \
          || $SUDO docker restart "nh-${name}" >/dev/null 2>&1 \
          || true
      done
      if [[ "$RESTART_HERMES_ON_PROBE" == "1" ]]; then
        local ids
        ids="$($SUDO docker ps -aq --filter "name=hermes" 2>/dev/null || true)"
        if [[ -n "$ids" ]]; then
          # shellcheck disable=SC2086
          $SUDO docker restart $ids >/dev/null 2>&1 || true
        else
          $SUDO docker restart "$HERMES_CTR" 2>/dev/null \
            || $SUDO docker restart nh-hermes 2>/dev/null \
            || $SUDO docker restart hermes 2>/dev/null \
            || true
        fi
      else
        log "not restarting hermes on probe fail (set STACK_WATCH_RESTART_HERMES=1 to enable)"
      fi
      mark_cooldown
    fi
  else
    write_fail_count 0
    rm -f "$DEGRADED_FILE" 2>/dev/null || $SUDO rm -f "$DEGRADED_FILE" 2>/dev/null || true
  fi
}

ensure_media_writable() {
  # Silent heal: OCR / file-gen / Zalo attach need Hermes UID on media/*.
  local uid="${HERMES_UID:-1000}"
  local gid="${HERMES_GID:-1000}"
  $SUDO mkdir -p "${_data_root}/media/inbound" "${_data_root}/media/out" 2>/dev/null || true
  $SUDO chown -R "${uid}:${gid}" "${_data_root}/media" 2>/dev/null || true
  $SUDO chmod -R ug+rwX "${_data_root}/media" 2>/dev/null || true
  $SUDO chmod g+s \
    "${_data_root}/media" \
    "${_data_root}/media/inbound" \
    "${_data_root}/media/out" \
    2>/dev/null || true
}

main() {
  cd "$ROOT"
  if boot_grace_active; then
    log "boot grace (${BOOT_GRACE_S}s) — skip heals (uptime still warming)"
    exit 0
  fi
  ensure_media_writable
  restart_bad_containers
  heal_by_health
  log "done profile=${PROFILE} project=${PROJECT}"
}

main "$@"
