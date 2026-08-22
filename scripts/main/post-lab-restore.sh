#!/usr/bin/env bash
# Post-lab restore: Zalo session, local Qwen, connectivity probes (AGENT_RULES §19).
# Run after final lab round before stopping the host.
# Usage: bash scripts/main/post-lab-restore.sh
set -euo pipefail

ROOT="${STACK_ROOT:-$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)}"
cd "$ROOT"
export ASSISTANT_SUDO_PASSWORD="${ASSISTANT_SUDO_PASSWORD:-}"
export ENABLE_ZALO=1

log() { echo "==> $*"; }
fail=0

log "1) local Qwen (Ollama)"
bash scripts/main/lab-enable-qwen-local.sh || fail=1

log "2) Zalo bridge + session"
for PRES in /home/tn/zalo-lab-preserve /home/tn/zalo-round3-preserve; do
  if [[ -f "${PRES}/credentials.json" ]]; then
    mkdir -p /data/assistant/zalo-session-backup
    cp -a "${PRES}/credentials.json" /data/assistant/zalo-session-backup/credentials.json
    chmod 600 /data/assistant/zalo-session-backup/credentials.json
    for f in zalo_admin_users.txt zalo_allowed_users.txt zalo_allowed_threads.txt; do
      src="${PRES}/${f}"
      # Skip files that look like credentials.json (corrupted preserve guard)
      if [[ -f "$src" ]] && [[ $(wc -c <"$src" 2>/dev/null || echo 9999) -lt 512 ]]; then
        cp -a "$src" /data/assistant/"${f}"
      fi
    done
    break
  fi
done
bash scripts/main/restore-zalo-session.sh 2>/dev/null || true
# Re-seed admin allowlist from postgres when text files missing/invalid
python3 - <<'PY' 2>/dev/null || true
import os, subprocess, sys
from pathlib import Path

def psql_rows(sql):
    pg = subprocess.check_output(["docker", "ps", "-q", "--filter", "name=^postgres$"], text=True).strip().split()
    if not pg:
        return []
    env = {}
    for line in Path("/opt/assistant/.env").read_text(encoding="utf-8", errors="replace").splitlines():
        s = line.strip()
        if not s or s.startswith("#") or "=" not in s:
            continue
        k, v = s.split("=", 1)
        env[k.strip()] = v.strip().strip('"').strip("'")
    u = env.get("MEMORY_DB_USER", "hermes")
    d = env.get("MEMORY_DB_NAME", "hermes_memory")
    cmd = ["docker", "exec", pg[0], "psql", "-U", u, "-d", d, "-t", "-A", "-c", sql]
    out = subprocess.check_output(cmd, text=True, errors="replace")
    rows = []
    for line in out.strip().splitlines():
        parts = line.split("|")
        if len(parts) >= 2 and parts[0].strip():
            rows.append((parts[0].strip(), parts[1].strip()))
    return rows

admins = psql_rows("SELECT id, COALESCE(NULLIF(name,''),'Tn') FROM zalo_entities WHERE kind='admin' LIMIT 5")
if admins:
    body = "\n".join(f"{uid}|{name}" for uid, name in admins) + "\n"
    Path("/data/assistant/zalo_admin_users.txt").write_text(body, encoding="utf-8")
    print("ADMIN_SEED_OK", len(admins))
PY
bash scripts/main/setup-zalo.sh 2>&1 | tail -20

log "3) health matrix"
curl -fsS -m 8 http://127.0.0.1:8787/health && echo || { echo "FAIL bridge"; fail=1; }
TOK=$(grep ^ZALO_API_TOKEN= .env 2>/dev/null | cut -d= -f2- || true)
[[ -n "$TOK" ]] && curl -fsS -m 8 -H "Authorization: Bearer ${TOK}" http://127.0.0.1:8100/v1/zalo/admin && echo || echo "WARN zalo-api admin"
curl -fsS -m 8 http://127.0.0.1:8096/health && echo || { echo "FAIL model-router"; fail=1; }

log "4) Qwen preflight"
if [[ -f test/scripts/qwen_combo_preflight.py ]]; then
  python3 - <<'PY' 2>&1 | tail -15 || fail=1
import json, os, sqlite3, glob, sys
from pathlib import Path
env = {}
for line in Path("/opt/assistant/.env").read_text(encoding="utf-8", errors="replace").splitlines():
    s = line.strip()
    if not s or s.startswith("#") or "=" not in s:
        continue
    k, v = s.split("=", 1)
    env[k.strip()] = v.strip().strip('"').strip("'")
enable = env.get("ENABLE_QWEN", "0") == "1"
key = any(env.get(k, "").strip() for k in ("QWEN_API_KEY", "DASHSCOPE_API_KEY", "ALIBABA_API_KEY"))
ollama = bool(env.get("OLLAMA_BASE_URL", "").strip() and env.get("OLLAMA_MODEL", "").strip())
dbs = glob.glob("/var/lib/docker/volumes/*omni*/_data/storage.sqlite")
h = cl = None
if dbs:
    c = sqlite3.connect(dbs[0])
    c.row_factory = sqlite3.Row
    for row in c.execute("select name,data from combos"):
        if row["name"] not in ("hermes", "classifier"):
            continue
        data = json.loads(row["data"] or "{}")
        models = data.get("models") or data.get("members") or []
        if row["name"] == "hermes":
            h = len(models)
        else:
            cl = len(models)
print("COMBO_HERMES", h)
print("COMBO_CLASSIFIER", cl)
if not enable:
    print("RESULT PASS_QWEN_OFF"); sys.exit(0)
if not key and not ollama:
    if (h or 0) >= 1 and (cl or 0) >= 1:
        print("RESULT PASS_QWEN_READY"); sys.exit(0)
    print("RESULT QWEN_COMBOS_EMPTY"); sys.exit(2)
if (h or 0) < 1 or (cl or 0) < 1:
    print("RESULT FAIL_EMPTY_COMBOS"); sys.exit(1)
print("RESULT PASS_QWEN_READY")
PY
fi

log "5) router chat smoke"
if ! curl -fsS -m 120 -X POST http://127.0.0.1:8096/v1/chat/completions \
  -H 'Content-Type: application/json' \
  -d '{"model":"hermes","messages":[{"role":"user","content":"OK"}],"max_tokens":8}' \
  | grep -q '"content"'; then
  echo "FAIL router chat"
  fail=1
fi

log "6) Hermes + router-worker tail (abnormal)"
docker logs --tail 30 assistant-hermes-1 2>&1 | grep -iE 'error|deception_hide|crash' || echo "hermes: no critical tail"
docker logs --tail 20 router-worker 2>&1 | grep -iE 'Unable to determine|failover' | tail -5 || true

if [[ "$fail" -eq 0 ]]; then
  echo "POST_LAB_RESTORE_OK"
  exit 0
fi
echo "POST_LAB_RESTORE_WARN (see above)"
exit 1
