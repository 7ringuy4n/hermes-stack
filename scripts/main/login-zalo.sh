#!/usr/bin/env bash
# Manual last step: QR login (or re-login) for the Zalo host bridge.
# Run ONLY after: profile stack healthy + bash scripts/main/setup-zalo.sh
#
# Attribution: bridge by Cường Tuấn Nguyễn (cuongdev) — hermes-zalo-plugin (MIT).
#
# First-setup admin: after loggedIn=true, seed sole admin = bridge ownId
# (account that logged into Zalo proxy). Then from your personal Zalo:
#   !zalo claim          — take admin (when seed is still the bridge account)
#   !zalo admin transfer @tag|uid|reply  — move sole admin to another user
set -euo pipefail

PORT="${ZALO_PLUGIN_PORT:-8787}"
DATA_DIR="${HERMES_DATA_DIR:-${ASSISTANT_DATA_DIR:-/data/assistant}}"
ADMIN_FILE="${ZALO_ADMIN_USERS_FILE:-${DATA_DIR}/zalo_admin_users.txt}"

echo "==> Zalo login (manual — original bridge: https://github.com/cuongdev/hermes-zalo-plugin )"
echo "    Author: Cường Tuấn Nguyễn (cuongdev) — MIT"
echo

if ! command -v hermes-zalo-plugin >/dev/null 2>&1; then
  echo "ERROR: hermes-zalo-plugin not on PATH. Run first: bash scripts/main/setup-zalo.sh" >&2
  exit 1
fi

# Prefer interactive QR via upstream CLI
if hermes-zalo-plugin login 2>/dev/null; then
  :
elif hermes-zalo-plugin setup --relogin 2>/dev/null; then
  :
else
  echo "Open QR in browser (tunnel :${PORT} if remote):"
  echo "  http://127.0.0.1:${PORT}/qr.png"
  echo "Or: ZALO_FORCE_QR=1 hermes-zalo-plugin start   # then scan"
  hermes-zalo-plugin setup 2>/dev/null || true
fi

systemctl --user try-restart com.hermes.zaloplugin.service 2>/dev/null \
  || systemctl --user try-restart assistant-zalo.service 2>/dev/null \
  || true

echo
echo "--- health ---"
HEALTH_JSON="$(curl -sf "http://127.0.0.1:${PORT}/health" || true)"
if [[ -n "$HEALTH_JSON" ]]; then
  echo "$HEALTH_JSON" | head -c 500
  echo
else
  echo "bridge not responding"
fi

# Seed sole admin from logged-in proxy account (first setup only).
python3 - "$ADMIN_FILE" "$HEALTH_JSON" <<'PY' || true
import json, os, sys
path, raw = sys.argv[1], sys.argv[2]
if not raw:
    raise SystemExit(0)
try:
    data = json.loads(raw)
except Exception:
    raise SystemExit(0)
own = str(data.get("ownId") or "").strip()
logged = data.get("loggedIn") is True or bool(own)
if not (logged and own):
    print("SKIP admin seed: bridge not logged in yet (no ownId)")
    raise SystemExit(0)
# Keep existing sole admin if file already set
if os.path.isfile(path):
    for line in open(path, encoding="utf-8"):
        t = line.strip()
        if t and not t.startswith("#"):
            print(f"admin file already set ({path}) — leave unchanged")
            raise SystemExit(0)
os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
with open(path, "w", encoding="utf-8", newline="\n") as f:
    f.write("# managed by login-zalo — sole Zalo admin (exactly one)\n")
    f.write(f"{own}\n")
print(f"OK: first-setup admin seeded from Zalo proxy login → uid={own}")
print(f"     file: {path}")
PY

echo
echo "When loggedIn=true: docker restart hermes admin-api 2>/dev/null || docker restart hermes"
echo "Pairing (if prompted): docker exec -it hermes hermes pairing approve zalo <CODE>"
echo
echo "Admin (sole, 1 user):"
echo "  1) login-zalo seeds admin = bridge ownId (account logged into proxy)"
echo "  2) From your personal Zalo → DM bot: !zalo claim"
echo "  3) Later: !zalo admin transfer @tag   # only one admin"
