#!/usr/bin/env bash
# Component backup/restore for assistant (source from ops.sh).
# Each store is a named component: enable with BACKUP_ENABLE_* (and stack ENABLE_*).
# Fail-fast when BACKUP_FAIL_FAST=1 (default). UTF-8 paths (Vietnamese filenames).
set -euo pipefail
export LC_ALL="${LC_ALL:-C.UTF-8}"
export LANG="${LANG:-C.UTF-8}"

: "${BACKUP_DIR:=/data/backups/assistant}"
: "${BACKUP_RETENTION_DAYS:=14}"
: "${BACKUP_FAIL_FAST:=1}"
: "${HERMES_DATA_DIR:=/data/hermes}"
: "${ROOT:=/opt/assistant}"
: "${SUDO:=}"

BACKUP_LIB_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
QDRANT_PY="${BACKUP_LIB_DIR}/backup_qdrant.py"

assistant_backup_flag() {
  local name="$1"
  case "$name" in
    config) echo "${BACKUP_ENABLE_CONFIG:-1}" ;;
    postgres) echo "${BACKUP_ENABLE_POSTGRES:-${ENABLE_MEMORY:-1}}" ;;
    qdrant) echo "${BACKUP_ENABLE_QDRANT:-${ENABLE_QDRANT:-1}}" ;;
    valkey) echo "${BACKUP_ENABLE_VALKEY:-${ENABLE_REDIS:-1}}" ;;
    hermes) echo "${BACKUP_ENABLE_HERMES:-${ENABLE_HERMES:-1}}" ;;
    openbao) echo "${BACKUP_ENABLE_OPENBAO:-${ENABLE_OPENBAO:-1}}" ;;
    zalo) echo "${BACKUP_ENABLE_ZALO:-${ENABLE_ZALO:-1}}" ;;
    schedules) echo "${BACKUP_ENABLE_SCHEDULES:-1}" ;;
    volumes) echo "${BACKUP_ENABLE_VOLUMES:-1}" ;;
    clouddrive) echo "${BACKUP_ENABLE_CLOUDDRIVE:-${ENABLE_CLOUDDRIVE:-0}}" ;;
    openvpn) echo "${BACKUP_ENABLE_OPENVPN:-${ENABLE_OPENVPN:-1}}" ;;
    *) echo "0" ;;
  esac
}

assistant_backup_wanted() {
  local name="$1"
  if [[ -n "${BACKUP_COMPONENTS:-}" ]]; then
    case ",${BACKUP_COMPONENTS}," in
      *",${name},"*) ;;
      *) return 1 ;;
    esac
  fi
  [[ "$(assistant_backup_flag "$name")" == "1" ]]
}

assistant_backup_fail() {
  local msg="$1"
  echo "ERROR: ${msg}" >&2
  if [[ "${BACKUP_FAIL_FAST}" == "1" ]]; then
    exit 1
  fi
  return 1
}

assistant_container() {
  local want="$1"
  docker ps --format '{{.Names}}' 2>/dev/null | awk -v w="$want" '$0==w {print; exit}'
}

as_volume() {
  local short="$1"
  docker volume ls --format '{{.Name}}' 2>/dev/null \
    | awk -v s="$short" '$0==s || $0 ~ ("_" s "$") { print; exit }'
}

as_tar_volume() {
  local short="$1" dest="$2"
  local vol img
  vol="$(as_volume "$short")"
  [[ -n "$vol" ]] || return 1
  img="postgres:16-alpine"
  docker image inspect "$img" >/dev/null 2>&1 || img="valkey/valkey:8-alpine"
  docker run --rm --entrypoint /bin/tar \
    -e LANG=C.UTF-8 -e LC_ALL=C.UTF-8 \
    -v "${vol}:/src:ro" \
    -v "$(dirname "$dest"):/dst" \
    "$img" -C /src -czf "/dst/$(basename "$dest")" .
}

as_untar_volume() {
  local short="$1" src="$2"
  local vol img
  vol="$(as_volume "$short")"
  [[ -n "$vol" ]] || return 1
  [[ -f "$src" ]] || return 1
  img="postgres:16-alpine"
  docker image inspect "$img" >/dev/null 2>&1 || img="valkey/valkey:8-alpine"
  docker run --rm --entrypoint /bin/tar \
    -e LANG=C.UTF-8 -e LC_ALL=C.UTF-8 \
    -v "${vol}:/dst" \
    -v "$(dirname "$src"):/bak:ro" \
    "$img" -C /dst -xzf "/bak/$(basename "$src")"
}

