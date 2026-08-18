#!/usr/bin/env bash
# Component backup/restore for assistant (source from ops.sh).
# Each store is a named component: enable with BACKUP_ENABLE_* (and stack ENABLE_*).
# Fail-fast when BACKUP_FAIL_FAST=1 (default). UTF-8 paths (Vietnamese filenames).
set -euo pipefail
export LC_ALL="${LC_ALL:-C.UTF-8}"
export LANG="${LANG:-C.UTF-8}"

: "${BACKUP_DIR:=/data/assistant/backups}"
: "${BACKUP_RETENTION_DAYS:=14}"
: "${BACKUP_FAIL_FAST:=1}"
: "${HERMES_DATA_DIR:=/data/assistant}"
: "${ROOT:=/opt/assistant}"
: "${SUDO:=}"

BACKUP_LIB_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
QDRANT_PY="${BACKUP_LIB_DIR}/backup_qdrant.py"
if ! declare -F assistant_options_dump >/dev/null 2>&1 && [[ -f "${BACKUP_LIB_DIR}/profile.sh" ]]; then
  # shellcheck source=profile.sh
  source "${BACKUP_LIB_DIR}/profile.sh"
fi

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
  local want="$1" name
  # Exact name first (postgres, redis, …); then Compose scale aliases (assistant-hermes-1).
  name="$(docker ps --format '{{.Names}}' 2>/dev/null | awk -v w="$want" '$0==w {print; exit}')"
  if [[ -n "$name" ]]; then
    echo "$name"
    return 0
  fi
  if [[ "$want" == "hermes" ]]; then
    docker ps --format '{{.Names}}' 2>/dev/null | awk '/hermes/ {print; exit}'
  fi
}

assistant_stop_hermes() {
  docker ps -q --filter name=hermes 2>/dev/null | while read -r id; do
    [[ -n "$id" ]] && docker stop "$id" >/dev/null 2>&1 || true
  done
}

assistant_compose_profiles() {
  # Mirror run.sh compose profiles so restore does not leave edge/Zalo services exited.
  local -a profiles=()
  case "${ENABLE_ZALO:-0}" in
    1) profiles+=(--profile zalo) ;;
  esac
  case "${ENABLE_TRAEFIK:-0}" in
    1)
      case "${TRAEFIK_ACME_ENABLED:-0}" in
        1) profiles+=(--profile traefik-acme) ;;
        *) profiles+=(--profile traefik) ;;
      esac
      ;;
  esac
  case "${ENABLE_API_GATEWAY:-0}" in
    1) profiles+=(--profile gateway) ;;
  esac
  case "${ENABLE_OPENVPN:-0}" in
    1) profiles+=(--profile openvpn) ;;
  esac
  case "${ENABLE_ANTIVIRUS:-0}" in
    1) profiles+=(--profile antivirus) ;;
  esac
  case "${ENABLE_NOTIFY:-0}" in
    1) profiles+=(--profile notify) ;;
  esac
  case "${ENABLE_CLOUDDRIVE:-0}" in
    1) profiles+=(--profile clouddrive) ;;
  esac
  case "${ENABLE_OMNIROUTER:-0}" in
    1) profiles+=(--profile omnirouter) ;;
  esac
  assistant_append_monitor_profiles profiles
  printf '%s\n' "${profiles[@]}"
}

assistant_compose() {
  local envf="${HERMES_DATA_DIR}/.env"
  [[ -f "$envf" ]] || envf="${ROOT}/.env"
  local -a files=(--project-directory "${ROOT}" -f "${ROOT}/docker/docker-compose.yml")
  local -a profiles=()
  local profile
  case "${ASSISTANT_PROFILE:-high}" in
    medium|high)
      [[ -f "${ROOT}/docker/docker-compose.medium.yml" ]] && files+=(-f "${ROOT}/docker/docker-compose.medium.yml")
      ;;
  esac
  case "${ASSISTANT_PROFILE:-high}" in
    high)
      [[ -f "${ROOT}/docker/docker-compose.high.yml" ]] && files+=(-f "${ROOT}/docker/docker-compose.high.yml")
      ;;
  esac
  case "${ENABLE_TRAEFIK:-0}${ENABLE_API_GATEWAY:-0}${ENABLE_OPENVPN:-0}" in
    *1*)
      [[ -f "${ROOT}/docker/docker-compose.edge.yml" ]] && files+=(-f "${ROOT}/docker/docker-compose.edge.yml")
      ;;
  esac
  if [[ "${HERMES_REPLICAS:-1}" == "1" && -f "${ROOT}/docker/docker-compose.hermes-hostports.yml" ]]; then
    files+=(-f "${ROOT}/docker/docker-compose.hermes-hostports.yml")
  fi
  while IFS= read -r profile; do
    [[ -n "$profile" ]] && profiles+=("$profile")
  done < <(assistant_compose_profiles)
  docker compose "${files[@]}" "${profiles[@]}" --env-file "$envf" "$@"
}

