#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Tn lab: Security/*.zip archives via ingest extract-archive + inject (AGENT_RULES §29.2)."""
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
DOCS = Path(os.environ.get("ASSISTANT_TEST_DOCS") or (ROOT.parent / "test docs" / "Security"))
OUT = ROOT / "test" / "reports" / "run-zalo-tn-archive-extract"
TN_ID = (os.environ.get("ZALO_TEST_USER_ID") or "").strip()

SAMPLES = ["1.zip", "2.zip", "3.zip", "4.zip"]


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
    if not TN_ID:
        print("ERROR: ZALO_TEST_USER_ID is required", file=sys.stderr)
        return 2
    OUT.mkdir(parents=True, exist_ok=True)
    missing = [n for n in SAMPLES if not (DOCS / n).is_file()]
    if missing:
        print("FAIL missing", missing)
        return 2

    c = connect()
    print(sudo_bash(c, "mkdir -p /tmp/hs-arch /data/assistant/lab-samples && chmod 777 /tmp/hs-arch", timeout=30))
    for name in SAMPLES:
        print("PUT", name, flush=True)
        sftp_put(c, _file_bytes(DOCS / name), f"/tmp/hs-arch/{name}")

    remote = f"""
set -euo pipefail
cp -f /tmp/hs-arch/*.zip /data/assistant/lab-samples/
export TN={TN_ID!r}
python3 - <<'PY'
import json, time, urllib.request
from pathlib import Path

TN = {TN_ID!r}
SAMPLES = Path('/data/assistant/lab-samples')
checks = []

def note(name, ok, detail=''):
    checks.append({{'name': name, 'ok': bool(ok), 'detail': str(detail)[:300]}})
    print(('PASS' if ok else 'FAIL'), name, str(detail)[:160], flush=True)

def post(url, body, timeout=90):
    req = urllib.request.Request(
        url, data=json.dumps(body).encode(),
        headers={{'Content-Type': 'application/json'}}, method='POST',
    )
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode() or '{{}}')

def inject(text, media):
    payload = {{
        'type': 'message', 'threadId': TN, 'threadType': 'user',
        'senderId': TN, 'senderName': 'Tn', 'text': text,
        'messageId': 'arch-' + str(int(time.time()*1000)),
        'attachments': media, 'media': media,
    }}
    req = urllib.request.Request(
        'http://127.0.0.1:8787/inject-event',
        data=json.dumps(payload).encode(),
        headers={{'Content-Type': 'application/json'}}, method='POST',
    )
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read().decode('utf-8', 'replace')[:200]

for name in {SAMPLES!r}:
    src = SAMPLES / name
    if not src.is_file():
        note('extract_' + name, False, 'missing')
        continue
    # Stage under media root for ingest resolve
    inbound = Path(f'/data/assistant/media/inbound/{{TN}}')
    inbound.mkdir(parents=True, exist_ok=True)
    dest = inbound / name
    dest.write_bytes(src.read_bytes())
    try:
        body = post('http://127.0.0.1:8099/v1/extract-archive', {{'path': str(dest)}}, timeout=120)
    except Exception as e:
        note('extract_' + name, False, type(e).__name__)
        continue
    reason = str(body.get('reason') or '')
    text = str(body.get('text') or '')
    media = body.get('media_files') or []
    ok_flag = bool(body.get('ok'))
    # Password-required is a valid handled outcome for locked packs
    if reason in {{'password_required', 'bad_password'}}:
        note('extract_' + name, True, f'handled:{{reason}}')
    elif ok_flag and (len(text.strip()) >= 3 or len(media) >= 1):
        note('extract_' + name, True, f'media={{len(media)}} chars={{len(text)}} head={{text[:100]}}')
    else:
        note('extract_' + name, False, json.dumps(body, ensure_ascii=False)[:200])
    # User-visible inject (one representative)
    if name == '1.zip':
        media_att = [{{'type': 'file', 'url': f'/opt/data/media/inbound/{{TN}}/{{name}}', 'name': name}}]
        inject('đọc file zip này, liệt kê nội dung media an toàn [' + str(int(time.time())) + ']', media_att)
    time.sleep(1)

ok = all(x['ok'] for x in checks)
print('VERDICT', 'PASS' if ok else 'FAIL')
print(json.dumps({{'checks': checks, 'ok': ok}}, ensure_ascii=False))
raise SystemExit(0 if ok else 1)
PY
"""
    out = _clean(sudo_bash(c, remote, timeout=300))
    (OUT / "remote.txt").write_text(out, encoding="utf-8")
    print(out)
    verdict = "PASS" if "VERDICT PASS" in out else "FAIL"
    report = {"ts": ts(), "verdict": verdict}
    try:
        for ln in reversed(out.splitlines()):
            if ln.startswith("{") and '"checks"' in ln:
                report["payload"] = json.loads(ln)
                break
    except Exception:
        pass
    (OUT / "SUMMARY.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print("REPORT", OUT / "SUMMARY.json", verdict)
    c.close()
    return 0 if verdict == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
