#!/usr/bin/env bash
# assistant entrypoint — core + optional workers (see docs/00-workers.md).
set -euo pipefail
export LC_ALL="${LC_ALL:-C.UTF-8}"
export LANG="${LANG:-C.UTF-8}"

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
export ROOT
export STACK_ROOT="${STACK_ROOT:-$ROOT}"

# Default product trees (main/). Override only for local experiments.
export SCRIPTS_DIR="${SCRIPTS_DIR:-$ROOT/scripts/main}"
export HERMES_DIR="${HERMES_DIR:-$ROOT/hermes/main}"

# shellcheck source=architect/backup-restore/lib/load-defaults.sh
source "${ROOT}/architect/backup-restore/lib/load-defaults.sh"
load_env_with_defaults

# shellcheck source=architect/backup-restore/lib/workers.sh
source "${ROOT}/architect/backup-restore/lib/workers.sh"
assistant_migrate_enable_active
assistant_workers_apply

cmd="${1:-help}"
shift || true

# Host-side media dirs (Hermes UID). Prevents Permission denied on inbound/out after
# fresh data volumes or root-owned mkdir from other tools.
ensure_hermes_media_dirs() {
  local data="${HERMES_DATA_DIR:-${ASSISTANT_DATA_DIR:-/data/assistant}}"
  local uid="${HERMES_UID:-1000}"
  local gid="${HERMES_GID:-1000}"
  mkdir -p "${data}/media/inbound" "${data}/media/out" 2>/dev/null || true
  chown -R "${uid}:${gid}" "${data}/media" 2>/dev/null || true
  chmod -R ug+rwX "${data}/media" 2>/dev/null || true
  chmod g+s "${data}/media" "${data}/media/inbound" "${data}/media/out" 2>/dev/null || true
  for f in .env config.yaml; do
    if [[ -f "${data}/${f}" ]]; then
      chown "${uid}:${gid}" "${data}/${f}" 2>/dev/null || true
      chmod u+rw "${data}/${f}" 2>/dev/null || true
    fi
  done
  chown "${uid}:${gid}" "${data}" 2>/dev/null || true
  chmod u+rwx "${data}" 2>/dev/null || true
}

compose() {
  # Core + optional worker overlays.
  local -a files=(--project-directory "$ROOT" -f "$ROOT/docker/docker-compose.yml")
  local -a profiles=()
  local -a scale_args=()
  local replicas="${HERMES_REPLICAS:-1}"
  local traefik_mode="${TRAEFIK_MODE:-local}"
  local acme="${TRAEFIK_ACME_ENABLED:-inactive}"

  if _env_active "${ENABLE_TRAEFIK:-}"; then
    case "${traefik_mode}" in
      public)
        if [[ "$acme" == "active" || "$acme" == "1" && -n "${TRAEFIK_ACME_EMAIL:-}" && -n "${TRAEFIK_ACME_DOMAIN:-}" ]]; then
          acme=1
        else
          if [[ "$acme" == "active" || "$acme" == "1" ]]; then
            echo "WARN: TRAEFIK_MODE=public/ACME missing TRAEFIK_ACME_EMAIL or TRAEFIK_ACME_DOMAIN — fail-soft to local" >&2
          fi
          acme=0
          export TRAEFIK_MODE=local
          traefik_mode=local
        fi
        ;;
      local)
        acme=0
        ;;
      *)
        echo "WARN: unknown TRAEFIK_MODE=${traefik_mode}; using local" >&2
        acme=0
        traefik_mode=local
        export TRAEFIK_MODE=local
        ;;
    esac
    export TRAEFIK_ACME_ENABLED="$acme"
  fi

  if _env_active "${ENABLE_OCR:-}" || _env_active "${ENABLE_JOBS:-}" || _env_active "${ENABLE_SEARXNG:-}" || [[ "${ENABLE_MEDIA_FILE:-inactive}" == "active" || "${WORKER_MEDIA_FILE:-inactive}" == "active" ]]; then
    files+=(-f "$ROOT/docker/docker-compose.media.yml")
  fi
  if _env_active "${ENABLE_SECURITY:-}" || _env_active "${ENABLE_MONITOR:-}" || _env_active "${ENABLE_NOTIFY:-}" || _env_active "${ENABLE_OPENBAO:-}" || _env_active "${ENABLE_SIEM:-}" || _env_active "${ENABLE_AUTHZ:-}" || _env_active "${ENABLE_CLOUDDRIVE:-}"; then
    files+=(-f "$ROOT/docker/docker-compose.security.yml")
  fi
  # Media GPU profile removed — image gen is Omni/9Router only.
  _env_active "${ENABLE_ZALO:-}" && profiles+=(--profile zalo)
  _env_active "${ENABLE_NOTIFY:-}" && profiles+=(--profile notify)
  _env_active "${ENABLE_SECURITY:-}" && profiles+=(--profile security)
  _env_active "${ENABLE_ANTIVIRUS:-}" && profiles+=(--profile antivirus)
  if _env_active "${SECURITY_SANDBOX:-}"; then
    echo "WARN: SECURITY_SANDBOX=active starts docker-socket-proxy — not a production isolation boundary" >&2
    profiles+=(--profile sandbox)
  fi
  _env_active "${ENABLE_CLOUDDRIVE:-}" && profiles+=(--profile clouddrive)
  _env_active "${ENABLE_SCHEDULE:-}" && profiles+=(--profile schedule)
  if [[ "${ENABLE_MEDIA_FILE:-inactive}" == "active" || "${WORKER_MEDIA_FILE:-inactive}" == "active" ]] || _env_active "${ENABLE_OCR:-}" || _env_active "${ENABLE_JOBS:-}"; then
    profiles+=(--profile media)
  fi

  if _env_active "${ENABLE_TRAEFIK:-}" || _env_active "${ENABLE_API_GATEWAY:-}" || _env_active "${ENABLE_OPENVPN:-}"; then
    files+=(-f "$ROOT/docker/docker-compose.edge.yml")
  fi
  if _env_active "${ENABLE_OMNIROUTER:-}"; then
    profiles+=(--profile omnirouter)
  fi
  if _env_active "${ENABLE_9ROUTER:-}"; then
    profiles+=(--profile 9router)
  fi
  if _env_active "${ENABLE_TRAEFIK:-}"; then
    case "${TRAEFIK_ACME_ENABLED:-0}" in
      1)
        bash "${SCRIPTS_DIR}/render-traefik-acme.sh"
        profiles+=(--profile traefik-acme)
        ;;
      *)
        profiles+=(--profile traefik)
        ;;
    esac
  fi
  if _env_active "${ENABLE_API_GATEWAY:-}"; then
    profiles+=(--profile gateway)
  fi
  if _env_active "${ENABLE_OPENVPN:-}"; then
    profiles+=(--profile openvpn)
  fi
  assistant_append_monitor_profiles profiles
  if [[ "$replicas" == "1" ]]; then
    files+=(-f "$ROOT/docker/docker-compose.hermes-hostports.yml")
  fi
  case "${1:-}" in
    up|create|run)
      # --scale must not trail a scoped `up … zalo-api` (compose errors e.g.
      # "no such service: hermes: disabled"). Only scale when hermes is in the
      # service list, or when this is a full-stack up (no explicit services).
      local -a up_rest=()
      if [[ $# -gt 0 ]]; then
        up_rest=("${@:2}")
      fi
      local a has_explicit_svc=0 has_hermes=0
      for a in "${up_rest[@]}"; do
        case "$a" in
          -*) ;;
          *)
            has_explicit_svc=1
            [[ "$a" == "hermes" ]] && has_hermes=1
            ;;
        esac
      done
      if [[ "$has_explicit_svc" -eq 0 || "$has_hermes" -eq 1 ]]; then
        scale_args=(--scale "hermes=${replicas}")
      fi
      ;;
  esac
  docker compose "${files[@]}" "${profiles[@]}" "$@" "${scale_args[@]}"
}