assistant_stack_up_datastore() {
  # Lightweight bring-up for restore (avoid run.sh first-setup / timers).
  assistant_compose up -d postgres redis qdrant
}

assistant_stack_up() {
  local scale="${HERMES_REPLICAS:-1}"
  assistant_compose up -d --scale "hermes=${scale}"
}

assistant_restart_postgres_clients() {
  # pg_dumpall --clean / pg_terminate_backend leaves pooled clients (memory) 503 until recycle.
  local i
  docker start postgres >/dev/null 2>&1 || true
  for i in $(seq 1 30); do
    docker exec postgres pg_isready -U "${MEMORY_DB_USER:-hermes}" >/dev/null 2>&1 && break
    sleep 1
  done
  docker restart memory ingest embedding authz 2>/dev/null || true
  sleep 2
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
  if declare -F assistant_options_dump >/dev/null 2>&1; then
    assistant_options_dump | $SUDO tee "${dir}/config/profile-options.env" >/dev/null
  fi
  if [[ -n "${BACKUP_CHANGE_REASON:-}" ]]; then
    printf '%s\n' "${BACKUP_CHANGE_REASON}" | $SUDO tee "${dir}/config/change-intent.txt" >/dev/null
  fi
  [[ -f "${ROOT}/docs/config/DEFAULTS.md" ]] && $SUDO cp -a "${ROOT}/docs/config/DEFAULTS.md" "${dir}/config/"
  [[ -d "${ROOT}/generated" ]] && $SUDO tar -C "${ROOT}" --format=posix -czf "${dir}/config/generated.tgz" generated
  [[ -d "${ROOT}/vendor" ]] && $SUDO tar -C "${ROOT}" --format=posix -czf "${dir}/config/vendor.tgz" vendor
  [[ -f "${ROOT}/docker-compose.yml" ]] && $SUDO cp -a "${ROOT}/docker-compose.yml" "${dir}/config/"
  if [[ -d "${ROOT}/docker" ]]; then
    $SUDO mkdir -p "${dir}/config/docker"
    $SUDO cp -a "${ROOT}/docker/"docker-compose*.yml "${dir}/config/docker/" 2>/dev/null || true
  fi
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
  local dir="$1" pg gz="${dir}/postgres/pg_dumpall.sql.gz" i dbuser
  dbuser="${MEMORY_DB_USER:-hermes}"
  pg="$(assistant_container postgres)"
  [[ -n "$pg" ]] || { assistant_backup_fail "postgres not running for restore"; return 1; }
  # Drop app connections so DROP DATABASE / --clean can proceed.
  docker stop memory session ingest embedding jobs jobs-worker 2>/dev/null || true
  assistant_stop_hermes
  for i in $(seq 1 30); do
    docker exec "$pg" pg_isready -U "$dbuser" >/dev/null 2>&1 && break
    sleep 2
  done
  docker exec -e PAGER=cat "$pg" psql -U "$dbuser" -d postgres -v ON_ERROR_STOP=on \
    -c "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE pid <> pg_backend_pid() AND datname IS NOT NULL;" \
    >/dev/null 2>&1 || true
  [[ -f "$gz" ]] || {
    if [[ -f "${dir}/hermes_memory.sql" ]]; then
      $SUDO cat "${dir}/hermes_memory.sql" | docker exec -i -e PAGER=cat "$pg" \
        psql -U "$dbuser" -d "${MEMORY_DB_NAME:-hermes_memory}" -v ON_ERROR_STOP=on
      return 0
    fi
    assistant_backup_fail "missing ${gz}"
    return 1
  }
  # pg_dumpall --clean emits DROP/CREATE/ALTER ROLE for the dump user; skip those.
  $SUDO gzip -dc "$gz" \
    | sed -E \
      -e "/^DROP ROLE( IF EXISTS)? ${dbuser}\\b/Id" \
      -e "/^CREATE ROLE ${dbuser}\\b/Id" \
      -e "/^ALTER ROLE ${dbuser}\\b/Id" \
      -e "/^DROP ROLE( IF EXISTS)? postgres\\b/Id" \
      -e "/^CREATE ROLE postgres\\b/Id" \
      -e "/^ALTER ROLE postgres\\b/Id" \
    | docker exec -i -e PAGER=cat -e LC_ALL=C.UTF-8 "$pg" \
      psql -U "$dbuser" -d postgres -v ON_ERROR_STOP=on
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
  local dir="$1" meta="${dir}/qdrant/manifest.json" base i snap_host snap_ctr col
  base="http://127.0.0.1:${QDRANT_PORT:-6333}"
  [[ -f "$meta" ]] || { assistant_backup_fail "missing qdrant/manifest.json"; return 1; }
  # Qdrant 1.13+: full storage snapshot restore is CLI/startup only.
  # Use per-collection snapshots from the backup manifest.
  docker start qdrant 2>/dev/null || true
  for i in $(seq 1 40); do
    python3 "$QDRANT_PY" list --base "$base" >/dev/null 2>&1 && break
    sleep 2
  done
  docker exec qdrant mkdir -p /qdrant/snapshots
  python3 - "$QDRANT_PY" "$base" "$dir/qdrant" "$meta" <<'PY'
import json, os, subprocess, sys
py, base, qdir, meta_path = sys.argv[1:5]
meta = json.load(open(meta_path, encoding="utf-8"))
snaps = meta.get("snapshots") or []
if not snaps:
    print("qdrant: no collection snapshots in manifest — skip recover (empty or storage-only)")
    raise SystemExit(0)
for s in snaps:
    col = s["collection"]
    host = os.path.join(qdir, f"col_{col}.snapshot")
    if not os.path.isfile(host):
        raise SystemExit(f"missing collection snapshot: {host}")
    ctr = f"/qdrant/snapshots/restore-{col}.snapshot"
    subprocess.check_call(["docker", "cp", host, f"qdrant:{ctr}"])
    loc = f"file://{ctr}"
    subprocess.check_call(
        ["python3", py, "recover-collection", "--base", base, "--collection", col, "--location", loc]
    )
print(f"qdrant: recovered {len(snaps)} collection(s)")
PY
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
  docker stop session jobs jobs-worker ingest 2>/dev/null || true
  assistant_stop_hermes
  docker stop redis
  vol="$(as_volume valkey_data)"
  [[ -n "$vol" ]] || vol="$(as_volume redis_data)"
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
  extra+=(--exclude='./backups')
  extra+=(--exclude='./workspace/docs')
  if [[ "${BACKUP_HERMES_INCLUDE_LAZY:-0}" != "1" ]]; then
    extra+=(--exclude='./lazy-packages')
  fi
  if [[ "${BACKUP_ENABLE_MEDIA:-1}" != "1" ]]; then
    extra+=(--exclude='./media')
  fi
  # Replica scratch dirs are large / ephemeral; shared config/env/skills stay in tree root.
  extra+=(--exclude='./replicas')
  # Zalo owner election is runtime-only (container ids); restoring it leaves SSE dead.
  extra+=(--exclude='./zalo_owner')
  extra+=(--exclude='./zalo_owner.lock')
  $SUDO tar -C "${HERMES_DATA_DIR}" --format=posix "${extra[@]}" \
    -czf "${dir}/hermes/data.tgz" .
  [[ -s "${dir}/hermes/data.tgz" ]] || { assistant_backup_fail "hermes tar empty"; return 1; }
}

