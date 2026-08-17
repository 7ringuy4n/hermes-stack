# -*- coding: utf-8 -*-
"""v0.5.0 VPS: destroy → deploy Low/Med/High (no Grafana/Loki/Prom) → health checks.

Zalo: installs bridge/proxy only — QR login is MANUAL (prints instruction).
Does not enable OmniRouter unless OMNIROUTER_IMAGE is set in env.
"""
from __future__ import annotations

import base64
import os
import sys
import time
from pathlib import Path

import paramiko

HOST = os.environ["ASSISTANT_SSH_HOST"]
USER = os.environ["ASSISTANT_SSH_USER"]
PW = os.environ["ASSISTANT_SSH_PASSWORD"]
ROOT = Path(os.environ.get("ASSISTANT_REPO_ROOT", Path(__file__).resolve().parents[2]))
REMOTE_ROOT = "/opt/assistant"
esc = PW.replace("'", "'\\''")


def connect():
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect(HOST, username=USER, password=PW, timeout=30, allow_agent=False, look_for_keys=False)
    return c


def emit(chunk: str) -> None:
    try:
        sys.stdout.write(chunk)
    except UnicodeEncodeError:
        sys.stdout.buffer.write(chunk.encode("utf-8", "replace"))
    sys.stdout.flush()


def sudo_bash(c, script: str, timeout: int = 3600) -> str:
    b64 = base64.b64encode(script.encode("utf-8")).decode("ascii")
    cmd = f"echo '{esc}' | sudo -S bash -lc \"echo {b64} | base64 -d | bash\""
    print(f"\n=== remote ({timeout}s) ===", flush=True)
    _i, o, e = c.exec_command(cmd, timeout=timeout, get_pty=True)
    chan = o.channel
    buf = []
    while True:
        while chan.recv_ready():
            chunk = chan.recv(8192).decode("utf-8", "replace")
            emit(chunk)
            buf.append(chunk)
        while chan.recv_stderr_ready():
            chunk = chan.recv_stderr(8192).decode("utf-8", "replace")
            emit(chunk)
            buf.append(chunk)
        if chan.exit_status_ready() and not chan.recv_ready() and not chan.recv_stderr_ready():
            break
        time.sleep(0.2)
    code = chan.recv_exit_status()
    if code != 0:
        raise SystemExit(f"remote exit {code}")
    return "".join(buf)


def sync_tree(c):
    """Sync key changed paths (LF) via SFTP + install."""
    rels = [
        "architect/backup-restore/lib/profile.sh",
        "architect/backup-restore/lib/backup.sh",
        "architect/models/model-router",
        "architect/models/omni-router",
        "architect/memory/session/app.py",
        "architect/gateway/api-gateway/app.py",
        "architect/gateway/api-gateway/messages/en.json",
        "architect/tools/jobs/app.py",
        "docker/docker-compose.yml",
        "docker/docker-compose.edge.yml",
        "docker/README.md",
        "run.sh",
        "scripts/main/log-archive.sh",
        "scripts/main/export-ovpn-client.sh",
        "scripts/main/heal-zalo-sse.sh",
        "scripts/main/stack-watch.sh",
        "scripts/main/zalo-watch.sh",
        "docs/00-profiles.md",
        "docs/06-model-routing.md",
        "docs/MULTI_NODE.md",
        "docs/CHANGELOG.md",
        "docs/config/DEFAULTS.md",
    ]
    sftp = c.open_sftp()

    def walk(local: Path, remote_base: str):
        if local.is_file():
            yield local, remote_base
            return
        for p in local.rglob("*"):
            if p.is_file():
                rel = p.relative_to(local).as_posix()
                yield p, f"{remote_base}/{rel}"

    for rel in rels:
        local = ROOT / rel
        if not local.exists():
            print("skip missing", rel, flush=True)
            continue
        for lp, rp in walk(local, f"{REMOTE_ROOT}/{rel}"):
            data = lp.read_bytes()
            if lp.suffix in {".sh", ".py", ".yml", ".yaml", ".md", ".json", ".txt"} or lp.name in {"run.sh", "Dockerfile"}:
                try:
                    data = data.decode("utf-8").replace("\r\n", "\n").encode("utf-8")
                except UnicodeDecodeError:
                    pass
            tmp = f"/tmp/sync_{lp.name}"
            remote_dir = str(Path(rp).parent).replace("\\", "/")
            with sftp.file(tmp, "wb") as f:
                f.write(data)
            mode = "755" if lp.suffix == ".sh" or lp.name == "run.sh" else "644"
            sudo_bash(
                c,
                f"mkdir -p '{remote_dir}' && install -m {mode} '{tmp}' '{rp}' && rm -f '{tmp}' && echo OK {rp}",
                timeout=60,
            )
    sftp.close()


