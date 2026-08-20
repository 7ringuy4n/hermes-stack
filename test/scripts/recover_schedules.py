# -*- coding: utf-8 -*-
"""Recover Hermes jobs.json, restart replicas, rebuild zalo-api (no destroy)."""
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
bash run.sh verify "$stamp"
echo BACKUP_VERIFY_OK
""",
            timeout=900,
        )
        if "BACKUP_VERIFY_OK" not in bak:
            print("FAIL backup", file=sys.stderr)
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
chmod +x /opt/assistant/scripts/main/hermes-cron-share.sh
sed -i 's/\r$//' /opt/assistant/scripts/main/hermes-cron-share.sh /opt/assistant/hermes/main/docker/hermes-replica-entry.sh || true
HERMES_DATA_DIR=/data/assistant bash /opt/assistant/scripts/main/hermes-cron-share.sh
python3 - <<'PY'
import json
from pathlib import Path
p = Path("/data/assistant/cron/jobs.json")
n = 0
enabled = 0
if p.is_file():
    data = json.loads(p.read_text(encoding="utf-8"))
    jobs = data.get("jobs") if isinstance(data, dict) else data
    jobs = jobs if isinstance(jobs, list) else []
    n = len(jobs)
    enabled = sum(1 for j in jobs if isinstance(j, dict) and j.get("enabled"))
print(f"HERMES_JOBS={n} enabled={enabled}")
PY
files="-f /opt/assistant/docker/docker-compose.yml -f /opt/assistant/docker/docker-compose.medium.yml -f /opt/assistant/docker/docker-compose.high.yml"
[[ "${ENABLE_TRAEFIK:-0}" == "1" || "${ENABLE_API_GATEWAY:-0}" == "1" ]] && files="$files -f /opt/assistant/docker/docker-compose.edge.yml"
profiles="--profile zalo --profile notify"
[[ "${ENABLE_ANTIVIRUS:-0}" == "1" ]] && profiles="$profiles --profile antivirus"
[[ "${ENABLE_TRAEFIK:-0}" == "1" ]] && profiles="$profiles --profile traefik"
[[ "${ENABLE_API_GATEWAY:-0}" == "1" ]] && profiles="$profiles --profile gateway"
docker compose --project-directory /opt/assistant $files $profiles build zalo-api
docker compose --project-directory /opt/assistant $files $profiles up -d --no-deps --force-recreate zalo-api
docker ps -q --filter name=hermes | xargs -r docker restart
sleep 15
curl -fsS -m 8 http://127.0.0.1:8100/health >/dev/null && echo zalo_api=ok
python3 - <<'PY'
import json, urllib.request
from pathlib import Path
env = {}
for line in Path("/opt/assistant/.env").read_text(encoding="utf-8", errors="replace").splitlines():
    s = line.strip()
    if not s or s.startswith("#") or "=" not in s:
        continue
    k, v = s.split("=", 1)
    env[k.strip()] = v.strip().strip('"').strip("'")
tok = env.get("ZALO_API_TOKEN") or env.get("ADMIN_API_TOKEN") or ""
admin = ""
p = Path("/data/assistant/zalo_admin_users.txt")
if p.is_file():
    for line in p.read_text(encoding="utf-8", errors="replace").splitlines():
        s = line.strip()
        if s and not s.startswith("#"):
            admin = s.split("|", 1)[0].strip()
            break
payload = json.dumps({
    "sender_id": admin or "x",
    "thread_id": admin or "x",
    "text": "!zalo schedule list",
    "chat_type": "user",
}).encode()
req = urllib.request.Request(
    "http://127.0.0.1:8100/v1/zalo/chat",
    data=payload,
    headers={"Authorization": f"Bearer {tok}", "Content-Type": "application/json"},
    method="POST",
)
with urllib.request.urlopen(req, timeout=20) as resp:
    data = json.loads(resp.read().decode())
reply = str(data.get("reply") or "")
low = reply.lower()
print("schedule_list_ok", ("lá»‹ch" in low or "lich" in low or "trá»‘ng" in low or "wakeup" in low or "giÃ¡" in low))
print("schedule_list_chars", len(reply))
print("schedule_list_handled", bool(data.get("handled")))
PY
echo RECOVER_SCHEDULES_DONE
""",
            timeout=900,
        )
        if "RECOVER_SCHEDULES_DONE" not in out:
            print("FAIL recover", file=sys.stderr)
            return 1
        return 0
    finally:
        c.close()


if __name__ == "__main__":
    raise SystemExit(main())

