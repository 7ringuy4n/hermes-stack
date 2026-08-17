# -*- coding: utf-8 -*-
"""Destroy current profile, deploy High with Notify + OmniRouter + monitor.

Env: ASSISTANT_SSH_HOST, ASSISTANT_SSH_USER, ASSISTANT_SSH_PASSWORD
Optional: ASSISTANT_REPO_ROOT
Does not write secrets into test/reports.
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

sys.path.insert(0, str(Path(__file__).resolve().parent))
from sanitize import sanitize

HOST = os.environ["ASSISTANT_SSH_HOST"]
USER = os.environ["ASSISTANT_SSH_USER"]
PW = os.environ["ASSISTANT_SSH_PASSWORD"]
ROOT = Path(os.environ.get("ASSISTANT_REPO_ROOT", Path(__file__).resolve().parents[2]))
REMOTE = "/opt/assistant"
RESUME = os.environ.get("RESUME", "0").strip() in {"1", "true", "yes"}
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
TEXT_EXT = {".sh", ".py", ".yml", ".yaml", ".md", ".json", ".txt", ".example"}


def emit(s: str) -> None:
    try:
        sys.stdout.write(s)
    except UnicodeEncodeError:
        enc = getattr(sys.stdout, "encoding", None) or "utf-8"
        sys.stdout.write(s.encode(enc, errors="replace").decode(enc, errors="replace"))
    sys.stdout.flush()


def connect():
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect(HOST, username=USER, password=PW, timeout=45, allow_agent=False, look_for_keys=False)
    return c


def sudo_bash(c, script: str, timeout: int = 3600) -> str:
    b64 = base64.b64encode(script.encode("utf-8")).decode("ascii")
    cmd = f"echo '{esc}' | sudo -S bash -lc \"echo {b64} | base64 -d | bash\""
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
        time.sleep(0.15)
    code = chan.recv_exit_status()
    text = "".join(buf)
    if code != 0:
        raise SystemExit(f"remote exit {code}: {sanitize(text)[-500:]}")
    return text


def should_skip(rel: str) -> bool:
    r = rel.replace("\\", "/")
    if any(p == "__pycache__" or p.endswith(".pyc") for p in r.split("/")):
        return True
    for s in SKIP_DIR:
        if r.startswith(s.rstrip("/") + "/") or r == s:
            return True
    return False


def _file_bytes(path: Path) -> bytes:
    data = path.read_bytes()
    if path.suffix.lower() in TEXT_EXT or path.name in {"run.sh", "Dockerfile"}:
        try:
            data = data.decode("utf-8").replace("\r\n", "\n").replace("\r", "\n").encode("utf-8")
        except UnicodeDecodeError:
            pass
    return data


def pack_tree() -> bytes:
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w:gz") as tar:
        for path in ROOT.rglob("*"):
            if not path.is_file():
                continue
            rel = path.relative_to(ROOT).as_posix()
            if should_skip(rel):
                continue
            data = _file_bytes(path)
            info = tarfile.TarInfo(name=rel)
            info.size = len(data)
            if path.suffix == ".sh" or path.name == "run.sh":
                info.mode = 0o755
            tar.addfile(info, io.BytesIO(data))
    return buf.getvalue()


def pack_skills() -> bytes:
    skills = ROOT / "hermes" / "main" / "skills"
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w:gz") as tar:
        for path in skills.rglob("*"):
            if not path.is_file() or "__pycache__" in path.parts:
                continue
            rel = path.relative_to(ROOT).as_posix()
            data = _file_bytes(path)
            info = tarfile.TarInfo(name=rel)
            info.size = len(data)
            tar.addfile(info, io.BytesIO(data))
    return buf.getvalue()


def sftp_put(c, local_bytes: bytes, remote_path: str) -> None:
    sftp = c.open_sftp()
    with sftp.file(remote_path, "wb") as f:
        f.write(local_bytes)
    sftp.close()


def sync_tree(c) -> None:
    emit("==> packing source + skills\n")
    tree = pack_tree()
    skills = pack_skills()
    sftp_put(c, tree, "/tmp/assistant-sync.tgz")
    sftp_put(c, skills, "/tmp/hermes-skills.tgz")
    sudo_bash(
        c,
        f"""
