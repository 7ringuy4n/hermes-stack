# -*- coding: utf-8 -*-
"""Tn inject suite: weather HCMC, mixed ≥3 requests, multi-task schedule.

Reports: test/reports/run-zalo-tn-weather-mixed/

Env: ASSISTANT_SSH_HOST, ASSISTANT_SSH_USER, ASSISTANT_SSH_PASSWORD
Optional: ZALO_TEST_USER_NAME=Tn, ZALO_CASE_WAIT_S=300
"""
from __future__ import annotations

import io
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from deploy_stack import connect, sudo_bash
from sanitize import sanitize as _sanitize

if hasattr(sys.stdout, "buffer"):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

ROOT = Path(os.environ.get("ASSISTANT_REPO_ROOT", Path(__file__).resolve().parents[2]))
OUT = ROOT / "test" / "reports" / "run-zalo-tn-weather-mixed"
WANT_NAME = (os.environ.get("ZALO_TEST_USER_NAME") or "Tn").strip()
WAIT_S = int(os.environ.get("ZALO_CASE_WAIT_S") or "300")
CONNECT_WAIT_S = int(os.environ.get("ZALO_CONNECT_WAIT_S") or "180")


def ts() -> str:
    return datetime.now(timezone.utc).astimezone().strftime("%Y-%m-%d %H:%M:%S %z")


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    c = connect()
    try:
        print(f"[{ts()}] Tn weather/mixed/schedule inject", flush=True)
        remote = rf"""
set -euo pipefail
export LC_ALL=C.UTF-8
cd /opt/assistant
set -a; . ./.env; set +a
python3 - <<'PY'
import json, time, urllib.request, subprocess, os
from pathlib import Path

want_name = {WANT_NAME!r}
wait_s = {WAIT_S}
connect_wait_s = {CONNECT_WAIT_S}

cases = [
    {{
        "id": "weather",
        "text": "tìm thông tin thời tiết hồ chí minh hiện tại",
        "need_send": True,
        "min_sends": 1,
        "forbid": ["/help", "trợ lý AI"],
        "expect_any": ["độ", "celsius", "trời", "mưa", "nắng", "nhiệt", "thời tiết", "HCM", "Hồ Chí Minh", "°", "C"],
    }},
    {{
        "id": "mixed3",
        "text": (
            "tin nhắn 1: chào mình ngắn gọn\n"
            "tin nhắn 2: tính 12 nhân 13, chỉ trả lời số\n"
            "tin nhắn 3: thời tiết Hà Nội hôm nay ngắn gọn"
        ),
        "need_send": True,
        "min_sends": 2,
        "forbid": ["/help"],
        "expect_any": ["156", "chào", "Hà Nội", "độ", "trời", "mưa", "nắng"],
    }},
    {{
        "id": "schedule3",
        "text": (
            "đặt lịch một lần lúc 23:55 hôm nay:\n"
            "1. nhắc uống nước\n"
            "2. kiểm tra thời tiết hồ chí minh ngắn\n"
            "3. nói một câu chúc ngủ ngon"
        ),
        "need_send": True,
        "min_sends": 1,
        "forbid": ["/help"],
        "expect_any": ["lịch", "23:55", "đã", "đặt", "schedule", "nhắc", "OK", "ok"],
    }},
]

def get(url, timeout=8):
    with urllib.request.urlopen(url, timeout=timeout) as r:
        return json.loads(r.read().decode() or "{{}}")

def hermes_logs(since="5m"):
    chunks=[]
    ids=subprocess.check_output(["docker","ps","-q","--filter","name=hermes"], text=True).split()
    for cid in ids:
        try:
            chunks.append(subprocess.check_output(["docker","logs","--since",since,cid], stderr=subprocess.STDOUT, text=True, errors="replace"))
        except Exception:
            pass
    return "\n".join(chunks)

def gateway_paths():
    out=[]
    for root in ("/opt/data/replicas","/data/assistant/replicas"):
        base=Path(root)
        if base.is_dir():
            out.extend(base.glob("*/logs/gateway.log"))
            out.extend(base.glob("*/logs/agent.log"))
    return out

def snapshot_offsets():
    offs={{}}
    for pth in gateway_paths():
        try: offs[str(pth)]=pth.stat().st_size
        except OSError: offs[str(pth)]=0
    return offs

def logs_since_offsets(offs):
    chunks=[]
    for path,start in offs.items():
        pth=Path(path)
        try:
            with pth.open("rb") as f:
                f.seek(start); chunks.append(f.read().decode("utf-8","replace"))
        except OSError:
            continue
    chunks.append(hermes_logs("4m"))
    return "\n".join(chunks)

def zalo_connected(blob: str) -> bool:
    if "Zalo: connected to bridge" in blob:
        return True
    for root in ("/opt/data/replicas","/data/assistant/replicas"):
        base=Path(root)
        if not base.is_dir():
            continue
        for gs in base.glob("*/gateway_state.json"):
            try:
                st=json.loads(gs.read_text(encoding="utf-8", errors="replace"))
            except Exception:
                continue
            plat=(st.get("platforms") or {{}}).get("zalo") or {{}}
            if plat.get("state")=="connected":
                return True
    return False

health=get("http://127.0.0.1:8787/health")
if not health.get("loggedIn"):
    raise SystemExit("BRIDGE_NOT_LOGGED_IN")
deadline=time.time()+connect_wait_s
while time.time()<deadline:
    if zalo_connected(hermes_logs("20m")):
        print("ZALO_CONNECTED"); break
    time.sleep(3)
else:
    raise SystemExit("ZALO_NOT_CONNECTED")

uid=""; uname=""
for path in ("/data/assistant/zalo_admin_users.txt","/opt/data/zalo_admin_users.txt"):
    p=Path(path)
    if not p.is_file(): continue
    for line in p.read_text(encoding="utf-8", errors="replace").splitlines():
        raw=line.strip()
        if not raw or raw.startswith("#"): continue
        left,_,right=raw.partition("|")
        cand=left.strip(); name=right.strip()
        if want_name and name.lower()==want_name.lower():
            uid,uname=cand,name; break
        if not uid:
            uid,uname=cand,name or "admin"
    if uid and want_name and uname.lower()==want_name.lower():
        break
_strict=(os.environ.get("ZALO_REQUIRE_NAMED_ADMIN") or "1").strip().lower() in ("1","true","yes")
if not uid or (_strict and want_name and uname.lower()!=want_name.lower()):
    raise SystemExit("NO_ADMIN_USER")
print("USER_NAME", uname)

tok=(os.environ.get("ZALO_PLUGIN_TOKEN") or "").strip()
headers={{"Content-Type":"application/json"}}
if tok:
    headers["Authorization"]="Bearer "+tok

results=[]
for case in cases:
    tag=case["id"]+"-"+str(int(time.time()))
    text=case["text"]+" ["+tag+"]"
    payload={{
        "type":"message",
        "payload":{{
            "threadId":uid,"threadType":"user","senderId":uid,"senderName":uname,
            "text":text,"isSelf":False,
        }},
    }}
    body=json.dumps(payload).encode("utf-8")
    req=urllib.request.Request("http://127.0.0.1:8787/inject-event", data=body, method="POST", headers=headers)
    t0=time.time()
    with urllib.request.urlopen(req, timeout=15) as r:
        inj=json.loads(r.read().decode() or "{{}}")
    offs=snapshot_offsets()
    send_count=0
    first_send_ms=None
    last_send_ms=None
    ready_lines=[]
    soul_blocked=False
    timeout_hit=False
    while time.time()<t0+wait_s:
        logs=logs_since_offsets(offs)
        if "SOUL.md blocked: deception_hide" in logs or "Context file SOUL.md blocked: deception_hide" in logs:
            soul_blocked=True; break
        if "queue turn timeout" in logs and (tag in logs or uid[-8:] in logs):
            timeout_hit=True
            # still count any sends that already happened
        for line in logs.splitlines():
            if "response ready" in line and uid[-8:] in line:
                if line not in ready_lines:
                    ready_lines.append(line[-200:])
            if "Zalo: send ok" in line and (tag in logs or uid[-8:] in line or "thread=" in line):
                pass
        # count send ok occurrences in new logs
        n=logs.count("Zalo: send ok")
        if n>send_count:
            if first_send_ms is None:
                first_send_ms=int((time.time()-t0)*1000)
            send_count=n
            last_send_ms=int((time.time()-t0)*1000)
        # stop early when enough sends and enough time after last send
        if send_count >= int(case.get("min_sends") or 1) and last_send_ms is not None:
            if time.time() > t0 + max(25, (last_send_ms/1000.0)+8):
                break
        if timeout_hit and send_count >= 1:
            break
        if timeout_hit and send_count == 0:
            break
        time.sleep(1.2)
    blob=logs_since_offsets(offs)
    low=blob.lower()
    forbid_hit=any(x.lower() in low for x in (case.get("forbid") or []))
    expect_hit=any(x.lower() in low for x in (case.get("expect_any") or []))
    ok=(
        bool(inj.get("ok"))
        and not soul_blocked
        and send_count >= int(case.get("min_sends") or 1)
        and first_send_ms is not None
        and not forbid_hit
    )
    row={{
        "id": case["id"],
        "tag": tag,
        "ok": ok,
        "inject_ok": bool(inj.get("ok")),
        "send_count": send_count,
        "first_send_ms": first_send_ms,
        "last_send_ms": last_send_ms,
        "soul_blocked": soul_blocked,
        "timeout": timeout_hit,
        "expect_hit": expect_hit,
        "forbid_hit": forbid_hit,
        "ready_n": len(ready_lines),
        "ready_sample": ready_lines[:3],
    }}
    results.append(row)
    print("CASE", json.dumps(row, ensure_ascii=False))
    time.sleep(8)

summary={{
    "user_name": uname,
    "cases": results,
    "pass": all(r.get("ok") for r in results),
}}
print("SUMMARY_JSON_BEGIN")
print(json.dumps(summary, ensure_ascii=False, indent=2))
print("SUMMARY_JSON_END")
if not summary["pass"]:
    raise SystemExit("FAIL_SUITE")
print("PASS_SUITE")
PY
"""
        out = sudo_bash(c, remote, timeout=WAIT_S * 4 + CONNECT_WAIT_S + 240)
    finally:
        c.close()

    (OUT / "raw.log").write_text(_sanitize(out or ""), encoding="utf-8", errors="replace")
    print(out or "", flush=True)
    summary = None
    if out and "SUMMARY_JSON_BEGIN" in out:
        try:
            chunk = out.split("SUMMARY_JSON_BEGIN", 1)[1].split("SUMMARY_JSON_END", 1)[0]
            summary = json.loads(chunk.strip())
        except Exception as e:
            print(f"warn parse: {e}", flush=True)
    if summary is None:
        summary = {"ok": False, "parse_error": True, "ts": ts()}
    else:
        summary["ts"] = ts()
        summary["ok"] = bool(summary.get("pass"))
    (OUT / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return 0 if out and "PASS_SUITE" in out else 1


if __name__ == "__main__":
    raise SystemExit(main())
