# -*- coding: utf-8 -*-
"""Sync SOUL.md + answering skill to VPS and restart Hermes."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from deploy_stack import ROOT, connect, sftp_put, sudo_bash, _file_bytes  # noqa: E402


def main() -> int:
    c = connect()
    try:
        sftp_put(c, _file_bytes(ROOT / "hermes" / "main" / "SOUL.md"), "/tmp/SOUL.md")
        sftp_put(
            c,
            _file_bytes(ROOT / "hermes" / "main" / "skills" / "core" / "answering" / "SKILL.md"),
            "/tmp/answering-SKILL.md",
        )
        out = sudo_bash(
            c,
            r"""
set -euo pipefail
install -m 0644 /tmp/SOUL.md /opt/assistant/hermes/main/SOUL.md
sed -i 's/\r$//' /opt/assistant/hermes/main/SOUL.md
mkdir -p /opt/assistant/hermes/main/skills/core/answering
install -m 0644 /tmp/answering-SKILL.md /opt/assistant/hermes/main/skills/core/answering/SKILL.md
sed -i 's/\r$//' /opt/assistant/hermes/main/skills/core/answering/SKILL.md
# Runtime copy Hermes reads from HERMES_HOME
if [[ -f /data/assistant/SOUL.md ]] || [[ -d /data/assistant ]]; then
  cp -f /opt/assistant/hermes/main/SOUL.md /data/assistant/SOUL.md
  chown 1000:1000 /data/assistant/SOUL.md || true
fi
docker ps -q --filter name=hermes --filter status=running | xargs -r docker restart
sleep 8
docker ps --filter name=hermes --format '{{.Names}} {{.Status}}'
echo SOUL_SYNC_DONE
""",
            timeout=180,
        )
        if "SOUL_SYNC_DONE" not in out:
            print("FAIL missing SOUL_SYNC_DONE")
            return 1
        return 0
    finally:
        c.close()


if __name__ == "__main__":
    raise SystemExit(main())

