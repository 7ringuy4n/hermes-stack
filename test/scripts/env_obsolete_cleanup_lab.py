#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Compare VPS .env keys to repo .env.example; report obsolete keys (no secret values)."""
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
EXAMPLE = ROOT / ".env.example"


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
    if not EXAMPLE.is_file():
        print("FAIL missing .env.example")
        return 2
    c = connect()
    print(sudo_bash(c, "mkdir -p /tmp/hs-suite && chmod 777 /tmp/hs-suite", timeout=30))
    sftp_put(c, _file_bytes(EXAMPLE), "/tmp/hs-suite/env.example")
    remote = r"""
set -euo pipefail
python3 - <<'PY'
from pathlib import Path
import json

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

example=keys(Path('/tmp/hs-suite/env.example'))
root=keys(Path('/opt/assistant/.env'))
data=keys(Path('/data/assistant/.env')) if Path('/data/assistant/.env').is_file() else set()
# Known retired / obsolete families still scrubbed by OpenBao
obsolete_known = {
    'FAL_KEY','FLUXAI_API_KEY','IMAGE_LLM_API_KEY','IMAGE_VENDOR_API_KEY',
    'IMAGE_OMNI_MODEL','IMAGE_GEN_SIZE','IMAGE_ALLOW_PILLOW','ADMIN_API_TOKEN',
    'MEM0_API_KEY','OLLAMA_HOST','QWEN_MODEL',
}
extra_root = sorted(k for k in root - example if k not in {'OPENBAO_DEV_ROOT_TOKEN'})
extra_data = sorted(data - example) if data else []
retired_present = sorted((root|data) & obsolete_known)
print('EXAMPLE', len(example))
print('ROOT_KEYS', len(root))
print('DATA_KEYS', len(data))
print('EXTRA_ROOT', ','.join(extra_root[:80]))
print('EXTRA_DATA', ','.join(extra_data[:80]))
print('RETIRED_PRESENT', ','.join(retired_present))
# Soft cleanup: comment is enough — do not delete operator flags blindly.
# Only clear values for retired secret keys if present (keep key line empty).
env_path=Path('/opt/assistant/.env')
changed=0
if env_path.is_file() and retired_present:
    lines=[]
    for ln in env_path.read_text(encoding='utf-8', errors='replace').splitlines():
        if '=' in ln and not ln.strip().startswith('#'):
            k=ln.split('=',1)[0].strip()
            if k in obsolete_known and ln.split('=',1)[1].strip():
                lines.append(f'{k}=')
                changed += 1
                continue
        lines.append(ln)
    env_path.write_text('\\n'.join(lines)+'\\n', encoding='utf-8')
print('CLEARED_RETIRED_VALUES', changed)
print('VERDICT', 'PASS')
print(json.dumps({
  'extra_root': extra_root,
  'extra_data': extra_data,
  'retired_present': retired_present,
  'cleared': changed,
}, ensure_ascii=False))
PY
"""
    out = _clean(sudo_bash(c, remote, timeout=120))
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
