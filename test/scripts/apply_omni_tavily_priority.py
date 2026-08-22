# -*- coding: utf-8 -*-
"""Pull develop on VPS and re-run Omni first-setup to enforce Tavily>Firecrawl>SearXNG priorities."""
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

set -a; . ./.env; set +a

# Confirm router-worker still has searxng-compat (stale image = 0).
compat=$(docker exec router-worker grep -c searxng-compat /app/websearch.py || echo 0)
echo "router_worker_searxng_compat_hits=${compat}"
if [ "${compat}" = "0" ]; then
  echo 'WARN: stale websearch.py — rebuilding router-worker'
  docker compose --project-directory /opt/assistant -f docker/docker-compose.yml \
    build router-worker 2>&1 | tail -30
  docker compose --project-directory /opt/assistant -f docker/docker-compose.yml \
    up -d --force-recreate router-worker 2>&1 | tail -20
  sleep 10
fi

python3 scripts/main/first-setup-omnirouter.py 2>&1 | tee /tmp/first-setup-tavily-priority.log | tail -60

echo '=== verify Omni search priorities + default provider ==='
python3 <<'PY'
import json, urllib.request, http.cookiejar
from pathlib import Path
env={}
for line in Path('.env').read_text(encoding='utf-8', errors='replace').splitlines():
    s=line.strip()
    if not s or s.startswith('#') or '=' not in s: continue
    k,v=s.split('=',1); env[k.strip()]=v.strip().strip('"').strip("'")
pw=env.get('OMNIROUTER_INITIAL_PASSWORD') or env.get('N9ROUTER_INITIAL_PASSWORD') or ''
cj=http.cookiejar.CookieJar(); op=urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj))
req=urllib.request.Request('http://127.0.0.1:20129/api/auth/login', data=json.dumps({'password':pw}).encode(), headers={'Content-Type':'application/json'}, method='POST')
op.open(req, timeout=15)
with op.open('http://127.0.0.1:20129/api/providers', timeout=20) as r:
    data=json.loads(r.read().decode() or '{}')
for c in sorted((data.get('connections') or []), key=lambda x: (x.get('priority') is None, x.get('priority') if isinstance(x.get('priority'), int) else 999)):
    prov=str(c.get('provider') or '')
    if prov in ('tavily-search','firecrawl-search','searxng-search'):
        print(f"prio={c.get('priority')} provider={prov} active={c.get('isActive')}")
key=env.get('OMNIROUTER_API_KEY') or ''
body=json.dumps({'query':'weather Ho Chi Minh city today','max_results':2}).encode()
req=urllib.request.Request('http://127.0.0.1:20129/v1/search', data=body, method='POST', headers={'Content-Type':'application/json','Authorization':'Bearer '+key})
with urllib.request.urlopen(req, timeout=45) as r:
    raw=json.loads(r.read().decode() or '{}')
print('omni_direct_provider=', raw.get('provider'))
PY

curl -sS -m 45 -o /tmp/ws.json -w 'router_search_http=%{http_code}\n' -X POST http://127.0.0.1:8096/v1/search \
  -H 'Content-Type: application/json' \
  -d '{"query":"weather Ho Chi Minh","max_results":2}' || true
python3 - <<'PY'
import json
from pathlib import Path
d=json.loads(Path('/tmp/ws.json').read_text(encoding='utf-8', errors='replace'))
print('router_backend=', d.get('backend'))
PY

echo OK_APPLY_OMNI_TAVILY_PRIORITY
"""


def main() -> int:
    c = connect()
    try:
        out = sudo_bash(c, REMOTE, timeout=900)
    finally:
        c.close()
    Path("test/reports/apply-omni-tavily-priority.log").write_text(
        out or "", encoding="utf-8", errors="replace"
    )
    sys.stdout.buffer.write((out or "").encode("utf-8", errors="replace")[-14000:])
    sys.stdout.buffer.write(b"\n")
    return 0 if out and "OK_APPLY_OMNI_TAVILY_PRIORITY" in out else 1


if __name__ == "__main__":
    raise SystemExit(main())
