#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""VPS lab: OpenBao KV store / update / scrub / load fill (case 43).

Never prints secret values — only key names and pass/fail.
"""
from __future__ import annotations

import io
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from deploy_stack import connect, sudo_bash  # noqa: E402

if hasattr(sys.stdout, "buffer"):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

ROOT = Path(os.environ.get("ASSISTANT_REPO_ROOT", Path(__file__).resolve().parents[2]))
OUT = ROOT / "test" / "reports" / "run-openbao-kv"
MARKER = f"lab-openbao-{int(time.time())}"


def ts() -> str:
    return datetime.now(timezone.utc).astimezone().strftime("%Y-%m-%d %H:%M:%S %z")


def _clean(text: str) -> str:
    lines = []
    for ln in (text or "").splitlines():
        s = ln.strip()
        if not s:
            continue
        low = s.lower()
        if "sudo" in low and "password" in low:
            continue
        if low.startswith("[sudo"):
            continue
        lines.append(s)
    return "\n".join(lines)


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    report: dict = {"ts": ts(), "checks": [], "verdict": "FAIL"}
    c = connect()
    remote = r"""
set -euo pipefail
cd /opt/assistant
python3 - <<'PY'
import json, os, subprocess, sys, urllib.request
from pathlib import Path

sys.path.insert(0, "/opt/assistant/scripts/main")
from openbao_common import ENV_SCRUB_KEYS, SEED_KEYS

ROOT = Path("/opt/assistant")
ENV = ROOT / ".env"
DATA = Path(os.environ.get("ASSISTANT_DATA_DIR") or "/data/assistant")
EXPORT = DATA / ".env.openbao"
MARKER = os.environ.get("OPENBAO_LAB_MARKER") or "lab-marker"

def load_env(path):
    out = {}
    if not path.is_file():
        return out
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        s = line.strip()
        if not s or s.startswith("#") or "=" not in s:
            continue
        k, _, v = s.partition("=")
        out[k.strip()] = v.strip().strip("'").strip('"')
    return out

env = load_env(ENV)
token_file = Path(os.environ.get("OPENBAO_TOKEN_FILE") or "/data/assistant/openbao/root-token")
token = (os.environ.get("OPENBAO_DEV_ROOT_TOKEN") or env.get("OPENBAO_DEV_ROOT_TOKEN") or "").strip()
if not token and token_file.is_file():
    token = token_file.read_text(encoding="utf-8", errors="replace").strip()
addr = (os.environ.get("OPENBAO_ADDR") or "http://127.0.0.1:8200").rstrip("/")
path = "secret/data/assistant/api-keys"
checks = []

def note(name, ok, detail=""):
    checks.append({"name": name, "ok": bool(ok), "detail": detail[:200]})
    print(("PASS" if ok else "FAIL"), name, detail[:120])

if not token or token.startswith("CHANGE_ME"):
    note("token", False, "OpenBao bootstrap token missing")
    print(json.dumps({"checks": checks}))
    raise SystemExit(2)

def kv_get():
    req = urllib.request.Request(
        f"{addr}/v1/{path}",
        headers={"X-Vault-Token": token},
        method="GET",
    )
    with urllib.request.urlopen(req, timeout=15) as resp:
        got = json.loads(resp.read().decode() or "{}")
    data = ((got.get("data") or {}).get("data") or {})
    return data if isinstance(data, dict) else {}

