# -*- coding: utf-8 -*-
"""Post-deploy checks: isolated plugin, omni-router auth, schedules, image gen."""
from __future__ import annotations

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from deploy_stack import connect, sudo_bash  # noqa: E402


def main() -> int:
    c = connect()
    try:
        out = sudo_bash(
            c,
            r"""
set -euo pipefail
cd /opt/assistant
set -a; . ./.env; set +a
echo "=== plugin ==="
h2=$(docker ps --filter name=assistant-hermes-2 --format '{{.Names}}' | head -1)
h1=$(docker ps --filter name=assistant-hermes-1 --format '{{.Names}}' | head -1)
grep -c isolate_session_chat_id /opt/assistant/hermes/main/plugins/zalo/adapter.py
test -f /opt/assistant/hermes/main/plugins/zalo/turn_wait.py && echo turn_wait=ok
docker exec "$h2" grep -c isolate_session_chat_id /opt/data/plugins/zalo/adapter.py
docker exec "$h2" test -f /opt/data/plugins/zalo/turn_wait.py && echo container_turn_wait=ok
docker exec "$h2" grep -c 'always use dispatcher' /opt/data/skills/image-gen/SKILL.md || docker exec "$h2" grep -c dispatcher /opt/data/skills/image-gen/SKILL.md
echo "hermes1=$h1 hermes2=$h2"
docker exec "$h1" printenv ZALO_PLUGIN_URL || true
docker exec "$h2" printenv ZALO_PLUGIN_URL || true
echo "=== omni-router ==="
curl -fsS -m 10 -H "Authorization: Bearer ${OMNIROUTER_API_KEY}" http://127.0.0.1:20129/v1/models \
  | python3 -c 'import sys,json; m=json.load(sys.stdin); d=m.get("data",[]); print("models_ok", len(d), (d[0].get("id") if d else ""))'
docker exec "$h2" sh -lc 'echo OMNIROUTER_SET=$([ -n "$OMNIROUTER_API_KEY" ] && echo 1 || echo 0); echo OPENAI_SET=$([ -n "$OPENAI_API_KEY" ] && echo 1 || echo 0); echo OPENAI_BASE=$OPENAI_BASE_URL'
set +e
docker exec "$h2" python3 -c "import os,urllib.request; k=os.environ.get('OPENAI_API_KEY') or os.environ.get('OMNIROUTER_API_KEY') or ''; base=(os.environ.get('OPENAI_BASE_URL') or 'http://model-router:8096/v1').rstrip('/'); url=base+'/models'; req=urllib.request.Request(url, headers={'Authorization':'Bearer '+k});
try:
 r=urllib.request.urlopen(req, timeout=8); print('hermes2_llm', r.status, url)
except Exception as e:
 print('hermes2_llm_fail', type(e).__name__, getattr(e,'code',e), url)
req2=urllib.request.Request('http://omni-router:20129/');
try:
 r2=urllib.request.urlopen(req2, timeout=5); print('hermes2_omni-router_root', r2.status)
except Exception as e:
 print('hermes2_omni-router_root', type(e).__name__, getattr(e,'code',e))"
set -e
echo "=== schedules ==="
curl -sS -m 8 http://127.0.0.1:8108/v1/schedules | python3 -c '
import sys,json
d=json.load(sys.stdin)
rows=d.get("schedules") or []
print("sched_n", len(rows))
for s in rows:
    print("id", s.get("id"), "enabled", s.get("enabled"), "time", s.get("time") or s.get("cron_expr"), "next", str(s.get("next_run_at") or "")[:19])
'
echo "=== comfy ==="
curl -sS -m 8 http://127.0.0.1:8188/system_stats >/dev/null && echo comfy_host=ok || echo comfy_host=skip
docker exec dispatcher python3 -c "import urllib.request; urllib.request.urlopen('http://comfyui-cpu:8188/system_stats', timeout=8); print('dispatcher_comfy=ok')"
echo "=== image comfy ==="
curl -sS -m 180 -X POST http://127.0.0.1:8090/v1/image \
  -H 'content-type: application/json' \
  -d '{"prompt":"a red apple on a table, simple","filename":"imgtest-comfy.png","refine":false,"provider":"comfy-cpu"}' \
  | python3 -c "import sys,json; d=json.load(sys.stdin); print('comfy_img', {k:d.get(k) for k in ('ok','backend','error','detail','file')})"
echo VERIFY_DONE
""",
            timeout=240,
        )
        return 0 if "VERIFY_DONE" in out else 1
    finally:
        c.close()


if __name__ == "__main__":
    raise SystemExit(main())