def patch_env(profile: str):
    return f"""
set -euo pipefail
ENVF=/data/assistant/.env
[[ -f "$ENVF" ]] || ENVF={REMOTE_ROOT}/.env
cp -a "$ENVF" "${{ENVF}}.bak.$(date +%s)" || true
python3 - <<'PY'
from pathlib import Path
import re
p = Path("/data/assistant/.env")
if not p.exists():
    p = Path("{REMOTE_ROOT}/.env")
text = p.read_text(encoding="utf-8")
vals = {{
  "ASSISTANT_PROFILE": "{profile}",
  "ENABLE_GRAFANA": "0",
  "ENABLE_LOKI": "0",
  "ENABLE_PROMETHEUS": "0",
  "ENABLE_ALLOY": "0",
  "ENABLE_TRAEFIK": "1",
  "ENABLE_API_GATEWAY": "1",
  "TRAEFIK_MODE": "local",
  "TRAEFIK_ACME_ENABLED": "0",
  "ENABLE_MODEL_ROUTER": "1",
  "ENABLE_OMNIROUTER": "0",
  "ENABLE_LOG_ARCHIVE": "1",
  "LOG_RETENTION_DAYS": "30",
  "ENABLE_ZALO": "1" if "{profile}" != "low" else "0",
  "GATEWAY_AUTH_ENABLED": "0",
}}
if "{profile}" == "high":
    vals["HERMES_REPLICAS"] = "2"
else:
    vals["HERMES_REPLICAS"] = "1"
for k, v in vals.items():
    line = f"{{k}}={{v}}"
    if re.search(rf"(?m)^{{re.escape(k)}}=", text):
        text = re.sub(rf"(?m)^{{re.escape(k)}}=.*$", line, text)
    else:
        text = text.rstrip() + "\\n" + line + "\\n"
p.write_text(text, encoding="utf-8")
print("patched", p, "profile={profile}")
PY
"""


def main():
    c = connect()
    print("connected", flush=True)
    sync_tree(c)

    # Destroy
    sudo_bash(
        c,
        f"""
set -euo pipefail
cd {REMOTE_ROOT}
bash run.sh destroy
docker ps -aq --filter label=com.docker.compose.project=assistant | xargs -r docker rm -f || true
echo DESTROY_OK
""",
        timeout=900,
    )

    notes = []
    for profile in ("low", "medium", "high"):
        sudo_bash(c, patch_env(profile), timeout=60)
        sudo_bash(
            c,
            f"""
set -euo pipefail
cd {REMOTE_ROOT}
export ASSISTANT_PROFILE={profile}
bash run.sh profile
bash run.sh up
sleep 20
echo "=== health {profile} ==="
curl -sf -m 5 http://127.0.0.1:20128/v1/models >/dev/null && echo nine_ok || echo nine_fail
curl -sf -m 5 http://127.0.0.1:8096/health || echo model_router_fail
curl -sf -m 5 http://127.0.0.1:8088/health || echo gw_fail
docker ps --format '{{{{.Names}}}} {{{{.Status}}}}' | head -n 40
# image backends check
grep -E '^IMAGE_BACKENDS=' /data/assistant/.env || true
""",
            timeout=2400,
        )
        notes.append(f"{profile}: up attempted")
        if profile != "high":
            sudo_bash(
                c,
                f"""
set -euo pipefail
cd {REMOTE_ROOT}
bash run.sh destroy
""",
                timeout=900,
            )

    # Zalo bridge (no QR)
    sudo_bash(
        c,
        f"""
set -euo pipefail
cd {REMOTE_ROOT}
export ENABLE_ZALO=1
if [[ -f scripts/main/setup-zalo.sh ]]; then
  bash scripts/main/setup-zalo.sh || true
fi
docker compose --project-directory {REMOTE_ROOT} -f docker/docker-compose.yml --profile zalo up -d zalo-proxy || true
echo
echo '==== MANUAL QR REQUIRED ===='
echo 'On VPS run: cd /opt/assistant && bash scripts/main/login-zalo.sh'
echo 'Then: ENABLE_ZALO=1 bash scripts/main/heal-zalo-sse.sh'
echo '============================'
""",
        timeout=300,
    )

    # Post high probes
    sudo_bash(
        c,
        r"""
set -euo pipefail
mkdir -p /opt/assistant/test
cat > /opt/assistant/test/NOTES.md <<'MD'
# v0.5.0 VPS test notes

Date: generated on host during Deploy-V050-Test

## Profiles exercised
- low → destroy
- medium → destroy
- high (final, monitor off)

## Flags
- ENABLE_GRAFANA/LOKI/PROMETHEUS/ALLOY=0
- TRAEFIK_MODE=local (fail-soft; no ACME domain on lab)
- HERMES_REPLICAS: low/med=1, high=2
- ENABLE_OMNIROUTER=0 (set image to enable)

## Zalo
- Bridge/proxy installed; **QR login is manual** via `login-zalo.sh`

## Follow-up tests (High)
- Concurrency: text, pdf, txt, md, docs, xlsx, pptx, image, music, video
- Web: weather Ho Chi Minh City
- Backup/restore round-trip + Zalo sseClients>=1
MD
echo WROTE_TEST_NOTES
curl -sf http://127.0.0.1:8096/health; echo
curl -sf http://127.0.0.1:8088/health; echo
docker ps --filter name=hermes --format '{{.Names}} {{.Status}}'
docker ps --filter name=model-router --format '{{.Names}} {{.Status}}'
docker ps --filter name=traefik --format '{{.Names}} {{.Status}}'
""",
        timeout=120,
    )
    c.close()
    print("\nV050_DEPLOY_PHASE_DONE", flush=True)
    print("NEXT: run login-zalo.sh manually on VPS, then concurrency + backup tests.", flush=True)


if __name__ == "__main__":
    main()
