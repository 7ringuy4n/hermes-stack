#!/usr/bin/env bash
# assistant entrypoint — commands depend on ASSISTANT_PROFILE (see docs/02-commands.md).
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

# shellcheck source=architect/backup-restore/lib/profile.sh
source "${ROOT}/architect/backup-restore/lib/profile.sh"
assistant_profile_apply

cmd="${1:-help}"
shift || true

compose() {
  # Low: base. Medium: + medium. High: + medium + high (+ optional notify/clouddrive/comfy-gpu).
  # Edge: + docker-compose.edge.yml when Traefik / API Gateway / OpenVPN enabled.
  # Hermes scale: HERMES_REPLICAS (default 1; High default 2). Host ports only when replicas=1.
  # Traefik mode: local = VPN/localhost (default). public = ACME when email+domain set.
  local -a files=(--project-directory "$ROOT" -f "$ROOT/docker/docker-compose.yml")
  local -a profiles=()
  local -a scale_args=()
  local replicas="${HERMES_REPLICAS:-1}"
  local traefik_mode="${TRAEFIK_MODE:-local}"
  local acme="${TRAEFIK_ACME_ENABLED:-0}"

  # Fail-soft: public/ACME without email+domain → local HTTP Traefik
  if [[ "${ENABLE_TRAEFIK:-0}" == "1" ]]; then
    case "${traefik_mode}" in
      public)
        if [[ "$acme" == "1" && -n "${TRAEFIK_ACME_EMAIL:-}" && -n "${TRAEFIK_ACME_DOMAIN:-}" ]]; then
          acme=1
        else
          if [[ "$acme" == "1" ]]; then
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

  case "$ASSISTANT_PROFILE" in
    medium)
      files+=(-f "$ROOT/docker/docker-compose.medium.yml")
      if [[ "${COMFYUI_HAS_GPU:-0}" == "1" ]]; then
        profiles+=(--profile comfy-gpu)
      fi
      if [[ "${ENABLE_ZALO:-0}" == "1" ]]; then
        profiles+=(--profile zalo)
      fi
      ;;
    high)
      files+=(-f "$ROOT/docker/docker-compose.medium.yml" -f "$ROOT/docker/docker-compose.high.yml")
      if [[ "${ENABLE_NOTIFY:-0}" == "1" ]]; then
        profiles+=(--profile notify)
      fi
      if [[ "${ENABLE_ANTIVIRUS:-0}" == "1" ]]; then
        profiles+=(--profile antivirus)
      fi
      if [[ "${SECURITY_SANDBOX:-0}" == "1" ]]; then
        echo "WARN: SECURITY_SANDBOX=1 starts docker-socket-proxy — not a production isolation boundary" >&2
        profiles+=(--profile sandbox)
      fi
      if [[ "${ENABLE_CLOUDDRIVE:-0}" == "1" ]]; then
        profiles+=(--profile clouddrive)
      fi
      if [[ "${COMFYUI_HAS_GPU:-0}" == "1" ]]; then
        profiles+=(--profile comfy-gpu)
      fi
      if [[ "${ENABLE_ZALO:-0}" == "1" ]]; then
        profiles+=(--profile zalo)
      fi
      ;;
    low)
      if [[ "${ENABLE_ZALO:-0}" == "1" ]]; then
        profiles+=(--profile zalo)
      fi
      ;;
  esac
  # Optionals usable on any profile when enabled (OCR/jobs via medium overlay)
  case "${ENABLE_OCR:-0}${ENABLE_JOBS:-0}${ENABLE_SEARXNG:-0}" in
    *1*)
      if [[ "$ASSISTANT_PROFILE" == "low" ]]; then
        files+=(-f "$ROOT/docker/docker-compose.medium.yml")
      fi
      ;;
  esac
  case "${ENABLE_TRAEFIK:-0}${ENABLE_API_GATEWAY:-0}${ENABLE_OPENVPN:-0}" in
    *1*)
      files+=(-f "$ROOT/docker/docker-compose.edge.yml")
      ;;
  esac
  if [[ "${ENABLE_OMNIROUTER:-0}" == "1" ]]; then
    profiles+=(--profile omnirouter)
  fi
  if [[ "${ENABLE_TRAEFIK:-0}" == "1" ]]; then
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
  if [[ "${ENABLE_API_GATEWAY:-0}" == "1" ]]; then
    profiles+=(--profile gateway)
  fi
  if [[ "${ENABLE_OPENVPN:-0}" == "1" ]]; then
    profiles+=(--profile openvpn)
  fi
  # Observability — opt-in via ENABLE_* / profile monitor (any profile)
  case "${ENABLE_GRAFANA:-0}${ENABLE_LOKI:-0}${ENABLE_PROMETHEUS:-0}${ENABLE_ALLOY:-0}" in
    *1*)
      profiles+=(--profile monitor)
      ;;
  esac
  if [[ "$replicas" == "1" ]]; then
    files+=(-f "$ROOT/docker/docker-compose.hermes-hostports.yml")
  fi
  case "${1:-}" in
    up|create|run)
      scale_args=(--scale "hermes=${replicas}")
      ;;
  esac
  docker compose "${files[@]}" "${profiles[@]}" "$@" "${scale_args[@]}"
}