set -euo pipefail
mkdir -p {REMOTE}
tar -xzf /tmp/assistant-sync.tgz -C {REMOTE}
tar -xzf /tmp/hermes-skills.tgz -C {REMOTE}
find {REMOTE} -type f \\( -name '*.sh' -o -name 'run.sh' \\) -exec sed -i 's/\\r$//' {{}} +
chmod +x {REMOTE}/run.sh || true
test -f {REMOTE}/hermes/main/skills/core/answering/SKILL.md
echo SYNC_OK
""",
        timeout=600,
    )
    emit(f"==> sync ok tree={len(tree)} skills={len(skills)}\n")


def remote_deploy(c) -> str:
    resume = "1" if RESUME else "0"
    return sudo_bash(
        c,
        rf"""
set -euo pipefail
cd {REMOTE}
touch .env
chmod 600 .env || true
upsert() {{
  local k="$1" v="$2"
  if grep -q "^${{k}}=" .env; then sed -i "s|^${{k}}=.*|${{k}}=${{v}}|" .env
  else echo "${{k}}=${{v}}" >> .env; fi
}}
fill_if_empty() {{
  local k="$1" v="$2"
  if ! grep -qE "^${{k}}=.+" .env; then upsert "$k" "$v"; fi
}}
rand() {{ python3 -c 'import secrets;print(secrets.token_urlsafe(24))'; }}

upsert ASSISTANT_PROFILE high
upsert HERMES_REPLICAS 2
upsert ENABLE_ZALO 0
upsert ENABLE_TELEGRAM 0
upsert ENABLE_TRAEFIK 1
upsert ENABLE_API_GATEWAY 1
upsert TRAEFIK_MODE local
upsert TRAEFIK_ACME_ENABLED 0
upsert ENABLE_OCR 1
upsert ENABLE_JOBS 1
upsert ENABLE_SEARXNG 1
upsert ENABLE_OPENBAO 1
upsert ENABLE_SECURITY 1
upsert ENABLE_SIEM 1
upsert ENABLE_POLICY 1
upsert ENABLE_AUTHZ 1
upsert ENABLE_MODEL_ROUTER 1
upsert ENABLE_NOTIFY 1
upsert ENABLE_OMNIROUTER 1
upsert ENABLE_GRAFANA 1
upsert ENABLE_LOKI 1
upsert ENABLE_PROMETHEUS 1
upsert ENABLE_ALLOY 1
upsert ENABLE_LOG_ARCHIVE 1
upsert ENABLE_CLOUDDRIVE 0
upsert ENABLE_OPENVPN 0
upsert ENABLE_ANTIVIRUS 0
upsert SECURITY_SANDBOX 0
upsert SECURITY_LLM_JUDGE 0
upsert ENABLE_LLM_JUDGE 0
upsert SECURITY_YARA 1
upsert SECURITY_FAIL_CLOSED 1
upsert LEARN_REQUIRE_APPROVE 0
upsert OFFICE_FILE_GEN 1
grep -q '^ASSISTANT_DATA_DIR=' .env || upsert ASSISTANT_DATA_DIR /data/assistant
grep -q '^HERMES_DATA_DIR=' .env || upsert HERMES_DATA_DIR /data/assistant
fill_if_empty GATEWAY_API_KEYS "$(rand)"
fill_if_empty API_SERVER_KEY "$(rand)"
if ! grep -qE '^OMNIROUTER_INITIAL_PASSWORD=.+' .env; then
  N9PW=$(grep -E '^N9ROUTER_INITIAL_PASSWORD=' .env | cut -d= -f2- || true)
  if [[ -n "$N9PW" ]]; then upsert OMNIROUTER_INITIAL_PASSWORD "$N9PW"; fi
fi

echo "=== CLEAR OLD FILES ==="
rm -rf /tmp/assistant /tmp/9r-*.json 2>/dev/null || true
mkdir -p /data/assistant/docs /data/assistant/backups /data/assistant/media/out
chown -R 1000:1000 /data/assistant || true
if [[ -f /tmp/hermes-skills.tgz ]]; then
  tar -xzf /tmp/hermes-skills.tgz -C {REMOTE}
fi
test -f {REMOTE}/hermes/main/skills/core/answering/SKILL.md

