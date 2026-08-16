#!/usr/bin/env python3
"""High-profile VPS redeploy (no Grafana/Loki/Prometheus). Chunked SSH — avoid PS buffer hang.

Phases: destroy | sync | up | zalo-bridge | verify | smoke | credentials | all
Env: ASSISTANT_SSH_HOST, ASSISTANT_SSH_USER, ASSISTANT_SSH_PASSWORD, ASSISTANT_REPO_ROOT
"""
from __future__ import annotations

import argparse
import os
import sys
import time
from pathlib import Path

import paramiko

HOST = os.environ.get("ASSISTANT_SSH_HOST", "72.61.127.249")
USER = os.environ.get("ASSISTANT_SSH_USER", "tringuyen")
PASSWORD = os.environ.get("ASSISTANT_SSH_PASSWORD", "")
REPO = Path(os.environ.get("ASSISTANT_REPO_ROOT") or Path(__file__).resolve().parents[2])
REMOTE = "/opt/assistant"
DATA = "/data/assistant"

if not PASSWORD:
    raise SystemExit("Set ASSISTANT_SSH_PASSWORD (do not hardcode secrets in the repo).")

# Credentials expected after high install (from .env on host — printed, not invented)
SYNC_GLOBS = [
    "docker",
    "run.sh",
    "architect/backup-restore/lib/profile.sh",
    "architect/backup-restore/lib/common.sh",
    "architect/backup-restore/lib/backup.sh",
    "scripts/main/stack-watch.sh",
    "scripts/main/first-setup-9router-hermes.py",
    "scripts/main/setup-zalo.sh",
    "scripts/main/login-zalo.sh",
    "scripts/main/check-high.sh",
    "scripts/main/check-medium.sh",
    "hermes/main/docker/hermes-replica-entry.sh",
    "hermes/main/plugins/zalo",
    "hermes/main/skills/image-gen",
    "hermes/main/skills/media-out",
    "hermes/main/skills/file-gen",
    "hermes/main/skills/documents",
    "hermes/main/skills/markdown",
    "hermes/main/SOUL.md",
    "architect/models/dispatcher",
]


def connect() -> paramiko.SSHClient:
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect(HOST, username=USER, password=PASSWORD, timeout=45)
    return c


def run(c: paramiko.SSHClient, cmd: str, timeout: int = 600) -> tuple[int, str]:
    print(f">> {cmd[:200]}", flush=True)
    _, o, e = c.exec_command(cmd, timeout=timeout)
    out = (o.read() + e.read()).decode("utf-8", "replace")
    code = o.channel.recv_exit_status()
    if out:
        print(out[-6000:] if len(out) > 6000 else out, flush=True)
    if code != 0:
        raise RuntimeError(f"remote exit {code}: {cmd[:120]}")
    return code, out


def sudo(c: paramiko.SSHClient, cmd: str, timeout: int = 600) -> tuple[int, str]:
    esc = PASSWORD.replace("'", "'\\''")
    return run(c, f"echo '{esc}' | sudo -S bash -lc {repr(cmd)}", timeout=timeout)


def phase_destroy(c: paramiko.SSHClient) -> None:
    sudo(
        c,
        f"cd {REMOTE} && set -a && . ./.env 2>/dev/null; set +a; "
        f"export ASSISTANT_PROFILE=high; "
        f"if [ -f run.sh ]; then bash run.sh destroy || true; fi; "
        f"docker ps -aq | xargs -r docker rm -f || true; "
        f"docker network prune -f || true; "
        f"rm -rf {DATA}/config.yaml {DATA}/.env {DATA}/replicas {DATA}/sessions || true; "
        f"mkdir -p {DATA}/media/out; chown -R 1000:1000 {DATA} || true",
        timeout=300,
    )


def _sftp_put_tree(sftp: paramiko.SFTPClient, local: Path, remote: str) -> None:
    def ensure_dir(path: str) -> None:
        parts = path.strip("/").split("/")
        cur = ""
        for p in parts:
            cur += "/" + p
            try:
                sftp.stat(cur)
            except OSError:
                try:
                    sftp.mkdir(cur)
                except OSError:
                    pass

    if local.is_file():
        ensure_dir(str(Path(remote).parent).replace("\\", "/"))
        sftp.put(str(local), remote)
        return
    for root, _dirs, files in os.walk(local):
        rel = Path(root).relative_to(local)
        rdir = remote if str(rel) == "." else f"{remote}/{rel.as_posix()}"
        ensure_dir(rdir)
        for name in files:
            if name.endswith(".pyc") or name == "__pycache__":
                continue
            lp = Path(root) / name
            data = lp.read_bytes().replace(b"\r\n", b"\n").replace(b"\r", b"\n")
            tmp = f"/tmp/up_{os.getpid()}_{name}"
            with sftp.file(tmp, "wb") as f:
                f.write(data)
            ensure_dir(rdir)
            # move via later sudo batch — keep in staging map
            sftp.put(str(lp), f"{rdir}/{name}")


