# -*- coding: utf-8 -*-
"""Backup+verify, sync, rebuild notify + zalo-api (no Hermes restart, no destroy).

Env: ASSISTANT_SSH_HOST, ASSISTANT_SSH_USER, ASSISTANT_SSH_PASSWORD
Does not write host/account/secrets into reports.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from deploy_stack import connect, sudo_bash, sync_tree  # noqa: E402


def main() -> int:
    c = connect()
    try:
        bak = sudo_bash(
            c,
            r"""
set -euo pipefail
export LC_ALL=C.UTF-8
cd /opt/assistant
out=$(bash run.sh backup)
echo "$out"
stamp=$(echo "$out" | grep -oE '[0-9]{8}[_T][0-9]{6}Z?' | tail -1 || true)
if [[ -z "$stamp" ]]; then
  stamp=$(ls -1 /data/assistant/backups 2>/dev/null | grep -E '^[0-9]{8}[_T][0-9]{6}' | tail -1 || true)
fi
echo "STAMP=${stamp}"
if [[ -z "$stamp" ]]; then
  echo "ERROR: no backup stamp"
  exit 1
fi
bash run.sh verify "$stamp"
echo BACKUP_VERIFY_OK
""",
            timeout=900,
        )
        if "BACKUP_VERIFY_OK" not in bak:
            print("FAIL backup/verify", file=sys.stderr)
            return 1
        sync_tree(c)
        out = sudo_bash(
            c,
            r"""
set -euo pipefail
export LC_ALL=C.UTF-8
cd /opt/assistant
set -a; . ./.env; set +a
export COMPOSE_PROGRESS=plain
files="-f /opt/assistant/docker/docker-compose.yml"
[[ "${ASSISTANT_PROFILE}" == "medium" || "${ASSISTANT_PROFILE}" == "high" ]] && files="$files -f /opt/assistant/docker/docker-compose.medium.yml"
[[ "${ASSISTANT_PROFILE}" == "high" ]] && files="$files -f /opt/assistant/docker/docker-compose.high.yml"
[[ "${ENABLE_TRAEFIK:-0}" == "1" || "${ENABLE_API_GATEWAY:-0}" == "1" ]] && files="$files -f /opt/assistant/docker/docker-compose.edge.yml"
[[ "${HERMES_REPLICAS:-1}" == "1" ]] && files="$files -f /opt/assistant/docker/docker-compose.hermes-hostports.yml"
profiles=""
[[ "${ENABLE_ZALO:-0}" == "1" ]] && profiles="$profiles --profile zalo"
[[ "${ENABLE_ANTIVIRUS:-0}" == "1" ]] && profiles="$profiles --profile antivirus"
[[ "${ENABLE_NOTIFY:-0}" == "1" ]] && profiles="$profiles --profile notify"
[[ "${ENABLE_TRAEFIK:-0}" == "1" ]] && profiles="$profiles --profile traefik"
[[ "${ENABLE_API_GATEWAY:-0}" == "1" ]] && profiles="$profiles --profile gateway"

docker compose --project-directory /opt/assistant $files $profiles build notify zalo-api
docker compose --project-directory /opt/assistant $files $profiles up -d --no-deps --force-recreate notify zalo-api
sleep 8
echo "=== HEALTH ==="
curl -fsS -m 8 http://127.0.0.1:8092/health
echo
curl -fsS -m 8 http://127.0.0.1:8100/health >/dev/null && echo zalo_api=ok
python3 - <<'PY'
import json, os, urllib.request
from pathlib import Path
# dest vs bridge ownId without printing ids
admin = ""
p = Path("/data/assistant/zalo_admin_users.txt")
if p.is_file():
    for line in p.read_text(encoding="utf-8", errors="replace").splitlines():
        s = line.strip()
        if s and not s.startswith("#"):
            admin = s.split("|", 1)[0].strip()
            break
own = ""
try:
    with urllib.request.urlopen("http://127.0.0.1:8787/health", timeout=5) as r:
        own = str(json.loads(r.read().decode()).get("ownId") or "").strip()
except Exception:
    pass
print("admin_file", "yes" if admin else "no")
print("admin_is_bridge_ownid", "yes" if admin and own and admin == own else "no")
req = urllib.request.Request(
    "http://127.0.0.1:8092/v1/alert",
    data=json.dumps({
        "title": "Notify dest probe",
        "body": "Lab check: Zalo admin inbox (no secrets).",
        "severity": "info",
        "channels": ["zalo", "log"],
        "kind": "alert",
    }).encode(),
    headers={"content-type": "application/json"},
    method="POST",
)
with urllib.request.urlopen(req, timeout=30) as resp:
    data = json.loads(resp.read().decode())
res = data.get("results") or {}
print("probe_zalo", res.get("zalo"))
print("probe_reason", res.get("zalo_reason"))
print("probe_source", res.get("zalo_dest_source"))
PY
echo REBUILD_NOTIFY_DONE
""",
            timeout=900,
        )
        if "REBUILD_NOTIFY_DONE" not in out:
            print("FAIL missing REBUILD_NOTIFY_DONE", file=sys.stderr)
            return 1
        return 0
    finally:
        c.close()


if __name__ == "__main__":
    raise SystemExit(main())

