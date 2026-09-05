# -*- coding: utf-8 -*-
"""Remote stack deploy helper (lab).

Env: ASSISTANT_SSH_HOST, ASSISTANT_SSH_USER, ASSISTANT_SSH_PASSWORD
Optional: ASSISTANT_REPO_ROOT
Optional flags (0/1, default 0 unless noted): ENABLE_ZALO, ENABLE_ANTIVIRUS,
  SECURITY_SANDBOX, SECURITY_LLM_JUDGE, ENABLE_LLM_JUDGE,
  ENABLE_OMNIROUTER, ENABLE_GRAFANA, ENABLE_LOKI, ENABLE_PROMETHEUS, ENABLE_ALLOY.
  Grafana=1 pairs Prometheus on (unless ENABLE_PROMETHEUS is set).
  Loki=1 pairs Alloy on (unless ENABLE_ALLOY is set).
Optional secret (host .env only, never logged): TAVILY_API_KEY.
Notify stays on for component lab alerting. OmniRouter defaults **on** (set ENABLE_OMNIROUTER=0 to force omni-router-only general chat).
Does not write secrets into test/reports. Does not run Zalo QR login.
"""
from __future__ import annotations

import base64
import io
import os
import re
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


def env_flag(name: str, default: str = "0") -> str:
    v = os.environ.get(name, default).strip().lower()
    return "1" if v in {"1", "true", "yes", "on"} else "0"


FLAG_ZALO = env_flag("ENABLE_ZALO")
FLAG_AV = env_flag("ENABLE_ANTIVIRUS")
FLAG_SANDBOX = env_flag("SECURITY_SANDBOX")
FLAG_JUDGE = env_flag("SECURITY_LLM_JUDGE")
FLAG_LLM_JUDGE = env_flag("ENABLE_LLM_JUDGE", FLAG_JUDGE)
FLAG_OMNI = env_flag("ENABLE_OMNIROUTER", "1")
FLAG_GRAFANA = env_flag("ENABLE_GRAFANA")
FLAG_LOKI = env_flag("ENABLE_LOKI")
# Pairing: Grafana starts Prometheus; Loki starts Alloy â€” unless the pair flag is set.
FLAG_PROM = env_flag("ENABLE_PROMETHEUS", FLAG_GRAFANA)
FLAG_ALLOY = env_flag("ENABLE_ALLOY", FLAG_LOKI)
_TAVILY_RAW = os.environ.get("TAVILY_API_KEY", "").strip()
if _TAVILY_RAW and not re.fullmatch(r"[A-Za-z0-9._-]+", _TAVILY_RAW):
    raise SystemExit("TAVILY_API_KEY rejected: unsafe characters")
FLAG_TAVILY = _TAVILY_RAW

