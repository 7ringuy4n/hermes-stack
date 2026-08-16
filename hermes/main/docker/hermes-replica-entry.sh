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

# Zalo allowlists stay on shared paths (compose already sets absolute /opt/data/...)
# Only replica 1 should attach to the Zalo bridge (avoid double SSE / duplicate replies).
case "${RID}" in
  *hermes-1|*hermes_1|*-1)
    : # keep ZALO_* from compose
    ;;
  *)
    export ZALO_PLUGIN_URL=""
    export ZALO_PLUGIN_TOKEN=""
    ;;
esac

echo "==> hermes replica home=${HERMES_HOME} (shared=${SHARED}) hostname=${RID} zalo_url=${ZALO_PLUGIN_URL:-<disabled>}"

# s6-overlay image entrypoint
exec /init "$@"
