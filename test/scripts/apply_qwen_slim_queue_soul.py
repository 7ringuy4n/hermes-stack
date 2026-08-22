# -*- coding: utf-8 -*-
"""Pull feature branch on VPS, slim Omni to Qwen, recreate hermes/omni, sync SOUL+adapter."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from deploy_stack import connect, sudo_bash

REMOTE = r"""
set -euo pipefail
cd /opt/assistant
git fetch origin
BRANCH=feature/qwen-slim-queue-soul-perf
git checkout "$BRANCH" 2>/dev/null || git checkout -B "$BRANCH" "origin/$BRANCH"
git reset --hard "origin/$BRANCH"
echo HEAD=$(git log -1 --oneline)

ensure_env() {
  local k="$1" v="$2"
  if grep -q "^${k}=" .env; then
    sed -i "s|^${k}=.*|${k}=${v}|" .env
  else
    echo "${k}=${v}" >> .env
  fi
}
ensure_env OMNIROUTE_DISABLE_CREDENTIAL_HEALTH_CHECK true
ensure_env OMNIROUTER_QWEN_ONLY_PROVIDERS 1
ensure_env ZALO_COMPOUND_WAIT_FOR_DELIVERY 0

set -a; . ./.env; set +a
python3 scripts/main/first-setup-omnirouter.py 2>&1 | tee /tmp/first-setup-qwen-slim.log | tail -80

docker compose --project-directory /opt/assistant -f docker/docker-compose.yml \
  up -d --force-recreate omni-router hermes 2>&1 | tail -40
sleep 12

python3 test/scripts/sync_zalo_adapter_replicas.py 2>/dev/null || true
python3 - <<'PY'
from pathlib import Path
import shutil
src = Path('/opt/assistant/hermes/main/SOUL.md')
if not src.is_file():
    raise SystemExit('SOUL missing: ' + str(src))
for root in (Path('/opt/data/replicas'), Path('/data/assistant/replicas')):
    if not root.is_dir():
        continue
    for dest in root.glob('*/SOUL.md'):
        shutil.copy2(src, dest)
        print('synced', dest)
print('SOUL sync done')
PY

python3 <<'PY'
import sqlite3, json, glob
dbs = glob.glob('/var/lib/docker/volumes/*omni*/_data/storage.sqlite')
if not dbs:
    print('WARN no omni sqlite')
else:
    c = sqlite3.connect(dbs[0])
    c.row_factory = sqlite3.Row
    for row in c.execute('select name, data from combos'):
        if row['name'] not in ('hermes', 'classifier', 'qwen-fast'):
            continue
        data = json.loads(row['data'] or '{}')
        models = data.get('models') or []
        names = []
        for m in models:
            if isinstance(m, str):
                names.append(m)
            elif isinstance(m, dict):
                names.append(str(m.get('model') or m.get('id') or '')[:100])
        non_qwen = [n for n in names if 'qwen' not in n.lower() and not n.lower().startswith('alibaba/')]
        print(row['name'], 'n=', len(names), 'non_qwen=', len(non_qwen), 'first=', names[:4])
PY

docker ps --filter name=hermes --format '{{.Names}} {{.Status}}'
docker ps --filter name=omni --format '{{.Names}} {{.Status}}'
echo OK_APPLY_QWEN_SLIM
"""


def main() -> int:
    c = connect()
    try:
        out = sudo_bash(c, REMOTE, timeout=900)
    finally:
        c.close()
    Path("test/reports/apply-qwen-slim-queue-soul.log").write_text(
        out or "", encoding="utf-8", errors="replace"
    )
    print(out or "")
    return 0 if out and "OK_APPLY_QWEN_SLIM" in out else 1


if __name__ == "__main__":
    raise SystemExit(main())