need_media() {
  if [[ "${ENABLE_MEDIA_FILE:-inactive}" == "active" || "${WORKER_MEDIA_FILE:-inactive}" == "active" ]] || _env_active "${ENABLE_OCR:-}" || _env_active "${ENABLE_JOBS:-}"; then
    return 0
  fi
  echo "Command '${1:-}' requires the media/file worker (ENABLE_MEDIA_FILE=active or ENABLE_OCR/JOBS=1)." >&2
  return 1
}

need_security() {
  if _env_active "${ENABLE_SECURITY:-}" || _env_active "${ENABLE_MONITOR:-}" || _env_active "${ENABLE_OPENBAO:-}"; then
    return 0
  fi
  echo "Command '${1:-}' requires security/monitor/openbao components enabled." >&2
  return 1
}

ops() {
  bash "${ROOT}/architect/backup-restore/ops.sh" "$@"
}

do_backup_first() {
  # Must succeed (backup + verify) before destroy, upgrade, or downgrade.
  local reason="${1:-pre-change}"
  local stamp="" bdir="${BACKUP_DIR:-/data/assistant/backups}"
  echo "==> backup first (${reason}) — verify must pass before proceeding"
  assistant_profile_summary
  export BACKUP_CHANGE_REASON="$reason"
  stamp="$(ops backup | tee /dev/stderr | tail -n 1 | tr -d '\r' | awk 'NF { line=$0 } END { print line }')"
  unset BACKUP_CHANGE_REASON
  if [[ -z "$stamp" || ! -d "${bdir}/${stamp}" ]]; then
    echo "ERROR: backup failed or stamp missing — abort ${reason}" >&2
    return 1
  fi
  echo "==> verify backup stamp=${stamp}"
  if ! ops verify "$stamp"; then
    echo "ERROR: backup verify failed for ${stamp} — abort ${reason}" >&2
    return 1
  fi
  echo "$stamp" > "${bdir}/PRE_CHANGE" 2>/dev/null \
    || echo "$stamp" | sudo tee "${bdir}/PRE_CHANGE" >/dev/null
  echo "BACKUP_FIRST_OK stamp=${stamp}"
  echo "Restore this point: bash run.sh restore ${stamp}"
}

do_stop_disabled_optionals() {
  # Compose --remove-orphans does not drop containers started under a --profile that is now off.
  local -a extra=()
  if [[ "${ENABLE_NOTIFY:-0}" != "1" ]]; then
    extra+=(notify alert-watch)
  fi
  if [[ "${ENABLE_SECURITY:-0}" != "1" ]]; then
    extra+=(openbao security-manager authz siem policy-center)
  fi
  if [[ "${ENABLE_ANTIVIRUS:-0}" != "1" ]]; then
    extra+=(clamav av-gateway)
  fi
  if [[ "${SECURITY_SANDBOX:-0}" != "1" ]]; then
    extra+=(docker-socket-proxy)
  fi
  if [[ "${ENABLE_CLOUDDRIVE:-0}" != "1" ]]; then
    extra+=(clouddrive-sync)
  fi
  while IFS= read -r n; do
    [[ -n "$n" ]] && extra+=("$n")
  done < <(assistant_disabled_monitor_containers)
  local n
  for n in "${extra[@]}"; do
    assistant_rm_container_by_service "$n"
  done
}

do_remove_stale_worker_containers() {
  assistant_remove_stale_worker_containers
}

do_auto_learn() {
  local base="${INGEST_URL:-http://127.0.0.1:8099}"
  echo "==> auto-learn (no approve) → ${base}"
  if curl -fsS -m 5 "${base}/health" >/dev/null 2>&1; then
    curl -fsS -m 120 -X POST "${base}/v1/learn/scan" \
      -H 'content-type: application/json' \
      -d '{"root":"docs"}' \
      && echo \
      || echo "WARN: learn/scan failed — check ingest logs"
  else
    echo "WARN: ingest not reachable at ${base} — start stack with: bash run.sh up"
    return 1
  fi
}

do_learn_status() {
  local base="${INGEST_URL:-http://127.0.0.1:8099}"
  curl -fsS -m 5 "${base}/health" && echo
  curl -fsS -m 8 "${base}/v1/learn/list?limit=5" 2>/dev/null | head -c 2000 && echo \
    || echo "WARN: cannot list knowledge"
}

