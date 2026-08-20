# -*- coding: utf-8 -*-
"""Worker add/remove via add-components. Backup+verify first.

Env: ASSISTANT_SSH_HOST, ASSISTANT_SSH_USER, ASSISTANT_SSH_PASSWORD
Reports: test/reports/run-worker-switch/ (no host/account)
"""
from __future__ import annotations

import base64
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import paramiko

sys.path.insert(0, str(Path(__file__).resolve().parent))
from sanitize import sanitize

HOST = os.environ["ASSISTANT_SSH_HOST"]
USER = os.environ["ASSISTANT_SSH_USER"]
PW = os.environ["ASSISTANT_SSH_PASSWORD"]
ROOT = Path(os.environ.get("ASSISTANT_REPO_ROOT", Path(__file__).resolve().parents[2]))
OUT = ROOT / "test" / "reports" / "run-worker-switch"
esc = PW.replace("'", "'\\''")
ROWS: list[dict] = []


def ts() -> str:
    return datetime.now(timezone.utc).astimezone().strftime("%Y-%m-%d %H:%M:%S %z")


def note(name: str, status: str, detail: str = "") -> None:
    row = {"ts": ts(), "name": name, "status": status, "detail": sanitize(detail)[:600]}
    ROWS.append(row)
    print(f"[{row['ts']}] {name} | {status} | {row['detail'][:200]}", flush=True)


def connect():
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect(HOST, username=USER, password=PW, timeout=30, allow_agent=False, look_for_keys=False)
    return c


def sudo_bash(c, script: str, timeout: int = 1800) -> str:
    b64 = base64.b64encode(script.encode("utf-8")).decode("ascii")
    cmd = f"echo '{esc}' | sudo -S bash -lc \"echo {b64} | base64 -d | bash\""
    _i, o, e = c.exec_command(cmd, timeout=timeout, get_pty=True)
    chan = o.channel
    buf: list[str] = []
    while True:
        while chan.recv_ready():
            chunk = chan.recv(16384).decode("utf-8", "replace")
            sys.stdout.write(chunk)
            sys.stdout.flush()
            buf.append(chunk)
        while chan.recv_stderr_ready():
            chunk = chan.recv_stderr(16384).decode("utf-8", "replace")
            sys.stdout.write(chunk)
            sys.stdout.flush()
            buf.append(chunk)
        if chan.exit_status_ready() and not chan.recv_ready() and not chan.recv_stderr_ready():
            break
        time.sleep(0.15)
    code = chan.recv_exit_status()
    text = sanitize("".join(buf))
    if code != 0:
        raise SystemExit(f"remote exit {code}")
    return text


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    c = connect()
    out = sudo_bash(
        c,
        r'''
set -euo pipefail
cd /opt/assistant
set -a; . ./.env; set +a
export COMPOSE_PROGRESS=plain
export ENABLE_ZALO="${ENABLE_ZALO:-1}"

echo "=== WORKERS_BEFORE ==="
bash run.sh workers || true
echo "=== DRY_ADD_NOTIFY ==="
bash run.sh add-components WORKER_NOTIFY=active --dry-run

echo "=== FAIL_SWITCH_PROFILE ==="
set +e
bash run.sh switch-profile high; echo "SWITCH_PROFILE_RC=$?"
bash run.sh add-components NOT_A_REAL_FLAG=1; echo "ADD_BOGUS_RC=$?"
set -e

echo "=== EXISTING_FLAGS ==="
grep -E '^(WORKER_|ENABLE_ZALO|ENABLE_ANTIVIRUS|SECURITY_SANDBOX|SECURITY_LLM_JUDGE|TRAEFIK_MODE)=' .env || true

echo "=== ADD_NOTIFY ==="
bash run.sh add-components WORKER_NOTIFY=active --no-up
grep -E '^WORKER_NOTIFY=' .env || true
test -f "${BACKUP_DIR:-/data/assistant/backups}/PRE_CHANGE" && echo PRE_CHANGE_OK || echo PRE_CHANGE_MISS
STAMP=$(cat "${BACKUP_DIR:-/data/assistant/backups}/PRE_CHANGE" 2>/dev/null || true)
echo "STAMP=$STAMP"
if [[ -n "$STAMP" ]]; then
  test -f "${BACKUP_DIR:-/data/assistant/backups}/$STAMP/config/profile-options.env" && echo OPTIONS_FILE_OK || echo OPTIONS_FILE_MISS
  test -f "${BACKUP_DIR:-/data/assistant/backups}/$STAMP/config/env.sealed" && echo ENV_SEALED_OK || echo ENV_SEALED_MISS
fi
echo "=== UP_AFTER_ADD ==="
bash run.sh up
sleep 8
docker ps --format '{{{{.Names}}}}' | grep -E 'notify' && echo NOTIFY_UP || echo NOTIFY_MISS
docker ps --format '{{{{.Names}}}}' | grep -E 'zalo' | head -5

echo "=== REMOVE_NOTIFY ==="
bash run.sh add-components WORKER_NOTIFY=inactive --no-up
bash run.sh up
sleep 8
if docker ps --format '{{{{.Names}}}}' | grep -qE '^notify$'; then echo NOTIFY_STILL_UP; else echo NOTIFY_GONE; fi
grep -E '^ENABLE_ZALO=' .env || true
grep -E '^WORKER_SCHEDULE=' .env || true

echo "=== WORKERS_AFTER ==="
bash run.sh workers || true
curl -fsS -m 8 http://127.0.0.1:8787/health || echo '{"ok":false}'
echo
curl -fsS -m 8 http://127.0.0.1:8088/health || echo GW_FAIL
echo
echo WORKER_SWITCH_DONE
''',
        timeout=3600,
    )
    c.close()

    def has(token: str) -> bool:
        return token in out

    checks = [
        ("dry_add", has("DRY_RUN") and has("=== DRY_ADD_NOTIFY ===")),
        ("fail_switch_profile", has("SWITCH_PROFILE_RC=") and not has("SWITCH_PROFILE_RC=0")),
        ("fail_bogus_flag", has("ADD_BOGUS_RC=") and not has("ADD_BOGUS_RC=0")),
        ("archive_options", has("OPTIONS_FILE_OK") or has("PRE_CHANGE_OK")),
        ("add_notify", has("NOTIFY_UP")),
        ("remove_notify", has("NOTIFY_GONE")),
        ("existing_zalo", has("ENABLE_ZALO=1")),
        ("profile_removed_msg", has("Profile upgrade/downgrade is removed") or has("Enable workers with")),
    ]
    fails = 0
    for name, ok in checks:
        status = "pass" if ok else "fail"
        if not ok:
            fails += 1
        note(name, status, "ok" if ok else "missing marker")

    (OUT / "raw.txt").write_text(sanitize(out)[-12000:], encoding="utf-8")
    (OUT / "raw.json").write_text(json.dumps(ROWS, indent=2), encoding="utf-8")
    lines = ["# Worker switch (add/remove)", "", f"- Timestamp: `{ts()}`", ""]
    for r in ROWS:
        lines.append(f"- **{r['name']}**: {r['status']} — {r['detail'][:180]}")
    lines += ["", f"Final: **{'PASS' if fails == 0 else 'FAIL'}** ({fails} fail)"]
    (OUT / "SUMMARY.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("wrote", OUT, "fails", fails, flush=True)
    if fails:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
