#!/bin/sh
# Per-replica HERMES_HOME so docker compose --scale hermes=N does not fight gateway.lock.
# Shared volume remains /opt/data; each replica uses /opt/data/replicas/<hostname>/.
# Singleton messaging (Zalo): exactly one replica keeps ZALO_PLUGIN_URL when scaled.
set -eu

SHARED="${HERMES_SHARED_DATA:-/opt/data}"
RID="$(hostname)"
export HERMES_HOME="${SHARED}/replicas/${RID}"
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

# Non-owner replicas must not load gateway.platforms.zalo / zalo-platform from the
# shared config.yaml — clearing ZALO_PLUGIN_URL alone still ERROR-spams adapter
# creation and can confuse stack-watch health.
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

disable_local_zalo_gateway() {
  cfg="${HERMES_HOME}/config.yaml"
  src="${SHARED}/config.yaml"
  [ -f "$src" ] || return 0
  if [ -L "$cfg" ] || [ ! -e "$cfg" ]; then
    rm -f "$cfg" 2>/dev/null || true
    cp -a "$src" "$cfg" 2>/dev/null || return 0
  fi
  uid="${HERMES_UID:-1000}"
  gid="${HERMES_GID:-1000}"
  chown "${uid}:${gid}" "$cfg" 2>/dev/null || true
  chmod u+rw "$cfg" 2>/dev/null || true
  if command -v python3 >/dev/null 2>&1; then
    python3 - "$cfg" <<'PY'
import sys
from pathlib import Path

path = Path(sys.argv[1])
text = path.read_text(encoding="utf-8", errors="replace")
lines = text.splitlines()
out = []
i = 0
in_plugins_enabled = False
plugins_indent = -1
changed = False
while i < len(lines):
    line = lines[i]
    stripped = line.strip()
    # Only gateway.platforms.zalo.enabled (indent under platforms)
    if stripped == "zalo:" and i + 1 < len(lines):
        nxt = lines[i + 1]
        if nxt.strip().startswith("enabled:"):
            # Require parent chain: look back for platforms: then gateway:
            indent_z = len(line) - len(line.lstrip(" "))
            parent_ok = False
            for j in range(i - 1, -1, -1):
                s = lines[j].strip()
                if not s or s.startswith("#"):
                    continue
                ind = len(lines[j]) - len(lines[j].lstrip(" "))
                if ind < indent_z and s == "platforms:":
                    parent_ok = True
                    break
                if ind < indent_z:
                    break
            if parent_ok:
                indent = nxt[: len(nxt) - len(nxt.lstrip(" "))]
                out.append(line)
                out.append(f"{indent}enabled: false")
                changed = True
                i += 2
                continue
    if stripped == "enabled:" and i > 0 and lines[i - 1].strip() == "plugins:":
        in_plugins_enabled = True
        plugins_indent = len(line) - len(line.lstrip(" "))
        out.append(line)
        i += 1
        continue
    if in_plugins_enabled:
        cur_indent = len(line) - len(line.lstrip(" ")) if line.strip() else plugins_indent + 2
        if stripped and not stripped.startswith("-") and cur_indent <= plugins_indent:
            in_plugins_enabled = False
        elif stripped in {"- zalo-platform", "- 'zalo-platform'", '- "zalo-platform"'}:
            changed = True
            i += 1
            continue
    out.append(line)
    i += 1
if changed:
    path.write_text("\n".join(out) + ("\n" if text.endswith("\n") else ""), encoding="utf-8")
    print(f"==> local config: disabled gateway zalo + removed zalo-platform plugin ({path})")
else:
    print(f"==> local config: zalo already disabled or absent ({path})")
PY
  else
    # Best-effort without Python (keep gateway usable; may still warn).
    sed -i '/^[[:space:]]*zalo:$/,/^[[:space:]]*[^[:space:]#]/{s/^\([[:space:]]*enabled:\).*/\1 false/;}' "$cfg" 2>/dev/null || true
    sed -i '/^[[:space:]]*- zalo-platform$/d' "$cfg" 2>/dev/null || true
    echo "==> local config: sed-disabled zalo platform (${cfg})"
  fi
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
# Drop Hermes category clones of office skills. They re-registered as name:pdf|docx|xlsx
# alongside SoT copies → skill_view collisions → reportlab/pip tool loops → Omni spam
# and fake "file sent" replies with nothing in media/out. Chat create uses file-gen.
if [ -d "$_dst_skills" ]; then
  for _cat in productivity documents; do
    for _n in pdf docx xlsx; do
      rm -rf "${_dst_skills}/${_cat}/${_n}" 2>/dev/null || true
    done
  done
  # Force SoT office skills (renamed frontmatter) over any stale replica copy.
  for _n in pdf docx xlsx; do
    if [ -d "${_src_skills}/${_n}" ]; then
      mkdir -p "${_dst_skills}/${_n}"
      cp -a "${_src_skills}/${_n}/." "${_dst_skills}/${_n}/" 2>/dev/null || true
    fi
    if [ -d "${_src_skills}/official/${_n}" ]; then
      mkdir -p "${_dst_skills}/official/${_n}"
      cp -a "${_src_skills}/official/${_n}/." "${_dst_skills}/official/${_n}/" 2>/dev/null || true
    fi
  done
  # Last resort: rewrite any leftover reserved frontmatter names under skills/.
  find "${_dst_skills}" -type f -name SKILL.md 2>/dev/null | while read -r _sk; do
    sed -i \
      -e 's/^name: pdf$/name: pdf-tools-local/' \
      -e 's/^name: docx$/name: docx-tools-local/' \
      -e 's/^name: xlsx$/name: xlsx-tools-local/' \
      "$_sk" 2>/dev/null || true
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
  disable_local_zalo_gateway
else
  use_shared_cron
  ensure_shared_config_link
fi

echo "==> hermes replica home=${HERMES_HOME} (shared=${SHARED}) host=${RID} cname=${CNAME} replicas=${REPLICAS} zalo_url=${ZALO_PLUGIN_URL:-<disabled>}"

# Image SoT: entrypoint-dispatch → /init → main-wrapper.sh <args>
# Must pass "gateway run" into main-wrapper (raw `/init gateway run` exits 127).
# Empty args → interactive CLI → immediate exit when stdin is not a TTY.
if [ "$#" -eq 0 ]; then
  set -- gateway run
fi
exec /opt/hermes/docker/entrypoint-dispatch.sh "$@"
