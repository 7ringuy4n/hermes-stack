# -*- coding: utf-8 -*-
"""Thorough VPS probe: websearch.py freshness + Tavily vs SearXNG default path."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from deploy_stack import connect, sudo_bash

REMOTE = r"""
set -euo pipefail
cd /opt/assistant
echo '=== HEAD ==='
git log -1 --oneline
echo '=== env search knobs (names only + values non-secret) ==='
grep -E '^(WEB_BACKENDS|HERMES_SEARXNG_URL|SEARXNG_URL|OMNIROUTER_SEARCH_PROVIDERS|WEB_SEARCH_PROVIDER_TIMEOUT_S|WEB_SEARCH_MAX_RESULTS)=' .env || true
echo '=== hermes container ==='
docker exec assistant-hermes-1 printenv SEARXNG_URL WEB_SEARCH_URL WEB_BACKENDS 2>/dev/null || true
echo '=== router-worker container ==='
docker exec router-worker printenv WEB_BACKENDS OMNIROUTER_SEARCH_PROVIDERS OMNIROUTER_BASE_URL WEB_SEARCH_PROVIDER_TIMEOUT_S 2>/dev/null || true
docker exec router-worker wc -l /app/websearch.py
docker exec router-worker grep -c searxng-compat /app/websearch.py || echo compat=0
echo '=== repo websearch ==='
wc -l architect/models/model-router/websearch.py
grep -c searxng-compat architect/models/model-router/websearch.py || true
echo '=== router health ==='
curl -sS -m 10 http://127.0.0.1:8096/health | head -c 800; echo
echo '=== POST /v1/search (3 queries) ==='
for q in 'weather Ho Chi Minh' 'gia xang E5' 'tin tuc hom nay'; do
  echo "-- q=$q"
  curl -sS -m 45 -o /tmp/ws.json -w 'http=%{http_code}\n' -X POST http://127.0.0.1:8096/v1/search \
    -H 'Content-Type: application/json' \
    -d "{\"query\":\"$q\",\"max_results\":2}" || true
  python3 - <<'PY'
import json
from pathlib import Path
raw=Path('/tmp/ws.json').read_text(encoding='utf-8', errors='replace')
try:
  d=json.loads(raw)
except Exception:
  print('body', raw[:200]); raise SystemExit
print('backend=', d.get('backend'), 'n=', len(d.get('results') or []), 'errors=', d.get('errors'))
if d.get('results'):
  print('first_title=', str((d['results'][0] or {}).get('title') or '')[:80])
PY
done
echo '=== GET searxng-compat ==='
curl -sS -m 45 -o /tmp/sx.json -w 'http=%{http_code}\n' \
  'http://127.0.0.1:8096/v1/searxng-compat/search?q=weather+hcm&format=json' || true
python3 - <<'PY'
import json
from pathlib import Path
d=json.loads(Path('/tmp/sx.json').read_text(encoding='utf-8', errors='replace'))
print('compat_engine_sample=', ((d.get('results') or [{}])[0] or {}).get('engine'))
print('compat_n=', d.get('number_of_results') or len(d.get('results') or []))
PY
echo '=== Omni providers (search) priorities ==='
python3 - <<'PY'
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
rows=[]
for c in data.get('connections') or []:
    prov=str(c.get('provider') or '')
    if 'search' in prov or prov in ('tavily-search','firecrawl-search','searxng-search','ollama-search'):
        rows.append((c.get('priority'), prov, c.get('name'), c.get('isActive'), c.get('id')))
rows.sort(key=lambda x: (x[0] is None, x[0] if isinstance(x[0], int) else 999, str(x[1])))
for r in rows:
    print('prio=', r[0], 'provider=', r[1], 'name=', r[2], 'active=', r[3])
# direct Omni search without forcing provider
key=env.get('OMNIROUTER_API_KEY') or ''
body=json.dumps({'query':'weather Ho Chi Minh city today','max_results':2}).encode()
req=urllib.request.Request('http://127.0.0.1:20129/v1/search', data=body, method='POST', headers={'Content-Type':'application/json','Authorization':'Bearer '+key})
try:
    with urllib.request.urlopen(req, timeout=45) as r:
        raw=json.loads(r.read().decode() or '{}')
    print('omni_direct_provider=', raw.get('provider'), 'n=', len(raw.get('results') or raw.get('data') or []) if isinstance(raw.get('results') or raw.get('data'), list) else type(raw.get('results')))
    print('omni_keys=', list(raw.keys())[:20])
except Exception as e:
    print('omni_direct_fail', type(e).__name__, e)
# force tavily
body2=json.dumps({'query':'weather Ho Chi Minh city today','max_results':2,'provider':'tavily-search'}).encode()
req2=urllib.request.Request('http://127.0.0.1:20129/v1/search', data=body2, method='POST', headers={'Content-Type':'application/json','Authorization':'Bearer '+key})
try:
    with urllib.request.urlopen(req2, timeout=45) as r:
        raw=json.loads(r.read().decode() or '{}')
    print('omni_tavily_forced_provider=', raw.get('provider'), 'n_results_field=', raw.get('results') is not None)
except Exception as e:
    print('omni_tavily_fail', type(e).__name__, str(e)[:160])
PY
echo '=== recent router/omni search logs ==='
docker logs --since 30m router-worker 2>&1 | grep -iE 'search|tavily|searx|backend|404|503' | tail -40 || true
docker logs --since 30m omni-router 2>&1 | grep -iE 'search|tavily|searx|provider' | tail -40 || true
echo PROBE_TAVILY_ORDER_DONE
"""


def main() -> int:
    c = connect()
    try:
        out = sudo_bash(c, REMOTE, timeout=240)
    finally:
        c.close()
    Path("test/reports/probe-tavily-vs-searxng.log").write_text(
        out or "", encoding="utf-8", errors="replace"
    )
    sys.stdout.buffer.write((out or "").encode("utf-8", errors="replace")[-12000:])
    sys.stdout.buffer.write(b"\n")
    return 0 if out and "PROBE_TAVILY_ORDER_DONE" in out else 1


if __name__ == "__main__":
    raise SystemExit(main())
