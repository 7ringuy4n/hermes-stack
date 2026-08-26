# -*- coding: utf-8 -*-
"""Zalo simple-text latency SLO lab (SSH, batch 5 text pings only).

Env: ASSISTANT_SSH_HOST, ASSISTANT_SSH_USER, ASSISTANT_SSH_PASSWORD
Optional: ZALO_LATENCY_N (default 5), CHAT_TIMEOUT_S (default 120)
Reports: test/reports/run-zalo-latency/ (no host/account)
"""
from __future__ import annotations

import base64
import io
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import paramiko

sys.path.insert(0, str(Path(__file__).resolve().parent))
from sanitize import sanitize

if hasattr(sys.stdout, "buffer"):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

HOST = os.environ.get("ASSISTANT_SSH_HOST", "")
USER = os.environ.get("ASSISTANT_SSH_USER", "")
PW = os.environ.get("ASSISTANT_SSH_PASSWORD", "")
ROOT = Path(os.environ.get("ASSISTANT_REPO_ROOT", Path(__file__).resolve().parents[2]))
OUT = ROOT / "test" / "reports" / "run-zalo-latency"
N = int(os.environ.get("ZALO_LATENCY_N", "5"))
SLO_MS = int(os.environ.get("SIMPLE_MSG_SLO_MS", "5000"))
CHAT_TO = int(os.environ.get("CHAT_TIMEOUT_S", "120"))
esc = PW.replace("'", "'\\''")
ROWS: list[dict] = []


def ts() -> str:
    return datetime.now(timezone.utc).astimezone().strftime("%Y-%m-%d %H:%M:%S %z")


def note(name: str, status: str, detail: str = "") -> None:
    row = {"ts": ts(), "name": name, "status": status, "detail": sanitize(detail)[:800]}
    ROWS.append(row)
    print(f"[{row['ts']}] {name} | {status} | {row['detail'][:240]}", flush=True)


def connect():
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect(HOST, username=USER, password=PW, timeout=45, allow_agent=False, look_for_keys=False)
    return c


def sudo_bash(c, script: str, timeout: int = 1800) -> str:
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
        time.sleep(0.1)
    code = chan.recv_exit_status()
    text = sanitize("".join(buf))
    if code != 0:
        raise SystemExit(f"remote exit {code}: {text[-400:]}")
    return text


def percentile(ms: list[int], p: float) -> int:
    if not ms:
        return 0
    ms = sorted(ms)
    idx = min(len(ms) - 1, max(0, int(round((p / 100.0) * (len(ms) - 1)))))
    return ms[idx]