need_med() {
  case "$ASSISTANT_PROFILE" in
    medium|high) return 0 ;;
    *)
      echo "Command '${1:-}' requires ASSISTANT_PROFILE=medium|high (now: ${ASSISTANT_PROFILE})." >&2
      return 1
      ;;
  esac
}

need_high() {
  case "$ASSISTANT_PROFILE" in
    high) return 0 ;;
    *)
      echo "Command '${1:-}' requires ASSISTANT_PROFILE=high (now: ${ASSISTANT_PROFILE})." >&2
      return 1
      ;;
  esac
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
  if [[ "${ENABLE_ANTIVIRUS:-0}" != "1" ]]; then
    extra+=(clamav av-gateway)
  fi
  if [[ "${SECURITY_SANDBOX:-0}" != "1" ]]; then
    extra+=(docker-socket-proxy)
  fi
  if [[ "${ENABLE_CLOUDDRIVE:-0}" != "1" ]]; then
    extra+=(clouddrive-sync)
  fi
  case "${ENABLE_GRAFANA:-0}${ENABLE_LOKI:-0}${ENABLE_PROMETHEUS:-0}${ENABLE_ALLOY:-0}" in
    *1*) ;;
    *) extra+=(grafana loki prometheus alloy nine-exporter stack-exporter) ;;
  esac
  local n
  for n in "${extra[@]}"; do
    docker rm -f "$n" >/dev/null 2>&1 || true
  done
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
  need_med compact || return 1
  echo "==> compact (skills drafts / memory hooks) — silent"
  local mem="${MEMORY_URL:-http://127.0.0.1:8095}"
  curl -fsS -m 30 -X POST "${mem}/v1/compact" >/dev/null 2>&1 || true
  if [[ -d "${ASSISTANT_DATA_DIR:-/data/assistant}/workspace/.skill-drafts" ]]; then
    find "${ASSISTANT_DATA_DIR}/workspace/.skill-drafts" -type f -mtime +7 -delete 2>/dev/null || true
  fi
  docker exec redis valkey-cli PING 2>/dev/null || docker exec redis redis-cli PING 2>/dev/null || true
  echo "compact done"
}

do_optimize_memory() {
  need_med optimize-memory || return 1
  do_compact
}

do_backup_sync_clouddrive() {
  need_high backup-sync-clouddrive || return 1
  case "${ENABLE_CLOUDDRIVE:-0}" in
    1) ;;
    *)
      echo "ENABLE_CLOUDDRIVE=0 — enable CloudDrive on High first." >&2
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
Environment=ASSISTANT_PROFILE=${ASSISTANT_PROFILE}
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
Environment=ASSISTANT_PROFILE=${ASSISTANT_PROFILE}
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

  # Host/container log archive (default 30d). Any profile when ENABLE_LOG_ARCHIVE=1.
  case "${ENABLE_LOG_ARCHIVE:-1}" in
    1|true|yes|on)
      $sudo tee "${unit_dir}/assistant-log-archive.service" >/dev/null <<EOF
[Unit]
Description=Assistant log archive (host journal + containers + Hermes)
After=docker.service
[Service]
Type=oneshot
WorkingDirectory=${STACK_ROOT}
Environment=ASSISTANT_PROFILE=${ASSISTANT_PROFILE}
Environment=STACK_ROOT=${STACK_ROOT}
Environment=ENABLE_LOG_ARCHIVE=1
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
Environment=ASSISTANT_PROFILE=${ASSISTANT_PROFILE}
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

  if [[ "${ENABLE_ZALO:-0}" == "1" ]]; then
    $sudo tee "${unit_dir}/assistant-zalo-watch.service" >/dev/null <<EOF
