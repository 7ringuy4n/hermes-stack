# -*- coding: utf-8 -*-
"""Upload OmniRouter first-setup and run it on the VPS."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from deploy_stack import ROOT, connect, sftp_put, sudo_bash, _file_bytes  # noqa: E402


def main() -> int:
    c = connect()
    try:
        sftp_put(
            c,
            _file_bytes(ROOT / "scripts" / "main" / "first-setup-omnirouter.py"),
            "/tmp/first-setup-omnirouter.py",
        )
        sftp_put(
            c,
            _file_bytes(ROOT / "scripts" / "main" / "first-setup-omnirouter.sh"),
            "/tmp/first-setup-omnirouter.sh",
        )
        sftp_put(c, _file_bytes(ROOT / "run.sh"), "/tmp/run.sh")
        out = sudo_bash(
            c,
            r"""
set -euo pipefail
install -m 0755 /tmp/first-setup-omnirouter.py /opt/assistant/scripts/main/first-setup-omnirouter.py
install -m 0755 /tmp/first-setup-omnirouter.sh /opt/assistant/scripts/main/first-setup-omnirouter.sh
install -m 0755 /tmp/run.sh /opt/assistant/run.sh
sed -i 's/\r$//' /opt/assistant/scripts/main/first-setup-omnirouter.py \
  /opt/assistant/scripts/main/first-setup-omnirouter.sh /opt/assistant/run.sh
cd /opt/assistant
set -a
. ./.env
set +a
export STACK_ROOT=/opt/assistant
python3 scripts/main/first-setup-omnirouter.py
echo OMNI_COMBO_SETUP_DONE
""",
            timeout=180,
        )
        if "OMNI_COMBO_SETUP_DONE" not in out:
            print("FAIL missing OMNI_COMBO_SETUP_DONE")
            return 1
        if "OK: first-setup omni-router complete" not in out:
            print("FAIL setup did not report OK")
            return 1
        return 0
    finally:
        c.close()


if __name__ == "__main__":
    raise SystemExit(main())