def main() -> int:
    if not HOST or not USER or not PW:
        print("SKIP: set ASSISTANT_SSH_HOST, ASSISTANT_SSH_USER, ASSISTANT_SSH_PASSWORD")
        return 0

    OUT.mkdir(parents=True, exist_ok=True)
    c = connect()
    script = f'''
set -euo pipefail
export LC_ALL=C.UTF-8
cd /opt/assistant
set -a; . ./.env; set +a
GW="${{GATEWAY_API_KEYS%%,*}}"
KEY="${{API_SERVER_KEY:-$GW}}"
export KEY N={N} CHAT_TO={CHAT_TO}
if [[ -z "$KEY" ]]; then
  echo 'RESULT:{{"status":"SKIP","reason":"no_api_server_key"}}'
  exit 0
fi
tmpdir=$(mktemp -d)
classify_one() {{
  i="$1"
  t0=$(date +%s%3N)
  code=$(curl -sS -m 25 -o "$tmpdir/cl-$i.json" -w "%{{http_code}}" \\
    -X POST "http://127.0.0.1:8096/v1/classify" \\
    -H "Content-Type: application/json" \\
    -d "{{\\"text\\":\\"ping $i xin chào\\",\\"timezone\\":\\"Asia/Ho_Chi_Minh\\"}}" || echo 000)
  t1=$(date +%s%3N)
  echo "classify $code $((t1-t0))" > "$tmpdir/k-$i.txt"
}}
send_one() {{
  i="$1"
  t0=$(date +%s%3N)
  code=$(curl -sS -m "$CHAT_TO" -o "$tmpdir/r-$i.json" -w "%{{http_code}}" \\
    -X POST "http://127.0.0.1:8080/v1/chat/completions" \\
    -H "Authorization: Bearer ${{KEY}}" -H "Content-Type: application/json" \\
    -d "{{\\"model\\":\\"hermes\\",\\"messages\\":[{{\\"role\\":\\"user\\",\\"content\\":\\"ping $i reply OK\\"}}],\\"max_tokens\\":8}}" || echo 000)
  t1=$(date +%s%3N)
  echo "text $code $((t1-t0))" > "$tmpdir/c-$i.txt"
}}
send_vi() {{
  i="$1"
  t0=$(date +%s%3N)
  code=$(curl -sS -m "$CHAT_TO" -o "$tmpdir/v-$i.json" -w "%{{http_code}}" \\
    -X POST "http://127.0.0.1:8080/v1/chat/completions" \\
    -H "Authorization: Bearer ${{KEY}}" -H "Content-Type: application/json" \\
    -d "{{\\"model\\":\\"hermes\\",\\"messages\\":[{{\\"role\\":\\"user\\",\\"content\\":\\"xin chào $i\\"}}],\\"max_tokens\\":16}}" || echo 000)
  t1=$(date +%s%3N)
  echo "vi $code $((t1-t0))" > "$tmpdir/vlat-$i.txt"
}}
for i in $(seq 1 $N); do send_one "$i"; done
for i in $(seq 1 $N); do send_vi "$i"; done
for i in $(seq 1 $N); do classify_one "$i"; done
echo "ROWS_BEGIN"
for i in $(seq 1 $N); do cat "$tmpdir/k-$i.txt" 2>/dev/null || echo "classify 000 0"; cat "$tmpdir/c-$i.txt" 2>/dev/null || echo "text 000 0"; cat "$tmpdir/vlat-$i.txt" 2>/dev/null || echo "vi 000 0"; done
echo "ROWS_END"
rm -rf "$tmpdir"
echo "RESULT:{{\\"status\\":\\"DONE\\",\\"n\\":$N}}"
'''
    out = sudo_bash(c, script, timeout=CHAT_TO * N * 3 + 90)
    latencies: list[int] = []
    classify_ms: list[int] = []
    vi_ms: list[int] = []
    http_codes: list[str] = []
    for line in out.splitlines():
        if line.strip() in {"ROWS_BEGIN", "ROWS_END"}:
            continue
        parts = line.split()
        if len(parts) >= 3 and parts[0] in {"text", "classify", "vi"}:
            if parts[0] == "text":
                http_codes.append(parts[1])
            if parts[2].isdigit():
                val = int(parts[2])
                if parts[0] == "text":
                    latencies.append(val)
                elif parts[0] == "classify":
                    classify_ms.append(val)
                else:
                    vi_ms.append(val)

    if not latencies:
        note("latency", "SKIP", "no samples")
        _write_report({"status": "SKIP"})
        return 0

    summary = {
        "n": len(latencies),
        "min_ms": min(latencies),
        "p50_ms": percentile(latencies, 50),
        "p95_ms": percentile(latencies, 95),
        "max_ms": max(latencies),
        "http_codes": http_codes,
        "classify_p50_ms": percentile(classify_ms, 50) if classify_ms else None,
        "classify_max_ms": max(classify_ms) if classify_ms else None,
        "vi_p50_ms": percentile(vi_ms, 50) if vi_ms else None,
        "vi_max_ms": max(vi_ms) if vi_ms else None,
    }
    note("latency", "RECORD", json.dumps(summary))

    fail = False
    if summary["max_ms"] > SLO_MS:
        note("slo", "FAIL", f"max {summary['max_ms']}ms > {SLO_MS}ms simple-message SLO")
        fail = True
    if summary["p95_ms"] > SLO_MS:
        note("slo", "FAIL", f"p95 {summary['p95_ms']}ms > {SLO_MS}ms simple-message SLO")
        fail = True
    if not fail:
        note("slo", "PASS", f"all samples <= {SLO_MS}ms")

    _write_report({"status": "FAIL" if fail else "PASS", "summary": summary})
    return 1 if fail else 0


def _write_report(payload: dict) -> None:
    payload["rows"] = ROWS
    path = OUT / f"latency-{datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')}.json"
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"report={path.relative_to(ROOT)}")


if __name__ == "__main__":
    raise SystemExit(main())