assistant_manifest_init() {
  local dir="$1"
  python3 - "$dir/manifest.json" <<'PY'
import json, sys, os, datetime
path = sys.argv[1]
os.makedirs(os.path.dirname(path), exist_ok=True)
doc = {
  "schema": "assistant-backup-v1",
  "created_at": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
  "components": {},
}
with open(path, "w", encoding="utf-8") as fh:
    json.dump(doc, fh, ensure_ascii=False, indent=2)
    fh.write("\n")
PY
}

assistant_manifest_add() {
  local dir="$1" name="$2" status="$3" note="${4:-}"
  python3 - "$dir/manifest.json" "$name" "$status" "$note" <<'PY'
import json, sys
path, name, status, note = sys.argv[1:5]
with open(path, encoding="utf-8") as fh:
    doc = json.load(fh)
doc.setdefault("components", {})[name] = {"status": status, "note": note}
with open(path, "w", encoding="utf-8") as fh:
    json.dump(doc, fh, ensure_ascii=False, indent=2)
    fh.write("\n")
PY
}

assistant_backup_config() {
  local dir="$1"
  $SUDO mkdir -p "${dir}/config"
  [[ -f "${ROOT}/.env" ]] && $SUDO cp -a "${ROOT}/.env" "${dir}/config/env.sealed" && $SUDO chmod 600 "${dir}/config/env.sealed"
  [[ -f "${ROOT}/docs/config/DEFAULTS.md" ]] && $SUDO cp -a "${ROOT}/docs/config/DEFAULTS.md" "${dir}/config/"
  [[ -d "${ROOT}/generated" ]] && $SUDO tar -C "${ROOT}" --format=posix -czf "${dir}/config/generated.tgz" generated
  [[ -d "${ROOT}/vendor" ]] && $SUDO tar -C "${ROOT}" --format=posix -czf "${dir}/config/vendor.tgz" vendor
  [[ -f "${ROOT}/docker-compose.yml" ]] && $SUDO cp -a "${ROOT}/docker-compose.yml" "${dir}/config/"
}

assistant_backup_postgres() {
  local dir="$1" pg dump
  pg="$(assistant_container postgres)"
  [[ -n "$pg" ]] || { assistant_backup_fail "postgres container postgres not running"; return 1; }
  dump="${dir}/postgres/pg_dumpall.sql.gz"
  $SUDO mkdir -p "${dir}/postgres"
  docker exec -e PAGER=cat -e LC_ALL=C.UTF-8 "$pg" \
    pg_dumpall -U "${MEMORY_DB_USER:-hermes}" --clean --if-exists \
    | $SUDO tee "${dir}/postgres/pg_dumpall.sql.tmp" >/dev/null
  [[ -s "${dir}/postgres/pg_dumpall.sql.tmp" ]] || { assistant_backup_fail "postgres dump empty"; return 1; }
  $SUDO gzip -f "${dir}/postgres/pg_dumpall.sql.tmp"
  $SUDO mv -f "${dir}/postgres/pg_dumpall.sql.tmp.gz" "$dump"
  [[ -s "$dump" ]] || { assistant_backup_fail "postgres gzip empty"; return 1; }
}

assistant_restore_postgres() {
  local dir="$1" pg gz="${dir}/postgres/pg_dumpall.sql.gz" i
  pg="$(assistant_container postgres)"
  [[ -n "$pg" ]] || { assistant_backup_fail "postgres not running for restore"; return 1; }
  for i in $(seq 1 30); do
    docker exec "$pg" pg_isready -U "${MEMORY_DB_USER:-hermes}" >/dev/null 2>&1 && break
    sleep 2
  done
  [[ -f "$gz" ]] || {
    if [[ -f "${dir}/hermes_memory.sql" ]]; then
      $SUDO cat "${dir}/hermes_memory.sql" | docker exec -i -e PAGER=cat "$pg" \
        psql -U "${MEMORY_DB_USER:-hermes}" -d "${MEMORY_DB_NAME:-hermes_memory}" -v ON_ERROR_STOP=on
      return 0
    fi
    assistant_backup_fail "missing ${gz}"
    return 1
  }
  $SUDO gzip -dc "$gz" | docker exec -i -e PAGER=cat -e LC_ALL=C.UTF-8 "$pg" \
    psql -U "${MEMORY_DB_USER:-hermes}" -d postgres -v ON_ERROR_STOP=on
}

