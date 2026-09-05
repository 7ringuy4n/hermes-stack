# -*- coding: utf-8 -*-
"""Two-pass lab: (1) sync develop + deploy High/Zalo, (2) destroy + Quick-start redeploy.

Env: ASSISTANT_SSH_HOST, ASSISTANT_SSH_USER, ASSISTANT_SSH_PASSWORD, ASSISTANT_REPO_ROOT
PASS=1|2|all (default all)
Does not print host/account into report files.
"""
from __future__ import annotations

import base64
import io
import os
import sys
import tarfile
import time
from pathlib import Path

import paramiko

HOST = os.environ["ASSISTANT_SSH_HOST"]
USER = os.environ["ASSISTANT_SSH_USER"]
PW = os.environ["ASSISTANT_SSH_PASSWORD"]
ROOT = Path(os.environ.get("ASSISTANT_REPO_ROOT", Path(__file__).resolve().parents[2]))
REMOTE = "/opt/assistant"
PASS = os.environ.get("PASS", "all").strip().lower()
SKIP_SYNC = os.environ.get("SKIP_SYNC", "0").strip() in {"1", "true", "yes"}
esc = PW.replace("'", "'\\''")

SKIP_DIR = {
    ".git",
    "__pycache__",
    "node_modules",
    ".cursor",
    "hermes/temp",
    "scripts/temp",
    "test/reports",
}


def connect():
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect(HOST, username=USER, password=PW, timeout=45, allow_agent=False, look_for_keys=False)
    return c


def emit(s: str) -> None:
    try:
        sys.stdout.write(s)
    except UnicodeEncodeError:
        sys.stdout.buffer.write(s.encode("utf-8", "replace"))
    sys.stdout.flush()


def sudo_bash(c, script: str, timeout: int = 3600) -> str:
    b64 = base64.b64encode(script.encode("utf-8")).decode("ascii")
    cmd = f"echo '{esc}' | sudo -S bash -lc \"echo {b64} | base64 -d | bash\""
    emit(f"\n=== remote ({timeout}s) ===\n")
    _i, o, e = c.exec_command(cmd, timeout=timeout, get_pty=True)
    chan = o.channel
    buf: list[str] = []
    while True:
        while chan.recv_ready():
            chunk = chan.recv(16384).decode("utf-8", "replace")
            emit(chunk)
            buf.append(chunk)
        while chan.recv_stderr_ready():
            chunk = chan.recv_stderr(16384).decode("utf-8", "replace")
            emit(chunk)
            buf.append(chunk)
        if chan.exit_status_ready() and not chan.recv_ready() and not chan.recv_stderr_ready():
            break
        time.sleep(0.2)
    code = chan.recv_exit_status()
    if code != 0:
        raise SystemExit(f"remote exit {code}")
    return "".join(buf)


def should_skip(rel: str) -> bool:
    parts = rel.replace("\\", "/").split("/")
    if any(p == "__pycache__" or p.endswith(".pyc") for p in parts):
        return True
    for s in SKIP_DIR:
        if rel.replace("\\", "/").startswith(s.rstrip("/") + "/") or rel.replace("\\", "/") == s:
            return True
    return False


def sync_tree(c) -> None:
    emit("==> packing tree\n")
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w:gz") as tar:
        for path in ROOT.rglob("*"):
            if not path.is_file():
                continue
            rel = path.relative_to(ROOT).as_posix()
            if should_skip(rel):
                continue
            data = path.read_bytes()
            if path.suffix in {".sh", ".py", ".yml", ".yaml", ".md", ".json", ".txt", ".example"} or path.name == "run.sh":
                try:
                    data = data.decode("utf-8").replace("\r\n", "\n").replace("\r", "\n").encode("utf-8")
                except UnicodeDecodeError:
                    pass
            info = tarfile.TarInfo(name=rel)
            info.size = len(data)
            if path.suffix == ".sh" or path.name == "run.sh":
                info.mode = 0o755
            tar.addfile(info, io.BytesIO(data))
    payload = buf.getvalue()
    emit(f"==> upload {len(payload)} bytes\n")
    sftp = c.open_sftp()
    with sftp.file("/tmp/assistant-sync.tgz", "wb") as f:
        f.write(payload)
    sftp.close()
    sudo_bash(
        c,
        f'''
set -euo pipefail
mkdir -p {REMOTE}
tar -xzf /tmp/assistant-sync.tgz -C {REMOTE}
# strip CR on shell entrypoints
find {REMOTE} -type f \\( -name '*.sh' -o -name 'run.sh' \\) -exec sed -i 's/\\r$//' {{}} +
chmod +x {REMOTE}/run.sh || true
echo SYNC_OK
''',
        timeout=600,
    )


