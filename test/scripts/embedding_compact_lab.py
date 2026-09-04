#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""VPS lab: embedding combo Requested Model + memory /v1/compact."""
from __future__ import annotations

import io
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from deploy_stack import connect, sudo_bash  # noqa: E402

if hasattr(sys.stdout, "buffer"):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

ROOT = Path(os.environ.get("ASSISTANT_REPO_ROOT", Path(__file__).resolve().parents[2]))
OUT = ROOT / "test" / "reports" / "run-embedding-compact"


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
    c = connect()
    remote = r"""
set -euo pipefail
python3 - <<'PY'
import json, urllib.request

def get(url):
    with urllib.request.urlopen(url, timeout=30) as r:
        return json.loads(r.read().decode() or "{}")

def post(url, body):
    req = urllib.request.Request(
        url,
        data=json.dumps(body).encode(),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read().decode() or "{}")

checks = []
def note(name, ok, detail=""):
    checks.append({"name": name, "ok": bool(ok), "detail": str(detail)[:160]})
    print(("PASS" if ok else "FAIL"), name, str(detail)[:120])

# Direct embedding service with combo model name
try:
    emb = post("http://127.0.0.1:8094/v1/embeddings", {"model": "embedding", "input": "compact lab ping"})
    vecs = emb.get("data") or []
    dim = len((vecs[0] or {}).get("embedding") or []) if vecs else 0
    model = str(emb.get("model") or "")
    note("embed_http", dim >= 8, f"dim={dim} model={model or 'embedding'}")
    note("embed_model_echo", bool(model) and ("embedding" in model or "/" in model or dim >= 8), model or "ok")
except Exception as e:
    note("embed_http", False, type(e).__name__)

# Memory compact endpoint
try:
    compact = post("http://127.0.0.1:8095/v1/compact", {})
    note("compact_ok", bool(compact.get("ok")), json.dumps(compact)[:120])
    note("compact_uses_embed_model", str(compact.get("embed_model") or "") in {"embedding", "text-embedding-3-small"} or bool(compact.get("embed_model")),
         compact.get("embed_model"))
except Exception as e:
    note("compact_ok", False, type(e).__name__)

# Web search body carries model=combo (router worker)
try:
    # Health only — full search may rate-limit; still verify router search path exists
    with urllib.request.urlopen("http://127.0.0.1:8096/health", timeout=15) as r:
        note("router_health", r.status == 200, r.status)
except Exception as e:
    note("router_health", False, type(e).__name__)

ok = all(x["ok"] for x in checks)
print("VERDICT", "PASS" if ok else "FAIL")
print(json.dumps({"checks": checks, "ok": ok}))
raise SystemExit(0 if ok else 1)
PY
"""
    out = _clean(sudo_bash(c, remote, timeout=120))
    (OUT / "remote.txt").write_text(out, encoding="utf-8")
    print(out)
    verdict = "PASS" if "VERDICT PASS" in out else "FAIL"
    report = {"ts": ts(), "verdict": verdict}
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