assistant_backup_qdrant() {
  local dir="$1" base
  [[ -f "$QDRANT_PY" ]] || { assistant_backup_fail "missing backup_qdrant.py"; return 1; }
  [[ -n "$(assistant_container qdrant)" ]] || { assistant_backup_fail "qdrant not running"; return 1; }
  $SUDO mkdir -p "${dir}/qdrant"
  base="http://127.0.0.1:${QDRANT_PORT:-6333}"
  python3 "$QDRANT_PY" backup --base "$base" --dir "${dir}/qdrant"
}

assistant_restore_qdrant() {
  local dir="$1" snap="${dir}/qdrant/storage.snapshot" vol i
  [[ -f "$snap" ]] || { assistant_backup_fail "missing qdrant storage.snapshot"; return 1; }
  vol="$(as_volume qdrant_data)"
  [[ -n "$vol" ]] || { assistant_backup_fail "qdrant_data volume missing"; return 1; }
  docker stop qdrant
  docker run --rm \
    -v "${vol}:/data" \
    --entrypoint /bin/sh \
    postgres:16-alpine \
    -c 'find /data -mindepth 1 -delete'
  docker start qdrant
  for i in $(seq 1 40); do
    python3 "$QDRANT_PY" list --base "http://127.0.0.1:${QDRANT_PORT:-6333}" >/dev/null 2>&1 && break
    sleep 2
  done
  docker exec qdrant mkdir -p /qdrant/snapshots
  docker cp "$snap" qdrant:/qdrant/snapshots/assistant-restore.snapshot
  python3 "$QDRANT_PY" recover-storage --base "http://127.0.0.1:${QDRANT_PORT:-6333}" \
    --location "file:///qdrant/snapshots/assistant-restore.snapshot"
}

assistant_backup_valkey() {
  local dir="$1" c
  c="$(assistant_container redis)"
  [[ -n "$c" ]] || { assistant_backup_fail "valkey redis not running"; return 1; }
  $SUDO mkdir -p "${dir}/valkey"
  docker exec "$c" valkey-cli SAVE || docker exec "$c" redis-cli SAVE
  docker cp "${c}:/data/dump.rdb" "${dir}/valkey/dump.rdb"
  [[ -s "${dir}/valkey/dump.rdb" ]] || { assistant_backup_fail "valkey dump.rdb empty"; return 1; }
}

assistant_restore_valkey() {
  local dir="$1" rdb="${dir}/valkey/dump.rdb" vol img
  [[ -f "$rdb" ]] || { assistant_backup_fail "missing valkey dump.rdb"; return 1; }
  docker stop session jobs jobs-worker ingest hermes 2>/dev/null || true
  docker stop redis
  vol="$(as_volume valkey_data)"
  [[ -n "$vol" ]] || { assistant_backup_fail "valkey_data volume missing"; return 1; }
  img="valkey/valkey:8-alpine"
  docker image inspect "$img" >/dev/null 2>&1 || img="postgres:16-alpine"
  docker run --rm \
    -v "${vol}:/data" \
    -v "$(cd "$(dirname "$rdb")" && pwd):/bak:ro" \
    --entrypoint /bin/cp \
    "$img" "/bak/$(basename "$rdb")" /data/dump.rdb
  docker start redis
  sleep 2
  docker exec redis valkey-cli PING | grep -qi PONG \
    || docker exec redis redis-cli PING | grep -qi PONG \
    || assistant_backup_fail "valkey ping after restore"
}

assistant_backup_hermes() {
  local dir="$1" extra=()
  [[ -d "${HERMES_DATA_DIR}" ]] || { assistant_backup_fail "HERMES_DATA_DIR missing"; return 1; }
  $SUDO mkdir -p "${dir}/hermes"
  extra+=(--exclude='./workspace/docs')
  if [[ "${BACKUP_HERMES_INCLUDE_LAZY:-0}" != "1" ]]; then
    extra+=(--exclude='./lazy-packages')
  fi
  if [[ "${BACKUP_ENABLE_MEDIA:-1}" != "1" ]]; then
    extra+=(--exclude='./media')
  fi
  $SUDO tar -C "${HERMES_DATA_DIR}" --format=posix "${extra[@]}" \
    -czf "${dir}/hermes/data.tgz" .
  [[ -s "${dir}/hermes/data.tgz" ]] || { assistant_backup_fail "hermes tar empty"; return 1; }
}