do_compact() {
  need_media compact || return 1
  echo "==> compact (skills drafts / memory hooks) — silent"
  local mem="${MEMORY_URL:-http://127.0.0.1:8095}"
  curl -fsS -m 30 -X POST "${mem}/v1/compact" >/dev/null 2>&1 || true
  if [[ -d "${ASSISTANT_DATA_DIR:-/data/assistant}/workspace/.skill-drafts" ]]; then
    find "${ASSISTANT_DATA_DIR}/workspace/.skill-drafts" -type f -mtime +7 -delete 2>/dev/null || true
  fi
  docker exec valkey valkey-cli PING 2>/dev/null || docker exec valkey redis-cli PING 2>/dev/null || true
  echo "compact done"
}

do_optimize_memory() {
  need_media optimize-memory || return 1
  do_compact
}

do_backup_sync_clouddrive() {
  need_security backup-sync-clouddrive || return 1
  case "${ENABLE_CLOUDDRIVE:-0}" in
    1) ;;
    *)
      echo "ENABLE_CLOUDDRIVE=inactive — enable CloudDrive on High first." >&2
      return 1
      ;;
  esac
  local latest mirror
  latest="$("${SUDO:-}" cat "${BACKUP_DIR}/LATEST" 2>/dev/null || true)"
  [[ -n "$latest" ]] || { echo "No LATEST stamp in ${BACKUP_DIR}"; return 1; }
  mirror="${CLOUDDRIVE_MIRROR_DIR:-/data/clouddrive}/assistant-backups"
  mkdir -p "$mirror"
  echo "==> sync stamp ${latest} → ${mirror}"
  rsync -a "${BACKUP_DIR}/${latest}/" "${mirror}/${latest}/" \
    || cp -a "${BACKUP_DIR}/${latest}" "$mirror/"
  echo "OK ${mirror}/${latest}"
}

do_install_timers() {
  local unit_dir="/etc/systemd/system"
  local sudo="${SUDO:-}"
  [[ "$(id -u)" -eq 0 ]] || sudo=sudo
  if ! $sudo true >/dev/null 2>&1; then
    echo "WARN: cannot sudo — skip systemd timers (re-run: bash run.sh install-timers)" >&2
    return 1
  fi
  $sudo tee "${unit_dir}/assistant-auto-learn.service" >/dev/null <<EOF
[Unit]
Description=Assistant auto-learn into Qdrant
After=docker.service
[Service]
Type=oneshot
WorkingDirectory=${STACK_ROOT}
ExecStart=/usr/bin/env bash ${STACK_ROOT}/run.sh auto-learn
EOF
  $sudo tee "${unit_dir}/assistant-auto-learn.timer" >/dev/null <<EOF
[Unit]
Description=Assistant auto-learn daily 00:00
[Timer]
OnCalendar=*-*-* 00:00:00
Persistent=true
[Install]
WantedBy=timers.target
EOF
  $sudo tee "${unit_dir}/assistant-backup.service" >/dev/null <<EOF
[Unit]
Description=Assistant daily backup
After=docker.service
[Service]
Type=oneshot
WorkingDirectory=${STACK_ROOT}
ExecStart=/usr/bin/env bash ${STACK_ROOT}/run.sh backup
EOF
  $sudo tee "${unit_dir}/assistant-backup.timer" >/dev/null <<EOF
[Unit]
Description=Assistant backup daily 00:30
[Timer]
OnCalendar=*-*-* 00:30:00
Persistent=true
[Install]
WantedBy=timers.target
EOF
  $sudo systemctl daemon-reload
  $sudo systemctl enable --now assistant-auto-learn.timer assistant-backup.timer

  # Host/container log archive (default 30d). Any profile when ENABLE_LOG_ARCHIVE=active.
  case "${ENABLE_LOG_ARCHIVE:-1}" in
    1|true|yes|on)
      $sudo tee "${unit_dir}/assistant-log-archive.service" >/dev/null <<EOF
[Unit]
Description=Assistant log archive (host journal + containers + Hermes)
After=docker.service
[Service]
Type=oneshot
WorkingDirectory=${STACK_ROOT}
Environment=STACK_ROOT=${STACK_ROOT}
Environment=ENABLE_LOG_ARCHIVE=active
Environment=LOG_RETENTION_DAYS=${LOG_RETENTION_DAYS:-30}
EnvironmentFile=-${STACK_ROOT}/.env
ExecStart=/usr/bin/env bash ${STACK_ROOT}/scripts/main/log-archive.sh
EOF
      $sudo tee "${unit_dir}/assistant-log-archive.timer" >/dev/null <<EOF
[Unit]
Description=Assistant log archive daily 01:15
[Timer]
OnCalendar=*-*-* 01:15:00
Persistent=true
[Install]
WantedBy=timers.target
EOF
      $sudo systemctl daemon-reload
      $sudo systemctl enable --now assistant-log-archive.timer
      ;;
    *)
      $sudo systemctl disable --now assistant-log-archive.timer >/dev/null 2>&1 || true
      ;;
  esac

  # Stack self-heal every 2 minutes (all profiles that install timers)
  $sudo tee "${unit_dir}/assistant-stack-watch.service" >/dev/null <<EOF
[Unit]
Description=Assistant stack self-heal (restart down/unhealthy)
After=docker.service
[Service]
Type=oneshot
WorkingDirectory=${STACK_ROOT}
Environment=STACK_ROOT=${STACK_ROOT}
Environment=ASSISTANT_DATA_DIR=${ASSISTANT_DATA_DIR:-/data/assistant}
EnvironmentFile=-${STACK_ROOT}/.env
ExecStart=/usr/bin/env bash ${STACK_ROOT}/scripts/main/stack-watch.sh
EOF
  $sudo tee "${unit_dir}/assistant-stack-watch.timer" >/dev/null <<EOF
[Unit]
Description=Assistant stack self-heal every 2 min
[Timer]
OnBootSec=2min
OnUnitActiveSec=2min
AccuracySec=30s
Persistent=true
[Install]
WantedBy=timers.target
EOF
  $sudo systemctl daemon-reload
  $sudo systemctl enable --now assistant-stack-watch.timer

  if _env_active "${ENABLE_ZALO:-}"; then
    $sudo tee "${unit_dir}/assistant-zalo-watch.service" >/dev/null <<EOF
