# -*- coding: utf-8 -*-
"""Concurrent Zalo-like mix: Traefik text (API_SERVER_KEY) + dispatcher image gen. Record delay.

Env: ASSISTANT_SSH_HOST, ASSISTANT_SSH_USER, ASSISTANT_SSH_PASSWORD
Optional: ZALO_MEDIA_MAX (default 12), IMAGE_TIMEOUT_S (default 180)
Reports: test/reports/run-zalo-concurrent-media/ (no host/account)
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
OUT = ROOT / "test" / "reports" / "run-zalo-concurrent-media"
MAX_N = int(os.environ.get("ZALO_MEDIA_MAX", "12"))
IMG_TO = int(os.environ.get("IMAGE_TIMEOUT_S", "180"))
esc = PW.replace("'", "'\\''")


def ts() -> str:
    return datetime.now(timezone.utc).astimezone().strftime("%Y-%m-%d %H:%M:%S %z")


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
        raise SystemExit(f"remote exit {code}")
    return text


def fire_burst(c, n: int, tag: str) -> dict:
    script = f'''
set -euo pipefail
cd /opt/assistant
set -a; . ./.env; set +a
GW="${{GATEWAY_API_KEYS%%,*}}"
KEY="${{API_SERVER_KEY:-$GW}}"
export KEY N={n} TAG={tag} IMG_TO={IMG_TO}
if [[ -z "$KEY" ]]; then
  echo 'RESULT:{{"status":"SKIP","reason":"no_api_server_key"}}'
  exit 0
fi
tmpdir=$(mktemp -d)
fire() {{
  i="$1"
  kind="text"
  if (( i % 2 == 0 )); then kind="image"; fi
  t0=$(date +%s%3N)
  if [[ "$kind" == "text" ]]; then
    code=$(curl -sS -m 60 -o "$tmpdir/r-$i.json" -w "%{{http_code}}" \
      -X POST "http://127.0.0.1:8080/v1/chat/completions" \
      -H "Authorization: Bearer ${{KEY}}" -H "Content-Type: application/json" \
      -d "{{\\"model\\":\\"hermes\\",\\"messages\\":[{{\\"role\\":\\"user\\",\\"content\\":\\"$TAG text $i ping\\"}}],\\"max_tokens\\":16}}" || echo 000)
  else
    code=$(curl -sS -m "$IMG_TO" -o "$tmpdir/r-$i.json" -w "%{{http_code}}" \
      -X POST "http://127.0.0.1:8090/v1/image" \
      -H "Content-Type: application/json" \
      -d "{{\\"prompt\\":\\"tiny red square test $i\\",\\"refine\\":false,\\"filename\\":\\"zalo-c-$i.jpg\\"}}" || echo 000)
  fi
  t1=$(date +%s%3N)
  echo "$kind $code $((t1-t0))" > "$tmpdir/c-$i.txt"
}}
export -f fire
export tmpdir TAG IMG_TO KEY
seq 1 $N | xargs -P $N -I{{}} bash -c 'fire "$@"' _ {{}}
ok=0; fail=0
echo "ROWS_BEGIN"
for i in $(seq 1 $N); do
  line=$(cat "$tmpdir/c-$i.txt" 2>/dev/null || echo "miss 000 0")
  echo "$line"
  code=$(echo "$line" | awk '{{print $2}}')
  if [[ "$code" =~ ^2 ]]; then ok=$((ok+1)); else fail=$((fail+1)); fi
done
echo "ROWS_END"
rm -rf "$tmpdir"
echo "RESULT:{{\\"status\\":\\"DONE\\",\\"n\\":$N,\\"ok\\":$ok,\\"fail\\":$fail,\\"tag\\":\\"$TAG\\"}}"
'''
    out = sudo_bash(c, script, timeout=max(300, IMG_TO * n + 60))
    rows: list[dict] = []
    capture = False
    result = {"status": "ERROR", "detail": sanitize(out)[-400:]}
    for line in out.splitlines():
        if line.strip() == "ROWS_BEGIN":
            capture = True
            continue
        if line.strip() == "ROWS_END":
            capture = False
            continue
        if capture:
            parts = line.split()
            if len(parts) >= 3:
                rows.append(
                    {
                        "kind": parts[0],
                        "http": parts[1],
                        "latency_ms": int(parts[2]) if parts[2].isdigit() else parts[2],
                    }
                )
        if line.startswith("RESULT:"):
            result = json.loads(line[len("RESULT:") :])
    result["rows"] = rows
    return result


def stats(rows: list[dict], kind: str) -> dict:
    ms = [int(r["latency_ms"]) for r in rows if r.get("kind") == kind and str(r.get("latency_ms")).isdigit()]
    if not ms:
        return {"n": 0}
    ms.sort()

    def pct(p: float) -> int:
        idx = min(len(ms) - 1, max(0, int(round((p / 100) * (len(ms) - 1)))))
        return ms[idx]

    return {"n": len(ms), "p50_ms": pct(50), "p95_ms": pct(95), "max_ms": ms[-1], "min_ms": ms[0]}


def bridge_health(c) -> dict:
    out = sudo_bash(
        c,
        'curl -fsS -m 8 http://127.0.0.1:8787/health || echo \'{"ok":false}\'',
        timeout=60,
    )
    line = [x for x in out.strip().splitlines() if x.startswith("{")][-1]
    try:
        return json.loads(line)
    except json.JSONDecodeError:
        return {"ok": False, "raw": sanitize(out)[:200]}


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    c = connect()
    report: dict = {"ts": ts(), "bursts": [], "bridge_before": bridge_health(c)}
    last_ok = 0
    first_fail = None
    fail_mode = None
    for n in (2, 4, 8, 12):
        if n > MAX_N:
            break
        t0 = time.time()
        res = fire_burst(c, n, "zalo-media-a")
        res["elapsed_s"] = round(time.time() - t0, 2)
        res["text_delay"] = stats(res.get("rows") or [], "text")
        res["image_delay"] = stats(res.get("rows") or [], "image")
        report["bursts"].append(res)
        print("burst", sanitize(json.dumps({k: v for k, v in res.items() if k != "rows"})), flush=True)
        if res.get("status") == "SKIP":
            break
        if res.get("fail", 1) == 0 and res.get("ok", 0) == n:
            last_ok = n
        else:
            first_fail = n
            fail_mode = "http_non_2xx_or_timeout"
            break
        time.sleep(3)

    report["bridge_after"] = bridge_health(c)
    report["last_all_success_n"] = last_ok
    report["first_fail_n"] = first_fail
    report["fail_mode"] = fail_mode
    report["sse_ok"] = (
        report["bridge_after"].get("sseClients") == 1
        and report["bridge_after"].get("loggedIn") is True
    )
    (OUT / "raw.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    lines = [
        "# Zalo concurrent text + media generation",
        "",
        f"- Timestamp: `{report['ts']}`",
        f"- Last all-success N: **{last_ok}**",
        f"- First-fail N: **{first_fail if first_fail is not None else 'none ≤ max'}**",
        f"- Fail mode: `{fail_mode or 'n/a'}`",
        f"- SSE single owner after: **{report['sse_ok']}**",
        "",
        "## Bursts (delay)",
        "",
    ]
    for b in report["bursts"]:
        lines.append(
            f"- N={b.get('n')} ok={b.get('ok')} fail={b.get('fail')} "
            f"elapsed_s={b.get('elapsed_s')} text={b.get('text_delay')} image={b.get('image_delay')}"
        )
    (OUT / "SUMMARY.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("wrote", OUT, flush=True)
    c.close()


if __name__ == "__main__":
    main()