assistant_restore_hermes() {
  local dir="$1" tgz="${dir}/hermes/data.tgz"
  [[ -f "$tgz" ]] || { assistant_backup_fail "missing hermes/data.tgz"; return 1; }
  docker stop hermes 2>/dev/null || true
  $SUDO mkdir -p "${HERMES_DATA_DIR}"
  $SUDO tar -C "${HERMES_DATA_DIR}" --format=posix -xzf "$tgz"
  $SUDO chown -R "${HERMES_UID:-1000}:${HERMES_GID:-1000}" "${HERMES_DATA_DIR}" 2>/dev/null || true
}

assistant_backup_openbao() {
  local dir="$1"
  $SUDO mkdir -p "${dir}/openbao"
  if [[ -n "$(assistant_container openbao)" ]]; then
    docker exec openbao bao kv get -format=json secret/assistant/api-keys \
      > "${dir}/openbao/kv-assistant-api-keys.json" 2>/dev/null \
      || docker exec openbao vault kv get -format=json secret/assistant/api-keys \
      > "${dir}/openbao/kv-assistant-api-keys.json" 2>/dev/null \
      || echo '{"note":"openbao -dev KV export skipped"}' > "${dir}/openbao/kv-assistant-api-keys.json"
  fi
  if [[ -f "${HERMES_DATA_DIR}/.env.openbao" ]]; then
    $SUDO cp -a "${HERMES_DATA_DIR}/.env.openbao" "${dir}/openbao/env.openbao"
    $SUDO chmod 600 "${dir}/openbao/env.openbao"
  fi
}

assistant_restore_openbao() {
  local dir="$1"
  if [[ -f "${dir}/openbao/env.openbao" ]]; then
    $SUDO cp -a "${dir}/openbao/env.openbao" "${HERMES_DATA_DIR}/.env.openbao"
    $SUDO chmod 600 "${HERMES_DATA_DIR}/.env.openbao"
  fi
  # Dev OpenBao is ephemeral; secrets SoT is .env + env.openbao after generate/deploy.
}

assistant_backup_zalo() {
  local dir="$1" unit
  $SUDO mkdir -p "${dir}/zalo"
  unit="${HOME}/.config/systemd/user/com.hermes.zaloplugin.service"
  if [[ -f "$unit" ]]; then
    cp -a "$unit" "${dir}/zalo/"
  fi
  systemctl --user cat com.hermes.zaloplugin.service > "${dir}/zalo/unit.cat" 2>/dev/null || true
  printf '%s\n' "${ZALO_VENDOR_DIR:-${ROOT}/vendor/hermes-zalo-plugin}" > "${dir}/zalo/vendor_dir.txt"
}

assistant_restore_zalo() {
  local dir="$1" unit_src="${dir}/zalo/com.hermes.zaloplugin.service"
  mkdir -p "${HOME}/.config/systemd/user"
  if [[ -f "$unit_src" ]]; then
    cp -a "$unit_src" "${HOME}/.config/systemd/user/"
    systemctl --user daemon-reload
    systemctl --user enable --now com.hermes.zaloplugin.service
  fi
}

assistant_backup_schedules() {
  local dir="$1"
  $SUDO mkdir -p "${dir}/schedules"
  systemctl list-timers 'assistant-*' --all --no-pager > "${dir}/schedules/systemd-timers.txt" 2>/dev/null || true
  crontab -l > "${dir}/schedules/crontab-user.txt" 2>/dev/null || true
  $SUDO crontab -l > "${dir}/schedules/crontab-root.txt" 2>/dev/null || true
  if [[ -d /etc/systemd/system ]]; then
    $SUDO tar -C /etc/systemd/system --format=posix -czf "${dir}/schedules/systemd-assistant.tgz" \
      --wildcards 'assistant-*' 2>/dev/null || true
  fi
  if [[ -d "${HOME}/.config/systemd/user" ]]; then
    tar -C "${HOME}/.config/systemd/user" --format=posix -czf "${dir}/schedules/systemd-user.tgz" \
      --wildcards 'assistant-*' --wildcards 'com.hermes.*' 2>/dev/null || true
  fi
  docker exec hermes hermes cron list > "${dir}/schedules/hermes-cron.txt" 2>/dev/null \
    || echo "(no hermes cron CLI)" > "${dir}/schedules/hermes-cron.txt"
  printf '%s\n' \
    "assistant-compact.timer 00:00 compact" \
    "assistant-backup.timer 00:30 backup" \
    "assistant-weekly-summary.timer Sun 09:00" \
    "assistant-zalo-journal-vacuum.timer daily (user)" \
    > "${dir}/schedules/expected-jobs.txt"
}