def phase_sync(c: paramiko.SSHClient) -> None:
    sftp = c.open_sftp()
    staging = f"/tmp/hermes_high_sync_{int(time.time())}"
    run(c, f"rm -rf {staging} && mkdir -p {staging}")
    for rel in SYNC_GLOBS:
        local = REPO / rel
        if not local.exists():
            print(f"skip missing {rel}", flush=True)
            continue
        print(f"sync {rel}", flush=True)
        _sftp_put_tree(sftp, local, f"{staging}/{rel}")
    sftp.close()
    sudo(
        c,
        f"mkdir -p {REMOTE} && cp -a {staging}/. {REMOTE}/ && "
        f"chown -R {USER}:{USER} {REMOTE} && rm -rf {staging} && "
        f"test -f {REMOTE}/docker/docker-compose.yml && test -f {REMOTE}/run.sh",
        timeout=120,
    )


def phase_up(c: paramiko.SSHClient) -> None:
    # Patch .env via SFTP (avoid nested bash quoting / CRLF issues)
    sftp = c.open_sftp()
    env_path = f"{REMOTE}/.env"
    try:
        with sftp.file(env_path, "r") as f:
            raw = f.read().decode("utf-8", "replace")
    except OSError:
        raw = ""
    lines = {k: v for k, v in (
        (ln.split("=", 1)[0].strip(), ln.split("=", 1)[1])
        for ln in raw.splitlines()
        if "=" in ln and not ln.strip().startswith("#")
    )}
    updates = {
        "ASSISTANT_PROFILE": "high",
        "HERMES_REPLICAS": "2",
        "ENABLE_ZALO": "1",
        "ENABLE_TRAEFIK": "1",
        "ENABLE_API_GATEWAY": "1",
        "ENABLE_GRAFANA": "0",
        "ENABLE_LOKI": "0",
        "ENABLE_PROMETHEUS": "0",
        "ENABLE_ALLOY": "0",
        "ENABLE_NOTIFY": "0",
        "ENABLE_ANTIVIRUS": "0",
        "ENABLE_CLOUDDRIVE": "0",
        "OFFICE_FILE_GEN": "1",
        "IMAGE_BACKENDS": "llm,vendor,comfy-cpu,comfy-gpu",
        "WEB_BACKENDS": "tavily,firecrawl",
        "ZALO_BRIDGE_URL": "http://zalo-proxy:8787",
        "ZALO_PLUGIN_URL": "http://zalo-proxy:8787",
        "GRAFANA_ADMIN_PASSWORD": lines.get("GRAFANA_ADMIN_PASSWORD") or "unused-monitor-off",
    }
    lines.update(updates)
    body = "\n".join(f"{k}={v}" for k, v in lines.items()) + "\n"
    tmp = "/tmp/assistant.env.new"
    with sftp.file(tmp, "w") as f:
        f.write(body.encode("utf-8"))
    sftp.close()
    sudo(c, f"cp {tmp} {env_path} && chmod 600 {env_path} && chown {USER}:{USER} {env_path}", timeout=30)
    for k, v in updates.items():
        print(f"  .env {k}={v}", flush=True)
    sudo(
        c,
        f"cd {REMOTE} && set -a && . ./.env && set +a && "
        f"export ASSISTANT_PROFILE=high HERMES_REPLICAS=2 "
        f"ENABLE_GRAFANA=0 ENABLE_LOKI=0 ENABLE_PROMETHEUS=0 ENABLE_ALLOY=0 "
        f"ENABLE_ZALO=1 ENABLE_TRAEFIK=1 ENABLE_API_GATEWAY=1 && "
        f"bash run.sh up",
        timeout=900,
    )


def phase_zalo_bridge(c: paramiko.SSHClient) -> None:
    # Bridge + proxy only; QR is manual (login-zalo.sh)
    sudo(
        c,
        f"cd {REMOTE} && set -a && . ./.env && set +a && "
        f"export ASSISTANT_PROFILE=high ENABLE_ZALO=1 && "
        f"bash scripts/main/setup-zalo.sh || true",
        timeout=600,
    )
    print(
        "\n=== MANUAL STEP REQUIRED ===\n"
        "On the VPS (or SSH), run QR login yourself:\n"
        f"  cd {REMOTE} && bash scripts/main/login-zalo.sh\n"
        "After scan succeeds, run: Deploy-High.ps1 -Phase verify\n",
        flush=True,
    )