assistant_zalo_clear_owner_lock() {
  local base="${HERMES_DATA_DIR:-/data/assistant}"
  $SUDO rm -rf "${base}/zalo_owner" "${base}/zalo_owner.lock" 2>/dev/null || true
}

assistant_zalo_post_restore_heal() {
  # After restore, Hermes container ids change — force a fresh Zalo SSE owner election.
  case "${ENABLE_ZALO:-0}" in
    1) ;;
    *) return 0 ;;
  esac
  log "Zalo post-restore heal (clear owner lock + restart proxy/hermes)"
  assistant_zalo_clear_owner_lock
  if [[ -f "${ROOT}/scripts/main/heal-zalo-sse.sh" ]]; then
    bash "${ROOT}/scripts/main/heal-zalo-sse.sh" || log "WARN: heal-zalo-sse returned non-zero"
  else
    docker restart "${ZALO_PROXY_CONTAINER:-zalo-proxy}" 2>/dev/null || true
    assistant_stop_hermes
    assistant_stack_up || true
  fi
}

assistant_restore_hermes() {
  local dir="$1" tgz="${dir}/hermes/data.tgz"
  [[ -f "$tgz" ]] || { assistant_backup_fail "missing hermes/data.tgz"; return 1; }
  assistant_stop_hermes
  $SUDO mkdir -p "${HERMES_DATA_DIR}"
  $SUDO tar -C "${HERMES_DATA_DIR}" --format=posix -xzf "$tgz"
  $SUDO chown -R "${HERMES_UID:-1000}:${HERMES_GID:-1000}" "${HERMES_DATA_DIR}" 2>/dev/null || true
  # Never keep a restored owner file (even from older stamps that still archived it).
  assistant_zalo_clear_owner_lock
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
  local dir="$1" data="${HERMES_DATA_DIR:-/data/assistant}"
  $SUDO mkdir -p "${dir}/schedules"
  if [[ -f "${ROOT}/scripts/main/hermes-cron-share.sh" ]]; then
    HERMES_DATA_DIR="$data" bash "${ROOT}/scripts/main/hermes-cron-share.sh" || true
  fi
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
  if [[ -f "${data}/cron/jobs.json" ]]; then
    $SUDO cp -a "${data}/cron/jobs.json" "${dir}/schedules/hermes-jobs.json"
  fi
  if [[ -d "${data}/cron" ]]; then
    $SUDO tar -C "${data}/cron" --format=posix -czf "${dir}/schedules/hermes-cron.tgz" \
      --exclude='.jobs.lock' --exclude='.tick.lock' --exclude='.fire-*' . 2>/dev/null || true
  fi
  docker exec "$(assistant_container hermes)" hermes cron list > "${dir}/schedules/hermes-cron.txt" 2>/dev/null \
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
    # Enable only units that exist on this host (profile may omit some timers).
    local u
    for u in assistant-compact.timer assistant-backup.timer assistant-auto-learn.timer \
             assistant-stack-watch.timer assistant-zalo-watch.timer assistant-weekly-summary.timer; do
      if [[ -f "/etc/systemd/system/${u}" ]]; then
        $SUDO systemctl enable --now "$u" 2>/dev/null || true
      fi
    done
  else
    if [[ -f "${ROOT}/run.sh" ]]; then
      (cd "${ROOT}" && bash run.sh install-timers) || log "WARN: install-timers skipped"
    else
      log "WARN: no timers tarball and no run.sh install-timers"
    fi
  fi
  if [[ -f "${dir}/schedules/systemd-user.tgz" ]]; then
    mkdir -p "${HOME}/.config/systemd/user"
    tar -C "${HOME}/.config/systemd/user" -xzf "${dir}/schedules/systemd-user.tgz"
    systemctl --user daemon-reload || true
  fi
  local data="${HERMES_DATA_DIR:-/data/assistant}"
  $SUDO mkdir -p "${data}/cron"
  if [[ -f "${dir}/schedules/hermes-cron.tgz" ]]; then
    $SUDO tar -C "${data}/cron" --format=posix -xzf "${dir}/schedules/hermes-cron.tgz" || true
  fi
  if [[ -f "${dir}/schedules/hermes-jobs.json" ]]; then
    $SUDO cp -a "${dir}/schedules/hermes-jobs.json" "${data}/cron/jobs.json"
  fi
  if [[ -f "${ROOT}/scripts/main/hermes-cron-share.sh" ]]; then
    HERMES_DATA_DIR="$data" bash "${ROOT}/scripts/main/hermes-cron-share.sh" || true
  fi
  $SUDO chown -R "${HERMES_UID:-1000}:${HERMES_GID:-1000}" "${data}/cron" 2>/dev/null || true
  assistant_stop_hermes
  assistant_stack_up || log "WARN: hermes up after schedule restore returned non-zero"
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
  # Stop edge/monitor containers that hold named volumes; stack_up (with profiles) brings them back.
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
  log "bring datastore up (postgres/redis/qdrant) for restore"
  assistant_stack_up_datastore || log "WARN: datastore up returned non-zero — continuing restore"
  for name in postgres qdrant valkey volumes hermes openbao zalo clouddrive openvpn; do
    if ! assistant_backup_wanted "$name"; then
      log "skip restore ${name}"
      continue
    fi
    log "component restore ${name}"
    if ! "assistant_restore_${name}" "$dir"; then
      assistant_backup_fail "restore ${name} failed"
    fi
  done
  log "bring full stack up after restore"
  assistant_zalo_clear_owner_lock
  assistant_stack_up || log "WARN: post-restore stack up returned non-zero"
  assistant_restart_postgres_clients
  if assistant_backup_wanted schedules; then
    assistant_restore_schedules "$dir"
  fi
  assistant_zalo_post_restore_heal
  log "restore done ${stamp}"
}

assistant_verify_backup() {
  local stamp="${1:-}" dir pg redis
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
  pg="$(assistant_container postgres || true)"
  if [[ -n "$pg" ]]; then
    docker exec "$pg" pg_isready -U "${MEMORY_DB_USER:-hermes}" || exit 1
  fi
  redis="$(assistant_container redis || true)"
  if [[ -n "$redis" ]]; then
    docker exec "$redis" valkey-cli PING || docker exec "$redis" redis-cli PING || exit 1
  fi
  if curl -fsS -m 5 "http://127.0.0.1:${QDRANT_PORT:-6333}/collections" >/dev/null 2>&1; then
    python3 "$QDRANT_PY" list --base "http://127.0.0.1:${QDRANT_PORT:-6333}" || exit 1
  fi
  systemctl list-timers 'assistant-*' --no-pager || true
  echo "verify OK stamp=${stamp}"
}
