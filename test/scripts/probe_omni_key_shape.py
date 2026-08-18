# -*- coding: utf-8 -*-
"""Check OmniRoute key shape and combo list without printing secrets."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from deploy_high import connect, sudo_bash  # noqa: E402

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
        with opener.open(req, timeout=20) as resp:
            raw = resp.read()
            return resp.status, json.loads(raw.decode() or '{}') if raw else {}
    except urllib.error.HTTPError as e:
        raw = e.read()
        try:
            parsed = json.loads(raw.decode() or '{}')
        except Exception:
            parsed = {'raw': raw[:200].decode('utf-8','replace')}
        return e.code, parsed

env = load_env('/opt/assistant/.env')
pw = env.get('OMNIROUTER_INITIAL_PASSWORD') or env.get('N9ROUTER_INITIAL_PASSWORD') or ''
base = 'http://127.0.0.1:20129'
opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(CookieJar()))
http(opener, 'POST', base + '/api/auth/login', {'password': pw})
st, data = http(opener, 'GET', base + '/api/keys')
print('allowKeyReveal', data.get('allowKeyReveal'))
for k in data.get('keys') or []:
    val = k.get('key') or k.get('apiKey') or k.get('token') or ''
    print('KEY name=', k.get('name'), 'fields=', list(k.keys()), 'len=', len(val), 'masked=', ('*' in val), 'prefix3=', val[:3])
st, data = http(opener, 'GET', base + '/api/combos')
print('N_COMBOS', data.get('total'), [(c.get('name'), len(c.get('models') or []), c.get('strategy')) for c in (data.get('combos') or [])])
stored = env.get('OMNIROUTER_API_KEY') or ''
print('ENV_KEY len=', len(stored), 'masked=', ('*' in stored), 'prefix3=', stored[:3])
print('CHECK_DONE')
PY
"""


def main() -> int:
    c = connect()
    try:
        sudo_bash(c, REMOTE, timeout=60)
        return 0
    finally:
        c.close()


if __name__ == "__main__":
    raise SystemExit(main())
