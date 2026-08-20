# -*- coding: utf-8 -*-
"""Dual Hermes isolation lab: scale=2, concurrent admin injects via Zalo bridge.

Uses bridge POST /inject-event as the sole admin (real inbound path). Never opens a
second SSE client. Restores HERMES_REPLICAS after the run when HERMES_DUAL_RESTORE=1.

Env: ASSISTANT_SSH_HOST, ASSISTANT_SSH_USER, ASSISTANT_SSH_PASSWORD
Optional: HERMES_DUAL_RESTORE (default 1), HERMES_DUAL_WAIT_S (default 90)
Reports: test/reports/run-hermes-dual-isolation/ (no host/account)
"""
from __future__ import annotations

import base64
import json
import os
import sys
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

import paramiko

sys.path.insert(0, str(Path(__file__).resolve().parent))
from sanitize import sanitize

HOST = os.environ["ASSISTANT_SSH_HOST"]
USER = os.environ["ASSISTANT_SSH_USER"]
PW = os.environ["ASSISTANT_SSH_PASSWORD"]
ROOT = Path(os.environ.get("ASSISTANT_REPO_ROOT", Path(__file__).resolve().parents[2]))
OUT = ROOT / "test" / "reports" / "run-hermes-dual-isolation"
RESTORE = os.environ.get("HERMES_DUAL_RESTORE", "1").strip().lower() in {"1", "true", "yes", "on"}
WAIT_S = int(os.environ.get("HERMES_DUAL_WAIT_S", "90"))
esc = PW.replace("'", "'\\''")


def ts() -> str:
    return datetime.now(timezone.utc).astimezone().strftime("%Y-%m-%d %H:%M:%S %z")


def connect():
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect(HOST, username=USER, password=PW, timeout=30, allow_agent=False, look_for_keys=False)
    return c