[Unit]
Description=Assistant Zalo SSE/bridge self-heal
After=docker.service
[Service]
Type=oneshot
WorkingDirectory=${STACK_ROOT}
Environment=ASSISTANT_PROFILE=${ASSISTANT_PROFILE}
Environment=STACK_ROOT=${STACK_ROOT}
Environment=ASSISTANT_DATA_DIR=${ASSISTANT_DATA_DIR:-/data/assistant}
Environment=ENABLE_ZALO=1
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

  case "$ASSISTANT_PROFILE" in
    medium|high)
      $sudo tee "${unit_dir}/assistant-compact.service" >/dev/null <<EOF
[Unit]
Description=Assistant compact skills/memory
After=docker.service
[Service]
Type=oneshot
WorkingDirectory=${STACK_ROOT}
Environment=ASSISTANT_PROFILE=${ASSISTANT_PROFILE}
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
      ;;
    low)
      # Compact is Medium+ only — disable leftover timer if profile was raised then lowered
      $sudo systemctl disable --now assistant-compact.timer >/dev/null 2>&1 || true
      ;;
  esac
  systemctl list-timers 'assistant-*' --no-pager || true
  echo "timers installed for profile=${ASSISTANT_PROFILE}"
}

# Timers (backup/learn/stack-watch; log-archive 30d; compact Medium+; zalo-watch when ENABLE_ZALO=1)
ensure_profile_timers() {
  echo "==> install timers (profile=${ASSISTANT_PROFILE}, ENABLE_ZALO=${ENABLE_ZALO:-0})"
  do_install_timers || true
}

do_channel_status() {
  echo "ASSISTANT_PROFILE=${ASSISTANT_PROFILE}"
  echo "ENABLE_ZALO=${ENABLE_ZALO:-0}"
  echo "ENABLE_TELEGRAM=${ENABLE_TELEGRAM:-0}"
  echo "social-app packs: architect/social-app/{zalo,telegram,http}"
}

do_destroy() {
  # Tear down this compose project: containers + networks. Named volumes /data kept.
  do_backup_first "destroy" || return 1
  local project="${COMPOSE_PROJECT_NAME:-assistant}"
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
  # After: git pull  →  bash run.sh update
  # Rebuilds/recreates stack from current tree; refreshes 9Router→Hermes wiring; prunes disk.
  do_backup_first "update" || return 1
  echo "==> update from current source (ASSISTANT_PROFILE=${ASSISTANT_PROFILE})"
  if [[ -d "${ROOT}/.git" ]]; then
    echo "==> git HEAD: $(git -C "$ROOT" rev-parse --short HEAD 2>/dev/null || echo unknown)"
    echo "    (run git pull yourself before update if you want remote changes)"
  fi

  assistant_profile_summary

  echo "==> pull vendor images (best-effort)"
  compose pull || true

  echo "==> rebuild + recreate"
  compose up -d --build --remove-orphans
  do_stop_disabled_optionals

  if [[ -n "${N9ROUTER_INITIAL_PASSWORD:-}" ]]; then
    echo "==> refresh 9Router Default Key + hermes combo"
    export STACK_ROOT="${STACK_ROOT:-$ROOT}"
    export HERMES_DATA_DIR="${HERMES_DATA_DIR:-/data/assistant}"
    python3 "${SCRIPTS_DIR}/first-setup-9router-hermes.py" \
      || echo "WARN: first-setup-llm failed — stack is up; fix .env / 9Router and re-run: bash run.sh first-setup-llm"
  else
    echo "WARN: N9ROUTER_INITIAL_PASSWORD empty — skip LLM first-setup refresh"
  fi

  # After LLM setup so N9ROUTER_API_KEY is in .env when seeding
  if [[ "$ASSISTANT_PROFILE" == "high" ]]; then
    echo "==> seed API keys into OpenBao"
    do_first_setup_openbao || echo "WARN: OpenBao seed failed — re-run: bash run.sh first-setup-openbao"
  fi

  echo "==> disk cleanup"
  docker builder prune -af >/dev/null 2>&1 || true
  docker image prune -af >/dev/null 2>&1 || true
  docker container prune -f >/dev/null 2>&1 || true
  rm -rf /tmp/assistant /tmp/assistant-low.tgz /tmp/9r-*.json 2>/dev/null || true
  df -h / 2>/dev/null | tail -1 || true

  ensure_profile_timers

  do_post_ready_learn

  if [[ "${ENABLE_ZALO:-0}" == "1" ]]; then
    if [[ "$(id -u)" -eq 0 ]]; then
      echo "NEXT (manual, as deploy user — not root): bash scripts/main/setup-zalo.sh && bash scripts/main/login-zalo.sh"
    else
      echo "==> Zalo install (after profile ready; login is manual)"
      bash "${SCRIPTS_DIR}/setup-zalo.sh" \
        || echo "WARN: setup-zalo failed — re-run: bash scripts/main/setup-zalo.sh"
      echo "NEXT (manual): bash scripts/main/login-zalo.sh"
    fi
  fi

  compose ps
  echo "OK: update complete"
}

