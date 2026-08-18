# -*- coding: utf-8 -*-
"""Inspect OmniRoute /api/models and combo create schema."""
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
        with opener.open(req, timeout=25) as resp:
            raw = resp.read()
            return resp.status, json.loads(raw.decode() or '{}') if raw else {}
    except urllib.error.HTTPError as e:
        raw = e.read()
        try:
            parsed = json.loads(raw.decode() or '{}')
        except Exception:
            parsed = {'raw': raw[:400].decode('utf-8','replace')}
        return e.code, parsed

env = load_env('/opt/assistant/.env')
pw = env.get('OMNIROUTER_INITIAL_PASSWORD') or env.get('N9ROUTER_INITIAL_PASSWORD') or ''
base = 'http://127.0.0.1:20129'
opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(CookieJar()))
http(opener, 'POST', base + '/api/auth/login', {'password': pw})

st, data = http(opener, 'GET', base + '/api/models')
models = data.get('models') or []
print('API_MODELS', st, 'n=', len(models), 'sample_keys=', list(models[0].keys())[:16] if models else None)
oc = [m for m in models if isinstance(m, dict) and str(m.get('id') or '').startswith('oc/')]
print('OC_FROM_API_MODELS', [m.get('id') for m in oc])

st, settings = http(opener, 'GET', base + '/api/settings')
print('comboStrategy', settings.get('comboStrategy'))
print('comboSticky', settings.get('comboStickyRoundRobinLimit'))
print('comboStrategies' in settings, type(settings.get('comboStrategies')).__name__ if 'comboStrategies' in settings else 'absent')

# discover required combo fields by sending name only
st, d = http(opener, 'POST', base + '/api/combos', {'name': 'probe-combo'})
print('COMBO_NAME_ONLY', st, d)

print('PROBE3_DONE')
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
