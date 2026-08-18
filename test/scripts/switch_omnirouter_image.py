# -*- coding: utf-8 -*-
"""Point omni-router at OMNIROUTER_IMAGE (OmniRoute) and recreate it."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from deploy_high import ROOT, connect, sftp_put, sudo_bash, _file_bytes  # noqa: E402

REMOTE_SH = r"""
set -euo pipefail
cd /opt/assistant
cp /tmp/docker-compose.yml /opt/assistant/docker/docker-compose.yml
sed -i 's/\r$//' /opt/assistant/docker/docker-compose.yml
upsert() {
  local k="$1" v="$2"
  if grep -q "^${k}=" .env; then sed -i "s|^${k}=.*|${k}=${v}|" .env
  else echo "${k}=${v}" >> .env; fi
}
upsert ENABLE_OMNIROUTER 1
upsert OMNIROUTER_IMAGE diegosouzapw/omniroute:latest
grep -E '^(ENABLE_OMNIROUTER|OMNIROUTER_IMAGE)=' .env
echo "=== PULL OMNIROUTE ==="
docker pull diegosouzapw/omniroute:latest
echo "=== REPLACE CONTAINER ==="
docker rm -f omni-router || true
docker volume ls -q | grep -E 'omni.?router' | xargs -r docker volume rm || true
set -a
. ./.env
set +a
export COMPOSE_PROGRESS=plain
docker compose --project-directory /opt/assistant -f /opt/assistant/docker/docker-compose.yml --profile omnirouter up -d --no-deps --force-recreate omni-router
echo "=== WAIT HEALTH ==="
ok=0
for i in $(seq 1 60); do
  curl -fsS -m 5 http://127.0.0.1:20129/health >/dev/null 2>&1 && ok=1 && break
  curl -fsS -m 5 http://127.0.0.1:20129/ >/dev/null 2>&1 && ok=1 && break
  sleep 3
done
docker ps --filter name=omni-router --format '{{.Names}} {{.Image}} {{.Status}} {{.Ports}}'
curl -sS -m 8 http://127.0.0.1:20129/health || true
echo
echo "HEALTH_OK=$ok"
python3 - <<'PY'
import json, re, time, urllib.request
from http.cookiejar import CookieJar
from pathlib import Path

def load_env(path):
    out = {}
    for line in Path(path).read_text(encoding="utf-8", errors="replace").splitlines():
        s = line.strip()
        if not s or s.startswith("#") or "=" not in s:
            continue
        k, v = s.split("=", 1)
        out[k.strip()] = v.strip().strip('"').strip("'")
    return out

def set_env_key(path, key, value):
    text = Path(path).read_text(encoding="utf-8")
    line = f"{key}={value}"
    if re.search(rf"(?m)^{re.escape(key)}=", text):
        text = re.sub(rf"(?m)^{re.escape(key)}=.*$", line, text)
    else:
        text = text.rstrip() + "\n" + line + "\n"
    Path(path).write_text(text, encoding="utf-8")

def http_json(opener, method, url, body=None):
    data = None if body is None else json.dumps(body).encode()
    req = urllib.request.Request(
        url,
        data=data,
        method=method,
        headers={"Content-Type": "application/json", "Accept": "application/json"},
    )
    with opener.open(req, timeout=20) as resp:
        raw = resp.read()
        return resp.status, json.loads(raw.decode() or "{}") if raw else {}

env = load_env("/opt/assistant/.env")
pw = env.get("OMNIROUTER_INITIAL_PASSWORD") or env.get("N9ROUTER_INITIAL_PASSWORD") or ""
base = "http://127.0.0.1:20129"
opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(CookieJar()))
for _ in range(30):
    try:
        st, _body = http_json(opener, "POST", base + "/api/auth/login", {"password": pw})
        if st == 200:
            break
    except Exception:
        time.sleep(2)
else:
    print("OMNI_LOGIN_FAIL")
    raise SystemExit(0)
key = ""
try:
    _, data = http_json(opener, "GET", base + "/api/keys")
    keys = data.get("keys") or data.get("data") or []
    if not keys:
        _, created = http_json(opener, "POST", base + "/api/keys", {"name": "Default Key"})
        keys = created.get("keys") or ([created] if created.get("key") else [])
    for k in keys:
        key = (k.get("key") or k.get("token") or k.get("apiKey") or "").strip()
        if key:
            break
except Exception as e:
    print("OMNI_KEY_FAIL", type(e).__name__)
if key:
    set_env_key("/opt/assistant/.env", "OMNIROUTER_API_KEY", key)
    print("OMNIROUTER_API_KEY_SET=1")
else:
    print("OMNIROUTER_API_KEY_SET=0")
print("IMAGE=" + env.get("OMNIROUTER_IMAGE", ""))
PY
set -a
. ./.env
set +a
docker compose --project-directory /opt/assistant -f /opt/assistant/docker/docker-compose.yml up -d --no-deps --force-recreate model-router
docker inspect omni-router --format '{{.Config.Image}}'
echo OMNI_SWITCH_DONE
"""


def main() -> int:
    c = connect()
    try:
        sftp_put(c, _file_bytes(ROOT / "docker" / "docker-compose.yml"), "/tmp/docker-compose.yml")
        out = sudo_bash(c, REMOTE_SH, timeout=900)
        if "OMNI_SWITCH_DONE" not in out:
            print("FAIL missing OMNI_SWITCH_DONE")
            return 1
        return 0
    finally:
        c.close()


if __name__ == "__main__":
    raise SystemExit(main())
