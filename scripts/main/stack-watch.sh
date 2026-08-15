#!/usr/bin/env bash
# Self-heal Docker stack: restart exited/unhealthy project containers and
# re-check core HTTP health endpoints. Silent recovery for operators/users.
set -euo pipefail

ROOT="${STACK_ROOT:-$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)}"
# shellcheck disable=SC1091
[[ -f "${ROOT}/.env" ]] && set -a && source <(tr -d '\r' < "${ROOT}/.env") && set +a

PROJECT="${COMPOSE_PROJECT_NAME:-assistant}"
PROFILE="${ASSISTANT_PROFILE:-low}"
STATE_DIR="${ASSISTANT_DATA_DIR:-${HERMES_DATA_DIR:-/data/assistant}}/watch"
COOLDOWN_FILE="${STATE_DIR}/stack-watch.cooldown"
if [[ "$(id -u)" -ne 0 ]]; then SUDO=sudo; else SUDO=; fi

mkdir -p "$STATE_DIR"
log() { echo "$(date -Is) stack-watch: $*"; }

in_cooldown() {
  local sec="${1:-60}"
  [[ -f "$COOLDOWN_FILE" ]] || return 1
  local then now
  then="$(cat "$COOLDOWN_FILE" 2>/dev/null || echo 0)"
  now="$(date +%s)"
  [[ $((now - then)) -lt "$sec" ]]
}
mark_cooldown() { date +%s >"$COOLDOWN_FILE"; }

compose() {
  local files=(-f "${ROOT}/docker-compose.yml")
  case "$PROFILE" in
    medium) files+=(-f "${ROOT}/docker-compose.medium.yml") ;;
    high) files+=(-f "${ROOT}/docker-compose.medium.yml" -f "${ROOT}/docker-compose.high.yml") ;;
  esac
  local profiles=()
  [[ "${ENABLE_ZALO:-0}" == "1" ]] && profiles+=(--profile zalo)
  [[ "${ENABLE_ANTIVIRUS:-0}" == "1" ]] && profiles+=(--profile antivirus)
  $SUDO docker compose -p "$PROJECT" "${files[@]}" "${profiles[@]}" "$@"
}

restart_bad_containers() {
  local names
  names="$($SUDO docker ps -a --filter "label=com.docker.compose.project=${PROJECT}" \
    --format '{{.Names}} {{.Status}}' 2>/dev/null || true)"
  [[ -n "$names" ]] || return 0
  local line name status
  while IFS= read -r line; do
    [[ -z "$line" ]] && continue
    name="${line%% *}"
    status="${line#* }"
    if echo "$status" | grep -qiE 'Exited|Dead|unhealthy|Restarting \('; then
      log "restart ${name} (${status})"
      $SUDO docker restart "$name" >/dev/null 2>&1 || true
    fi
  done <<<"$names"
}

ensure_core_up() {
  # Bring missing/stopped services back without full rebuild
  log "compose up -d (ensure running)"
  compose up -d --remove-orphans >/dev/null 2>&1 || true
}

probe() {
  local name="$1" url="$2"
  if curl -sf -m 4 "$url" >/dev/null 2>&1; then
    return 0
  fi
  log "DOWN ${name} ${url}"
  return 1
}

heal_by_health() {
  local failed=0
  probe 9router "http://127.0.0.1:${N9ROUTER_HOST_PORT:-20128}/v1/models" || failed=1
  probe dispatcher "http://127.0.0.1:${DISPATCHER_PORT:-8090}/health" || failed=1
  probe hermes_dash "http://127.0.0.1:${HERMES_DASHBOARD_PORT:-29119}/" || true

  case "$PROFILE" in
    medium|high)
      probe ocr "http://127.0.0.1:${OCR_PORT:-8091}/health" || failed=1
      probe jobs "http://127.0.0.1:${JOBS_PORT:-8104}/health" || failed=1
      ;;
  esac
  case "$PROFILE" in
    high)
      probe admin-api "http://127.0.0.1:${ADMIN_API_PORT:-8100}/health" || failed=1
      probe grafana "http://127.0.0.1:${GRAFANA_HOST_PORT:-23000}/api/health" || failed=1
      ;;
  esac

  if [[ "$failed" -ne 0 ]]; then
    if in_cooldown 90; then
      log "heal skipped (cooldown)"
    else
      log "healing after failed probes"
      ensure_core_up
      restart_bad_containers
      $SUDO docker restart 9router 2>/dev/null || true
      $SUDO docker restart dispatcher 2>/dev/null || true
      $SUDO docker restart "${HERMES_CONTAINER:-hermes}" 2>/dev/null || true
      mark_cooldown
    fi
  fi
}

main() {
  cd "$ROOT"
  restart_bad_containers
  heal_by_health
  log "done profile=${PROFILE}"
}

main "$@"
