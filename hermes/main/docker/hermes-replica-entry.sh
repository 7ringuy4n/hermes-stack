#!/bin/sh
# Per-replica HERMES_HOME so docker compose --scale hermes=N does not fight gateway.lock.
# Shared volume remains /opt/data; each replica uses /opt/data/replicas/<hostname>/.
# Singleton messaging (Zalo): only *-hermes-1 keeps ZALO_PLUGIN_URL; others clear it.
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

link_shared config.yaml
link_shared .env
link_shared skills
link_shared messages
link_shared plugins
link_shared lazy-packages

# Compose scale uses container id as hostname; resolve service name from /etc/hosts.
resolve_cname() {
  ip="$(hostname -i 2>/dev/null | awk '{print $1}')"
  if [ -n "$ip" ]; then
    getent hosts "$ip" 2>/dev/null | awk '{print $2}' | head -n1
  fi
}
CNAME="$(resolve_cname || true)"
CNAME="${CNAME:-$RID}"

# Only replica 1 should attach to the Zalo bridge (avoid double SSE / duplicate replies).
case "${CNAME}" in
  *hermes-1|*hermes_1|*-1)
    : # keep ZALO_* from compose
    ;;
  *)
    case "${RID}" in
      *hermes-1|*hermes_1|*-1)
        :
        ;;
      *)
        export ZALO_PLUGIN_URL=""
        export ZALO_PLUGIN_TOKEN=""
        ;;
    esac
    ;;
esac

echo "==> hermes replica home=${HERMES_HOME} (shared=${SHARED}) host=${RID} cname=${CNAME} zalo_url=${ZALO_PLUGIN_URL:-<disabled>}"

# Image SoT: entrypoint-dispatch → /init → main-wrapper.sh <args>
# Must pass "gateway run" into main-wrapper (raw `/init gateway run` exits 127).
# Empty args → interactive CLI → immediate exit when stdin is not a TTY.
if [ "$#" -eq 0 ]; then
  set -- gateway run
fi
exec /opt/hermes/docker/entrypoint-dispatch.sh "$@"