assistant_restore_schedules() {
  local dir="$1"
  if [[ -f "${dir}/schedules/systemd-assistant.tgz" ]]; then
    $SUDO tar -C /etc/systemd/system -xzf "${dir}/schedules/systemd-assistant.tgz"
    $SUDO systemctl daemon-reload
    $SUDO systemctl enable --now assistant-compact.timer assistant-backup.timer assistant-weekly-summary.timer
  else
    bash "${BACKUP_LIB_DIR}/../ops.sh" install-timers
  fi
  if [[ -f "${dir}/schedules/systemd-user.tgz" ]]; then
    mkdir -p "${HOME}/.config/systemd/user"
    tar -C "${HOME}/.config/systemd/user" -xzf "${dir}/schedules/systemd-user.tgz"
    systemctl --user daemon-reload || true
  fi
}

assistant_backup_volumes() {
  local dir="$1" v
  $SUDO mkdir -p "${dir}/volumes"
  for v in grafana_data loki_data prometheus_data alloy_data traefik_letsencrypt nine_router_data; do
    if [[ -n "$(as_volume "$v")" ]]; then
      as_tar_volume "$v" "${dir}/volumes/${v}.tgz" || assistant_backup_fail "volume tar ${v}"
    fi
  done
  if [[ "${BACKUP_ENABLE_CLAMAV:-0}" == "1" ]] && [[ -n "$(as_volume clamav_data)" ]]; then
    as_tar_volume clamav_data "${dir}/volumes/clamav_data.tgz" || true
  fi
}

assistant_restore_volumes() {
  local dir="$1" v
  docker stop grafana loki prometheus alloy traefik 9router 2>/dev/null || true
  for v in grafana_data loki_data prometheus_data alloy_data traefik_letsencrypt nine_router_data; do
    if [[ -f "${dir}/volumes/${v}.tgz" ]]; then
      as_untar_volume "$v" "${dir}/volumes/${v}.tgz" || assistant_backup_fail "volume restore ${v}"
    fi
  done
}

assistant_backup_clouddrive() {
  local dir="$1"
  [[ -d "${CLOUDDRIVE_MIRROR_DIR:-/data/clouddrive}" ]] || return 0
  $SUDO mkdir -p "${dir}/clouddrive"
  $SUDO tar -C "${CLOUDDRIVE_MIRROR_DIR:-/data/clouddrive}" --format=posix -czf "${dir}/clouddrive/mirror.tgz" .
}

assistant_restore_clouddrive() {
  local dir="$1"
  [[ -f "${dir}/clouddrive/mirror.tgz" ]] || return 0
  $SUDO mkdir -p "${CLOUDDRIVE_MIRROR_DIR:-/data/clouddrive}"
  $SUDO tar -C "${CLOUDDRIVE_MIRROR_DIR:-/data/clouddrive}" -xzf "${dir}/clouddrive/mirror.tgz"
}

assistant_backup_openvpn() {
  local dir="$1" ov="${OVPN_DATA_DIR:-/data/openvpn}"
  [[ -d "$ov" ]] || { echo "openvpn dir missing, skip"; return 0; }
  $SUDO mkdir -p "${dir}/openvpn"
  $SUDO tar -C "$ov" --format=posix -czf "${dir}/openvpn/data.tgz" .
}

assistant_restore_openvpn() {
  local dir="$1" ov="${OVPN_DATA_DIR:-/data/openvpn}"
  [[ -f "${dir}/openvpn/data.tgz" ]] || return 0
  $SUDO mkdir -p "$ov"
  $SUDO tar -C "$ov" -xzf "${dir}/openvpn/data.tgz"
}

# Order: dump stores while running, then host files.
ASSISTANT_BACKUP_ORDER=(config postgres qdrant valkey hermes openbao zalo schedules volumes clouddrive openvpn)
# Restore stores before generate/deploy; schedules last.
ASSISTANT_RESTORE_ORDER=(config postgres qdrant valkey volumes hermes openbao zalo clouddrive openvpn schedules)