do_first_setup_openbao() {
  need_high first-setup-openbao || return 1
  export STACK_ROOT="${STACK_ROOT:-$ROOT}"
  export ASSISTANT_DATA_DIR="${ASSISTANT_DATA_DIR:-/data/assistant}"
  export HERMES_DATA_DIR="${HERMES_DATA_DIR:-$ASSISTANT_DATA_DIR}"
  python3 "${SCRIPTS_DIR}/first-setup-openbao.py"
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

do_archive_before_change() {
  # Snapshot live options + DR backup; verify stamp before any upgrade/downgrade/add.
  local reason="${1:-manual}"
  echo "==> current options (before change)"
  assistant_options_dump
  do_backup_first "$reason"
}

do_switch_profile() {
  local target="" dry=0 noup=0 arg
  for arg in "$@"; do
    case "$arg" in
      --dry-run) dry=1 ;;
      --no-up) noup=1 ;;
      low|medium|high) target="$arg" ;;
      *)
        echo "usage: bash run.sh switch-profile <low|medium|high> [--dry-run] [--no-up]" >&2
        return 2
        ;;
    esac
  done
  [[ -n "$target" ]] || { echo "usage: bash run.sh switch-profile <low|medium|high> [--dry-run] [--no-up]" >&2; return 2; }
  echo "==> switch-profile ${ASSISTANT_PROFILE} → ${target}"
  if [[ "$dry" == "1" ]]; then
    assistant_profile_summary
    echo "DRY_RUN: would archive, set ASSISTANT_PROFILE=${target}, then $([[ "$noup" == "1" ]] && echo 'skip up' || echo 'run.sh up --remove-orphans')"
    return 0
  fi
  do_archive_before_change "switch-profile:${ASSISTANT_PROFILE}->${target}" || return 1
  local stamp
  stamp="$(cat "${BACKUP_DIR:-/data/assistant/backups}/PRE_CHANGE" 2>/dev/null || true)"
  env_upsert ASSISTANT_PROFILE "$target"
  echo "OK: wrote ASSISTANT_PROFILE=${target} to .env (stamp=${stamp})"
  if [[ "$noup" == "1" ]]; then
    echo "NEXT: bash run.sh up     # apply overlays; --remove-orphans drops leftover tier services"
    echo "UNDO: bash run.sh restore ${stamp}"
    return 0
  fi
  echo "==> apply new profile"
  exec bash "${ROOT}/run.sh" up
}