[Unit]
Description=Assistant Zalo SSE/bridge self-heal
After=docker.service
[Service]
Type=oneshot
WorkingDirectory=${STACK_ROOT}
Environment=STACK_ROOT=${STACK_ROOT}
Environment=ASSISTANT_DATA_DIR=${ASSISTANT_DATA_DIR:-/data/assistant}
Environment=ENABLE_ZALO=active
EnvironmentFile=-${STACK_ROOT}/.env
ExecStart=/usr/bin/env bash ${STACK_ROOT}/scripts/main/zalo-watch.sh
EOF
    $sudo tee "${unit_dir}/assistant-zalo-watch.timer" >/dev/null <<EOF
[Unit]
Description=Assistant Zalo self-heal every 1 min
[Timer]
OnBootSec=1min
OnUnitActiveSec=1min
AccuracySec=15s
Persistent=true
[Install]
WantedBy=timers.target
EOF
    $sudo systemctl daemon-reload
    $sudo systemctl enable --now assistant-zalo-watch.timer
  else
    $sudo systemctl disable --now assistant-zalo-watch.timer >/dev/null 2>&1 || true
  fi

  if [[ "${ENABLE_MEDIA_FILE:-inactive}" == "active" || "${WORKER_MEDIA_FILE:-inactive}" == "active" ]] || _env_active "${ENABLE_JOBS:-}"; then
      $sudo tee "${unit_dir}/assistant-compact.service" >/dev/null <<EOF
[Unit]
Description=Assistant compact skills/memory
After=docker.service
[Service]
Type=oneshot
WorkingDirectory=${STACK_ROOT}
ExecStart=/usr/bin/env bash ${STACK_ROOT}/run.sh compact
EOF
      $sudo tee "${unit_dir}/assistant-compact.timer" >/dev/null <<EOF
[Unit]
Description=Assistant compact daily 00:00
[Timer]
OnCalendar=*-*-* 00:00:00
Persistent=true
[Install]
WantedBy=timers.target
EOF
      $sudo systemctl daemon-reload
      $sudo systemctl enable --now assistant-compact.timer
  else
      $sudo systemctl disable --now assistant-compact.timer >/dev/null 2>&1 || true
  fi
  systemctl list-timers 'assistant-*' --no-pager || true
  echo "timers installed"
}

# Timers (backup/learn/stack-watch; log-archive 30d; compact when media worker active; zalo-watch when ENABLE_ZALO=active)
ensure_profile_timers() {
  echo "==> install timers (ENABLE_ZALO=${ENABLE_ZALO:-inactive})"
  do_install_timers || true
}

do_channel_status() {
  assistant_workers_summary
  echo "ENABLE_ZALO=${ENABLE_ZALO:-inactive}"
  echo "ENABLE_TELEGRAM=${ENABLE_TELEGRAM:-0}"
  echo "social-app packs: architect/social-app/{zalo,telegram,http}"
}

do_destroy() {
  # Tear down this compose project: containers + networks. Named volumes /data kept.
  local project="${COMPOSE_PROJECT_NAME:-assistant}"
  local existing
  existing="$(docker ps -aq --filter "label=com.docker.compose.project=${project}" 2>/dev/null | wc -l | tr -d ' ')"
  if [[ "${existing:-0}" -eq 0 ]]; then
    echo "==> no project containers — skip backup before destroy (clean / first-setup host)"
  else
    do_backup_first "destroy" || return 1
  fi
  echo "==> destroy stack project=${project} (containers + networks; volumes kept)"
  compose down --remove-orphans || true

  # Leftovers labeled with this compose project (stopped/orphaned)
  local ids
  ids="$(docker ps -aq --filter "label=com.docker.compose.project=${project}" 2>/dev/null || true)"
  if [[ -n "${ids}" ]]; then
    echo "==> remove leftover project containers"
    # shellcheck disable=SC2086
    docker rm -f ${ids} 2>/dev/null || true
  fi

  # Project networks (e.g. assistant_internal)
  local nets
  nets="$(docker network ls -q --filter "label=com.docker.compose.project=${project}" 2>/dev/null || true)"
  if [[ -n "${nets}" ]]; then
    echo "==> remove project networks"
    # shellcheck disable=SC2086
    docker network rm ${nets} 2>/dev/null || true
  fi
  docker network rm "${project}_internal" 2>/dev/null || true

  echo "==> remaining project containers: $(docker ps -aq --filter "label=com.docker.compose.project=${project}" 2>/dev/null | wc -l | tr -d ' ')"
  echo "OK: destroy complete (data volumes and ${ASSISTANT_DATA_DIR:-/data/assistant} untouched)"
}