assistant_backup_all() {
  local stamp dir name
  stamp="$(date +%Y%m%d_%H%M%S)"
  dir="${BACKUP_DIR}/${stamp}"
  $SUDO mkdir -p "$dir"
  $SUDO chown "$(id -u):$(id -g)" "$dir" 2>/dev/null || true
  log "backup → ${dir}"
  assistant_manifest_init "$dir"
  for name in "${ASSISTANT_BACKUP_ORDER[@]}"; do
    if ! assistant_backup_wanted "$name"; then
      assistant_manifest_add "$dir" "$name" "skipped" "flag off"
      continue
    fi
    log "component backup ${name}"
    if "assistant_backup_${name}" "$dir"; then
      assistant_manifest_add "$dir" "$name" "ok" ""
    else
      assistant_manifest_add "$dir" "$name" "failed" "see logs"
      assistant_backup_fail "component ${name} failed"
    fi
  done
  echo "${stamp}" | $SUDO tee "${BACKUP_DIR}/LATEST" >/dev/null
  find "${BACKUP_DIR}" -mindepth 1 -maxdepth 1 -type d -mtime "+${BACKUP_RETENTION_DAYS}" \
    -exec $SUDO rm -rf {} + 2>/dev/null || true
  log "backup OK ${dir}"
  echo "$stamp"
}

assistant_restore_all() {
  local stamp="${1:-}" dir name
  [[ -n "$stamp" ]] || stamp="$($SUDO cat "${BACKUP_DIR}/LATEST" 2>/dev/null || true)"
  [[ -n "$stamp" ]] || { echo "usage: ops.sh restore <stamp>"; exit 1; }
  dir="${BACKUP_DIR}/${stamp}"
  [[ -d "$dir" ]] || { echo "missing ${dir}"; exit 1; }
  log "restore from ${dir}"
  if [[ -f "${dir}/config/env.sealed" ]]; then
    $SUDO cp -a "${dir}/config/env.sealed" "${ROOT}/.env"
    $SUDO chmod 600 "${ROOT}/.env"
  elif [[ -f "${dir}/env.sealed" ]]; then
    $SUDO cp -a "${dir}/env.sealed" "${ROOT}/.env"
  fi
  if assistant_backup_wanted config; then
    [[ -f "${dir}/config/generated.tgz" ]] && $SUDO tar -C "${ROOT}" -xzf "${dir}/config/generated.tgz"
    [[ -f "${dir}/config/vendor.tgz" ]] && $SUDO tar -C "${ROOT}" -xzf "${dir}/config/vendor.tgz"
  fi
  log "bring stack up (empty volumes) so vendor restore APIs work"
  bash "${BACKUP_LIB_DIR}/../generate.sh"
  bash "${BACKUP_LIB_DIR}/../deploy.sh"
  for name in postgres qdrant valkey volumes hermes openbao zalo clouddrive openvpn; do
    if ! assistant_backup_wanted "$name"; then
      log "skip restore ${name}"
      continue
    fi
    log "component restore ${name}"
    "assistant_restore_${name}" "$dir"
  done
  bash "${BACKUP_LIB_DIR}/../deploy.sh"
  if assistant_backup_wanted schedules; then
    assistant_restore_schedules "$dir"
  fi
  log "restore done ${stamp}"
}

assistant_verify_backup() {
  local stamp="${1:-}" dir
  [[ -n "$stamp" ]] || stamp="$($SUDO cat "${BACKUP_DIR}/LATEST" 2>/dev/null || true)"
  dir="${BACKUP_DIR}/${stamp}"
  [[ -f "${dir}/manifest.json" ]] || { echo "missing manifest ${dir}"; exit 1; }
  python3 - "$dir/manifest.json" <<'PY'
import json, sys
doc = json.load(open(sys.argv[1], encoding="utf-8"))
bad = [k for k, v in doc.get("components", {}).items() if v.get("status") == "failed"]
print(json.dumps(doc, ensure_ascii=False, indent=2))
if bad:
    raise SystemExit("failed components: " + ",".join(bad))
PY
  echo "==> live checks"
  docker exec postgres pg_isready -U "${MEMORY_DB_USER:-hermes}" || true
  docker exec redis valkey-cli PING || true
  python3 "$QDRANT_PY" list --base "http://127.0.0.1:${QDRANT_PORT:-6333}" || true
  systemctl list-timers 'assistant-*' --no-pager || true
}