do_add_components() {
  local dry=0 noup=0
  local -a pairs=()
  local arg k v
  for arg in "$@"; do
    case "$arg" in
      --dry-run) dry=1 ;;
      --no-up) noup=1 ;;
      *=*)
        k="${arg%%=*}"
        v="${arg#*=}"
        if ! assistant_option_key_ok "$k"; then
          echo "ERROR: unknown option ${k} (not in profile option list)" >&2
          return 2
        fi
        pairs+=("${k}=${v}")
        ;;
      *)
        echo "usage: bash run.sh add-components KEY=VAL [KEY=VAL…] [--dry-run] [--no-up]" >&2
        return 2
        ;;
    esac
  done
  [[ ${#pairs[@]} -gt 0 ]] || { echo "usage: bash run.sh add-components KEY=VAL [KEY=VAL…] [--dry-run] [--no-up]" >&2; return 2; }
  echo "==> add-components ${pairs[*]}"
  assistant_profile_summary
  for arg in "${pairs[@]}"; do
    k="${arg%%=*}"
    case "$k" in
      ENABLE_OPENBAO|ENABLE_AUTHZ|ENABLE_SIEM|ENABLE_POLICY|ENABLE_SECURITY|ENABLE_NOTIFY)
        if [[ "$ASSISTANT_PROFILE" != "high" ]]; then
          echo "WARN: ${k} needs High overlay — run: bash run.sh switch-profile high" >&2
        fi
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
  if [[ "$noup" == "1" ]]; then
    echo "NEXT: bash run.sh up"
    echo "UNDO: bash run.sh restore ${stamp}"
    return 0
  fi
  exec bash "${ROOT}/run.sh" up
}

do_help() {
  cat <<EOF
assistant — ASSISTANT_PROFILE=${ASSISTANT_PROFILE}
Docs: docs/02-commands.md

Stack (all):
  up | down | destroy | ps | logs [svc] | profile | update

  update   # backup+verify, then after git pull: rebuild stack, refresh LLM wiring, prune disk
  destroy  # backup+verify, then remove project containers + networks (volumes/data kept)
           # then rebuild with: bash run.sh up

Change tier / add components (all — backup+verify first):
  switch-profile <low|medium|high> [--dry-run] [--no-up]
  add-components KEY=VAL […] [--dry-run] [--no-up]
  profile                 # show current options

DR (all):
  backup | restore [stamp] | verify [stamp] | migrate

Knowledge (all):
  auto-learn | learn-status
  post-ready-learn        # after Hermes+9Router: sync hermes/main/skills|docs → ingest

Memory (medium|high):
  compact | optimize-memory
  check-medium            # smoke OCR / Jobs / SearXNG / dispatcher

Timers:
  install-timers          # Low: optional; Medium/High: auto on up|update

First setup:
  install-docker [user]   # if docker missing; default = SSH login user (not a hardcoded name)
  first-setup-llm         # 9Router Default Key → combo hermes (oc/* round-robin)

High:
  first-setup-openbao     # seed API keys → OpenBao UI (:8200); also on up|update
  check-high              # smoke OpenBao / Grafana / AV / authz / …
  backup-sync-clouddrive  # when ENABLE_CLOUDDRIVE=1

Attachable:
  channel-status
  setup-zalo              # after check-*: install bridge+adapter (no QR)
  login-zalo              # MANUAL last step — QR login (cuongdev hermes-zalo-plugin)
  zalo-watch              # self-heal bridge/SSE (also timer when ENABLE_ZALO=1)
  stack-watch             # self-heal down/unhealthy compose services (timer)
EOF
}

case "$cmd" in
  up)
    assistant_profile_summary
    compose up -d --remove-orphans
    do_stop_disabled_optionals
    ensure_profile_timers
    # Wire 9Router Default Key + hermes combo before OpenBao seed so N9ROUTER_API_KEY is present
    if [[ -n "${N9ROUTER_INITIAL_PASSWORD:-}" ]]; then
      echo "==> first-setup-llm (9Router key + hermes combo)"
      export STACK_ROOT="${STACK_ROOT:-$ROOT}"
      export HERMES_DATA_DIR="${HERMES_DATA_DIR:-${ASSISTANT_DATA_DIR:-/data/assistant}}"
      python3 "${SCRIPTS_DIR}/first-setup-9router-hermes.py" \
        || echo "WARN: first-setup-llm failed — re-run: bash run.sh first-setup-llm"
    else
      echo "WARN: N9ROUTER_INITIAL_PASSWORD empty — skip LLM first-setup"
    fi
    if [[ "$ASSISTANT_PROFILE" == "high" ]]; then
      do_first_setup_openbao || echo "WARN: OpenBao seed failed — re-run: bash run.sh first-setup-openbao"
    fi
    do_post_ready_learn
    if [[ "${ENABLE_ZALO:-0}" == "1" ]]; then
      if [[ "$(id -u)" -eq 0 ]]; then
        echo "NEXT (manual, as deploy user — not root): bash scripts/main/setup-zalo.sh"
        echo "THEN: bash scripts/main/login-zalo.sh"
      else
        echo "==> Zalo install (after profile ready; login is manual)"
        bash "${SCRIPTS_DIR}/setup-zalo.sh" \
          || echo "WARN: setup-zalo failed — re-run after check-*: bash scripts/main/setup-zalo.sh"
        echo "NEXT (manual): bash scripts/main/login-zalo.sh"
      fi
    fi
    ;;
  down) compose down ;;
  destroy) do_destroy ;;
  ps) compose ps ;;
  logs) compose logs -f --tail=100 "$@" ;;
  profile) assistant_profile_summary ;;
  switch-profile|change-profile) do_switch_profile "$@" ;;
  add-components|enable-components) do_add_components "$@" ;;
  update) do_update ;;
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
  check-medium|smoke-medium)
    need_med check-medium || exit 1
    bash "${SCRIPTS_DIR}/check-medium.sh"
    ;;
  check-high|smoke-high)
    need_high check-high || exit 1
    bash "${SCRIPTS_DIR}/check-high.sh"
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
    do_post_ready_learn
    ;;
  first-setup-openbao|setup-openbao)
    do_first_setup_openbao
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
