#!/bin/sh
# Per-replica HERMES_HOME so docker compose --scale hermes=N does not fight gateway.lock.
# Shared volume remains /opt/data; each replica uses /opt/data/replicas/<hostname>/.
# Singleton messaging (Zalo): exactly one replica keeps ZALO_PLUGIN_URL when scaled.
set -eu

SHARED="${HERMES_SHARED_DATA:-/opt/data}"
RID="$(hostname)"
export HERMES_HOME="${SHARED}/replicas/${RID}"
mkdir -p "${HERMES_HOME}"

# Link shared SoT into replica home (config/env/skills/messages/plugins)
link_shared() {
  name="$1"
  src="${SHARED}/${name}"
  dst="${HERMES_HOME}/${name}"
  if [ -e "$src" ] && [ ! -e "$dst" ]; then
    ln -sfn "$src" "$dst"
  fi
}

link_shared_cron() {
  # One shared jobs.json survives destroy (replica dirs are named by container id).
  # Only the Zalo-owner replica runs the ticker against the shared dir.
  shared_cron="${SHARED}/cron"
  mkdir -p "$shared_cron"
  local_cron="${HERMES_HOME}/cron"
  if [ -f "${local_cron}/jobs.json" ] && [ ! -L "$local_cron" ]; then
    if [ ! -s "${shared_cron}/jobs.json" ]; then
      cp -a "${local_cron}/jobs.json" "${shared_cron}/jobs.json" 2>/dev/null || true
    fi
  fi
}

use_shared_cron() {
  shared_cron="${SHARED}/cron"
  mkdir -p "$shared_cron"
  local_cron="${HERMES_HOME}/cron"
  if [ -e "$local_cron" ] && [ ! -L "$local_cron" ]; then
    mv "$local_cron" "${HERMES_HOME}/cron.replica-local" 2>/dev/null || rm -rf "$local_cron"
  fi
  ln -sfn "$shared_cron" "$local_cron"
  uid="${HERMES_UID:-1000}"
  gid="${HERMES_GID:-1000}"
  chown "${uid}:${gid}" "$shared_cron" 2>/dev/null || true
  chmod 775 "$shared_cron" 2>/dev/null || true
  if [ -f "${shared_cron}/jobs.json" ]; then
    chown "${uid}:${gid}" "${shared_cron}/jobs.json" 2>/dev/null || true
    chmod 664 "${shared_cron}/jobs.json" 2>/dev/null || true
  fi
}

use_local_empty_cron() {
  local_cron="${HERMES_HOME}/cron"
  if [ -L "$local_cron" ]; then
    rm -f "$local_cron"
  fi
  mkdir -p "$local_cron"
  printf '%s\n' '{"jobs":[],"updated_at":null}' > "${local_cron}/jobs.json"
  chmod 664 "${local_cron}/jobs.json" 2>/dev/null || true
}

link_shared config.yaml
link_shared .env
link_shared SOUL.md
# Skills source is :ro bind-mount; replica needs a writable copy so Hermes
# can populate per-category subdirs at startup.
_src_skills="${SHARED}/skills"
_dst_skills="${HERMES_HOME}/skills"
if [ -L "$_dst_skills" ]; then
  rm -f "$_dst_skills"
fi
if [ -d "$_src_skills" ] && [ ! -d "$_dst_skills" ]; then
  cp -a "$_src_skills" "$_dst_skills" 2>/dev/null || true
elif [ -d "$_src_skills" ] && [ -d "$_dst_skills" ]; then
  # Merge new skills from source without overwriting existing
  cp -a -n "$_src_skills"/. "$_dst_skills"/ 2>/dev/null || true
fi
link_shared messages
link_shared plugins
link_shared lazy-packages
link_shared zalo_admin_users.txt
link_shared zalo_allowed_threads.txt
link_shared zalo_denied_threads.txt
link_shared zalo_allowed_users.txt
link_shared zalo_users_mode.txt
link_shared_cron

# Compose scale uses container id as hostname; resolve service name from /etc/hosts.
resolve_cname() {
  ip="$(hostname -i 2>/dev/null | awk '{print $1}')"
  if [ -n "$ip" ]; then
    getent hosts "$ip" 2>/dev/null | awk '{print $2}' | head -n1
  fi
}
CNAME="$(resolve_cname || true)"
CNAME="${CNAME:-$RID}"

# Only one replica attaches to Zalo (avoid double SSE).
# Do NOT treat bare service DNS "hermes" as owner — every scaled replica shares that alias.
REPLICAS="${HERMES_REPLICAS:-1}"
keep_zalo=0
LOCKDIR="${SHARED}/zalo_owner.lock"
OWNER="${SHARED}/zalo_owner"

is_named_primary() {
  case "$1" in
    *hermes-1|*hermes_1) return 0 ;;
  esac
  return 1
}

claim_zalo_lock() {
  if mkdir "${LOCKDIR}" 2>/dev/null; then
    printf '%s\n' "${RID}" > "${OWNER}"
    return 0
  fi
  if [ -f "${OWNER}" ] && [ "$(cat "${OWNER}" 2>/dev/null)" = "${RID}" ]; then
    return 0
  fi
  # Stale reclaim: previous owner container id is gone from Docker DNS.
  if [ -f "${OWNER}" ]; then
    old="$(cat "${OWNER}" 2>/dev/null || true)"
    if [ -n "${old}" ] && [ "${old}" != "${RID}" ] && ! getent hosts "${old}" >/dev/null 2>&1; then
      rm -rf "${LOCKDIR}" "${OWNER}" 2>/dev/null || true
      if mkdir "${LOCKDIR}" 2>/dev/null; then
        printf '%s\n' "${RID}" > "${OWNER}"
        return 0
      fi
    fi
  fi
  return 1
}

# Drop stale owner before election (dead container id leaves orphan lock).
if [ -f "${OWNER}" ]; then
  old="$(cat "${OWNER}" 2>/dev/null || true)"
  if [ -n "${old}" ] && [ "${old}" != "${RID}" ] && ! getent hosts "${old}" >/dev/null 2>&1; then
    rm -rf "${LOCKDIR}" "${OWNER}" 2>/dev/null || true
  fi
fi

case "${REPLICAS}" in
  ""|1)
    keep_zalo=1
    ;;
  *)
    if is_named_primary "${CNAME}" || is_named_primary "${RID}"; then
      keep_zalo=1
      # Still record ownership so other replicas see a live owner id.
      mkdir "${LOCKDIR}" 2>/dev/null || true
      printf '%s\n' "${RID}" > "${OWNER}" 2>/dev/null || true
    elif claim_zalo_lock; then
      keep_zalo=1
    fi
    ;;
esac

if [ "$keep_zalo" != "1" ]; then
  export ZALO_PLUGIN_URL=""
  export ZALO_PLUGIN_TOKEN=""
  use_local_empty_cron
else
  use_shared_cron
fi

echo "==> hermes replica home=${HERMES_HOME} (shared=${SHARED}) host=${RID} cname=${CNAME} replicas=${REPLICAS} zalo_url=${ZALO_PLUGIN_URL:-<disabled>}"

# Image SoT: entrypoint-dispatch → /init → main-wrapper.sh <args>
# Must pass "gateway run" into main-wrapper (raw `/init gateway run` exits 127).
# Empty args → interactive CLI → immediate exit when stdin is not a TTY.
if [ "$#" -eq 0 ]; then
  set -- gateway run
fi
exec /opt/hermes/docker/entrypoint-dispatch.sh "$@"
