# -*- coding: utf-8 -*-
"""Inspect OmniRoute providers and oc/* model ids."""
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
        with opener.open(req, timeout=25) as resp:
            raw = resp.read()
            return resp.status, json.loads(raw.decode() or '{}') if raw else {}
    except urllib.error.HTTPError as e:
        raw = e.read()
        try:
            parsed = json.loads(raw.decode() or '{}')
        except Exception:
            parsed = {'raw': raw[:300].decode('utf-8','replace')}
        return e.code, parsed

env = load_env('/opt/assistant/.env')
pw = env.get('OMNIROUTER_INITIAL_PASSWORD') or env.get('N9ROUTER_INITIAL_PASSWORD') or ''
base = 'http://127.0.0.1:20129'
opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(CookieJar()))
http(opener, 'POST', base + '/api/auth/login', {'password': pw})

st, data = http(opener, 'GET', base + '/api/providers')
conns = data.get('connections') or data.get('providers') or []
print('N_CONNECTIONS', len(conns))
for c in conns:
    if not isinstance(c, dict):
        continue
    name = c.get('name') or c.get('id') or c.get('type') or c.get('provider')
    typ = c.get('type') or c.get('providerType') or c.get('kind')
    keys = list(c.keys())[:14]
    print('CONN', name, 'type=', typ, 'keys=', keys)

st, data = http(opener, 'GET', base + '/v1/models')
ids = [m.get('id') for m in (data.get('data') or []) if isinstance(m, dict)]
oc = [i for i in ids if isinstance(i, str) and (i.startswith('oc/') or 'opencode' in i.lower() or i.startswith('opencode'))]
print('N_MODELS', len(ids))
print('OC_IDS', oc[:40], 'n=', len(oc))
print('ID_PREFIXES', sorted({(i.split('/')[0] if '/' in i else i.split(':')[0]) for i in ids if isinstance(i, str)})[:40])

# try other catalog endpoints
for path in [
    '/api/models',
    '/api/catalog',
    '/api/providers/catalog',
    '/api/provider-types',
    '/api/connections',
]:
    st, d = http(opener, 'GET', base + path)
    print('TRY', path, st, list(d)[:10] if isinstance(d, dict) else type(d).__name__)

# combo create schema: empty POST to see error
st, d = http(opener, 'POST', base + '/api/combos', {})
print('COMBO_EMPTY_POST', st, d if isinstance(d, dict) else type(d).__name__)

print('PROBE2_DONE')
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