def phase_verify(c: paramiko.SSHClient) -> None:
    run(c, "curl -sS http://127.0.0.1:8787/health || true")
    run(c, "docker ps --format 'table {{.Names}}\t{{.Status}}' | head -60")
    # Hermes ↔ 9router
    sudo(
        c,
        "docker exec $(docker ps -q -f name=assistant-hermes | head -1) "
        "sh -c 'wget -qO- http://9router:20128/v1/models 2>/dev/null | head -c 200 || "
        "curl -sS http://9router:20128/v1/models | head -c 200' || true",
        timeout=60,
    )
    # Image backends must not be empty on high
    sudo(
        c,
        "docker exec dispatcher sh -c 'echo IMAGE_BACKENDS=$IMAGE_BACKENDS; echo OFFICE=$OFFICE_FILE_GEN'",
        timeout=30,
    )
    run(c, "curl -sS http://127.0.0.1:8787/health")
    print("Zalo check: sseClients should be >=1 after QR login.", flush=True)


def phase_credentials(c: paramiko.SSHClient) -> None:
    _, out = run(
        c,
        f"set -a; . {REMOTE}/.env; set +a; "
        "echo ASSISTANT_PROFILE=$ASSISTANT_PROFILE; "
        "echo HERMES_REPLICAS=$HERMES_REPLICAS; "
        "echo HERMES_DASHBOARD_USER=$HERMES_DASHBOARD_USER; "
        "echo HERMES_DASHBOARD_PASSWORD=$HERMES_DASHBOARD_PASSWORD; "
        "echo HERMES_DASHBOARD_SECRET=$HERMES_DASHBOARD_SECRET; "
        "echo API_SERVER_KEY=$API_SERVER_KEY; "
        "echo N9ROUTER_INITIAL_PASSWORD=$N9ROUTER_INITIAL_PASSWORD; "
        "echo MEMORY_DB_PASSWORD=$MEMORY_DB_PASSWORD; "
        "echo ZALO_API_TOKEN=${ZALO_API_TOKEN:-$ADMIN_API_TOKEN}; "
        "echo GRAFANA_ADMIN_PASSWORD=${GRAFANA_ADMIN_PASSWORD:-(monitor disabled)}; "
        "echo ENABLE_GRAFANA=$ENABLE_GRAFANA ENABLE_LOKI=$ENABLE_LOKI ENABLE_PROMETHEUS=$ENABLE_PROMETHEUS",
    )
    print("\n=== ADMIN CREDENTIALS (from VPS .env) ===\n" + out, flush=True)


def phase_smoke(c: paramiko.SSHClient) -> None:
    """API-level smoke: text/image/office/web. Music/video should refuse."""
    tests = r"""
set -e
echo '== image =='
curl -sS -X POST http://127.0.0.1:8090/v1/image -H 'content-type: application/json' \
  -d '{"prompt":"red circle on white","filename":"smoke_img.png","refine":false}' | head -c 400
echo
echo '== send-file refuse music =='
curl -sS -o /tmp/m.json -w '%{http_code}' -X POST http://127.0.0.1:8090/v1/send-file \
  -H 'content-type: application/json' \
  -d '{"path":"/data/media/out/no.mp3","thread_id":"0","thread_type":"user"}' || true
echo
echo '== searxng weather =='
curl -sS 'http://127.0.0.1:8080/search?q=weather+Ho+Chi+Minh+City&format=json' | head -c 500
echo
echo '== concurrency hermes health x20 =='
for i in $(seq 1 20); do
  curl -sS -o /dev/null -w '%{http_code}\n' http://127.0.0.1:8088/health &
done
wait
echo done
"""
    run(c, tests, timeout=300)
    print(
        "Manual Hermes chat checks (after Zalo QR): ask for 1 text, pdf, txt, md, docx, xlsx, pptx, image; "
        "music/video should be refused; weather HCMC via web search.",
        flush=True,
    )


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--phase",
        default="all",
        choices=["all", "destroy", "sync", "up", "zalo-bridge", "verify", "smoke", "credentials"],
    )
    args = ap.parse_args()
    c = connect()
    try:
        order = {
            "destroy": [phase_destroy],
            "sync": [phase_sync],
            "up": [phase_up],
            "zalo-bridge": [phase_zalo_bridge],
            "verify": [phase_verify],
            "smoke": [phase_smoke],
            "credentials": [phase_credentials],
            "all": [
                phase_destroy,
                phase_sync,
                phase_up,
                phase_zalo_bridge,
                phase_credentials,
                phase_verify,
            ],
        }[args.phase]
        for fn in order:
            print(f"\n==== {fn.__name__} ====", flush=True)
            fn(c)
        return 0
    finally:
        c.close()


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as e:
        print(f"FATAL: {e}", file=sys.stderr, flush=True)
        raise SystemExit(1)
