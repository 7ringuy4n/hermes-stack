# -*- coding: utf-8 -*-
"""Re-seed OpenBao without legacy ADMIN_API_TOKEN."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from deploy_stack import ROOT, connect, sftp_put, sudo_bash, _file_bytes  # noqa: E402


def main() -> int:
    c = connect()
    try:
        sftp_put(
            c,
            _file_bytes(ROOT / "scripts" / "main" / "first-setup-openbao.py"),
            "/tmp/first-setup-openbao.py",
        )
        out = sudo_bash(
            c,
            r"""
set -euo pipefail
install -m 0755 /tmp/first-setup-openbao.py /opt/assistant/scripts/main/first-setup-openbao.py
sed -i 's/\r$//' /opt/assistant/scripts/main/first-setup-openbao.py
cd /opt/assistant
set -a
. ./.env
set +a
export STACK_ROOT=/opt/assistant
python3 scripts/main/first-setup-openbao.py
python3 - <<'PY'
import json, os, urllib.request
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

env = load_env('/opt/assistant/.env')
token_path = Path(os.environ.get('OPENBAO_TOKEN_FILE') or '/data/assistant/openbao/root-token')
token = env.get('OPENBAO_DEV_ROOT_TOKEN') or ''
if not token and token_path.is_file():
    token = token_path.read_text(encoding='utf-8', errors='replace').strip()
addr = (env.get('OPENBAO_ADDR') or 'http://127.0.0.1:8200').rstrip('/')
req = urllib.request.Request(
    addr + '/v1/secret/data/assistant/api-keys',
    headers={'X-Vault-Token': token, 'Accept': 'application/json'},
)
with urllib.request.urlopen(req, timeout=15) as resp:
    data = json.loads(resp.read().decode())
keys = sorted(((data.get('data') or {}).get('data') or {}).keys())
print('OPENBAO_KEYS', ','.join(keys))
print('HAS_ADMIN_API_TOKEN', 'ADMIN_API_TOKEN' in keys)
print('HAS_ZALO_API_TOKEN', 'ZALO_API_TOKEN' in keys)
PY
echo OPENBAO_ADMIN_DROP_DONE
""",
            timeout=60,
        )
        if "OPENBAO_ADMIN_DROP_DONE" not in out:
            print("FAIL missing OPENBAO_ADMIN_DROP_DONE")
            return 1
        if "HAS_ADMIN_API_TOKEN True" in out:
            print("FAIL ADMIN_API_TOKEN still in OpenBao")
            return 1
        return 0
    finally:
        c.close()


if __name__ == "__main__":
    raise SystemExit(main())