do_update() {
  # After: git pull  →  bash run.sh update [component...]
  # With no args: rebuild whole stack (legacy).
  # With args: update only named compose services (no global down; preserve volumes).
  # Examples:
  #   bash run.sh update hermes
  #   bash run.sh update schedule-worker zalo-api
  #   bash run.sh update all
  local services=("$@")
  if [[ ${#services[@]} -eq 0 || " ${services[*]} " == *" all "* ]]; then
    services=()
  fi

  do_backup_first "update" || return 1
  echo "==> update from current source"
  if [[ -d "${ROOT}/.git" ]]; then
    echo "==> git HEAD: $(git -C "$ROOT" rev-parse --short HEAD 2>/dev/null || echo unknown)"
    echo "    (run git pull yourself before update if you want remote changes)"
  fi
  # Model-router prompt/config SoT lives in Hermes skills; keep bake fallback identical.
  if [[ -f "${SCRIPTS_DIR}/sync-model-router-skills.sh" ]]; then
    bash "${SCRIPTS_DIR}/sync-model-router-skills.sh" || echo "WARN: sync-model-router-skills failed"
  elif [[ -f "${SCRIPTS_DIR}/sync-classify-skill.sh" ]]; then
    bash "${SCRIPTS_DIR}/sync-classify-skill.sh" || echo "WARN: sync-classify-skill failed"
  fi
  if [[ -f "${SCRIPTS_DIR}/sync-zalo-plugins.sh" ]]; then
    bash "${SCRIPTS_DIR}/sync-zalo-plugins.sh" || echo "WARN: sync-zalo-plugins failed"
  fi

  assistant_profile_summary

  if [[ ${#services[@]} -gt 0 ]]; then
    echo "==> component update: ${services[*]}"
    echo "==> pull selected images (best-effort)"
    do_load_openbao_env_for_compose
    compose pull "${services[@]}" || true
    ensure_hermes_media_dirs
    # Scoped recreate — never docker compose down; never touch postgres unless requested.
    for svc in "${services[@]}"; do
      if [[ "$svc" == "postgres" ]]; then
        echo "WARN: refusing implicit postgres recreate — pass explicit confirmation via UPDATE_ALLOW_POSTGRES=1"
        if [[ "${UPDATE_ALLOW_POSTGRES:-0}" != "1" ]]; then
          continue
        fi
      fi
      echo "==> up --no-deps --build $svc"
      compose up -d --no-deps --build "$svc" || return $?
    done
    do_stop_disabled_optionals
    compose ps
    echo "OK: component update complete (${services[*]})"
    return 0
  fi

  echo "==> pull vendor images (best-effort)"
  do_load_openbao_env_for_compose
  compose pull || true

  echo "==> rebuild + recreate"
  ensure_hermes_media_dirs
  # Clear hex-prefixed compose rename orphans + duplicate service containers
  # (avoids: Conflict … name "/<hex>_assistant-authz-1" is already in use).
  do_remove_stale_worker_containers
  if ! compose up -d --build --remove-orphans; then
    echo "WARN: compose up failed — clearing recreate orphans and retrying once"
    do_remove_stale_worker_containers
    compose up -d --build --remove-orphans || return $?
  fi
  do_stop_disabled_optionals

  if _env_active "${ENABLE_OPENBAO:-}"; then
    echo "==> seed API keys into OpenBao"
    do_first_setup_openbao || echo "WARN: OpenBao seed failed — re-run: bash run.sh first-setup-openbao"
  fi
  do_scrub_plaintext_env

  echo "==> disk cleanup"
  docker builder prune -af >/dev/null 2>&1 || true
  docker image prune -af >/dev/null 2>&1 || true
  docker container prune -f >/dev/null 2>&1 || true
  rm -rf /tmp/assistant /tmp/assistant-low.tgz /tmp/9r-*.json 2>/dev/null || true
  df -h / 2>/dev/null | tail -1 || true

  ensure_profile_timers

  do_post_ready_learn
  do_zalo_setup_hint

  compose ps
  echo "OK: update complete"
}

do_first_setup_openbao() {
  need_security first-setup-openbao || return 1
  export STACK_ROOT="${STACK_ROOT:-$ROOT}"
  export ASSISTANT_DATA_DIR="${ASSISTANT_DATA_DIR:-/data/assistant}"
  export HERMES_DATA_DIR="${HERMES_DATA_DIR:-$ASSISTANT_DATA_DIR}"
  python3 "${SCRIPTS_DIR}/first-setup-openbao.py" || return $?
  # Re-export KV → data dir so compose env_file (hermes) picks up secrets after UI edits / re-seed.
  python3 "${SCRIPTS_DIR}/load-openbao-env.py" \
    || echo "WARN: load-openbao-env failed — re-run: bash run.sh load-openbao-env"
}

do_scrub_plaintext_env() {
  # After compose is up: drop host-side secret exports so disk scans cannot list keys.
  # Next recreate: bash run.sh load-openbao-env (or first-setup-openbao) before up|update.
  [[ -f "${SCRIPTS_DIR}/scrub-plaintext-env.py" ]] || return 0
  echo "==> scrub plaintext .env / .env.openbao exports"
  STACK_ROOT="${ROOT}" ASSISTANT_DATA_DIR="${ASSISTANT_DATA_DIR:-${HERMES_DATA_DIR:-/data/assistant}}" \
    python3 "${SCRIPTS_DIR}/scrub-plaintext-env.py" \
    || echo "WARN: scrub-plaintext-env returned non-zero"
}

do_load_openbao_env_for_compose() {
  # Compose ${VAR:?} and hermes env_file need KV export before up|update.
  _env_active "${ENABLE_OPENBAO:-}" || return 0
  [[ -f "${SCRIPTS_DIR}/load-openbao-env.py" ]] || return 0
  echo "==> load OpenBao env for compose"
  export STACK_ROOT="${STACK_ROOT:-$ROOT}"
  export ASSISTANT_DATA_DIR="${ASSISTANT_DATA_DIR:-/data/assistant}"
  export HERMES_DATA_DIR="${HERMES_DATA_DIR:-$ASSISTANT_DATA_DIR}"
  python3 "${SCRIPTS_DIR}/load-openbao-env.py" \
    || echo "WARN: load-openbao-env failed — re-run: bash run.sh load-openbao-env"
}

do_post_ready_learn() {
  # All profiles: after Hermes + 9Router ready, if hermes/main/skills not empty → learn skill|docs
  echo "==> post-ready learn (skills|docs)"
  export STACK_ROOT="${STACK_ROOT:-$ROOT}"
  export ASSISTANT_DATA_DIR="${ASSISTANT_DATA_DIR:-/data/assistant}"
  export HERMES_DATA_DIR="${HERMES_DATA_DIR:-$ASSISTANT_DATA_DIR}"
  python3 "${SCRIPTS_DIR}/post-ready-learn.py" \
    || echo "WARN: post-ready-learn failed — re-run: bash run.sh post-ready-learn"
}

do_zalo_setup_hint() {
  _env_active "${ENABLE_ZALO:-}" || return 0
  if [[ "$(id -u)" -eq 0 ]]; then
    echo "NEXT (manual, as deploy user — not root): bash scripts/main/setup-zalo.sh"
  else
    echo "NEXT (Zalo QR + adapter): bash scripts/main/setup-zalo.sh"
  fi
}

do_post_up_hooks() {
  # Full stack bring-up hooks — skipped when ASSISTANT_UP_LIGHT=1 (e.g. setup-zalo after QR).
  ensure_profile_timers
  if _env_active "${ENABLE_9ROUTER:-}" && [[ -n "${N9ROUTER_INITIAL_PASSWORD:-}" ]]; then
    echo "==> first-setup-llm (9Router key + hermes combo)"
    export STACK_ROOT="${STACK_ROOT:-$ROOT}"
    export HERMES_DATA_DIR="${HERMES_DATA_DIR:-${ASSISTANT_DATA_DIR:-/data/assistant}}"
    python3 "${SCRIPTS_DIR}/first-setup-9router-hermes.py" \
      || echo "WARN: first-setup-llm failed — re-run: bash run.sh first-setup-llm"
  elif _env_active "${ENABLE_9ROUTER:-}"; then
    echo "WARN: N9ROUTER_INITIAL_PASSWORD empty — skip 9Router first-setup"
  fi
  if _env_active "${ENABLE_OMNIROUTER:-}"; then
    echo "==> first-setup-omnirouter (hermes/classifier ← Omni OpenCode cloud)"
    export STACK_ROOT="${STACK_ROOT:-$ROOT}"
    python3 "${SCRIPTS_DIR}/first-setup-omnirouter.py" \
      || echo "WARN: first-setup-omnirouter failed — re-run: bash run.sh first-setup-omnirouter"
  fi
  if _env_active "${ENABLE_OPENBAO:-}"; then
    do_first_setup_openbao || echo "WARN: OpenBao seed failed — re-run: bash run.sh first-setup-openbao"
  fi
  do_scrub_plaintext_env
  do_post_ready_learn
  do_zalo_setup_hint
}

env_upsert() {
  local k="$1" v="$2" f="${ROOT}/.env"
  touch "$f"
  chmod 600 "$f" 2>/dev/null || true
  if grep -q "^${k}=" "$f"; then
    sed -i "s|^${k}=.*|${k}=${v}|" "$f"
  else
    echo "${k}=${v}" >> "$f"
  fi
}

_reject_edge_flag_off() {
  local k="$1" v="$2"
  case "$k" in
    ENABLE_TRAEFIK)
      if [[ "$v" == "0" ]]; then
        echo "ERROR: disable Traefik with: bash run.sh uninstall traefik" >&2
        echo "      (not add-components ENABLE_TRAEFIK=inactive)" >&2
        return 1
      fi
      ;;
    ENABLE_API_GATEWAY)
      if [[ "$v" == "0" ]]; then
        echo "ERROR: disable API Gateway with: bash run.sh uninstall gateway" >&2
        echo "      (not add-components ENABLE_API_GATEWAY=inactive)" >&2
        return 1
      fi
      ;;
  esac
  return 0
}

_apply_component_change() {
  local stamp="$1"
  shift
  local noup="${1:-0}"
  local doupdate="${2:-0}"
  if [[ "$noup" == "1" ]]; then
    if [[ "$doupdate" == "1" ]]; then
      echo "NEXT: bash run.sh update"
    else
      echo "NEXT: bash run.sh up"
    fi
    echo "UNDO: bash run.sh restore ${stamp}"
    return 0
  fi
  if [[ "$doupdate" == "1" ]]; then
    export ASSISTANT_PURGE_WORKER_COMPOSE=1
    do_update
  else
    export ASSISTANT_PURGE_WORKER_COMPOSE=1
    exec bash "${ROOT}/run.sh" up
  fi
}

do_archive_before_change() {
  # Snapshot live options + DR backup; verify stamp before worker add/remove.
  local reason="${1:-manual}"
  echo "==> current options (before change)"
  assistant_options_dump
  local project="${COMPOSE_PROJECT_NAME:-assistant}"
  local existing
  existing="$(docker ps -aq --filter "label=com.docker.compose.project=${project}" 2>/dev/null | wc -l | tr -d ' ')"
  if [[ "${existing:-0}" -eq 0 ]]; then
    echo "==> no project containers — skip backup before ${reason} (clean / first-setup host)"
    return 0
  fi
  do_backup_first "$reason"
}

do_switch_profile() {
  echo "Profile upgrade/downgrade is removed."
  echo "Enable workers with: bash run.sh install schedule media security notify message monitor"
  echo "  (or: bash run.sh install list)"
  return 2
}

do_remove_components() {
  local dry=0 noup=0 doupdate=0
  local -a pairs=()
  local arg k v
  for arg in "$@"; do
    case "$arg" in
      --dry-run) dry=1 ;;
      --no-up) noup=1 ;;
      --update) doupdate=1 ;;
      *=*)
        k="${arg%%=*}"
        v="${arg#*=}"
        if ! assistant_option_key_ok "$k"; then
          echo "ERROR: unknown option ${k} (not in worker option list)" >&2
          return 2
        fi
        case "$k" in
          ENABLE_TRAEFIK)
            echo "ERROR: disable Traefik with: bash run.sh uninstall traefik" >&2
            return 2
            ;;
          ENABLE_API_GATEWAY)
            echo "ERROR: disable API Gateway with: bash run.sh uninstall gateway" >&2
            return 2
            ;;
        esac
        # Normalize remove verbs to inactive/0
        case "$(printf '%s' "$v" | tr '[:upper:]' '[:lower:]')" in
          remove|off|inactive|0|false|no) v="inactive" ;;
        esac
        case "$k" in
          ENABLE_*) v="0" ;;
          WORKER_*) v="inactive" ;;
        esac
        pairs+=("${k}=${v}")
        ;;
      WORKER_*|ENABLE_*)
        # bare key → deactivate
        k="$arg"
        if ! assistant_option_key_ok "$k"; then
          echo "ERROR: unknown option ${k}" >&2
          return 2
        fi
        case "$k" in
          ENABLE_TRAEFIK)
            echo "ERROR: disable Traefik with: bash run.sh uninstall traefik" >&2
            return 2
            ;;
          ENABLE_API_GATEWAY)
            echo "ERROR: disable API Gateway with: bash run.sh uninstall gateway" >&2
            return 2
            ;;
        esac
        case "$k" in
          ENABLE_*) pairs+=("${k}=0") ;;
          WORKER_*) pairs+=("${k}=inactive") ;;
          *) pairs+=("${k}=0") ;;
        esac
        ;;
      *)
        echo "usage: bash run.sh remove-components KEY[=inactive|0] […] [--dry-run] [--no-up] [--update]" >&2
        return 2
        ;;
    esac
  done
  [[ ${#pairs[@]} -gt 0 ]] || { echo "usage: bash run.sh remove-components KEY[=…] […] [--dry-run] [--no-up] [--update]" >&2; return 2; }
  echo "==> remove-components ${pairs[*]}"
  if [[ "$dry" == "1" ]]; then
    echo "DRY_RUN: would archive then set: ${pairs[*]}"
    return 0
  fi
  do_archive_before_change "remove-components:${pairs[*]}" || return 1
  local stamp
  stamp="$(cat "${BACKUP_DIR:-/data/assistant/backups}/PRE_CHANGE" 2>/dev/null || true)"
  for arg in "${pairs[@]}"; do
    env_upsert "${arg%%=*}" "${arg#*=}"
  done
  echo "OK: wrote ${pairs[*]} (stamp=${stamp})"
  _apply_component_change "$stamp" "$noup" "$doupdate"
}

do_install() {
  local dry=0 noup=0 doupdate=0
  local -a names=()
  local arg
  for arg in "$@"; do
    case "$arg" in
      --dry-run) dry=1 ;;
      --no-up) noup=1 ;;
      --update) doupdate=1 ;;
      list|-l|--list|help|-h|--help)
        bash "${SCRIPTS_DIR}/install-component.sh" list
        return 0
        ;;
      *)
        names+=("$arg")
        ;;
    esac
  done
  [[ ${#names[@]} -gt 0 ]] || {
    echo "usage: bash run.sh install NAME [NAME…] [--dry-run] [--no-up] [--update]" >&2
    echo "       bash run.sh install list" >&2
    bash "${SCRIPTS_DIR}/install-component.sh" list >&2
    return 2
  }
  local -a pairs=()
  while IFS= read -r line; do
    [[ -n "$line" ]] && pairs+=("$line")
  done < <(bash "${SCRIPTS_DIR}/install-component.sh" resolve "${names[@]}")
  [[ ${#pairs[@]} -gt 0 ]] || return 1
  local -a extra=()
  [[ "$dry" == "1" ]] && extra+=(--dry-run)
  [[ "$noup" == "1" ]] && extra+=(--no-up)
  [[ "$doupdate" == "1" ]] && extra+=(--update)
  do_add_components "${pairs[@]}" "${extra[@]}"
}

do_uninstall() {
  local dry=0 noup=0 doupdate=0
  local -a names=()
  local arg
  for arg in "$@"; do
    case "$arg" in
      --dry-run) dry=1 ;;
      --no-up) noup=1 ;;
      --update) doupdate=1 ;;
      list|-l|--list|help|-h|--help)
        bash "${SCRIPTS_DIR}/install-component.sh" list
        return 0
        ;;
      *)
        names+=("$arg")
        ;;
    esac
  done
  [[ ${#names[@]} -gt 0 ]] || {
    echo "usage: bash run.sh uninstall NAME [NAME…] [--dry-run] [--no-up] [--update]" >&2
    return 2
  }
  local -a pairs=()
  while IFS= read -r line; do
    [[ -n "$line" ]] && pairs+=("$line")
  done < <(bash "${SCRIPTS_DIR}/install-component.sh" unresolve "${names[@]}")
  [[ ${#pairs[@]} -gt 0 ]] || return 1
  local -a extra=()
  [[ "$dry" == "1" ]] && extra+=(--dry-run)
  [[ "$noup" == "1" ]] && extra+=(--no-up)
  [[ "$doupdate" == "1" ]] && extra+=(--update)
  do_remove_components "${pairs[@]}" "${extra[@]}"
}

do_add_components() {
  local dry=0 noup=0 doupdate=0
  local -a pairs=()
  local arg k v
  for arg in "$@"; do
    case "$arg" in
      --dry-run) dry=1 ;;
      --no-up) noup=1 ;;
      --update) doupdate=1 ;;
      *=*)
        k="${arg%%=*}"
        v="${arg#*=}"
        if ! assistant_option_key_ok "$k"; then
          echo "ERROR: unknown option ${k} (not in worker option list)" >&2
          return 2
        fi
        _reject_edge_flag_off "$k" "$v" || return 2
        pairs+=("${k}=${v}")
        ;;
      *)
        echo "usage: bash run.sh add-components KEY=VAL [KEY=VAL…] [--dry-run] [--no-up] [--update]" >&2
        return 2
        ;;
    esac
  done
  [[ ${#pairs[@]} -gt 0 ]] || { echo "usage: bash run.sh add-components KEY=VAL [KEY=VAL…] [--dry-run] [--no-up] [--update]" >&2; return 2; }
  echo "==> add-components ${pairs[*]}"
  assistant_profile_summary
  for arg in "${pairs[@]}"; do
    k="${arg%%=*}"
    case "$k" in
      ENABLE_OPENBAO|ENABLE_AUTHZ|ENABLE_SIEM|ENABLE_POLICY|ENABLE_SECURITY|ENABLE_NOTIFY)
        echo "NOTE: ${k}=1 loads the security/notify overlay (docker-compose.security.yml)" >&2
        ;;
    esac
  done
  if [[ "$dry" == "1" ]]; then
    echo "DRY_RUN: would archive then set: ${pairs[*]}"
    return 0
  fi
  do_archive_before_change "add-components:${pairs[*]}" || return 1
  local stamp
  stamp="$(cat "${BACKUP_DIR:-/data/assistant/backups}/PRE_CHANGE" 2>/dev/null || true)"
  for arg in "${pairs[@]}"; do
    env_upsert "${arg%%=*}" "${arg#*=}"
  done
  echo "OK: wrote ${pairs[*]} (stamp=${stamp})"
  _apply_component_change "$stamp" "$noup" "$doupdate"
}

do_help() {
  cat <<EOF
assistant — workers $(assistant_workers_summary | head -n1)
Docs: docs/02-commands.md

Stack (all):
  up | down | destroy | ps | logs [svc] | workers | update

  update   # backup+verify, then after git pull: rebuild stack, refresh LLM wiring, prune disk
  destroy  # backup+verify, then remove project containers + networks (volumes/data kept)
           # then rebuild with: bash run.sh up

Change workers (backup+verify first):
  install NAME [NAME…]          # short names → .env (see: bash run.sh install list)
  uninstall NAME [NAME…]        # deactivate by short name
  add-components KEY=VAL […] [--dry-run] [--no-up] [--update]
  remove-components KEY[=inactive|0] […] [--dry-run] [--no-up] [--update]
  install-workers …             # alias of add-components
  remove-workers …              # alias of remove-components
  workers                       # show current worker activation

DR (all):
  backup | restore [stamp] | verify [stamp] | migrate

Knowledge (all):
  auto-learn | learn-status
  post-ready-learn        # after Hermes+router: sync hermes/main/skills|docs → ingest

Memory (media worker):
  compact | optimize-memory
  check-media             # smoke OCR / Jobs / SearXNG / dispatcher

Timers:
  install-timers

First setup:
  install-docker [user]   # if docker missing; default = SSH login user (not a hardcoded name)
  first-setup-omnirouter  # OmniRoute Default Key → hermes/classifier OpenCode cloud
  first-setup-llm         # 9Router Default Key → combo hermes (only when ENABLE_9ROUTER=active)

Security overlay:
  first-setup-openbao     # seed API keys → OpenBao UI (:8200); also on up|update
  load-openbao-env        # pull KV → $ASSISTANT_DATA_DIR/.env.openbao for compose
  check-security          # smoke OpenBao / Grafana / AV / authz / …
  backup-sync-clouddrive  # when ENABLE_CLOUDDRIVE=active

Attachable:
  channel-status
  setup-zalo              # QR first, then bridge + zalo-api + adapter (deploy user, not sudo)
  login-zalo              # re-login QR when stack already installed
  zalo-watch              # self-heal bridge/SSE (also timer when ENABLE_ZALO=active)
  stack-watch             # self-heal down/unhealthy compose services (timer)
EOF
}

case "$cmd" in
  up)
    assistant_profile_summary
    ensure_hermes_media_dirs
    do_remove_stale_worker_containers
    do_load_openbao_env_for_compose
    compose up -d --remove-orphans
    do_stop_disabled_optionals
    if [[ -f "${SCRIPTS_DIR}/hermes-cron-share.sh" ]]; then
      echo "==> share Hermes schedules (keep jobs across replica ids)"
      bash "${SCRIPTS_DIR}/hermes-cron-share.sh" || true
    fi
    if [[ "${ASSISTANT_UP_LIGHT:-0}" == "1" ]]; then
      echo "==> up (light — compose only; timers: bash run.sh install-timers)"
    else
      do_post_up_hooks
    fi
    ;;
  down) compose down ;;
  destroy) do_destroy ;;
  ps) compose ps ;;
  logs) compose logs -f --tail=100 "$@" ;;
  workers|profile) assistant_workers_summary ;;
  switch-profile|change-profile) do_switch_profile "$@" ;;
  install|enable) do_install "$@" ;;
  uninstall|disable) do_uninstall "$@" ;;
  add-components|enable-components|install-workers) do_add_components "$@" ;;
  remove-components|disable-components|remove-workers) do_remove_components "$@" ;;
  update) do_update "$@" ;;
  backup) ops backup "$@" ;;
  restore) ops restore "$@" ;;
  verify) ops verify "$@" ;;
  migrate) ops migrate "$@" ;;
  auto-learn) do_auto_learn ;;
  learn-status) do_learn_status ;;
  post-ready-learn|learn-skills)
    do_post_ready_learn
    ;;
  compact) do_compact ;;
  optimize-memory|optimize) do_optimize_memory ;;
  check-media|smoke-media)
    need_media check-media || exit 1
    bash "${SCRIPTS_DIR}/check-media.sh"
    ;;
  check-security|smoke-security)
    need_security check-security || exit 1
    bash "${SCRIPTS_DIR}/check-security.sh"
    ;;
  install-timers|timers) do_install_timers ;;
  install-docker)
    # Prefer explicit arg; else current login user (works under sudo via SUDO_USER)
    _docker_user="${1:-}"
    if [[ -z "$_docker_user" ]]; then
      _docker_user="${SUDO_USER:-}"
    fi
    if [[ -z "$_docker_user" || "$_docker_user" == "root" ]]; then
      _docker_user="$(logname 2>/dev/null || true)"
    fi
    if [[ -z "$_docker_user" || "$_docker_user" == "root" ]]; then
      _docker_user="$(whoami)"
    fi
    sudo bash "${SCRIPTS_DIR}/install-docker.sh" "${_docker_user}"
    ;;
  first-setup-llm|setup-llm)
    export STACK_ROOT="${STACK_ROOT:-$ROOT}"
    export HERMES_DATA_DIR="${HERMES_DATA_DIR:-/data/assistant}"
    python3 "${SCRIPTS_DIR}/first-setup-9router-hermes.py"
    if _env_active "${ENABLE_OMNIROUTER:-}"; then
      python3 "${SCRIPTS_DIR}/first-setup-omnirouter.py"
    fi
    do_post_ready_learn
    ;;
  first-setup-omnirouter|setup-omnirouter)
    export STACK_ROOT="${STACK_ROOT:-$ROOT}"
    python3 "${SCRIPTS_DIR}/first-setup-omnirouter.py"
    ;;
  first-setup-openbao|setup-openbao)
    do_first_setup_openbao
    ;;
  load-openbao-env)
    need_security load-openbao-env || exit 1
    export STACK_ROOT="${STACK_ROOT:-$ROOT}"
    export ASSISTANT_DATA_DIR="${ASSISTANT_DATA_DIR:-/data/assistant}"
    export HERMES_DATA_DIR="${HERMES_DATA_DIR:-$ASSISTANT_DATA_DIR}"
    python3 "${SCRIPTS_DIR}/load-openbao-env.py"
    ;;
  setup-zalo)
    export STACK_ROOT="${STACK_ROOT:-$ROOT}"
    export HERMES_DATA_DIR="${HERMES_DATA_DIR:-${ASSISTANT_DATA_DIR:-/data/assistant}}"
    bash "${SCRIPTS_DIR}/setup-zalo.sh"
    ;;
  login-zalo)
    bash "${SCRIPTS_DIR}/login-zalo.sh"
    ;;
  zalo-watch)
    export STACK_ROOT="${STACK_ROOT:-$ROOT}"
    bash "${SCRIPTS_DIR}/zalo-watch.sh"
    ;;
  stack-watch)
    export STACK_ROOT="${STACK_ROOT:-$ROOT}"
    bash "${SCRIPTS_DIR}/stack-watch.sh"
    ;;
  backup-sync-clouddrive) do_backup_sync_clouddrive ;;
  channel-status) do_channel_status ;;
  help|-h|--help) do_help ;;
  *)
    echo "Unknown command: ${cmd}" >&2
    do_help
    exit 2
    ;;
esac