export COMPOSE_PROGRESS=plain
if [[ "{resume}" == "1" ]]; then
  echo "=== RESUME HIGH UP (prune stale containers) ==="
  docker ps -aq --filter status=dead | xargs -r docker rm -f || true
  docker ps -aq --filter status=created | xargs -r docker rm -f || true
  docker container prune -f || true
else
  echo "=== DESTROY CURRENT PROFILE ==="
  bash run.sh destroy
  docker ps -aq --filter label=com.docker.compose.project=assistant | xargs -r docker rm -f || true
  docker ps -aq --filter status=dead | xargs -r docker rm -f || true
  docker ps -aq --filter status=created | xargs -r docker rm -f || true
  tar -xzf /tmp/hermes-skills.tgz -C {REMOTE} 2>/dev/null || true
fi

echo "=== BUILD + HIGH UP ==="
docker compose --project-directory {REMOTE} -f {REMOTE}/docker/docker-compose.yml build embedding dispatcher ingest || true
bash run.sh up
sleep 25
for i in $(seq 1 40); do
  curl -fsS -m 5 http://127.0.0.1:8080/health >/dev/null 2>&1 && \
  curl -fsS -m 5 http://127.0.0.1:23000/api/health >/dev/null 2>&1 && break
  sleep 3
done

echo "=== HEALTH ==="
curl -sS -m 10 http://127.0.0.1:20128/health || true
echo
curl -sS -m 10 http://127.0.0.1:8080/health || true
echo
curl -sS -m 10 http://127.0.0.1:8099/health || true
echo
curl -sS -m 10 http://127.0.0.1:8092/health || true
echo
curl -sS -m 10 http://127.0.0.1:20129/health || true
echo
curl -sS -m 10 http://127.0.0.1:23000/api/health || true
echo

echo "=== CHECK HIGH ==="
set +e
bash run.sh check-high
check_rc=$?
set -e
docker ps --format '{{{{.Names}}}} {{{{.Status}}}}' | sort
echo CHECK_HIGH_RC=$check_rc

echo "=== CLEAN SOURCE / TEMP ==="
rm -f /tmp/assistant-sync.tgz /tmp/hermes-skills.tgz /tmp/assistant.env.new
rm -rf /tmp/assistant /tmp/9r-*.json
find {REMOTE} -type d -name __pycache__ -prune -exec rm -rf {{}} + 2>/dev/null || true
docker builder prune -af >/dev/null 2>&1 || true
docker image prune -f >/dev/null 2>&1 || true
echo CLEAN_OK

echo "=== ADMIN CREDENTIALS ==="
python3 - <<'PY'
from pathlib import Path
env = {{}}
for line in Path("/opt/assistant/.env").read_text(encoding="utf-8", errors="replace").splitlines():
    s = line.strip()
    if not s or s.startswith("#") or "=" not in s:
        continue
    k, v = s.split("=", 1)
    env[k.strip()] = v.strip().strip('"').strip("'")
keys = [
    "ASSISTANT_PROFILE",
    "HERMES_REPLICAS",
    "ENABLE_NOTIFY",
    "ENABLE_OMNIROUTER",
    "ENABLE_GRAFANA",
    "HERMES_DASHBOARD_USER",
    "HERMES_DASHBOARD_PASSWORD",
    "GRAFANA_ADMIN_USER",
    "GRAFANA_ADMIN_PASSWORD",
    "N9ROUTER_INITIAL_PASSWORD",
    "OPENBAO_DEV_ROOT_TOKEN",
]
print("ADMIN_BEGIN")
for k in keys:
    print(f"{{k}}={{env.get(k, '')}}")
print("ADMIN_END")
PY

echo HIGH_DEPLOY_DONE
""",
        timeout=5400,
    )


def main() -> int:
    c = connect()
    try:
        if SKIP_SYNC or RESUME:
            emit("==> skip sync\n")
        else:
            sync_tree(c)
        out = remote_deploy(c)
        if "HIGH_DEPLOY_DONE" not in out:
            emit("FAIL missing HIGH_DEPLOY_DONE\n")
            return 1
        if "ADMIN_BEGIN" in out:
            start = out.index("ADMIN_BEGIN")
            end = out.index("ADMIN_END") + len("ADMIN_END")
            emit("\n" + out[start:end] + "\n")
        return 0
    finally:
        c.close()


if __name__ == "__main__":
    raise SystemExit(main())
