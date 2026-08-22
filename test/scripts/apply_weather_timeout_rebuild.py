# -*- coding: utf-8 -*-
"""Pull develop on VPS, rebuild router-worker (searxng-compat), raise timeouts, recreate hermes."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from deploy_stack import connect, sudo_bash

REMOTE = r"""
set -euo pipefail
cd /opt/assistant
git fetch origin
git checkout develop
git reset --hard origin/develop
echo HEAD=$(git log -1 --oneline)

ensure_env() {
  local k="$1" v="$2"
  if grep -q "^${k}=" .env; then
    sed -i "s|^${k}=.*|${k}=${v}|" .env
  else
    echo "${k}=${v}" >> .env
  fi
}
ensure_env WEB_BACKENDS omni
ensure_env HERMES_SEARXNG_URL 'http://model-router:8096/v1/searxng-compat'
ensure_env OMNIROUTER_SEARCH_PROVIDERS 'tavily-search,firecrawl-search,searxng-search'
ensure_env WEB_SEARCH_PROVIDER_TIMEOUT_S 30
ensure_env ZALO_QUEUE_TURN_TIMEOUT_S 300
ensure_env MODEL_ROUTER_TIMEOUT_S 180
ensure_env OMNIROUTE_DISABLE_CREDENTIAL_HEALTH_CHECK true

set -a; . ./.env; set +a

# Rebuild router-worker so searxng-compat ships (lab image was stale @ 361 lines).
docker compose --project-directory /opt/assistant -f docker/docker-compose.yml \
  build router-worker 2>&1 | tail -40
docker compose --project-directory /opt/assistant -f docker/docker-compose.yml \
  up -d --force-recreate router-worker hermes omni-router 2>&1 | tail -40
sleep 15

python3 scripts/main/first-setup-omnirouter.py 2>&1 | tee /tmp/first-setup-after-weather-fix.log | tail -40

# Sync SOUL (deception_hide safe) into replicas
python3 <<'PY'
from pathlib import Path
import shutil
src = Path('/opt/assistant/hermes/main/SOUL.md')
for dest in (Path('/opt/data/SOUL.md'), Path('/data/assistant/SOUL.md')):
    if dest.parent.is_dir():
        shutil.copy2(src, dest)
for root in (Path('/opt/data/replicas'), Path('/data/assistant/replicas')):
    if not root.is_dir():
        continue
    for dest in root.glob('*/SOUL.md'):
        shutil.copy2(src, dest)
print('SOUL synced')
PY

echo '=== verify searxng-compat ==='
docker exec router-worker grep -c searxng-compat /app/websearch.py || true
curl -sS -m 45 -o /tmp/sx.json -w 'sx_http=%{http_code}\n' \
  'http://127.0.0.1:8096/v1/searxng-compat/search?q=thoi+tiet+Ho+Chi+Minh&format=json' || true
head -c 350 /tmp/sx.json; echo
curl -sS -m 60 -o /tmp/ws.json -w 'ws_http=%{http_code}\n' -X POST http://127.0.0.1:8096/v1/search \
  -H 'Content-Type: application/json' \
  -d '{"query":"thoi tiet Ho Chi Minh hien tai","max_results":2}' || true
head -c 350 /tmp/ws.json; echo

docker ps --filter name=router-worker --format '{{.Names}} {{.Status}}'
docker ps --filter name=hermes --format '{{.Names}} {{.Status}}'
docker exec assistant-hermes-1 printenv ZALO_QUEUE_TURN_TIMEOUT_S SEARXNG_URL || true
echo OK_APPLY_WEATHER_TIMEOUT
"""


def main() -> int:
    c = connect()
    try:
        out = sudo_bash(c, REMOTE, timeout=1200)
    finally:
        c.close()
    Path("test/reports/apply-weather-timeout-rebuild.log").write_text(
        out or "", encoding="utf-8", errors="replace"
    )
    sys.stdout.buffer.write((out or "").encode("utf-8", errors="replace")[-14000:])
    sys.stdout.buffer.write(b"\n")
    return 0 if out and "OK_APPLY_WEATHER_TIMEOUT" in out else 1


if __name__ == "__main__":
    raise SystemExit(main())