SKIP_DIR = {
    ".git",
    "__pycache__",
    "node_modules",
    ".cursor",
    "hermes/temp",
    "scripts/temp",
    "test/reports",
    "Untitled",
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
    script = str(script or "").replace("\r\n", "\n").replace("\r", "\n")
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
    zalo = FLAG_ZALO
    av = FLAG_AV
    sandbox = FLAG_SANDBOX
    judge = FLAG_JUDGE
    llm_judge = FLAG_LLM_JUDGE
    omni = FLAG_OMNI
    grafana = FLAG_GRAFANA
    loki = FLAG_LOKI
    prom = FLAG_PROM
    alloy = FLAG_ALLOY
    tavily = FLAG_TAVILY
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
upsert ENABLE_ZALO {zalo}
upsert ENABLE_TELEGRAM 0
upsert ENABLE_TRAEFIK 1
upsert ENABLE_API_GATEWAY 1
upsert TRAEFIK_MODE local
upsert TRAEFIK_ACME_ENABLED 0
upsert ENABLE_MEDIA_FILE active
upsert WORKER_MEDIA_FILE active
upsert ENABLE_JOBS 1
upsert HERMES_WORKFLOW 1
upsert ZALO_WORKFLOW 1
upsert ENABLE_SEARXNG 1
upsert ENABLE_OPENBAO 1
upsert ENABLE_SECURITY 1
upsert ENABLE_SIEM 1
upsert ENABLE_POLICY 1
upsert ENABLE_AUTHZ 1
upsert ENABLE_MODEL_ROUTER 1
upsert ENABLE_NOTIFY 1
upsert ENABLE_OMNIROUTER {omni}
upsert OMNIROUTER_IMAGE diegosouzapw/omniroute:latest
upsert ENABLE_GRAFANA {grafana}
upsert ENABLE_LOKI {loki}
upsert ENABLE_PROMETHEUS {prom}
upsert ENABLE_ALLOY {alloy}
upsert ENABLE_LOG_ARCHIVE 1
upsert ENABLE_CLOUDDRIVE 0
upsert ENABLE_OPENVPN 0
upsert ENABLE_ANTIVIRUS {av}
upsert SECURITY_SANDBOX {sandbox}
upsert SECURITY_LLM_JUDGE {judge}
upsert ENABLE_LLM_JUDGE {llm_judge}
upsert SECURITY_YARA 1
upsert SECURITY_FAIL_CLOSED 1
upsert LEARN_REQUIRE_APPROVE 0
upsert OFFICE_FILE_GEN 1
if [[ -n "{tavily}" ]]; then
  upsert TAVILY_API_KEY {tavily}
fi
grep -q '^ASSISTANT_DATA_DIR=' .env || upsert ASSISTANT_DATA_DIR /data/assistant
grep -q '^HERMES_DATA_DIR=' .env || upsert HERMES_DATA_DIR /data/assistant
fill_if_empty GATEWAY_API_KEYS "$(rand)"
fill_if_empty API_SERVER_KEY "$(rand)"
fill_if_empty HERMES_DASHBOARD_USER admin
fill_if_empty GRAFANA_ADMIN_USER admin
if ! grep -qE '^ZALO_API_TOKEN=.+' .env && ! grep -qE '^ADMIN_API_TOKEN=.+' .env; then
  TOK=$(rand)
  upsert ZALO_API_TOKEN "$TOK"
  upsert ADMIN_API_TOKEN "$TOK"
fi
if ! grep -qE '^OMNIROUTER_INITIAL_PASSWORD=.+' .env; then
  N9PW=$(grep -E '^OMNIROUTER_INITIAL_PASSWORD=' .env | cut -d= -f2- || true)
  if [[ -n "$N9PW" ]]; then upsert OMNIROUTER_INITIAL_PASSWORD "$N9PW"; fi
fi
if [[ "{sandbox}" == "1" ]]; then
  upsert SECURITY_DOCKER_HOST tcp://docker-socket-proxy:2375
fi

echo "=== CLEAR OLD FILES ==="
rm -rf /tmp/assistant /tmp/assistant.env.new 2>/dev/null || true
rm -f /tmp/assistant-sync.tgz 2>/dev/null || true
docker rm -f grafana prometheus loki alloy omni-exporter node-exporter stack-exporter omni-exporter 2>/dev/null || true
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
  echo "=== SNAPSHOT SCHEDULES (keep through destroy) ==="
  mkdir -p /data/assistant/backups
  if [[ -f /opt/assistant/scripts/main/hermes-cron-share.sh ]]; then
    HERMES_DATA_DIR=/data/assistant bash /opt/assistant/scripts/main/hermes-cron-share.sh || true
  fi
  python3 - <<'PY'
import json
from pathlib import Path
p = Path("/data/assistant/cron/jobs.json")
n = 0
if p.is_file():
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
        jobs = data.get("jobs") if isinstance(data, dict) else data
        n = len(jobs) if isinstance(jobs, list) else 0
    except Exception:
        n = 0
print("HERMES_JOBS_BEFORE=" + str(n))
PY
  CRON_SNAP=/data/assistant/backups/.pre-destroy-hermes-cron.txt
  HERMES_CID=$(docker ps -q --filter name=hermes | head -1 || true)
  if [[ -n "$HERMES_CID" ]]; then
    docker exec "$HERMES_CID" hermes cron list > "$CRON_SNAP" 2>/dev/null || true
  fi
  systemctl list-timers 'assistant-*' --all --no-pager 2>/dev/null | head -20 || true

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
for i in $(seq 1 90); do
  ok=1
  curl -fsS -m 5 http://127.0.0.1:8080/health >/dev/null 2>&1 || ok=0
  if [[ "{grafana}" == "1" ]]; then
    curl -fsS -m 5 http://127.0.0.1:23000/api/health >/dev/null 2>&1 || ok=0
  fi
  if [[ "{zalo}" == "1" ]]; then
    curl -fsS -m 5 http://127.0.0.1:8100/health >/dev/null 2>&1 || ok=0
  fi
  if [[ "{av}" == "1" ]]; then
    curl -fsS -m 5 http://127.0.0.1:8098/health >/dev/null 2>&1 || ok=0
  fi
  [[ "$ok" == "1" ]] && break
  sleep 5
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
if [[ "{omni}" == "1" ]]; then curl -sS -m 10 http://127.0.0.1:20129/ || true; echo; fi
if [[ "{grafana}" == "1" ]]; then curl -sS -m 10 http://127.0.0.1:23000/api/health || true; echo; fi
curl -sS -m 10 http://127.0.0.1:8093/health || true
echo
if [[ "{av}" == "1" ]]; then curl -sS -m 10 http://127.0.0.1:8098/health || true; echo; fi
if [[ "{zalo}" == "1" ]]; then curl -sS -m 10 http://127.0.0.1:8100/health || true; echo; fi

echo "=== VERIFY SCHEDULES AFTER UP ==="
if [[ -f /opt/assistant/scripts/main/hermes-cron-share.sh ]]; then
  HERMES_DATA_DIR=/data/assistant bash /opt/assistant/scripts/main/hermes-cron-share.sh || true
fi
python3 - <<'PY'
import json
from pathlib import Path
p = Path("/data/assistant/cron/jobs.json")
n = 0
if p.is_file():
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
        jobs = data.get("jobs") if isinstance(data, dict) else data
        n = len(jobs) if isinstance(jobs, list) else 0
    except Exception:
        n = 0
print("HERMES_JOBS_AFTER=" + str(n))
print("CRON_PRESERVED=1" if n else "CRON_PRESERVED=empty")
PY
docker ps -q --filter name=hermes | xargs -r docker restart || true
for i in $(seq 1 24); do
  curl -fsS -m 5 http://127.0.0.1:8080/health >/dev/null 2>&1 && break
  sleep 5
done
systemctl list-timers 'assistant-*' --all --no-pager 2>/dev/null | head -20 || true

echo "=== CHECK HIGH ==="
set +e
bash run.sh check-security
check_rc=$?
set -e
docker ps --format '{{{{.Names}}}} {{{{.Status}}}}' | sort
echo CHECK_HIGH_RC=$check_rc

if [[ "{zalo}" == "1" ]]; then
  echo "=== SETUP ZALO (install only, no QR) ==="
  linger_uid=$(id -u {USER})
  loginctl enable-linger {USER} || true
  for i in $(seq 1 20); do
    [[ -S /run/user/${{linger_uid}}/bus ]] && break
    sleep 1
  done
  sudo -u {USER} -H env \
    XDG_RUNTIME_DIR=/run/user/${{linger_uid}} \
    DBUS_SESSION_BUS_ADDRESS=unix:path=/run/user/${{linger_uid}}/bus \
    ASSISTANT_SUDO_PASSWORD='{esc}' \
    ENABLE_ZALO=1 \
    bash {REMOTE}/scripts/main/setup-zalo.sh
  echo SETUP_ZALO_OK
  echo ZALO_NEED_QR=1
fi

echo "=== CLEAN SOURCE / TEMP ==="
rm -f /tmp/assistant-sync.tgz /tmp/hermes-skills.tgz /tmp/assistant.env.new
rm -rf /tmp/assistant
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
    "ENABLE_ZALO",
    "ENABLE_ANTIVIRUS",
    "SECURITY_SANDBOX",
    "SECURITY_LLM_JUDGE",
    "ENABLE_LLM_JUDGE",
    "SECURITY_YARA",
    "HERMES_DASHBOARD_USER",
    "HERMES_DASHBOARD_PASSWORD",
    "GRAFANA_ADMIN_USER",
    "GRAFANA_ADMIN_PASSWORD",
    "OMNIROUTER_INITIAL_PASSWORD",
    "OMNIROUTER_INITIAL_PASSWORD",
    "OPENBAO_DEV_ROOT_TOKEN",
]
print("ADMIN_BEGIN")
for k in keys:
    print(f"{{k}}={{env.get(k, '')}}")
