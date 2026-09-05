#!/bin/sh
# Per-replica HERMES_HOME so docker compose --scale hermes=N does not fight gateway.lock.
# Shared volume remains /opt/data; each replica uses /opt/data/replicas/<hostname>/.
# Zalo HA: every replica loads the adapter; a renewable Valkey lease elects the
# single bridge/SSE owner. Traefik fronts the bridge path.
set -eu

SHARED="${HERMES_SHARED_DATA:-/opt/data}"
RID="$(hostname)"
export HERMES_HOME="${SHARED}/replicas/${RID}"

# The upstream s6 bootstrap remaps the hermes UID with usermod. Its image-level
# passwd home is /opt/data, which also contains read-only bind mounts in this
# stack; usermod recursively touching that shared root can fail on first boot
# and leave the container to recover only after a restart. Point the passwd
# entry at this writable replica home before the upstream remap runs.
if [ "$(id -u)" = "0" ] && command -v usermod >/dev/null 2>&1; then
  passwd_home="$(getent passwd hermes 2>/dev/null | cut -d: -f6 || true)"
  if [ -n "$passwd_home" ] && [ "$passwd_home" != "$HERMES_HOME" ]; then
    usermod -d "$HERMES_HOME" hermes
  fi
fi
mkdir -p "${HERMES_HOME}"

# Shared media dirs must stay writable by Hermes UID across restarts/replicas.
# Root-owned or missing inbound/out causes Permission denied on OCR / file-gen / attach.
ensure_shared_media() {
  uid="${HERMES_UID:-1000}"
  gid="${HERMES_GID:-1000}"
  mkdir -p "${SHARED}/media/inbound" "${SHARED}/media/out"
  chown -R "${uid}:${gid}" "${SHARED}/media" 2>/dev/null || true
  chmod -R ug+rwX "${SHARED}/media" 2>/dev/null || true
  chmod g+s "${SHARED}/media" "${SHARED}/media/inbound" "${SHARED}/media/out" 2>/dev/null || true
  # Shared SoT files Hermes may rewrite (home channel / auto-sethome).
  for f in .env config.yaml; do
    if [ -f "${SHARED}/${f}" ]; then
      chown "${uid}:${gid}" "${SHARED}/${f}" 2>/dev/null || true
      chmod u+rw "${SHARED}/${f}" 2>/dev/null || true
    fi
  done
  chown "${uid}:${gid}" "${SHARED}" 2>/dev/null || true
  chmod u+rwx "${SHARED}" 2>/dev/null || true
}
ensure_shared_media

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

ensure_shared_config_link() {
  cfg="${HERMES_HOME}/config.yaml"
  src="${SHARED}/config.yaml"
  [ -f "$src" ] || return 0
  if [ -L "$cfg" ]; then
    return 0
  fi
  rm -f "$cfg" 2>/dev/null || true
  ln -sfn "$src" "$cfg"
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
  # Overlay repo SoT (update existing files). Keep replica-only skills (no delete).
  # cp -n would leave stale image-gen / media-out after a rolling deploy.
  cp -a "$_src_skills"/. "$_dst_skills"/ 2>/dev/null || true
fi
# Advanced local Office toolkits are repository references, not chat runtime
# skills. If copied into a replica, Hermes also creates categorized clones and
# registers each folder basename, producing ambiguous pdf/docx/xlsx lookups.
# Chat creation is exclusively file-gen -> Dispatcher, so exclude every local
# toolkit copy from the runtime skill tree before Hermes starts.
if [ -d "$_dst_skills" ]; then
  for _cat in productivity documents; do
    for _n in pdf docx xlsx; do
      rm -rf "${_dst_skills}/${_cat}/${_n}" 2>/dev/null || true
    done
  done
  for _n in pdf docx xlsx; do
    rm -rf "${_dst_skills}/${_n}" "${_dst_skills}/official/${_n}" 2>/dev/null || true
  done
fi
link_shared messages
# Plugins: overlay SoT so new modules (classify_client, gateway_noise) land on
# existing replica dirs. A leftover directory is not replaced by link_shared.
_src_plugins="${SHARED}/plugins"
_dst_plugins="${HERMES_HOME}/plugins"
if [ -L "$_dst_plugins" ]; then
  :
elif [ -d "$_src_plugins" ]; then
  mkdir -p "$_dst_plugins"
  cp -a "$_src_plugins"/. "$_dst_plugins"/ 2>/dev/null || true
fi
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

# Built-in Hermes cron remains singleton; Zalo ownership is independent and is
# elected by the adapter's Valkey lease.
REPLICAS="${HERMES_REPLICAS:-1}"

is_named_primary() {
  case "$1" in
    *hermes-1|*hermes_1) return 0 ;;
  esac
  return 1
}

case "${REPLICAS}" in
  ""|1)
    use_shared_cron
    ;;
  *)
    if is_named_primary "${CNAME}" || is_named_primary "${RID}"; then
      use_shared_cron
    else
      use_local_empty_cron
    fi
    ;;
esac
ensure_shared_config_link

echo "==> hermes replica home=${HERMES_HOME} (shared=${SHARED}) host=${RID} cname=${CNAME} replicas=${REPLICAS} zalo_url=${ZALO_PLUGIN_URL:-<disabled>}"

# Image SoT: entrypoint-dispatch → /init → main-wrapper.sh <args>
# Must pass "gateway run" into main-wrapper (raw `/init gateway run` exits 127).
# Empty args → interactive CLI → immediate exit when stdin is not a TTY.
if [ "$#" -eq 0 ]; then
  set -- gateway run
fi
exec /opt/hermes/docker/entrypoint-dispatch.sh "$@"