def sudo_bash(c, script: str, timeout: int = 900) -> str:
    b64 = base64.b64encode(script.encode("utf-8")).decode("ascii")
    cmd = f"echo '{esc}' | sudo -S bash -lc \"echo {b64} | base64 -d | bash\""
    _i, o, e = c.exec_command(cmd, timeout=timeout, get_pty=True)
    chan = o.channel
    buf: list[str] = []
    while True:
        while chan.recv_ready():
            chunk = chan.recv(8192).decode("utf-8", "replace")
            sys.stdout.write(chunk)
            sys.stdout.flush()
            buf.append(chunk)
        while chan.recv_stderr_ready():
            chunk = chan.recv_stderr(8192).decode("utf-8", "replace")
            sys.stdout.write(chunk)
            sys.stdout.flush()
            buf.append(chunk)
        if chan.exit_status_ready() and not chan.recv_ready() and not chan.recv_stderr_ready():
            break
        time.sleep(0.05)
    code = chan.recv_exit_status()
    text = sanitize("".join(buf))
    if code != 0:
        raise SystemExit(f"remote exit {code}: {text[-800:]}")
    return text


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    tag = uuid.uuid4().hex[:8]
    c = connect()
    report: dict = {"ts": ts(), "tag": tag}

    prep = sudo_bash(
        c,
        r"""
set -euo pipefail
cd /opt/assistant
set -a; . ./.env; set +a
echo "PREV_REPLICAS=${HERMES_REPLICAS:-1}"
uid="${HERMES_UID:-1000}"; gid="${HERMES_GID:-1000}"
mkdir -p /data/assistant/media/inbound /data/assistant/media/out
chown -R "$uid:$gid" /data/assistant/media
chmod -R ug+rwX /data/assistant/media
chmod g+s /data/assistant/media /data/assistant/media/inbound /data/assistant/media/out
python3 - <<'PY'
from pathlib import Path
root = Path("/data/assistant/media/inbound")
(root / "dual_probe.txt").write_text("dual isolation probe text\n", encoding="utf-8")
(root / "dual_probe.pdf").write_bytes(b"%PDF-1.1\n1 0 obj<<>>endobj\ntrailer<<>>\n%%EOF\n")
print("fixtures_ok")
PY
curl -fsS -m 8 http://127.0.0.1:8787/health || echo '{"ok":false}'
""",
        timeout=120,
    )
    report["prep"] = sanitize(prep)[-1500:]
    prev = "1"
    for line in prep.splitlines():
        if line.startswith("PREV_REPLICAS="):
            prev = line.split("=", 1)[1].strip() or "1"
    report["prev_replicas"] = prev

    scale = sudo_bash(
        c,
        """
set -euo pipefail
cd /opt/assistant
set -a; . ./.env; set +a
if grep -q '^HERMES_REPLICAS=' .env; then
  sed -i 's/^HERMES_REPLICAS=.*/HERMES_REPLICAS=2/' .env
else
  echo 'HERMES_REPLICAS=2' >> .env
fi
set -a; . ./.env; set +a
export COMPOSE_PROGRESS=plain
bash run.sh up 2>&1 | tail -40
sleep 10
docker ps --filter name=hermes --format '{{.Names}} {{.Status}}'
echo HERMES_COUNT=$(docker ps -q --filter name=hermes | wc -l | tr -d ' ')
curl -fsS -m 8 http://127.0.0.1:8787/health || true
""",
        timeout=600,
    )
    report["scale"] = sanitize(scale)[-2500:]

    # Upload remote probe script via base64 to avoid quoting hell
    remote_py = f"""
import concurrent.futures, json, time, urllib.request
from pathlib import Path
admin_line = Path("/data/assistant/zalo_admin_users.txt").read_text(encoding="utf-8").splitlines()[0]
admin = admin_line.split("|")[0].strip()
assert admin, "no admin"
tag = {tag!r}
kinds = [
  ("hello", f"xin chào dual-{{tag}}-hello"),
  ("web", f"tìm trên web thời tiết Hồ Chí Minh hôm nay dual-{{tag}}-web"),
  ("txt", f"tạo file txt ghi nội dung: isolation probe dual-{{tag}}-txt rồi gửi lại"),
  ("ocr_txt", f"đọc file /opt/data/media/inbound/dual_probe.txt và tóm tắt dual-{{tag}}-ocr-txt"),
  ("ocr_pdf", f"OCR hoặc tóm tắt /opt/data/media/inbound/dual_probe.pdf dual-{{tag}}-ocr-pdf"),
]

def one(kind, text):
  body = json.dumps({{
    "type": "message",
    "payload": {{
      "text": text,
      "thread_id": admin,
      "thread_type": "user",
      "sender_id": admin,
      "sender_name": "admin",
      "chat_type": "user",
      "message_id": f"dual-{{kind}}-{{tag}}-{{int(time.time()*1000)}}",
    }},
  }}).encode()
  t0 = time.time()
  try:
    req = urllib.request.Request(
      "http://127.0.0.1:8787/inject-event",
      data=body,
      headers={{"Content-Type": "application/json"}},
      method="POST",
    )
    with urllib.request.urlopen(req, timeout=30) as r:
      raw = r.read().decode()
    return {{"kind": kind, "ok": True, "raw": raw[:200], "elapsed_s": round(time.time()-t0, 2)}}
  except Exception as e:
    return {{"kind": kind, "ok": False, "error": type(e).__name__ + ":" + str(e)[:120], "elapsed_s": round(time.time()-t0, 2)}}

results = []
with concurrent.futures.ThreadPoolExecutor(max_workers=len(kinds)) as ex:
  futs = [ex.submit(one, k, t) for k, t in kinds]
  for f in concurrent.futures.as_completed(futs):
    results.append(f.result())
print("INJECT_RESULTS", json.dumps(results, ensure_ascii=False))
"""
    py_b64 = base64.b64encode(remote_py.encode("utf-8")).decode("ascii")
    burst = sudo_bash(
        c,
        f"""
set -euo pipefail
echo {py_b64} | base64 -d > /tmp/dual_inject.py
python3 /tmp/dual_inject.py
sleep {WAIT_S}
echo '=== hermes logs ==='
for h in $(docker ps --format '{{{{.Names}}}}' | grep hermes); do
  echo "-- $h"
  docker logs --since 4m "$h" 2>&1 | grep -Ei 'Permission denied|/opt/data/media|dual-{tag}|SSE|zalo_owner|crash' | tail -50 || true
done
echo HERMES_COUNT=$(docker ps -q --filter name=hermes | wc -l | tr -d ' ')
curl -fsS -m 8 http://127.0.0.1:8787/health || true
for h in $(docker ps --format '{{{{.Names}}}}' | grep hermes); do
  docker exec "$h" sh -c 'touch /opt/data/media/inbound/_dual_w /opt/data/media/out/_dual_w && rm -f /opt/data/media/inbound/_dual_w /opt/data/media/out/_dual_w && echo media_ok' || echo media_fail
done
# abnormal scan siblings
docker logs --since 10m router-worker 2>&1 | grep -Ei 'error|fail|403|empty content' | tail -20 || true
docker logs --since 10m zalo-api 2>&1 | grep -Ei 'error|fail|traceback' | tail -15 || true
""",
        timeout=WAIT_S + 180,
    )
    report["burst"] = sanitize(burst)[-8000:]

    if RESTORE:
        restore = sudo_bash(
            c,
            f"""
set -euo pipefail
cd /opt/assistant
PREV={prev}
if grep -q '^HERMES_REPLICAS=' .env; then
  sed -i "s/^HERMES_REPLICAS=.*/HERMES_REPLICAS=$PREV/" .env
else
  echo "HERMES_REPLICAS=$PREV" >> .env
fi
set -a; . ./.env; set +a
bash run.sh up 2>&1 | tail -25
sleep 8
echo HERMES_COUNT=$(docker ps -q --filter name=hermes | wc -l | tr -d ' ')
docker ps --filter name=hermes --format '{{{{.Names}}}} {{{{.Status}}}}'
curl -fsS -m 8 http://127.0.0.1:8787/health || true
""",
            timeout=600,
        )
        report["restore"] = sanitize(restore)[-2000:]

    report["pass"] = {
        "inject_seen": "INJECT_RESULTS" in burst,
        "inject_all_ok": '"ok": false' not in burst.lower().replace(" ", "")
        and '"ok":false' not in burst.replace(" ", ""),
        "no_media_perm_denied": "Permission denied: /opt/data/media" not in burst
        and "Permission denied: '/opt/data/media" not in burst,
        "media_ok": "media_ok" in burst and "media_fail" not in burst,
        "hermes_scaled": "HERMES_COUNT=2" in scale or "HERMES_COUNT=2" in burst,
        "sse_single": '"sseClients":1' in burst.replace(" ", "") or '"sseClients": 1' in burst,
        "restored": (not RESTORE)
        or (f"HERMES_COUNT={prev}" in report.get("restore", ""))
        or prev == "2",
    }
    (OUT / "raw.json").write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    (OUT / "summary.md").write_text(
        "\n".join(
            [
                "# Dual Hermes isolation lab",
                "",
                f"- Timestamp: `{report['ts']}`",
                f"- Tag: `{tag}`",
                f"- Prev replicas: `{prev}`",
                f"- Pass flags: `{json.dumps(report['pass'])}`",
                "",
                "See `raw.json` for excerpts.",
                "",
            ]
        ),
        encoding="utf-8",
    )
    print(json.dumps(report["pass"], indent=2))
    c.close()
    return 0 if all(report["pass"].values()) else 1


if __name__ == "__main__":
    raise SystemExit(main())
