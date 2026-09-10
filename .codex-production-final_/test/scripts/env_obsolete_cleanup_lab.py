#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""VPS lab: run cleanup-obsolete-env; assert retired keys removed (no secret values)."""
from __future__ import annotations

import io
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from deploy_stack import connect, sudo_bash, sftp_put, _file_bytes  # noqa: E402

if hasattr(sys.stdout, "buffer"):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

ROOT = Path(os.environ.get("ASSISTANT_REPO_ROOT", Path(__file__).resolve().parents[2]))
OUT = ROOT / "test" / "reports" / "run-env-obsolete-cleanup"
SCRUB = ROOT / "scripts" / "main" / "cleanup-obsolete-env.py"
COMMON = ROOT / "scripts" / "main" / "openbao_common.py"


def ts() -> str:
    return datetime.now(timezone.utc).astimezone().strftime("%Y-%m-%d %H:%M:%S %z")


def _clean(text: str) -> str:
    return "\n".join(
        ln
        for ln in (text or "").splitlines()
        if ln.strip() and "password" not in ln.lower()
    )


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    for p in (SCRUB, COMMON):
        if not p.is_file():
            print(f"FAIL missing {p}")
            return 2
    c = connect()
    print(sudo_bash(c, "mkdir -p /tmp/hs-suite && chmod 777 /tmp/hs-suite", timeout=30))
    sftp_put(c, _file_bytes(SCRUB), "/tmp/hs-suite/cleanup-obsolete-env.py")
    sftp_put(c, _file_bytes(COMMON), "/tmp/hs-suite/openbao_common.py")
    # Seed a retired pin if missing so the lab always exercises deletion.
    seed = r"""
set -euo pipefail
cd /opt/assistant
if ! grep -qE '^ADMIN_API_TOKEN=' .env 2>/dev/null; then
  printf '\nADMIN_API_TOKEN=\n' >> .env
fi
if ! grep -qE '^WEB_BACKENDS=' .env 2>/dev/null; then
  printf '\nWEB_BACKENDS=omni\n' >> .env
fi
STACK_ROOT=/opt/assistant ASSISTANT_DATA_DIR=/data/assistant \
  python3 /tmp/hs-suite/cleanup-obsolete-env.py
python3 - <<'PY'
from pathlib import Path

def keys(path):
    out=set()
    if not path.is_file():
        return out
    for ln in path.read_text(encoding='utf-8', errors='replace').splitlines():
        s=ln.strip()
        if not s or s.startswith('#') or '=' not in s:
            continue
        k=s.split('=',1)[0].strip()
        if k:
            out.add(k)
    return out

root=keys(Path('/opt/assistant/.env'))
data=keys(Path('/data/assistant/.env')) if Path('/data/assistant/.env').is_file() else set()
retired={'ADMIN_API_TOKEN','WEB_BACKENDS','FAL_KEY','IMAGE_OMNI_MODEL','MEM0_API_KEY'}
hit=sorted((root|data) & retired)
print('ROOT_HAS_ADMIN', 'ADMIN_API_TOKEN' in root)
print('ROOT_HAS_WEB_BACKENDS', 'WEB_BACKENDS' in root)
print('RETIRED_STILL_PRESENT', ','.join(hit) if hit else '')
print('VERDICT', 'PASS' if not hit else 'FAIL')
PY
"""
    out = _clean(sudo_bash(c, seed, timeout=120))
    (OUT / "remote.txt").write_text(out, encoding="utf-8")
    print(out)
    verdict = "PASS" if "VERDICT PASS" in out else "FAIL"
    (OUT / "SUMMARY.json").write_text(
        json.dumps({"ts": ts(), "verdict": verdict, "tail": out[-2000:]}, indent=2),
        encoding="utf-8",
    )
    c.close()
    return 0 if verdict == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
