# -*- coding: utf-8 -*-
"""See if POST /api/keys returns a full OmniRoute token."""
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
            parsed = {'raw': raw[:300].decode('utf-8','replace')}
        return e.code, parsed

env = load_env('/opt/assistant/.env')
pw = env.get('OMNIROUTER_INITIAL_PASSWORD') or env.get('N9ROUTER_INITIAL_PASSWORD') or ''
base = 'http://127.0.0.1:20129'
opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(CookieJar()))
http(opener, 'POST', base + '/api/auth/login', {'password': pw})
st, created = http(opener, 'POST', base + '/api/keys', {'name': 'assistant-stack'})
print('POST_KEYS', st, 'fields=', list(created.keys()) if isinstance(created, dict) else type(created).__name__)
val = ''
if isinstance(created, dict):
    val = created.get('key') or created.get('apiKey') or created.get('token') or ''
    inner = created.get('keys') or []
    print('inner_n', len(inner) if isinstance(inner, list) else None)
    if not val and inner and isinstance(inner, list):
        val = (inner[0].get('key') if isinstance(inner[0], dict) else '') or ''
print('created_len', len(val), 'masked', '*' in val, 'prefix3', val[:3])
# try reveal
kid = created.get('id') if isinstance(created, dict) else None
if kid:
    for path in [f'/api/keys/{kid}', f'/api/keys/{kid}/reveal', f'/api/keys/{kid}?reveal=1']:
        st, d = http(opener, 'GET', base + path)
        print('TRY', path, st, list(d.keys())[:8] if isinstance(d, dict) else st)
print('KEYCREATE_DONE')
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