def ensure_env_keys(c) -> None:
    """Ensure GATEWAY_API_KEYS and ZALO tokens exist (generate if missing)."""
    sudo_bash(
        c,
        f'''
set -euo pipefail
cd {REMOTE}
touch .env
upsert() {{
  local k="$1" v="$2"
  if grep -q "^${{k}}=" .env; then
    sed -i "s|^${{k}}=.*|${{k}}=${{v}}|" .env
  else
    echo "${{k}}=${{v}}" >> .env
  fi
}}
# Preserve existing secrets; only fill empty/missing gateway key
if ! grep -qE '^GATEWAY_API_KEYS=.+' .env; then
  KEY=$(python3 -c 'import secrets;print(secrets.token_urlsafe(24))')
  upsert GATEWAY_API_KEYS "$KEY"
  echo "SET_GATEWAY_API_KEYS=1"
fi
if ! grep -qE '^ZALO_API_TOKEN=.+' .env; then
  TOK=$(python3 -c 'import secrets;print(secrets.token_urlsafe(24))')
  upsert ZALO_API_TOKEN "$TOK"
  echo "SET_ZALO_API_TOKEN=1"
fi
# Point Hermes at zalo-api
if ! grep -q '^ZALO_API_URL=' .env; then
  upsert ZALO_API_URL "http://zalo-api:8100"
fi
upsert ENABLE_ZALO 1
upsert ASSISTANT_PROFILE high
upsert ENABLE_TRAEFIK 1
upsert ENABLE_API_GATEWAY 1
upsert GATEWAY_REQUIRE_AUTH 1
upsert TRAEFIK_MODE local
upsert ENABLE_GRAFANA 0
upsert ENABLE_LOKI 0
upsert ENABLE_PROMETHEUS 0
upsert ENABLE_ALLOY 0
upsert ENABLE_ANTIVIRUS 0
upsert SECURITY_FAIL_CLOSED 1
upsert SECURITY_SANDBOX 0
upsert SECURITY_LLM_JUDGE 0
upsert ENABLE_LLM_JUDGE 0
# data dir
grep -q '^ASSISTANT_DATA_DIR=' .env || upsert ASSISTANT_DATA_DIR /data/assistant
grep -q '^HERMES_DATA_DIR=' .env || upsert HERMES_DATA_DIR /data/assistant
mkdir -p /data/assistant /data/assistant/backups
chown -R 1000:1000 /data/assistant || true
echo ENV_OK
''',
        timeout=120,
    )


def destroy_stack(c) -> None:
    sudo_bash(
        c,
        f'''
set -euo pipefail
cd {REMOTE}
set -a; . ./.env; set +a || true
export ASSISTANT_PROFILE="${{ASSISTANT_PROFILE:-high}}"
bash run.sh down || true
NAMES="zalo-proxy zalo-api admin-api hermes traefik api-gateway docker-socket-proxy openbao postgres redis qdrant omni-router model-router dispatcher memory session ingest embedding ocr jobs searxng comfyui-cpu security-manager siem authz policy-center notify av-gateway clamav"
for n in $NAMES; do docker rm -f "$n" 2>/dev/null || true; done
docker ps -aq --filter name=assistant | xargs -r docker rm -f || true
docker ps -aq --filter name=hermes | xargs -r docker rm -f || true
echo DESTROY_OK
''',
        timeout=600,
    )


def deploy_high(c, label: str) -> None:
    sudo_bash(
        c,
        f'''
set -euo pipefail
cd {REMOTE}
set -a; . ./.env; set +a
export ASSISTANT_PROFILE=high
export ENABLE_ZALO=1
export ENABLE_TRAEFIK=1
export ENABLE_API_GATEWAY=1
export TRAEFIK_MODE=local
export COMPOSE_PROGRESS=plain
echo "==> {label}: run.sh up"
bash run.sh up
echo "==> install timers"
bash run.sh install-timers || true
echo "==> wait health"
sleep 20
bash run.sh ps || true
echo "==> first-setup-llm (Quick start)"
bash run.sh first-setup-llm || true
curl -fsS -m 8 http://127.0.0.1:20128/health || curl -fsS -m 8 http://127.0.0.1:20128/ || true
echo
curl -fsS -m 8 http://127.0.0.1:8080/health || true
echo
curl -fsS -m 8 http://127.0.0.1:8088/health || true
echo
curl -fsS -m 8 http://127.0.0.1:8787/health || true
echo
docker ps --format '{{{{.Names}}}} {{{{.Status}}}}' | head -40
echo DEPLOY_OK
''',
        timeout=3600,
    )


def quick_start_redeploy(c) -> None:
    """Pass 2: README-style up only (no source sync/edit)."""
    sudo_bash(
        c,
        f'''
set -euo pipefail
cd {REMOTE}
set -a; . ./.env; set +a
export ASSISTANT_PROFILE=high
export ENABLE_ZALO=1
echo "==> Quick start style: down + up"
bash run.sh down || true
bash run.sh up
echo "==> first-setup-llm (Quick start)"
bash run.sh first-setup-llm || true
bash run.sh install-timers || true
sleep 25
bash run.sh ps || true
# edge + zalo probes
curl -fsS -m 8 http://127.0.0.1:8088/health && echo GW_OK || echo GW_FAIL
curl -fsS -m 8 http://127.0.0.1:8080/health >/dev/null && echo TRAEFIK_OK || echo TRAEFIK_FAIL
curl -fsS -m 8 http://127.0.0.1:8787/health || true
echo
docker ps --filter name=hermes --format '{{{{.Names}}}} {{{{.Status}}}} {{{{.Ports}}}}'
docker ps --filter name=traefik --format '{{{{.Names}}}} {{{{.Status}}}} {{{{.Ports}}}}'
docker ps --filter name=api-gateway --format '{{{{.Names}}}} {{{{.Status}}}} {{{{.Ports}}}}'
docker ps --filter name=zalo --format '{{{{.Names}}}} {{{{.Status}}}}'
echo QUICKSTART_OK
''',
        timeout=3600,
    )


def main() -> None:
    c = connect()
    try:
        if PASS in {"1", "all", "pass1"}:
            emit("==> PASS 1: sync + deploy\n")
            if not SKIP_SYNC:
                sync_tree(c)
            else:
                emit("==> SKIP_SYNC=1\n")
            ensure_env_keys(c)
            destroy_stack(c)
            deploy_high(c, "pass1")
        if PASS in {"2", "all", "pass2"}:
            emit("==> PASS 2: script-only Quick start redeploy\n")
            quick_start_redeploy(c)
    finally:
        c.close()
    emit("==> lab_two_pass done\n")


if __name__ == "__main__":
    main()
