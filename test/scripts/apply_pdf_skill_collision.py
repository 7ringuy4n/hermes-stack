# -*- coding: utf-8 -*-
"""Pull develop fix for pdf skill collision; recreate hermes; purge clones; smoke."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from deploy_stack import connect, sudo_bash

REMOTE = r"""
set -euo pipefail
cd /opt/assistant
git fetch origin
# Prefer PR branch if present, else develop tip after merge
git fetch origin fix/pdf-skill-collision-office-file:refs/remotes/origin/fix/pdf-skill-collision-office-file 2>/dev/null || true
if git rev-parse --verify origin/fix/pdf-skill-collision-office-file >/dev/null 2>&1; then
  git checkout -B fix/pdf-skill-collision-office-file origin/fix/pdf-skill-collision-office-file
else
  git checkout -B develop origin/develop
  git reset --hard origin/develop
fi
echo HEAD=$(git log -1 --oneline)

# Purge colliding clones on all replicas before recreate
find /data/assistant/replicas -type d \( -path '*/skills/productivity/pdf' -o -path '*/skills/productivity/docx' -o -path '*/skills/productivity/xlsx' -o -path '*/skills/documents/pdf' -o -path '*/skills/documents/docx' -o -path '*/skills/documents/xlsx' \) -prune -exec rm -rf {} + 2>/dev/null || true

docker compose --project-directory /opt/assistant -f docker/docker-compose.yml --profile media up -d --force-recreate --no-deps hermes 2>&1 | tail -20
sleep 12

echo '==> reserved names on active replica'
RID=$(docker inspect -f '{{.Config.Hostname}}' assistant-hermes-1 2>/dev/null || docker ps -q -f name=hermes | head -1 | xargs -I{} docker inspect -f '{{.Config.Hostname}}' {})
echo RID=$RID
grep -Rsn '^name: pdf$' /data/assistant/replicas/$RID/skills 2>/dev/null | head || echo 'no name:pdf'
grep -Rsn '^name: pdf-tools-local$' /data/assistant/replicas/$RID/skills 2>/dev/null | head || true
test ! -d /data/assistant/replicas/$RID/skills/productivity/pdf && echo 'productivity/pdf purged' || echo 'WARN productivity/pdf still present'

echo '==> office-file smoke (write must ok)'
curl -sS -m 30 -X POST http://127.0.0.1:8090/v1/office-file \
  -H 'Content-Type: application/json' \
  -d '{"prompt":"tạo 1 file pdf và điền vào số 1","thread_id":"smoke-office","thread_type":"user","filename":"so_1_fix.pdf","caption":""}'
echo
ls -lt /data/assistant/media/out/so_1_fix.pdf 2>/dev/null | head -2

echo '==> abnormal 2m'
docker logs --since 2m assistant-hermes-1 2>&1 | grep -iE 'Skill name collision for .pdf|Ambiguous skill name .pdf|reportlab|ERROR|Traceback|EADDRINUSE' | tail -20 || true
journalctl --user -u com.hermes.zaloplugin --since '5 min ago' 2>/dev/null | grep -iE 'error|EADDRINUSE' | tail -8 || true
echo OK_APPLY_PDF
"""


def main() -> int:
    c = connect()
    try:
        out = sudo_bash(c, REMOTE, timeout=300)
    finally:
        c.close()
    path = Path("test/reports/apply-pdf-skill-collision.log")
    path.write_text(out or "", encoding="utf-8", errors="replace")
    sys.stdout.buffer.write((out or "").encode("utf-8", errors="replace"))
    sys.stdout.buffer.write(b"\n")
    return 0 if out and "OK_APPLY_PDF" in out else 1


if __name__ == "__main__":
    raise SystemExit(main())
