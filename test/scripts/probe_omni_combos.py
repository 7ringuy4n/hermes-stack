# -*- coding: utf-8 -*-
"""Probe OmniRoute combo/provider APIs (no secrets printed)."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from deploy_high import connect, sudo_bash  # noqa: E402

REMOTE = r"""
set -euo pipefail
python3 - <<'PY'
import json, urllib.request
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

import urllib.error
env = load_env('/opt/assistant/.env')
pw = env.get('OMNIROUTER_INITIAL_PASSWORD') or env.get('N9ROUTER_INITIAL_PASSWORD') or ''
base = 'http://127.0.0.1:20129'
opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(CookieJar()))
st, body = http(opener, 'POST', base + '/api/auth/login', {'password': pw})
print('LOGIN', st, 'success' if st == 200 else list(body)[:8])
for path in [
    '/api/combos',
    '/api/settings',
    '/api/providers',
    '/api/keys',
    '/v1/models',
    '/api/providers/suggested-models?url=https://opencode.ai/zen/v1/models&type=opencode-free',
]:
    st, data = http(opener, 'GET', base + path)
    if isinstance(data, dict):
        keys = list(data.keys())[:12]
        extra = ''
        if 'combos' in data:
            extra = f' n_combos={len(data.get("combos") or [])}'
        if 'data' in data and isinstance(data['data'], list):
            extra += f' n_data={len(data["data"])}'
            if data['data'] and isinstance(data['data'][0], dict):
                extra += ' sample_keys=' + ','.join(list(data['data'][0].keys())[:8])
                ids = [x.get('id') for x in data['data'][:8] if isinstance(x, dict)]
                extra += ' ids=' + ','.join(str(i) for i in ids if i)
        if 'providers' in data:
            extra += f' n_providers={len(data.get("providers") or [])}'
        print(f'GET {path.split("?")[0]} {st} keys={keys}{extra}')
    else:
        print(f'GET {path.split("?")[0]} {st} type={type(data).__name__}')
print('PROBE_DONE')
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
