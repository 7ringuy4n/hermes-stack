# -*- coding: utf-8 -*-
"""Upgrade/downgrade + existing/add/remove options. Archives config stamps.

Env: ASSISTANT_SSH_HOST, ASSISTANT_SSH_USER, ASSISTANT_SSH_PASSWORD
Optional: PROFILE_SWITCH_FULL=1 to run full backup (default: BACKUP_COMPONENTS=config)
Reports: test/reports/run-profile-switch/ (no host/account)
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
OUT = ROOT / "test" / "reports" / "run-profile-switch"
FULL = os.environ.get("PROFILE_SWITCH_FULL", "0").strip() in {"1", "true", "yes"}
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
    comps = "" if FULL else "export BACKUP_COMPONENTS=config"
    c = connect()
    out = sudo_bash(
        c,
        rf'''
set -euo pipefail
cd /opt/assistant
set -a; . ./.env; set +a
{comps}
export COMPOSE_PROGRESS=plain
export ASSISTANT_PROFILE="${{ASSISTANT_PROFILE:-high}}"
export ENABLE_ZALO="${{ENABLE_ZALO:-1}}"

echo "=== PROFILE_BEFORE ==="
bash run.sh profile || true
echo "=== DRY_SWITCH ==="
bash run.sh switch-profile high --dry-run
echo "=== DRY_ADD ==="
bash run.sh add-components ENABLE_NOTIFY=1 --dry-run

echo "=== FAIL_SWITCH_BOGUS ==="
set +e
bash run.sh switch-profile bogus; echo "SWITCH_BOGUS_RC=$?"
bash run.sh add-components NOT_A_REAL_FLAG=1; echo "ADD_BOGUS_RC=$?"
set -e

echo "=== EXISTING_FLAGS ==="
grep -E '^(ASSISTANT_PROFILE|ENABLE_ZALO|ENABLE_ANTIVIRUS|SECURITY_SANDBOX|SECURITY_LLM_JUDGE|TRAEFIK_MODE)=' .env || true

echo "=== ADD_NOTIFY ==="
bash run.sh add-components ENABLE_NOTIFY=1 --no-up
grep -E '^ENABLE_NOTIFY=' .env || true
test -f "${{BACKUP_DIR:-/data/assistant/backups}}/PRE_CHANGE" && echo PRE_CHANGE_OK || echo PRE_CHANGE_MISS
STAMP=$(cat "${{BACKUP_DIR:-/data/assistant/backups}}/PRE_CHANGE" 2>/dev/null || true)
echo "STAMP=$STAMP"
if [[ -n "$STAMP" ]]; then
  test -f "${{BACKUP_DIR:-/data/assistant/backups}}/$STAMP/config/profile-options.env" && echo OPTIONS_FILE_OK || echo OPTIONS_FILE_MISS
  test -f "${{BACKUP_DIR:-/data/assistant/backups}}/$STAMP/config/env.sealed" && echo ENV_SEALED_OK || echo ENV_SEALED_MISS
fi
echo "=== UP_AFTER_ADD ==="
bash run.sh up
sleep 8
docker ps --format '{{{{.Names}}}}' | grep -E 'notify' && echo NOTIFY_UP || echo NOTIFY_MISS
docker ps --format '{{{{.Names}}}}' | grep -E 'zalo' | head -5

echo "=== REMOVE_NOTIFY ==="
bash run.sh add-components ENABLE_NOTIFY=0 --no-up
bash run.sh up
sleep 8
if docker ps --format '{{{{.Names}}}}' | grep -qE '^notify$'; then echo NOTIFY_STILL_UP; else echo NOTIFY_GONE; fi
docker ps --format '{{{{.Names}}}}' | grep -qE '^alert-watch$' && echo ALERT_STILL || echo ALERT_GONE
grep -E '^ENABLE_ZALO=' .env || true

echo "=== DOWNGRADE_MEDIUM ==="
bash run.sh switch-profile medium --no-up
grep -E '^ASSISTANT_PROFILE=' .env
bash run.sh up
sleep 10
echo "=== MEDIUM_PS ==="
docker ps --format '{{{{.Names}}}}' | sort
docker ps --format '{{{{.Names}}}}' | grep -qE '^openbao$' && echo OPENBAO_STILL || echo OPENBAO_GONE
docker ps --format '{{{{.Names}}}}' | grep -qE '^authz$' && echo AUTHZ_STILL || echo AUTHZ_GONE
docker ps --format '{{{{.Names}}}}' | grep -qE '^ocr$' && echo OCR_OK || echo OCR_MISS
docker ps --format '{{{{.Names}}}}' | grep -qE '^zalo-api$' && echo ZALO_OK || echo ZALO_MISS
grep -E '^ENABLE_ZALO=' .env || true
hermes_n=$(docker ps --format '{{{{.Names}}}}' | grep -c hermes || true)
echo "HERMES_N=$hermes_n"

echo "=== UPGRADE_HIGH ==="
bash run.sh switch-profile high --no-up
grep -E '^ASSISTANT_PROFILE=' .env
bash run.sh up
sleep 12
echo "=== HIGH_PS ==="
docker ps --format '{{{{.Names}}}}' | sort
docker ps --format '{{{{.Names}}}}' | grep -qE '^openbao$' && echo OPENBAO_BACK || echo OPENBAO_MISS
docker ps --format '{{{{.Names}}}}' | grep -qE '^authz$' && echo AUTHZ_BACK || echo AUTHZ_MISS
docker ps --format '{{{{.Names}}}}' | grep -qE '^security-manager$' && echo SEC_BACK || echo SEC_MISS
hermes_n=$(docker ps --format '{{{{.Names}}}}' | grep -c hermes || true)
echo "HERMES_N=$hermes_n"
grep -E '^(ASSISTANT_PROFILE|ENABLE_ZALO|ENABLE_NOTIFY|ENABLE_ANTIVIRUS|SECURITY_SANDBOX|SECURITY_LLM_JUDGE|TRAEFIK_MODE)=' .env || true
curl -fsS -m 8 http://127.0.0.1:8787/health || echo '{{"ok":false}}'
echo
curl -fsS -m 8 http://127.0.0.1:8088/health || echo GW_FAIL
echo
echo PROFILE_SWITCH_DONE
''',
        timeout=3600,
    )
    c.close()

    def has(token: str) -> bool:
        return token in out

    checks = [
        ("dry_switch", has("DRY_RUN") and has("=== DRY_SWITCH ===")),
        ("fail_bogus_profile", has("SWITCH_BOGUS_RC=") and not has("SWITCH_BOGUS_RC=0")),
        ("fail_bogus_flag", has("ADD_BOGUS_RC=") and not has("ADD_BOGUS_RC=0")),
        ("archive_options", has("OPTIONS_FILE_OK") or has("PRE_CHANGE_OK")),
        ("add_notify", has("NOTIFY_UP")),
        ("remove_notify", has("NOTIFY_GONE")),
        ("existing_zalo", has("ENABLE_ZALO=1")),
        ("downgrade_openbao_gone", has("OPENBAO_GONE")),
        ("downgrade_ocr", has("OCR_OK")),
        ("downgrade_zalo", has("ZALO_OK")),
        ("upgrade_openbao", has("OPENBAO_BACK")),
        ("upgrade_authz", has("AUTHZ_BACK")),
        ("upgrade_security", has("SEC_BACK")),
    ]
    fails = 0
    for name, ok in checks:
        # dry_switch: script prints DRY_RUN from run.sh
        status = "pass" if ok else "fail"
        if not ok:
            fails += 1
        note(name, status, "ok" if ok else "missing marker")

    # Hermes×2 after upgrade: HERMES_N last occurrence
    hermes_ns = [ln for ln in out.splitlines() if ln.startswith("HERMES_N=")]
    last_h = hermes_ns[-1] if hermes_ns else "HERMES_N=0"
    h_ok = last_h.strip() in {"HERMES_N=2", "HERMES_N=3"}  # 2 replicas; allow stray name
    if last_h.strip() == "HERMES_N=2":
        note("upgrade_hermes_x2", "pass", last_h)
    else:
        # assistant-hermes-1/2 counts as 2
        note("upgrade_hermes_x2", "pass" if last_h.endswith("=2") else "fail", last_h)
        if not last_h.endswith("=2"):
            fails += 1

    (OUT / "raw.txt").write_text(sanitize(out)[-12000:], encoding="utf-8")
    (OUT / "raw.json").write_text(json.dumps(ROWS, indent=2), encoding="utf-8")
    lines = ["# Profile switch (upgrade/downgrade + options)", "", f"- Timestamp: `{ts()}`", ""]
    for r in ROWS:
        lines.append(f"- **{r['name']}**: {r['status']} — {r['detail'][:180]}")
    lines += ["", f"Final: **{'PASS' if fails == 0 else 'FAIL'}** ({fails} fail)"]
    (OUT / "SUMMARY.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("wrote", OUT, "fails", fails, flush=True)
    if fails:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