print("TAVILY_PRESENT=" + ("1" if env.get("TAVILY_API_KEY") else "0"))
print("ADMIN_END")
PY

echo "=== POST CONNECT ==="
n9c=$(curl -sS -m 8 -o /dev/null -w '%{{http_code}}' http://127.0.0.1:20128/ || echo 000)
echo "omni-router_http=$n9c"
tr_ok=0
for i in $(seq 1 12); do
  if curl -fsS -m 8 http://127.0.0.1:8080/health >/dev/null 2>&1; then tr_ok=1; break; fi
  sleep 2
done
echo "traefik_ok=$tr_ok"
gw_ok=0
curl -fsS -m 8 http://127.0.0.1:8088/health >/dev/null 2>&1 && gw_ok=1 || true
echo "gateway_ok=$gw_ok"
python3 - <<'PY'
import json, urllib.request
try:
    h = json.load(urllib.request.urlopen("http://127.0.0.1:8090/health", timeout=8))
    keys = h.get("keys") or {{}}
    print("dispatcher_ok", h.get("ok"))
    print("dispatcher_tavily", bool(keys.get("tavily")))
except Exception as e:
    print("dispatcher_ok", False)
    print("dispatcher_tavily", False)
    print("dispatcher_err", type(e).__name__)
PY
hcount=$(docker ps --filter name=hermes --filter status=running --format '{{{{.Names}}}}' | wc -l | tr -d ' ')
echo "hermes_running=$hcount"
mon=$(docker ps --format '{{{{.Names}}}}' | grep -E '^(grafana|prometheus|loki|alloy)$' || true)
if [[ -z "$mon" ]]; then echo "monitor_off=1"; else echo "monitor_unexpected=$mon"; fi
echo POST_CONNECT_DONE

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
        if FLAG_ZALO == "1":
            emit("\nZALO_NEED_QR=1 â€” scan QR manually; this script does not run login-zalo.\n")
        return 0
    finally:
        c.close()


if __name__ == "__main__":
    raise SystemExit(main())

