# -*- coding: utf-8 -*-
"""Find OmniRoute usage/stats API paths."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from deploy_stack import connect, sudo_bash  # noqa: E402

REMOTE = r"""
set -euo pipefail
python3 - <<'PY'
import json, urllib.request, urllib.error
from http.cookiejar import CookieJar
from pathlib import Path

def load_env(path):
    out = {}
    for line in Path(path).read_text(encoding='utf-8', errors='replace').splitlines():
        s = line.strip()
        if not s or s.startswith('#') or '=' not in s:
            continue
        k, v = s.split('=', 1)
        out[k.strip()] = v.strip().strip('"').strip("'")
    return out

def http(opener, method, url, body=None):
    data = None if body is None else json.dumps(body).encode()
    req = urllib.request.Request(url, data=data, method=method, headers={'Content-Type':'application/json','Accept':'application/json'})
    try:
        with opener.open(req, timeout=12) as resp:
            raw = resp.read()
            parsed = json.loads(raw.decode() or '{}') if raw else {}
            return resp.status, parsed
    except urllib.error.HTTPError as e:
        return e.code, {'err': e.reason}

env = load_env('/opt/assistant/.env')
pw = env.get('OMNIROUTER_INITIAL_PASSWORD') or env.get('N9ROUTER_INITIAL_PASSWORD') or ''
base = 'http://127.0.0.1:20129'
opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(CookieJar()))
st, body = http(opener, 'POST', base + '/api/auth/login', {'password': pw})
print('LOGIN', st)
paths = [
    '/api/usage/stats', '/api/usage', '/api/stats', '/api/analytics',
    '/api/metrics', '/api/dashboard', '/api/dashboard/stats',
    '/api/requests/stats', '/api/logs/stats', '/api/activity',
    '/api/combos', '/api/providers', '/api/health', '/health',
    '/api/usage/summary', '/api/usage/overview', '/api/billing/stats',
]
for p in paths:
    st, d = http(opener, 'GET', base + p)
    keys = list(d)[:10] if isinstance(d, dict) else type(d).__name__
    print(f'{st} {p} {keys}')
print('PATHS_DONE')
PY
"""


def main() -> int:
    c = connect()
    try:
        sudo_bash(c, REMOTE, timeout=45)
        return 0
    finally:
        c.close()


if __name__ == "__main__":
    raise SystemExit(main())

