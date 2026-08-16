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
# shellcheck disable=SC1091
[[ -f "${ROOT}/.env" ]] && set -a && source <(tr -d '\r' < "${ROOT}/.env") && set +a

PROJECT="${COMPOSE_PROJECT_NAME:-assistant}"
PROFILE="${ASSISTANT_PROFILE:-low}"
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
BOOT_GRACE_S="${STACK_WATCH_BOOT_GRACE:-600}"
RESTART_HERMES_ON_PROBE="${STACK_WATCH_RESTART_HERMES:-0}"
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

boot_grace_active() {
  local up
  up="$(awk '{print int($1)}' /proc/uptime 2>/dev/null || echo 999999)"
  [[ "$up" -lt "$BOOT_GRACE_S" ]]
}

compose() {
  local files=(-f "${ROOT}/docker-compose.yml")
  case "$PROFILE" in
    medium) files+=(-f "${ROOT}/docker-compose.medium.yml") ;;
    high) files+=(-f "${ROOT}/docker-compose.medium.yml" -f "${ROOT}/docker-compose.high.yml") ;;
  esac
  # Lab monolith compose often has no medium/high overlays — ignore missing files
  local existing=()
  local f
  for f in "${files[@]}"; do
    [[ "$f" == "-f" ]] && continue
    [[ -f "$f" ]] && existing+=(-f "$f")
  done
  [[ ${#existing[@]} -eq 0 ]] && existing=(-f "${ROOT}/docker-compose.yml")
  local profiles=()
  [[ "${ENABLE_ZALO:-0}" == "1" ]] && profiles+=(--profile zalo)
  [[ "${ENABLE_ANTIVIRUS:-0}" == "1" ]] && profiles+=(--profile antivirus)
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
      # Skip hermes unless explicitly allowed
      if [[ "$name" == *"hermes"* && "$RESTART_HERMES_ON_PROBE" != "1" ]]; then
        log "skip hermes bad-state (${status}) — STACK_WATCH_RESTART_HERMES!=1"
        continue
      fi
      log "restart ${name} (${status})"
      $SUDO docker restart "$name" >/dev/null 2>&1 || true
    fi
  done <<<"$names"
}

ensure_core_up() {
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
      log "healing after failed probes (hermes restart=${RESTART_HERMES_ON_PROBE})"
      ensure_core_up
      restart_bad_containers
      $SUDO docker restart 9router 2>/dev/null || $SUDO docker restart nh-9router 2>/dev/null || true
      $SUDO docker restart dispatcher 2>/dev/null || $SUDO docker restart nh-dispatcher 2>/dev/null || true
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
  fi
}

main() {
  cd "$ROOT"
  if boot_grace_active; then
    log "boot grace (${BOOT_GRACE_S}s) — skip heals (uptime still warming)"
    exit 0
  fi
  restart_bad_containers
  heal_by_health
  log "done profile=${PROFILE} project=${PROJECT}"
}

main "$@"