def kv_put(data):
    body = json.dumps({"data": data}).encode()
    req = urllib.request.Request(
        f"{addr}/v1/{path}",
        data=body,
        headers={"X-Vault-Token": token, "Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=15) as resp:
        resp.read()

try:
    data = kv_get()
except Exception as e:
    note("kv_get", False, type(e).__name__)
    print(json.dumps({"checks": checks}))
    raise SystemExit(2)

note("store_omni", "OMNIROUTER_API_KEY" in data and bool(str(data.get("OMNIROUTER_API_KEY") or "").strip()),
     f"keys={len(data)}")
note("seed_list_pollinations", "POLLINATIONS_API_KEY" in SEED_KEYS)

# Update marker key then verify read-back
data2 = dict(data)
data2["LAB_OPENBAO_MARKER"] = MARKER
original_tavily = data2.get("TAVILY_API_KEY")
data2["TAVILY_API_KEY"] = MARKER
kv_put(data2)
got = kv_get()
note("update_propagate", got.get("LAB_OPENBAO_MARKER") == MARKER, "marker roundtrip")

# Scrub plaintext
import importlib.util
spec = importlib.util.spec_from_file_location(
    "scrub", "/opt/assistant/scripts/main/scrub-plaintext-env.py"
)
scrub = importlib.util.module_from_spec(spec)
spec.loader.exec_module(scrub)
rc = scrub.main()
note("scrub_rc", rc == 0, f"rc={rc}")
note("scrub_export_gone", not EXPORT.is_file(), str(EXPORT))
env_after = load_env(ENV)
empty_hosts = [k for k in ENV_SCRUB_KEYS if not str(env_after.get(k) or "").strip()]
note("scrub_host_keys_empty", len(empty_hosts) >= 1, f"empty={len(empty_hosts)}")
note("token_external", token_file.is_file() and "OPENBAO_DEV_ROOT_TOKEN" not in env_after)

# Load refill
spec2 = importlib.util.spec_from_file_location(
    "loadbao", "/opt/assistant/scripts/main/load-openbao-env.py"
)
loadbao = importlib.util.module_from_spec(spec2)
spec2.loader.exec_module(loadbao)
rc2 = loadbao.main()
note("load_rc", rc2 == 0, f"rc={rc2}")
note("load_export_back", EXPORT.is_file())
env_fill = load_env(ENV)
runtime_fill = load_env(EXPORT)
note("load_repo_env_unchanged", not str(env_fill.get("TAVILY_API_KEY") or "").strip())
note("load_runtime_rotation", runtime_fill.get("TAVILY_API_KEY") == MARKER)

# The sync command must import the transient export into Compose, recreate the
# consumers, and scrub both disk copies afterward.
sync = subprocess.run(
    ["bash", "run.sh", "sync-openbao-env"],
    cwd=ROOT,
    capture_output=True,
    text=True,
    timeout=420,
)
note("sync_rc", sync.returncode == 0, f"rc={sync.returncode}")
inspect = subprocess.run(
    ["docker", "inspect", "model-router", "--format", "{{json .Config.Env}}"],
    capture_output=True,
    text=True,
    timeout=30,
)
try:
    router_env = json.loads(inspect.stdout or "[]")
except Exception:
    router_env = []
note("consumer_fetched_rotated_key", f"TAVILY_API_KEY={MARKER}" in router_env)
note("sync_scrub_export_gone", not EXPORT.is_file())
note("sync_repo_env_clean", not str(load_env(ENV).get("TAVILY_API_KEY") or "").strip())

# Drop lab marker from KV (cleanup)
final = kv_get()
final.pop("LAB_OPENBAO_MARKER", None)
if original_tavily is None:
    final.pop("TAVILY_API_KEY", None)
else:
    final["TAVILY_API_KEY"] = original_tavily
kv_put(final)
note("cleanup_marker", "LAB_OPENBAO_MARKER" not in kv_get())

# Final scrub proves plaintext is gone; then restore compose fill for ops continuity.
restore = subprocess.run(
    ["bash", "run.sh", "sync-openbao-env"],
    cwd=ROOT,
    capture_output=True,
    text=True,
    timeout=420,
)
note("ops_restore_sync", restore.returncode == 0, f"rc={restore.returncode}")
note("final_scrub_export_gone", not EXPORT.is_file())

ok = all(x["ok"] for x in checks)
print("VERDICT", "PASS" if ok else "FAIL")
print(json.dumps({"checks": checks, "ok": ok}))
raise SystemExit(0 if ok else 1)
PY
"""
    # Pass marker without embedding secrets in local logs
    remote = f"export OPENBAO_LAB_MARKER={MARKER!r}\n" + remote
    out = _clean(sudo_bash(c, remote, timeout=600))
    (OUT / "remote.txt").write_text(out, encoding="utf-8")
    print(out)
    verdict = "PASS" if "VERDICT PASS" in out else "FAIL"
    report["verdict"] = verdict
    try:
        for ln in out.splitlines():
            if ln.startswith("{") and '"checks"' in ln:
                report["payload"] = json.loads(ln)
                break
    except Exception:
        pass
    (OUT / "SUMMARY.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print("REPORT", OUT / "SUMMARY.json", verdict)
    return 0 if verdict == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
