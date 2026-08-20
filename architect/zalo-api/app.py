"""Zalo / lab admin API — approve/remove threads & users without SSH.

Protect with ZALO_API_TOKEN (alias ADMIN_API_TOKEN; VPN Traefik or Bearer). Never returns stack traces.
In-Zalo commands: POST /v1/zalo/chat (only ZALO_ADMIN_USERS).
"""
from __future__ import annotations

import glob
import os
import re
import shutil
import subprocess
from typing import Any, Optional

import httpx
from fastapi import FastAPI, Header, HTTPException
from pydantic import BaseModel, Field

from channels_registry import list_channels, resolve, sync_from_allowlist, upsert as channel_upsert
from schedule_list import fmt_hermes_cron_list
from schedule_crud import (
    USAGE as SCHEDULE_USAGE,
    apply_schedule_update,
    fmt_list as fmt_schedule_list,
    fmt_show as fmt_schedule_show,
    jobs_file as schedule_jobs_file,
    load_bundle as load_schedule_bundle,
    new_job as new_schedule_job,
    parse_update_args as parse_schedule_update,
    resolve_job as resolve_schedule_job,
    save_bundle as save_schedule_bundle,
    split_add_args,
    take_all_flag as take_schedule_all_flag,
    jobs_for_thread as schedule_jobs_for_thread,
    visible_jobs as visible_schedule_jobs,
)

TOKEN = (os.environ.get("ZALO_API_TOKEN") or os.environ.get("ADMIN_API_TOKEN") or "").strip()
ZALO_BRIDGE = os.environ.get("ZALO_BRIDGE_URL", "http://host.docker.internal:8787").rstrip("/")
ZALO_TOKEN = os.environ.get("ZALO_PLUGIN_TOKEN", "")
AUTHZ_URL = os.environ.get("AUTHZ_URL", "http://authz:8097").rstrip("/")
NOTIFY_URL = os.environ.get("NOTIFY_URL", "http://notify:8092").rstrip("/")
SESSION_URL = os.environ.get("SESSION_URL", "http://session:8107").rstrip("/")
INGEST_URL = os.environ.get("INGEST_URL", "http://ingest:8099").rstrip("/")
# When 1: !zalo approve success → notify admin Zalo DM; no in-thread approve reply.
NOTIFY_ON_APPROVE = (os.environ.get("NOTIFY_ON_APPROVE", "1") or "1").strip().lower() in {
    "1",
    "true",
    "yes",
    "on",
}
ALLOWED_FILE = os.environ.get(
    "ZALO_ALLOWED_THREADS_FILE", "/data/hermes/zalo_allowed_threads.txt"
)
DENIED_THREADS_FILE = os.environ.get(
    "ZALO_DENIED_THREADS_FILE", "/data/hermes/zalo_denied_threads.txt"
)
ALLOWED_USERS_FILE = os.environ.get(
    "ZALO_ALLOWED_USERS_FILE", "/data/hermes/zalo_allowed_users.txt"
)
HERMES_DATA = os.environ.get("HERMES_DATA_DIR", "/data/hermes")
WORKFLOW_URL = (os.environ.get("WORKFLOW_URL") or "http://workflow:8108").rstrip("/")


def _workflow_http(method: str, path: str, payload: Optional[dict[str, Any]] = None) -> dict[str, Any]:
    url = f"{WORKFLOW_URL}{path}"
    try:
        r = httpx.request(method, url, json=payload, timeout=8.0)
        if r.status_code >= 300:
            return {}
        data = r.json()
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _workflow_row_as_job(row: dict[str, Any]) -> dict[str, Any]:
    expr = str(row.get("cron_expr") or "")
    origin = row.get("origin") if isinstance(row.get("origin"), dict) else {}
    return {
        "id": str(row.get("id") or ""),
        "name": str(row.get("name") or row.get("id") or "lịch"),
        "prompt": str(row.get("text") or ""),
        "schedule": {"kind": "cron", "expr": expr, "display": expr},
        "schedule_display": expr,
        "origin": origin,
        "enabled": bool(row.get("enabled", True)),
        "state": "scheduled",
        "deliver": "origin",
    }


def _merge_workflow_schedules(jobs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    data = _workflow_http("GET", "/v1/schedules")
    rows = data.get("schedules") if isinstance(data, dict) else None
    if not isinstance(rows, list) or not rows:
        return jobs
    by_id = {str(j.get("id") or ""): j for j in jobs if isinstance(j, dict)}
    for row in rows:
        if not isinstance(row, dict):
            continue
        job = _workflow_row_as_job(row)
        if job.get("id"):
            by_id[str(job["id"])] = job
    return [j for j in by_id.values() if j.get("id")]


def _workflow_upsert_schedule(job: dict[str, Any], expr: str, prompt: str, tz_name: str) -> None:
    if not expr or not prompt:
        return
    origin = job.get("origin") if isinstance(job.get("origin"), dict) else {}
    tid = str(origin.get("thread_id") or origin.get("chat_id") or "")
    ctx = {
        "thread_id": tid,
        "thread_type": str(origin.get("thread_type") or "user"),
        "chat_type": str(origin.get("chat_type") or "dm"),
        "sender_id": str(origin.get("user_id") or ""),
        "sender_name": str(origin.get("chat_name") or tid),
        "execute": "hermes",
    }
    _workflow_http(
        "POST",
        "/v1/schedules",
        {
            "id": str(job.get("id") or ""),
            "name": str(job.get("name") or ""),
            "cron_expr": expr,
            "timezone": tz_name,
            "text": prompt,
            "origin": origin,
            "context": ctx,
            "enabled": True,
        },
    )


def _workflow_delete_schedule(sid: str) -> None:
    if sid:
        _workflow_http("DELETE", f"/v1/schedules/{sid}")
# Sole operator admin (exactly one uid). File wins over env when present.
ADMIN_USERS_FILE = os.environ.get(
    "ZALO_ADMIN_USERS_FILE",
    os.path.join(HERMES_DATA, "zalo_admin_users.txt"),
)
TIMING_FOOTER_RULE = "timing footer off unless ZALO_TIMING_FOOTER=1"
RESPONSE_POLICY_TEXT = """# Response policy (always — default, survives session clear)

- One message per turn. No multi-bubble.
- NEVER end a reply with an italic datetime / timezone footer.
- NEVER invent timing numbers.
- Request/response timing footer is optional (`ZALO_TIMING_FOOTER`). Default off — do not write a ⏱ line.
- This rule lives in workspace/skills, not Redis session. Keep after clearsessions.
- Timezone for clock times in content: TZ=Asia/Ho_Chi_Minh, one clock only.
- Daily schedule: if the requested local time is still ahead of now today, schedule today — not tomorrow.
- Never announce skill/memory saves in Zalo.
- NEVER name server paths or secrets (/opt/data, /data/hermes, workspace dir, tokens, .env, IP).
- Do not scan/list server env or credential files when the user asks — refuse briefly.
- Do not tell the user they are on Zalo or suggest /help unless they asked for commands.
- On server/tool errors: only the `session.interrupted` copy from `messages/ux.json` (or brief English). No job_id, internal schedule ids, or self-improvement text.
- Compound user message with multiple requests: answer all parts, not only the first.
- Numbered lists count (`1 …` / `2. …` / `2.Sau đó`), not only `tin nhắn 1:`.
- Immediate compound is split into turns; Valkey queues parts so the next turn starts only after the current send (do not interrupt).
- A daily numbered list (`hàng ngày` / `hằng ngày` / `06:00 GMT+7`) is **one lịch/schedule**. When it runs, finish every item after media. Do not register parallel schedules at the same clock.
- User-facing wording: **lịch** / **schedule** — never **cron** / **cron job**.
- After sending a generated file: send the file only. Do not add a success ack line.
- Never send Hermes busy/interrupt UX (`Interrupting current task`, `First-time tip`, `/busy queue|steer|status`).
- Tone: follow `communication/friendly-response` — no banter, no insults, no sarcasm, no blame. Stay friendly under all user emotions. Prefer result → explanation → next step.
- Response language: same language as the user's request unless they explicitly ask for another.
- Vietnamese people/gender words: follow `communication/vi-people-terms` (context, not a fixed map).
- If the user swears: still answer the question. Do not refuse the turn. Do not repeat slurs as an attack. Do not roast or insult on request.
"""
HERMES_STATE_DB_REL = (
    "state.db",
    os.path.join(".hermes", "state.db"),
    os.path.join("home", ".hermes", "state.db"),
)
HERMES_SESSION_DIRS = (
    "sessions",
    os.path.join(".hermes", "sessions"),
    os.path.join("state", "sessions"),
)
app = FastAPI(title="assistant-zalo-api", version="1.3.0")


def _read_admin_file() -> list[dict[str, str]]:
    """Exactly one admin line preferred: `uid` or `uid | name`."""
    out: list[dict[str, str]] = []
    try:
        if not os.path.isfile(ADMIN_USERS_FILE):
            return out
        with open(ADMIN_USERS_FILE, encoding="utf-8") as f:
            for line in f:
                raw = line.strip()
                if not raw or raw.startswith("#"):
                    continue
                if "|" in raw:
                    uid, name = raw.split("|", 1)
                else:
                    uid, name = raw, ""
                uid = uid.strip()
                if uid:
                    out.append({"id": uid, "name": name.strip()})
                    break  # sole admin
    except Exception:
        pass
    return out


def _write_admin_user(uid: str, name: str = "") -> None:
    """Persist exactly one admin uid (overwrites file)."""
    uid = (uid or "").strip()
    if not uid:
        raise ValueError("admin uid required")
    os.makedirs(os.path.dirname(ADMIN_USERS_FILE) or ".", exist_ok=True)
    with open(ADMIN_USERS_FILE, "w", encoding="utf-8", newline="\n") as f:
        f.write("# managed by zalo-api — sole Zalo admin (exactly one)\n")
        if name.strip():
            f.write(f"{uid} | {name.strip()}\n")
        else:
            f.write(f"{uid}\n")


def _admin_users() -> set[str]:
    """Sole admin from file, else bootstrap from ZALO_ADMIN_USERS env (first id only)."""
    filed = _read_admin_file()
    if filed:
        return {filed[0]["id"]}
    env_ids = [
        x.strip()
        for x in os.environ.get("ZALO_ADMIN_USERS", "").split(",")
        if x.strip()
    ]
    return {env_ids[0]} if env_ids else set()


def _admin_is_bot_placeholder(bot_id: str) -> bool:
    """True when sole admin is still the logged-in bridge account (first-setup seed)."""
    admins = _admin_users()
    bid = (bot_id or "").strip()
    return bool(bid) and admins == {bid}


def _bridge_health() -> dict[str, Any]:
    try:
        with httpx.Client(timeout=5.0) as client:
            r = client.get(f"{ZALO_BRIDGE}/health", headers=_bridge_headers())
            if r.status_code < 400:
                data = r.json()
                return data if isinstance(data, dict) else {}
    except Exception:
        pass
    return {}


def _bridge_logged_in() -> bool:
    h = _bridge_health()
    if not h:
        return False
    if h.get("loggedIn") is True:
        return True
    # some builds use ownId without loggedIn flag
    return bool(str(h.get("ownId") or "").strip()) and h.get("sessionDead") is not True


def _reset_all_sessions() -> dict[str, Any]:
    try:
        with httpx.Client(timeout=60.0) as client:
            resp = client.post(f"{SESSION_URL}/v1/sessions/reset-all")
            resp.raise_for_status()
            return resp.json()
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


def _ensure_timing_rule() -> bool:
    """Re-apply default timing footer after session wipe (not stored in Redis)."""
    try:
        ws = os.path.join(HERMES_DATA, "workspace")
        os.makedirs(ws, exist_ok=True)
        path = os.path.join(ws, "RESPONSE_POLICY.md")
        with open(path, "w", encoding="utf-8", newline="\n") as f:
            f.write(RESPONSE_POLICY_TEXT)
        user_md = os.path.join(HERMES_DATA, "memories", "USER.md")
        if os.path.isfile(user_md):
            text = open(user_md, encoding="utf-8", errors="replace").read()
            if "ICT datetime" in text or "_YYYY-MM-DD" in text or "end with ICT" in text.lower():
                text = text.replace("end with ICT datetime.", f"end with `{TIMING_FOOTER_RULE}`.")
                text = text.replace("end with ICT datetime", f"end with `{TIMING_FOOTER_RULE}`")
                with open(user_md, "w", encoding="utf-8", newline="\n") as f:
                    f.write(text)
        return True
    except Exception:
        return False


DOCKER_SOCK = os.environ.get("DOCKER_SOCK", "/var/run/docker.sock")


HERMES_CONTAINER = (os.environ.get("HERMES_CONTAINER") or "hermes").strip() or "hermes"


def _docker_sock_restart(container: str | None = None, timeout: float = 90.0) -> bool:
    """Restart container via mounted docker.sock (no docker CLI in image)."""
    name = (container or HERMES_CONTAINER).strip() or "hermes"
    if not os.path.exists(DOCKER_SOCK):
        return False
    try:
        with httpx.Client(
            transport=httpx.HTTPTransport(uds=DOCKER_SOCK),
            timeout=timeout,
        ) as client:
            r = client.post(f"http://localhost/v1.43/containers/{name}/restart?t=10")
            return r.status_code in (204, 200)
    except Exception:
        return False


def _docker_bin() -> Optional[str]:
    """Host docker CLI — usually missing inside zalo-api container (no docker.sock)."""
    for cand in ("/usr/bin/docker", "/bin/docker", "docker"):
        if cand == "docker":
            return shutil.which("docker")
        if os.path.isfile(cand) and os.access(cand, os.X_OK):
            return cand
    return None


def _docker_exec_hermes(
    args: list[str],
    timeout: float = 90.0,
    *,
    max_out: int = 800,
) -> tuple[int, str]:
    docker = _docker_bin()
    if not docker:
        # Volume wipe of /data/hermes is enough; skip docker exec noise.
        return 0, ""
    try:
        r = subprocess.run(
            [docker, "exec", HERMES_CONTAINER, *args],
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        out = ((r.stdout or "") + (r.stderr or "")).strip()
        cap = max(80, int(max_out))
        return r.returncode, out[:cap]
    except Exception as exc:
        return -1, str(exc)


def _fetch_hermes_cron_list() -> tuple[int, str]:
    return _docker_exec_hermes(
        ["hermes", "cron", "list"],
        timeout=120.0,
        max_out=6000,
    )


def _wipe_hermes_file_sessions() -> dict[str, Any]:
    """Wipe ephemeral Hermes gateway files (state.db + sessions/).

    Durable chat SoT is session service (Valkey) + Memory Manager — not state.db.
    Clearing local SQLite still helps unbind Zalo routing leftovers on disk.
    """
    removed = 0
    samples: list[str] = []

    roots = [HERMES_DATA]
    replicas = os.path.join(HERMES_DATA, "replicas")
    if os.path.isdir(replicas):
        try:
            for name in os.listdir(replicas):
                p = os.path.join(replicas, name)
                if os.path.isdir(p):
                    roots.append(p)
        except OSError:
            pass

    for root in roots:
        for rel in HERMES_STATE_DB_REL:
            fp = os.path.join(root, rel)
            if not os.path.isfile(fp):
                continue
            try:
                os.remove(fp)
                removed += 1
                if len(samples) < 12:
                    samples.append(f"state.db ({os.path.relpath(fp, HERMES_DATA)})")
            except OSError:
                continue

        for rel in HERMES_SESSION_DIRS:
            sess_root = os.path.join(root, rel)
            if not os.path.isdir(sess_root):
                continue
            try:
                names = os.listdir(sess_root)
            except OSError:
                continue
            for name in names:
                fp = os.path.join(sess_root, name)
                try:
                    if os.path.isdir(fp):
                        shutil.rmtree(fp)
                    else:
                        os.remove(fp)
                    removed += 1
                    if len(samples) < 12:
                        samples.append(name)
                except OSError:
                    continue

    for pattern in (
        os.path.join(HERMES_DATA, "cron_*"),
        os.path.join(HERMES_DATA, "sessions", "cron_*"),
        os.path.join(HERMES_DATA, ".hermes", "sessions", "cron_*"),
        os.path.join(HERMES_DATA, "sessions", "request_dump_*"),
        os.path.join(HERMES_DATA, "replicas", "*", "state.db"),
        os.path.join(HERMES_DATA, "replicas", "*", "gateway_state.json"),
    ):
        for fp in glob.glob(pattern):
            try:
                if os.path.isdir(fp):
                    shutil.rmtree(fp)
                elif os.path.isfile(fp):
                    os.remove(fp)
                else:
                    continue
                removed += 1
                if len(samples) < 12:
                    samples.append(os.path.basename(fp))
            except OSError:
                continue

    # In-container paths (HERMES_HOME may differ from zalo-api mount layout)
    rc, container_out = _docker_exec_hermes(
        [
            "bash",
            "-lc",
            r"""
set +e
H="${HERMES_HOME:-/opt/data}"
n=0
for f in "$H/state.db" "$H/.hermes/state.db" /opt/data/home/.hermes/state.db; do
  if [ -f "$f" ]; then rm -f "$f" && n=$((n+1)); fi
done
# Per-replica ephemeral homes (stateless Hermes)
if [ -d /opt/data/replicas ]; then
  for d in /opt/data/replicas/*; do
    [ -d "$d" ] || continue
    for f in "$d/state.db" "$d/.hermes/state.db" "$d/gateway_state.json"; do
      if [ -f "$f" ] && [ ! -L "$f" ]; then rm -f "$f" && n=$((n+1)); fi
    done
    if [ -d "$d/sessions" ] && [ ! -L "$d/sessions" ]; then
      shopt -s nullglob
      for x in "$d/sessions/"*; do rm -rf "$x" && n=$((n+1)); done
    fi
  done
fi
if [ -d "$H/sessions" ]; then
  shopt -s nullglob
  for x in "$H/sessions/"*; do rm -rf "$x" && n=$((n+1)); done
fi
hermes tools disable cronjob 2>/dev/null
for j in daily-optimize-rules-memory daily_optimize_rules_memory optimize-rules-memory; do
  hermes cron remove "$j" 2>/dev/null
done
hermes sessions prune 2>/dev/null
echo "hermes_container_removed=$n"
""",
        ]
    )

    return {
        "ok": True,
        "deleted_files": removed,
        "sample": samples,
        "hermes_exec_rc": rc,
        "hermes_exec": container_out,
    }


def _restart_hermes() -> bool:
    if _docker_sock_restart(HERMES_CONTAINER):
        return True
    docker = _docker_bin()
    if not docker:
        return False
    try:
        subprocess.run(
            [docker, "restart", HERMES_CONTAINER],
            check=False,
            timeout=90,
            capture_output=True,
        )
        return True
    except Exception:
        return False


def _learn_pending() -> dict[str, Any]:
    try:
        with httpx.Client(timeout=20.0) as c:
            r = c.get(f"{INGEST_URL}/v1/learn/pending")
            r.raise_for_status()
            return r.json()
    except Exception as exc:
        return {"ok": False, "error": str(exc), "items": []}


def _learn_catalog(q: str = "") -> dict[str, Any]:
    try:
        with httpx.Client(timeout=30.0) as c:
            params = {"q": q} if q else None
            r = c.get(f"{INGEST_URL}/v1/learn/list", params=params)
            r.raise_for_status()
            return r.json() if r.content else {}
    except Exception as exc:
        return {"ok": False, "error": str(exc), "documents": [], "pending": []}


def _learn_find(selector: str) -> dict[str, Any]:
    try:
        with httpx.Client(timeout=30.0) as c:
            r = c.post(
                f"{INGEST_URL}/v1/learn/find",
                json={"pending_id": selector, "selector": selector},
            )
            if r.status_code == 400:
                return {"ok": False, "error": "keyword required", "documents": [], "pending": [], "hits": []}
            r.raise_for_status()
            return r.json() if r.content else {}
    except Exception as exc:
        return {"ok": False, "error": str(exc), "documents": [], "pending": [], "hits": []}


def _learn_scan(root: str, *, thread: str = "", sender: str = "", sender_name: str = "") -> dict[str, Any]:
    try:
        with httpx.Client(timeout=60.0) as c:
            r = c.post(
                f"{INGEST_URL}/v1/learn/scan",
                json={
                    "root": root,
                    "thread_id": thread or None,
                    "sender_id": sender or None,
                    "sender_name": sender_name or None,
                },
            )
            if r.status_code == 400:
                return {"ok": False, "error": (r.text or "bad root")[:200], "submitted": [], "skipped": []}
            r.raise_for_status()
            return r.json() if r.content else {}
    except Exception as extra:
        return {"ok": False, "error": str(extra), "submitted": [], "skipped": []}


def _fmt_learn_scan(data: dict[str, Any]) -> str:
    if not data.get("ok"):
        return f"scan docs failed: {data.get('error', 'unknown')}"
    if data.get("empty"):
        return "docs trống — kiểm tra ENABLE_CLOUDDRIVE / rclone sync /data/clouddrive"
    submitted = data.get("submitted") or []
    skipped = data.get("skipped") or []
    scanned = int(data.get("scanned") or 0)
    n = int(data.get("count") or len(submitted) or 0)
    skip_pending = sum(1 for s in skipped if s.get("reason") == "pending")
    skip_indexed = sum(1 for s in skipped if s.get("reason") == "indexed")
    skip_cap = sum(1 for s in skipped if s.get("reason") == "cap")
    lines = [f"scan docs: {scanned} file, mới {n}, bỏ {len(skipped)}"]
    if skip_indexed:
        lines.append(f"đã học: {skip_indexed}")
    if skip_pending:
        lines.append(f"đã chờ: {skip_pending}")
    if skip_cap:
        lines.append(f"còn lại (cap): {skip_cap} — chạy scan lại sau khi approve")
    for it in submitted[:15]:
        lines.append(f"• {it.get('pending_id')} {it.get('document_name')}")
    if n > 15:
        lines.append(f"… +{n - 15}")
    if n:
        lines.append("Duyệt: !zalo learn approve *")
    elif not skipped:
        lines.append("Không có file mới.")
    return "\n".join(lines)


def _fold_learn_text(s: str) -> str:
    t = s or ""
    for a, b in (
        ("\u2010", "-"),
        ("\u2011", "-"),
        ("\u2012", "-"),
        ("\u2013", "-"),
        ("\u2014", "-"),
        ("\u2212", "-"),
        ("\u00a0", " "),
        ("\u202f", " "),
    ):
        t = t.replace(a, b)
    return t


_LEARN_FILE_RE = re.compile(
    r"([A-Za-z0-9][A-Za-z0-9._\-]{0,180}\.(?:pdf|docx?|xlsx?|xlsm|csv|txt|md|pptx?))",
    re.I,
)


def _learn_filenames(text: str) -> list[str]:
    folded = _fold_learn_text(text or "")
    out: list[str] = []
    seen: set[str] = set()
    for m in _LEARN_FILE_RE.finditer(folded):
        name = m.group(1)
        key = name.lower()
        if key not in seen:
            seen.add(key)
            out.append(name)
    return out


def _learn_sel_from_chat(typed: str, quote: str) -> tuple[str, str]:
    """Typed keyword wins; otherwise send the whole quoted bot message (content)."""
    typed = (typed or "").strip()
    if typed and typed not in {"*", "all"}:
        names = _learn_filenames(typed)
        if names and (len(typed) > 64 or "\n" in typed):
            return ", ".join(names), ""
        return typed, ""
    q = (quote or "").strip()
    if q:
        return q, ""
    return "", "empty"


def _learn_need_sel_reply(action: str, why: str) -> str:
    if action == "find":
        return "Reply tin bot rồi gửi !zalo learn find — xem file khớp, chưa xóa."
    return (
        "Reply tin bot rồi gửi !zalo learn delete — xem list file khớp (chưa xóa).\n"
        "Xóa 1 file: !zalo learn delete <id hoặc tên>\n"
        "Xóa hết list: reply lại → !zalo learn delete all"
    )


def _fmt_learn_catalog(data: dict[str, Any], q: str = "") -> str:
    if not data.get("ok") and data.get("error"):
        return f"learn list failed: {data.get('error')}"
    docs = data.get("documents") or []
    pending = data.get("pending") or []
    q = q or str(data.get("query") or "")
    total = int(data.get("total") or data.get("count") or len(docs))
    if not docs and not pending and total == 0:
        if q:
            return f"Không thấy kiến thức khớp «{q}»."
        return "Chưa có kiến thức đã học. Chờ duyệt: trống."
    lines: list[str] = []
    chunks = int(data.get("chunk_hits") or 0)
    if docs or total:
        head = f"đã học ({total} file, {chunks} chunks)"
        if q:
            head += f" khớp «{q}»"
        lines.append(head + ":")
        for d in docs:
            short = d.get("document_id_short") or str(d.get("document_id") or "")[:8]
            title = d.get("title") or d.get("document_name") or "tài liệu"
            n = d.get("chunks")
            lines.append(f"• {short} {title} ({n})")
        extra = total - len(docs)
        lines.append(f"Còn {max(0, extra)} file.")
    else:
        lines.append("đã học: (trống)" + (f" — không khớp «{q}»" if q else ""))
    if pending:
        lines.append(f"chờ duyệt ({len(pending)}):")
        for it in pending:
            pid = it.get("pending_id")
            who = it.get("sender_name") or "?"
            lines.append(f"• {pid} {who} / {it.get('title') or 'tài liệu'}")
    else:
        lines.append("chờ duyệt: trống")
    lines.append("Xóa: reply tin bot → !zalo learn delete (xem list) rồi delete <id|tên>")
    lines.append("Tìm: reply tin bot → !zalo learn find")
    return "\n".join(lines)


def _fmt_learn_find(data: dict[str, Any], q: str) -> str:
    if not data.get("ok") and data.get("error"):
        return f"find {q} failed: {data.get('error')}"
    docs = data.get("documents") or []
    pending = data.get("pending") or []
    hits = data.get("hits") or []
    total = int(data.get("total") or data.get("count") or len(docs))
    if not docs and not pending and not hits:
        return f"Không thấy kiến thức khớp «{q}»."
    chunks = int(data.get("chunk_hits") or 0)
    lines = [f"khớp «{q}» — {len(docs)}/{total} file, {chunks} chunks:"]
    for d in docs:
        short = d.get("document_id_short") or str(d.get("document_id") or "")[:8]
        title = d.get("title") or "tài liệu"
        n = d.get("chunks")
        lines.append(f"• {short} {title} ({n})")
    extra = total - len(docs)
    lines.append(f"Còn {max(0, extra)} file.")
    if pending:
        lines.append(f"pending {len(pending)}:")
        for it in pending:
            lines.append(f"• {it.get('pending_id')} {it.get('title') or 'tài liệu'}")
    lines.append(f"Xóa khớp: !zalo learn delete {q}")
    return "\n".join(lines)


def _fmt_learn_delete_preview(data: dict[str, Any]) -> str:
    """Reply+delete lists matches; does not remove until they pick or delete all."""
    if not data.get("ok") and data.get("error"):
        return f"learn delete preview failed: {data.get('error')}"
    docs = data.get("documents") or []
    pending = data.get("pending") or []
    if not docs and not pending:
        names = [str(n) for n in (data.get("looked_up") or []) if n]
        lines = ["Không thấy kiến thức khớp tin này trong kho đã học."]
        if names:
            lines.append("Tên trong tin trích (không còn / khác tên lưu):")
            for n in names[:8]:
                lines.append(f"• {n}")
        lines.append("Gõ !zalo learn list để xem file đang có.")
        return "\n".join(lines)
    chunks = int(data.get("chunk_hits") or 0)
    lines = [f"Khớp tin này — {len(docs)} file, {chunks} chunks (chưa xóa):"]
    for d in docs[:20]:
        short = d.get("document_id_short") or str(d.get("document_id") or "")[:8]
        title = d.get("title") or "tài liệu"
        n = d.get("chunks")
        lines.append(f"• {short} {title} ({n})")
    if pending:
        lines.append(f"chờ duyệt ({len(pending)}):")
        for it in pending[:10]:
            lines.append(f"• {it.get('pending_id')} {it.get('title') or 'tài liệu'}")
    lines.append("Xóa 1 file: !zalo learn delete <id hoặc tên>")
    lines.append("Xóa hết list trên: reply lại tin bot → !zalo learn delete all")
    return "\n".join(lines)


def _learn_decide(action: str, selector: str) -> dict[str, Any]:
    if action == "delete":
        path = "delete"
        timeout = 60.0
    else:
        path = "approve" if action == "approve" else "reject"
        timeout = 300.0
    try:
        with httpx.Client(timeout=timeout) as c:
            r = c.post(
                f"{INGEST_URL}/v1/learn/{path}",
                json={"pending_id": selector, "selector": selector},
            )
            if r.status_code == 404:
                return {"ok": False, "error": "not found"}
            if r.status_code >= 400:
                detail = (r.text or "").strip()[:240]
                return {"ok": False, "error": detail or f"HTTP {r.status_code}"}
            data = r.json() if r.content else {}
            if isinstance(data, dict) and not data.get("ok", True):
                return {
                    "ok": False,
                    "error": data.get("error") or "; ".join(data.get("errors") or []) or "failed",
                    "items": data.get("items") or [],
                    "errors": data.get("errors") or [],
                }
            return data
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


def _learn_requester_ids(data: dict[str, Any]) -> set[str]:
    ids: set[str] = set()
    for it in data.get("items") or []:
        if not isinstance(it, dict):
            continue
        for k in ("thread_id", "sender_id"):
            v = str(it.get(k) or "").strip()
            if v:
                ids.add(v)
    return ids


def _learn_reject_ack(
    detail: str, data: dict[str, Any], *, thread: str, sender: str
) -> dict[str, Any]:
    """Reject is silent in the submitter's chat. No INFO dump to the requester."""
    here = {str(thread or "").strip(), str(sender or "").strip()}
    here.discard("")
    if here & _learn_requester_ids(data):
        return {"ok": True, "handled": True, "reply": ""}
    return {"ok": True, "handled": True, "reply": detail}


def _fmt_learn_result(action: str, selector: str, data: dict[str, Any]) -> str:
    if action == "delete":
        if not data.get("ok"):
            return f"delete {selector} failed: {data.get('error', 'unknown')}"
        pts = int(data.get("points") or 0)
        docs = [str(d) for d in (data.get("documents") or []) if d]
        pending = data.get("pending") or []
        if pts == 0 and not pending:
            shown = selector if len(selector) < 80 else selector[:77] + "…"
            return (
                f"Không thấy kiến thức khớp nội dung tin đó («{shown}»). "
                "Reply đúng tin bot rồi !zalo learn delete, hoặc !zalo learn list."
            )
        bits = [f"Đã xóa {pts} chunks"]
        if docs:
            bits.append("file: " + ", ".join(docs[:8]))
        if pending:
            bits.append(f"pending {len(pending)}")
        return " · ".join(bits)
    verb = "Đã học" if action == "approve" else "Đã từ chối"
    if not data.get("ok"):
        return f"{action} {selector} failed: {data.get('error', 'unknown')}"
    items = data.get("items") or []
    if not items and data.get("pending_id"):
        chunks = (data.get("ingest") or {}).get("chunks")
        items = [
            {
                "pending_id": data.get("pending_id"),
                "document_name": "",
                "chunks": chunks,
            }
        ]
    bits: list[str] = []
    for it in items:
        pid = str(it.get("pending_id") or "")
        name = str(it.get("document_name") or "").strip()
        chunks = it.get("chunks")
        err = it.get("error")
        label = " ".join(x for x in (pid, name) if x)
        if err:
            bits.append(f"{label} lỗi:{err}".strip())
        elif chunks is not None and action == "approve":
            bits.append(f"{label} ({chunks} chunks)".strip())
        else:
            bits.append(label or selector)
    n = int(data.get("count") or len(bits) or 0)
    extra = data.get("errors") or []
    if n > 1:
        body = f"{verb} {n}:\n" + "\n".join(f"• {b}" for b in bits)
    else:
        body = f"{verb} {bits[0]}" if bits else f"{verb} {selector}"
    if extra:
        body += "\nlỗi: " + ", ".join(str(x) for x in extra)
    return body


def _auth(authorization: Optional[str], x_admin_token: Optional[str]) -> None:
    if not TOKEN:
        return
    got = (x_admin_token or "").strip()
    if authorization and authorization.lower().startswith("bearer "):
        got = authorization.split(" ", 1)[1].strip()
    if got != TOKEN:
        raise HTTPException(401, "unauthorized")


def _looks_like_thread_id(s: str) -> bool:
    return bool(s) and s.isdigit() and len(s) >= 10


def _bridge_headers() -> dict[str, str]:
    h: dict[str, str] = {}
    if ZALO_TOKEN:
        h["x-bridge-token"] = ZALO_TOKEN
    return h


def _dig_name(obj: Any) -> str:
    """Best-effort display name from zca-js getUserInfo / getGroupInfo shapes."""
    if obj is None:
        return ""
    if isinstance(obj, str):
        return obj.strip()
    if not isinstance(obj, dict):
        return ""
    for key in (
        "displayName",
        "zaloName",
        "name",
        "groupName",
        "dName",
        "username",
        "title",
    ):
        v = obj.get(key)
        if isinstance(v, str) and v.strip():
            return v.strip()
    # Nested maps — zca-js uses snake_case: changed_profiles / unchanged_profiles
    for nest in (
        "changed_profiles",
        "unchanged_profiles",
        "changedProfiles",
        "gridInfoMap",
        "grid_info_map",
        "profiles",
        "groups",
        "info",
        "data",
        "result",
    ):
        inner = obj.get(nest)
        if isinstance(inner, dict):
            if any(k in inner for k in ("displayName", "zaloName", "name", "groupName")):
                got = _dig_name(inner)
                if got:
                    return got
            for v in inner.values():
                got = _dig_name(v)
                if got:
                    return got
    return ""


def _bridge_api(method: str, *args: Any) -> Any:
    """Call zca-js method via hermes-zalo-plugin bridge POST /api/{method}."""
    try:
        with httpx.Client(timeout=20) as c:
            r = c.post(
                f"{ZALO_BRIDGE}/api/{method}",
                json={"args": list(args)},
                headers=_bridge_headers(),
            )
            if r.status_code >= 300:
                return {}
            data = r.json()
            # Bridges sometimes wrap as {ok, result} / {data}
            if isinstance(data, dict):
                for key in ("result", "data", "info"):
                    if key in data and data[key] is not None:
                        return data[key]
                return data
            return data
    except Exception:
        return {}


def _profile_from_userinfo(info: dict[str, Any], uid: str) -> dict[str, Any]:
    """Pick profile dict for uid from zca-js UserInfoResponse."""
    # Keys may be bare uid or `${uid}_0` (zca-js friend_pversion_map)
    keys = (uid, f"{uid}_0", f"{uid}_1")
    for nest in (
        "changed_profiles",
        "unchanged_profiles",
        "changedProfiles",
        "unchangedProfiles",
        "profiles",
    ):
        mp = info.get(nest)
        if not isinstance(mp, dict):
            continue
        for k in keys:
            if k in mp and isinstance(mp[k], dict):
                return mp[k]
        # single entry
        if len(mp) == 1:
            only = next(iter(mp.values()))
            if isinstance(only, dict):
                return only
        # fuzzy: key startswith uid
        for k, v in mp.items():
            if isinstance(v, dict) and str(k).startswith(uid):
                return v
    return {}


def _fetch_user_name(uid: str) -> str:
    """Zalo display name via bridge → zca-js api.getUserInfo(userId).

    Official Zalo OA OpenAPI is not used here; personal account uses unofficial
    zca-js (same as hermes-zalo-plugin). Returns displayName / zaloName.
    """
    uid = (uid or "").strip()
    if not uid:
        return ""
    # Prefer single-string form (zca-js docs); also try list
    for args in ((uid,), ([uid],)):
        info = _bridge_api("getUserInfo", *args)
        if not isinstance(info, dict) or not info:
            continue
        prof = _profile_from_userinfo(info, uid)
        got = _dig_name(prof) or _dig_name(info)
        if got:
            return got
    return ""


def _fetch_group_name(tid: str) -> str:
    tid = (tid or "").strip()
    if not tid:
        return ""
    info = _bridge_api("getGroupInfo", tid)
    if not isinstance(info, dict):
        return ""
    nested = (
        info.get("gridInfoMap")
        or info.get("grid_info_map")
        or info.get("groups")
        or {}
    )
    if isinstance(nested, dict):
        if tid in nested:
            return _dig_name(nested[tid]) or _dig_name(info)
        if len(nested) == 1:
            return _dig_name(next(iter(nested.values()))) or _dig_name(info)
    return _dig_name(info)


def _resolve_user_ref(ref: str, users: list[dict[str, str]]) -> Optional[str]:
    """Resolve name or user:uid / bare uid → uid."""
    ref = (ref or "").strip()
    if not ref:
        return None
    if ref.lower().startswith("user:"):
        ref = ref.split(":", 1)[1].strip()
    if _looks_like_thread_id(ref):
        return ref
    low = ref.lower()
    for u in users:
        if u.get("name") and u["name"].lower() == low:
            return u["id"]
    matches = [u for u in users if u.get("name") and low in u["name"].lower()]
    if len(matches) == 1:
        return matches[0]["id"]
    return None


def _format_user_line(u: dict[str, str]) -> str:
    name = (u.get("name") or "").strip()
    return name if name else f"(chưa có tên · {u['id'][-6:]})"


def _format_thread_line(e: dict[str, str]) -> str:
    name = (e.get("name") or "").strip()
    return name if name else f"(chưa đặt tên · …{e['id'][-6:]})"


class ApproveThread(BaseModel):
    thread_id: str
    note: str = ""


class RemoveThread(BaseModel):
    thread_id: str


class ApproveUser(BaseModel):
    code: str = Field(..., description="Hermes pairing code")


class RevokeUser(BaseModel):
    user_id: str


class ChatCmd(BaseModel):
    sender_id: str
    thread_id: str = ""
    text: str
    chat_type: str = ""  # user|group|dm
    # From Zalo @tags / reply-to (adapter fills these)
    mentions: list[Any] = Field(default_factory=list)
    reply_uid: str = ""
    bot_id: str = ""
    sender_name: str = ""  # Zalo display name of sender
    quote_text: str = ""  # quoted / replied message body (citations)


@app.get("/health")
def health() -> dict[str, Any]:
    _scrub_admin_from_deny()
    try:
        sync_from_allowlist("zalo", _read_entries(), kind="group")
    except Exception:
        pass
    return {"ok": True, "service": "zalo-api", "admin_users": len(_admin_users())}


class ChannelResolveReq(BaseModel):
    platform: str = "zalo"
    ref: str = Field(..., min_length=1)


@app.get("/v1/channels")
def channels_list(
    platform: Optional[str] = None,
    authorization: Optional[str] = Header(default=None),
    x_admin_token: Optional[str] = Header(default=None),
) -> dict[str, Any]:
    _auth(authorization, x_admin_token)
    rows = list_channels(platform)
    return {"ok": True, "channels": rows, "count": len(rows)}


@app.post("/v1/channels/resolve")
def channels_resolve(
    body: ChannelResolveReq,
    authorization: Optional[str] = Header(default=None),
    x_admin_token: Optional[str] = Header(default=None),
) -> dict[str, Any]:
    _auth(authorization, x_admin_token)
    hit = resolve(body.platform, body.ref)
    if not hit:
        return {"ok": False, "error": "not_found", "platform": body.platform, "ref": body.ref}
    return {"ok": True, "channel": hit}


@app.post("/v1/channels/upsert")
def channels_upsert(
    body: dict[str, Any],
    authorization: Optional[str] = Header(default=None),
    x_admin_token: Optional[str] = Header(default=None),
) -> dict[str, Any]:
    _auth(authorization, x_admin_token)
    plat = str(body.get("platform") or "zalo")
    eid = str(body.get("external_id") or body.get("id") or "").strip()
    if not eid:
        raise HTTPException(400, "external_id required")
    row = channel_upsert(
        plat,
        eid,
        name=str(body.get("name") or ""),
        kind=str(body.get("kind") or "group"),
        meta=body.get("meta") if isinstance(body.get("meta"), dict) else None,
    )
    return {"ok": True, "channel": row}


@app.post("/v1/sessions/reset-all")
def api_reset_all_sessions(
    authorization: Optional[str] = Header(default=None),
    x_admin_token: Optional[str] = Header(default=None),
) -> dict[str, Any]:
    """Clear Redis + Hermes file sessions. Same as !zalo clearsessions."""
    _auth(authorization, x_admin_token)
    data = _reset_all_sessions()
    if not data.get("ok"):
        raise HTTPException(502, data.get("error") or "session reset failed")
    files = _wipe_hermes_file_sessions()
    _ensure_timing_rule()
    restarted = _restart_hermes()
    return {
        **data,
        "hermes_files": files.get("deleted_files") or 0,
        "hermes_sample": files.get("sample") or [],
        "hermes_restarted": restarted,
    }


@app.get("/v1/zalo/status")
def zalo_status(
    authorization: Optional[str] = Header(default=None),
    x_admin_token: Optional[str] = Header(default=None),
) -> dict[str, Any]:
    _auth(authorization, x_admin_token)
    try:
        headers = {}
        if ZALO_TOKEN:
            headers["x-bridge-token"] = ZALO_TOKEN
        with httpx.Client(timeout=10) as c:
            r = c.get(f"{ZALO_BRIDGE}/health", headers=headers)
            bridge = r.status_code < 300
    except Exception:
        bridge = False
    entries = _read_entries()
    return {
        "ok": True,
        "bridge_up": bridge,
        "allowed_threads": [e["id"] for e in entries],
        "threads": entries,
        "admin_users_configured": bool(_admin_users()),
    }


@app.post("/v1/zalo/threads/list")
def list_threads(
    authorization: Optional[str] = Header(default=None),
    x_admin_token: Optional[str] = Header(default=None),
) -> dict[str, Any]:
    _auth(authorization, x_admin_token)
    entries = _read_entries()
    return {"ok": True, "threads": [e["id"] for e in entries], "entries": entries}


@app.post("/v1/zalo/threads/approve")
def approve_thread(
    req: ApproveThread,
    authorization: Optional[str] = Header(default=None),
    x_admin_token: Optional[str] = Header(default=None),
) -> dict[str, Any]:
    _auth(authorization, x_admin_token)
    tid = req.thread_id.strip()
    if not tid:
        raise HTTPException(400, "thread_id required")
    cur = _allow_thread(tid, label=req.note)
    return {"ok": True, "thread_id": tid, "allowed_threads": [e["id"] for e in cur], "entries": cur}


@app.post("/v1/zalo/threads/remove")
def remove_thread(
    req: RemoveThread,
    authorization: Optional[str] = Header(default=None),
    x_admin_token: Optional[str] = Header(default=None),
) -> dict[str, Any]:
    _auth(authorization, x_admin_token)
    tid = req.thread_id.strip()
    if not tid:
        raise HTTPException(400, "thread_id required")
    cur = _kick_thread(tid)
    return {"ok": True, "thread_id": tid, "allowed_threads": [e["id"] for e in cur], "entries": cur}


@app.post("/v1/zalo/users/approve")
def approve_user(
    req: ApproveUser,
    authorization: Optional[str] = Header(default=None),
    x_admin_token: Optional[str] = Header(default=None),
) -> dict[str, Any]:
    _auth(authorization, x_admin_token)
    code = req.code.strip()
    if not code:
        raise HTTPException(400, "code required")
    ok, detail = _pairing_approve(code)
    return {"ok": ok, "code": code, "detail": detail}


@app.post("/v1/zalo/users/revoke")
def revoke_user(
    req: RevokeUser,
    authorization: Optional[str] = Header(default=None),
    x_admin_token: Optional[str] = Header(default=None),
) -> dict[str, Any]:
    _auth(authorization, x_admin_token)
    uid = req.user_id.strip()
    if not uid:
        raise HTTPException(400, "user_id required")
    ok, detail = _pairing_revoke(uid)
    _remove_allowed_user(uid)
    return {"ok": ok, "user_id": uid, "detail": detail}


@app.post("/v1/zalo/chat")
def chat_command(
    req: ChatCmd,
    authorization: Optional[str] = Header(default=None),
    x_admin_token: Optional[str] = Header(default=None),
) -> dict[str, Any]:
    """In-Zalo admin: !zalo … — sole admin (file/env); claim/help/whoami open."""
    _auth(authorization, x_admin_token)
    _scrub_admin_from_deny()
    raw_text = (req.text or "").strip()
    quote_text = str(req.quote_text or "").strip()
    # Pull '!zalo …' out of '@Bạn Thân !zalo approve @Trihai' (never chop multi-word @bot)
    m_cmd = re.search(r"!zalo\b[\s\S]*", raw_text, flags=re.I)
    text = (m_cmd.group(0).strip() if m_cmd else raw_text)
    if not text.lower().startswith("!zalo"):
        return {"ok": True, "handled": False, "reply": ""}

    sender = str(req.sender_id or "").strip()
    thread = str(req.thread_id or "").strip()
    chat_type = (req.chat_type or "").strip().lower()
    bot_id = str(req.bot_id or "").strip()
    sender_name = str(req.sender_name or "").strip()
    # Original message for mention pos/len + @Name tokens
    mention_map = _normalize_mentions(
        req.mentions, text=raw_text, exclude={sender, bot_id, thread}
    )
    mention_uids = [m["uid"] for m in mention_map]
    mention_names = {m["uid"]: m["name"] for m in mention_map if m.get("name")}
    reply_uid = str(req.reply_uid or "").strip()
    if reply_uid and reply_uid in {sender, bot_id}:
        reply_uid = ""

    if chat_type in {"user", "dm"}:
        kind = "dm"
    elif chat_type == "group":
        kind = "group"
    else:
        kind = "group" if thread and thread != sender else "dm"

    parts = text.split()
    cmd = (parts[1].lower() if len(parts) > 1 else "help")
    rest = text.split(None, 2)[2].strip() if len(parts) > 2 else ""
    arg0 = parts[2].strip() if len(parts) > 2 else ""

    entries = _read_entries()
    by_id = {e["id"]: e for e in entries}
    here_name = (by_id.get(thread) or {}).get("name") or ""
    if kind == "group" and thread and not here_name:
        fetched = _fetch_group_name(thread)
        if fetched:
            here_name = fetched

    admins = _admin_users()

    if cmd in {"whoami", "me", "here"}:
        my_name = sender_name or _fetch_user_name(sender) or "(unknown)"
        lines = [
            f"bạn={my_name}",
            f"uid={sender or '(missing)'}",
            f"đang ở={'DM' if kind == 'dm' else 'group'}",
        ]
        if kind == "group":
            lines.append(f"nhóm={here_name or '(chưa đặt tên) → !zalo label Tên'}")
        lines.append(f"admin={'yes' if sender in admins else 'no'}")
        if not admins:
            lines.append("hint: sau khi Zalo proxy login → !zalo claim (first setup)")
        elif _admin_is_bot_placeholder(bot_id):
            lines.append("hint: admin đang là tài khoản bridge — gửi !zalo claim để nhận quyền")
        return {"ok": True, "handled": True, "reply": "\n".join(lines)}

    if cmd in {"help", "?"}:
        return {
            "ok": True,
            "handled": True,
            "reply": (
                "!zalo whoami — tên + uid + chat này\n"
                "!zalo claim — first setup: nhận sole admin (khi proxy đã login)\n"
                "!zalo admin — xem admin hiện tại\n"
                "!zalo admin transfer @tag|uid|reply — chuyển admin (chỉ 1 người)\n"
                "!zalo who @tag — (admin) DM tên người\n"
                "!zalo list — nhóm (theo tên)\n"
                "!zalo allow [Tên] — allow nhóm này\n"
                "!zalo label <Tên>\n"
                "!zalo approve @tag — thêm người (báo admin qua notify DM)\n"
                "!zalo users | users on|off\n"
                "!zalo refresh — lấy lại tên user + nhóm từ Zalo\n"
                "!zalo kick @tag | <id>… — kick USER (nhiều id ok)\n"
                "!zalo kick <Tên nhóm> | thread:<id> — kick GROUP\n"
                "!zalo status | clearsessions | help\n"
                "!zalo schedule list — (admin) lịch chat này\n"
                "!zalo schedule list all — (admin) mọi lịch\n"
                "!zalo schedule add|show|update|remove — (admin) CRUD lịch\n"
                "!zalo learn | learn list | learn find | learn scan docs\n"
                "!zalo learn approve|reject <id|*>\n"
                "!zalo learn delete — reply tin bot: xem list (chưa xóa). Rồi delete <id|tên> hoặc delete all\n"
                "(admin: clearsessions = lưu Redis → LTM rồi xóa session; learn = duyệt kiến thức)\n"
                "(ưu tiên @tag / tên; id cũng được)"
            ),
        }

    # First setup / bootstrap: claim sole admin after Zalo proxy is logged in.
    if cmd in {"claim", "iamadmin", "takeadmin"}:
        if not sender:
            return {"ok": True, "handled": True, "reply": "claim cần sender_id"}
        if bot_id and sender == bot_id:
            return {
                "ok": True,
                "handled": True,
                "reply": "Không claim bằng chính tài khoản bridge. Dùng Zalo cá nhân của bạn nhắn bot.",
            }
        if not _bridge_logged_in():
            return {
                "ok": True,
                "handled": True,
                "reply": "Zalo proxy chưa login. Chạy: bash scripts/main/login-zalo.sh rồi !zalo claim",
            }
        if admins and not _admin_is_bot_placeholder(bot_id):
            cur = next(iter(admins))
            return {
                "ok": True,
                "handled": True,
                "reply": f"Đã có admin (uid={cur}). Chỉ admin mới !zalo admin transfer …",
            }
        _write_admin_user(sender, sender_name)
        return {
            "ok": True,
            "handled": True,
            "reply": (
                f"OK: bạn là sole admin\n"
                f"uid={sender}\n"
                f"name={sender_name or _fetch_user_name(sender) or '(unknown)'}\n"
                f"Chuyển quyền: !zalo admin transfer @tag"
            ),
        }

    # admin / admin transfer / admin who — partially open for "who"
    if cmd in {"admin", "owner"}:
        sub = (arg0 or "who").lower()
        if sub in {"who", "status", "show", "me"}:
            if not admins:
                return {
                    "ok": True,
                    "handled": True,
                    "reply": "Chưa có admin. Sau proxy login: !zalo claim",
                }
            aid = next(iter(admins))
            aname = _fetch_user_name(aid) or "(unknown)"
            note = ""
            if _admin_is_bot_placeholder(bot_id):
                note = "\n(seed = tài khoản đã login Zalo proxy — !zalo claim để nhận quyền)"
            return {
                "ok": True,
                "handled": True,
                "reply": f"admin={aname}\nuid={aid}{note}",
            }
        if sub in {"transfer", "give", "set", "to"}:
            if sender not in admins:
                # Allow claim-path instead of silent deny when still bot placeholder
                if _admin_is_bot_placeholder(bot_id):
                    return {
                        "ok": True,
                        "handled": True,
                        "reply": "Admin đang là bridge account. Gửi !zalo claim trước, rồi transfer.",
                    }
                return {"ok": True, "handled": True, "reply": ""}
            targets = list(mention_uids)
            if reply_uid and reply_uid not in targets:
                targets.append(reply_uid)
            # !zalo admin transfer <uid>
            transfer_rest = text.split(None, 3)[3].strip() if len(parts) > 3 else ""
            if not targets and transfer_rest:
                ref = transfer_rest.split()[0].strip()
                if ref.startswith("user:"):
                    ref = ref.split(":", 1)[-1].strip()
                if _looks_like_thread_id(ref):
                    targets = [ref]
                else:
                    resolved = _resolve_user_ref(ref, _read_allowed_users())
                    if resolved:
                        targets = [resolved]
            if not targets:
                return {
                    "ok": True,
                    "handled": True,
                    "reply": (
                        "usage:\n"
                        "!zalo admin transfer @tag\n"
                        "!zalo admin transfer (reply tin họ)\n"
                        "!zalo admin transfer <uid>"
                    ),
                }
            new_uid = targets[0]
            if bot_id and new_uid == bot_id:
                return {
                    "ok": True,
                    "handled": True,
                    "reply": "Không chuyển admin về tài khoản bridge.",
                }
            if new_uid == sender:
                return {"ok": True, "handled": True, "reply": "Bạn đã là admin."}
            new_name = mention_names.get(new_uid) or _fetch_user_name(new_uid) or ""
            _write_admin_user(new_uid, new_name)
            return {
                "ok": True,
                "handled": True,
                "reply": (
                    f"OK: transferred sole admin\n"
                    f"uid={new_uid}\n"
                    f"name={new_name or '(unknown)'}"
                ),
            }
        return {
            "ok": True,
            "handled": True,
            "reply": "usage:\n!zalo admin\n!zalo admin transfer @tag|uid|reply",
        }

    if not admins:
        return {
            "ok": True,
            "handled": True,
            "reply": (
                "Chưa có admin. Sau khi Zalo proxy login, gửi: !zalo claim\n"
                "(hoặc login-zalo seed tài khoản bridge → rồi claim từ Zalo cá nhân)"
            ),
        }
    if sender not in admins:
        return {"ok": True, "handled": True, "reply": ""}

    # Resolve tagged user id — from a group, DM the admin (not the group).
    if cmd in {"who", "whois", "id"}:
        targets = list(mention_uids)
        if reply_uid and reply_uid not in targets:
            targets.append(reply_uid)
        if not targets and rest.startswith("user:") and _looks_like_thread_id(rest.split(":", 1)[-1]):
            targets = [rest.split(":", 1)[-1].strip()]
        if not targets:
            body = (
                "Chưa thấy người được tag.\n"
                "Cách chắc:\n"
                "1) Reply một tin của họ → !zalo who\n"
                "2) Tag từ danh sách @ (không gõ tay @Tên)"
            )
            return _chat_reply(body, reply_dm=(kind == "group"), group_ack="Đã gửi inbox." if kind == "group" else "")
        lines = ["who:"]
        if here_name:
            lines.append(f"trong nhóm={here_name}")
        for u in targets:
            nm = _fetch_user_name(u) or "(không lấy được tên)"
            lines.append(f"• {nm}")
        lines.append("Approve: !zalo approve @tag  hoặc reply + !zalo approve")
        return _chat_reply(
            "\n".join(lines),
            reply_dm=(kind == "group"),
            group_ack="Đã gửi inbox." if kind == "group" else "",
        )

    if cmd in {"list", "threads"}:
        if not entries:
            return {"ok": True, "handled": True, "reply": "allowed: (empty)\nMở group → !zalo allow Tên nhóm"}
        force_refresh = arg0 in {"refresh", "sync", "names"}
        # Refresh missing (or all) names from bridge
        changed = False
        for e in entries:
            if force_refresh or not e.get("name"):
                nm = _fetch_group_name(e["id"])
                if nm and nm != e.get("name"):
                    e["name"] = nm
                    changed = True
                elif nm and not e.get("name"):
                    e["name"] = nm
                    changed = True
        if changed:
            _write_entries(entries)
        lines = [f"nhóm đã allow ({len(entries)}):"]
        for i, e in enumerate(entries, 1):
            mark = "  ← đây" if e["id"] == thread else ""
            lines.append(f"{i}. {_format_thread_line(e)}{mark}")
        lines.append("Đặt tên: !zalo label Tên  |  Kick: !zalo kick <Tên nhóm>")
        return {"ok": True, "handled": True, "reply": "\n".join(lines)}

    if cmd == "status":
        st = zalo_status(authorization, x_admin_token)
        mode = _users_mode()
        n_users = len(_read_allowed_users())
        return {
            "ok": True,
            "handled": True,
            "reply": (
                f"bridge={'up' if st.get('bridge_up') else 'down'}\n"
                f"threads={len(st.get('allowed_threads') or [])}\n"
                f"users_mode={mode} approved_users={n_users}\n"
                f"(open = mọi member trong group allow @bot được)"
            ),
        }

    if cmd in {"clearsessions", "resetsessions", "clear-sessions", "reset-sessions"}:
        data = _reset_all_sessions()
        if not data.get("ok"):
            return {
                "ok": True,
                "handled": True,
                "reply": f"clear sessions failed: {data.get('error', 'unknown')}",
            }
        total = int(data.get("deleted") or 0)
        files = _wipe_hermes_file_sessions()
        n_files = int(files.get("deleted_files") or 0)
        _ensure_timing_rule()
        _restart_hermes()  # recreate state.db after wipe
        ltm = data.get("ltm") or {}
        n_arch = int(ltm.get("archived") or 0)
        msg = (
            f"Đã lưu {n_arch} session vào LTM, xóa {total} Redis + {n_files} file Hermes. "
            f"Chat mới từ lượt sau."
        )
        if NOTIFY_ON_APPROVE and _notify_admin("Zalo — sessions cleared", msg):
            return {"ok": True, "handled": True, "reply": ""}
        return {"ok": True, "handled": True, "reply": msg}

    if cmd in {"schedule", "cron", "lich"}:
        sub = (arg0 or "list").lower()
        tz_name = os.environ.get("TZ", "Asia/Ho_Chi_Minh")
        path = schedule_jobs_file(HERMES_DATA)
        bundle = load_schedule_bundle(path)
        file_jobs: list[dict[str, Any]] = list(bundle.get("jobs") or [])
        jobs: list[dict[str, Any]] = _merge_workflow_schedules(file_jobs)
        rest = " ".join(parts[3:]).strip() if len(parts) > 3 else ""

        if sub in {"list", "ls", "jobs"}:
            want_all, _ = take_schedule_all_flag(rest)
            vis = visible_schedule_jobs(jobs)
            if want_all:
                if vis:
                    return {
                        "ok": True,
                        "handled": True,
                        "reply": fmt_schedule_list(vis, heading="lịch tất cả"),
                    }
                rc, raw = _fetch_hermes_cron_list()
                if rc not in {0, -1} and not raw:
                    return {
                        "ok": True,
                        "handled": True,
                        "reply": "Không đọc được lịch (docker/Hermes).",
                    }
                if raw.strip():
                    return {
                        "ok": True,
                        "handled": True,
                        "reply": fmt_hermes_cron_list(raw, heading="lịch tất cả"),
                    }
                return {
                    "ok": True,
                    "handled": True,
                    "reply": fmt_schedule_list(jobs, heading="lịch tất cả"),
                }
            scoped = schedule_jobs_for_thread(jobs, thread)
            if scoped:
                return {
                    "ok": True,
                    "handled": True,
                    "reply": fmt_schedule_list(scoped, heading="lịch chat này"),
                }
            if vis:
                return {
                    "ok": True,
                    "handled": True,
                    "reply": (
                        "Chưa có lịch trong cuộc chat này.\n"
                        "Admin xem tất cả: !zalo schedule list all"
                    ),
                }
            rc, raw = _fetch_hermes_cron_list()
            if rc not in {0, -1} and not raw:
                return {
                    "ok": True,
                    "handled": True,
                    "reply": "Không đọc được lịch (docker/Hermes).",
                }
            if raw.strip():
                return {
                    "ok": True,
                    "handled": True,
                    "reply": fmt_hermes_cron_list(raw, heading="lịch tất cả"),
                }
            return {
                "ok": True,
                "handled": True,
                "reply": "Chưa có lịch trong cuộc chat này.",
            }

        if sub in {"help", "?"}:
            return {"ok": True, "handled": True, "reply": SCHEDULE_USAGE}

        if sub in {"show", "get", "view"}:
            want_all, sel = take_schedule_all_flag(rest or "")
            vis = visible_schedule_jobs(jobs)
            pool = vis if want_all else schedule_jobs_for_thread(jobs, thread)
            job, err = resolve_schedule_job(pool, sel or "")
            if (err or job is None) and not want_all and sel and not sel.split()[0].isdigit():
                job, err = resolve_schedule_job(vis, sel)
            if err or job is None:
                return {"ok": True, "handled": True, "reply": err or SCHEDULE_USAGE}
            return {"ok": True, "handled": True, "reply": fmt_schedule_show(job)}

        if sub in {"add", "create", "new"}:
            expr, name, prompt = split_add_args(rest)
            if not expr or not prompt:
                return {
                    "ok": True,
                    "handled": True,
                    "reply": "usage:\n!zalo schedule add 6:00 <nội dung>\n!zalo schedule add 0 6 * * * <nội dung>",
                }
            job = new_schedule_job(
                prompt=prompt,
                expr=expr,
                name=name,
                tz_name=tz_name,
                sender=sender,
                thread=thread,
                sender_name=sender_name,
            )
            file_jobs.append(job)
            save_schedule_bundle(path, file_jobs, tz_name)
            _workflow_upsert_schedule(job, expr, prompt, tz_name)
            return {
                "ok": True,
                "handled": True,
                "reply": "Đã thêm lịch:\n" + fmt_schedule_show(job),
            }

        if sub in {"update", "edit", "set"}:
            want_all, sel = take_schedule_all_flag(rest)
            vis = visible_schedule_jobs(jobs)
            pool = vis if want_all else schedule_jobs_for_thread(jobs, thread)
            job, expr, new_prompt, err = parse_schedule_update(sel, pool)
            head = (sel or "").split(None, 1)[0] if sel else ""
            if (err or job is None) and not want_all and head and not head.isdigit():
                job, expr, new_prompt, err = parse_schedule_update(sel, vis)
            if err or job is None:
                return {"ok": True, "handled": True, "reply": err or SCHEDULE_USAGE}
            apply_schedule_update(job, expr, new_prompt)
            jid = str(job.get("id") or "")
            replaced = False
            for i, row in enumerate(file_jobs):
                if str(row.get("id") or "") == jid:
                    file_jobs[i] = job
                    replaced = True
                    break
            if replaced:
                save_schedule_bundle(path, file_jobs, tz_name)
            sch = str((job.get("schedule") or {}).get("expr") or job.get("schedule_display") or "")
            _workflow_upsert_schedule(job, sch, str(job.get("prompt") or ""), tz_name)
            return {
                "ok": True,
                "handled": True,
                "reply": "Đã cập nhật lịch:\n" + fmt_schedule_show(job),
            }

        if sub in {"remove", "rm", "delete", "del"}:
            want_all, sel = take_schedule_all_flag(rest)
            vis = visible_schedule_jobs(jobs)
            pool = vis if want_all else schedule_jobs_for_thread(jobs, thread)
            job, err = resolve_schedule_job(pool, sel)
            if (err or job is None) and not want_all and sel and not sel.split()[0].isdigit():
                job, err = resolve_schedule_job(vis, sel)
            if err or job is None:
                return {"ok": True, "handled": True, "reply": err or SCHEDULE_USAGE}
            jid = str(job.get("id") or "")
            file_jobs = [j for j in file_jobs if str(j.get("id") or "") != jid]
            save_schedule_bundle(path, file_jobs, tz_name)
            _workflow_delete_schedule(jid)
            label = fmt_schedule_show(job).splitlines()[0]
            return {"ok": True, "handled": True, "reply": f"Đã xóa lịch: {label}"}

        return {
            "ok": True,
            "handled": True,
            "reply": SCHEDULE_USAGE,
        }

    if cmd in {"learn", "pending", "kienthuc"}:
        sub = (arg0 or "list").lower()
        if sub in {"approve", "ok", "yes"}:
            sel = " ".join(parts[3:]).strip() if len(parts) > 3 else ""
            if not sel:
                return {
                    "ok": True,
                    "handled": True,
                    "reply": "usage: !zalo learn approve <id|name|*>",
                }
            data = _learn_decide("approve", sel)
            return {"ok": True, "handled": True, "reply": _fmt_learn_result("approve", sel, data)}
        if sub in {"reject", "deny", "no"}:
            sel = " ".join(parts[3:]).strip() if len(parts) > 3 else ""
            if not sel:
                return {
                    "ok": True,
                    "handled": True,
                    "reply": "usage: !zalo learn reject <id|name|*>",
                }
            data = _learn_decide("reject", sel)
            return _learn_reject_ack(
                _fmt_learn_result("reject", sel, data),
                data,
                thread=thread,
                sender=sender,
            )
        if sub in {"delete", "del", "rm", "remove", "unlearn", "forget", "xoa"}:
            typed = " ".join(parts[3:]).strip() if len(parts) > 3 else ""
            wipe_listed = typed.lower() in {"all", "these", "het", "hết"}
            if wipe_listed:
                if not quote_text:
                    return {
                        "ok": True,
                        "handled": True,
                        "reply": "Reply tin bot rồi gửi !zalo learn delete all",
                    }
                data = _learn_decide("delete", quote_text)
                return {
                    "ok": True,
                    "handled": True,
                    "reply": _fmt_learn_result("delete", "listed", data),
                }
            if not typed:
                if not quote_text:
                    return {
                        "ok": True,
                        "handled": True,
                        "reply": _learn_need_sel_reply("delete", "empty"),
                    }
                data = _learn_find(quote_text)
                return {
                    "ok": True,
                    "handled": True,
                    "reply": _fmt_learn_delete_preview(data),
                }
            if typed in {"*", "all"}:
                return {
                    "ok": True,
                    "handled": True,
                    "reply": _learn_need_sel_reply("delete", "empty"),
                }
            data = _learn_decide("delete", typed)
            return {"ok": True, "handled": True, "reply": _fmt_learn_result("delete", typed, data)}
        if sub in {"scan"}:
            target = " ".join(parts[3:]).strip().lower() if len(parts) > 3 else "docs"
            if target in {"", "doc"}:
                target = "docs"
            if target not in {"docs", "clouddrive"}:
                return {
                    "ok": True,
                    "handled": True,
                    "reply": "usage: !zalo learn scan docs",
                }
            data = _learn_scan(target, thread=thread, sender=sender, sender_name=sender_name)
            return {"ok": True, "handled": True, "reply": _fmt_learn_scan(data)}
        if sub in {"find", "search", "tim", "grep"}:
            sel = " ".join(parts[3:]).strip() if len(parts) > 3 else ""
            sel, why = _learn_sel_from_chat(sel, quote_text)
            if not sel or sel in {"*", "all"}:
                return {
                    "ok": True,
                    "handled": True,
                    "reply": _learn_need_sel_reply("find", why),
                }
            data = _learn_find(sel)
            return {"ok": True, "handled": True, "reply": _fmt_learn_find(data, sel)}
        if sub in {"", "list", "ls", "docs", "pending"}:
            q = " ".join(parts[3:]).strip() if sub in {"list", "ls", "docs"} and len(parts) > 3 else ""
            data = _learn_catalog(q)
            return {"ok": True, "handled": True, "reply": _fmt_learn_catalog(data, q)}
        sel = " ".join(parts[2:]).strip()
        data = _learn_find(sel)
        return {"ok": True, "handled": True, "reply": _fmt_learn_find(data, sel)}

    if cmd in {"label", "name", "rename"}:
        if not rest:
            return {"ok": True, "handled": True, "reply": "usage: !zalo label Tên nhóm (trong group đó)"}
        if not thread:
            return {"ok": True, "handled": True, "reply": "no thread context"}
        _allow_thread(thread, label=rest)
        return {
            "ok": True,
            "handled": True,
            "reply": f"đã đặt tên nhóm: {rest}",
        }

    if cmd in {"allow", "add", "approve-thread"}:
        if not rest:
            tid, label = thread, ""
        elif _looks_like_thread_id(arg0):
            tid = arg0
            label = " ".join(parts[3:]).strip() if len(parts) > 3 else ""
        else:
            # treat whole rest as display name for CURRENT chat
            tid, label = thread, rest
        if not tid:
            return {
                "ok": True,
                "handled": True,
                "reply": "usage:\n!zalo allow\n!zalo allow Tên nhóm",
            }
        if not label:
            label = _fetch_group_name(tid) or ""
        cur = _allow_thread(tid, label=label)
        shown = label or (by_id.get(tid) or {}).get("name") or _fetch_group_name(tid) or "(chưa đặt tên)"
        here = " (nhóm này)" if tid == thread else ""
        return {
            "ok": True,
            "handled": True,
            "reply": f"allowed{here}: {shown}\n({len(cur)} nhóm)",
        }

    if cmd in {"refresh", "syncnames", "names"}:
        users = _read_allowed_users()
        u_ok = g_ok = 0
        for u in users:
            nm = _fetch_user_name(u["id"])
            if nm:
                u["name"] = nm
                u_ok += 1
        _write_allowed_users(users)
        for e in entries:
            nm = _fetch_group_name(e["id"])
            if nm:
                e["name"] = nm
                g_ok += 1
        _write_entries(entries)
        return {
            "ok": True,
            "handled": True,
            "reply": (
                f"refresh tên:\n"
                f"• users: {u_ok}/{len(users)} có tên\n"
                f"• groups: {g_ok}/{len(entries)} có tên\n"
                f"!zalo users | !zalo list"
            ),
        }

    if cmd in {"kick", "remove", "deny", "revoke"}:
        users_now = _read_allowed_users()
        user_ids = {u["id"] for u in users_now}
        thread_ids = {e["id"] for e in entries}
        user_targets = list(mention_uids)
        if reply_uid and reply_uid not in user_targets:
            user_targets.append(reply_uid)

        force_user = rest.lower().startswith("user:")
        force_thread = rest.lower().startswith("thread:") or rest.lower().startswith("group:")
        # Collect all long digit ids (supports multi-line paste of several !zalo kick …)
        id_hits = re.findall(r"\d{10,}", rest or "")
        if force_user:
            uid = rest.split(":", 1)[1].strip()
            id_hits = re.findall(r"\d{10,}", uid) or ([uid] if _looks_like_thread_id(uid) else [])
        if force_thread:
            tid_only = rest.split(":", 1)[1].strip()
            id_hits = re.findall(r"\d{10,}", tid_only) or (
                [tid_only] if _looks_like_thread_id(tid_only) else []
            )

        kick_users: list[str] = []
        kick_threads: list[str] = []
        for iid in id_hits:
            if iid in _admin_users() or (iid == sender and kind == "dm"):
                continue
            if force_thread:
                kick_threads.append(iid)
            elif force_user or iid in user_ids:
                kick_users.append(iid)
            elif iid in thread_ids:
                kick_threads.append(iid)
            else:
                # unknown id → treat as USER (re-approve flow)
                kick_users.append(iid)

        for uid in user_targets:
            if uid not in kick_users:
                kick_users.append(uid)

        if not kick_users and not kick_threads and rest.startswith("@"):
            return {
                "ok": True,
                "handled": True,
                "reply": "Tag Zalo thật từ danh sách @:\n@bot !zalo kick @NgườiĐó",
            }

        # Name without @ / without digit ids → resolve by display name
        if (
            rest
            and not force_user
            and not force_thread
            and not rest.startswith("@")
            and not id_hits
            and not kick_users
        ):
            # first line only for name match
            name_ref = rest.splitlines()[0].strip()
            uid_hit = _resolve_user_ref(name_ref, users_now)
            tid_hit = _resolve_thread_ref(name_ref, entries)
            if uid_hit and tid_hit:
                un = next((u["name"] for u in users_now if u["id"] == uid_hit), uid_hit)
                tn = (by_id.get(tid_hit) or {}).get("name") or tid_hit
                return {
                    "ok": True,
                    "handled": True,
                    "reply": (
                        f"'{name_ref}' khớp cả người ({un}) và nhóm ({tn}).\n"
                        f"!zalo kick user:{uid_hit}\n"
                        f"!zalo kick thread:{tid_hit}"
                    ),
                }
            if uid_hit:
                kick_users.append(uid_hit)
            elif tid_hit:
                kick_threads.append(tid_hit)

        lines: list[str] = []
        if kick_users:
            lines.append("đã kick user:")
            for uid in kick_users:
                nm = next((u["name"] for u in users_now if u["id"] == uid), "") or _fetch_user_name(
                    uid
                )
                _pairing_revoke(uid)
                _remove_allowed_user(uid)
                lines.append(f"• {nm or '(no name)'} · …{uid[-6:]}")
        if kick_threads:
            lines.append("đã kick nhóm:")
            for tid in kick_threads:
                name = (by_id.get(tid) or {}).get("name") or _fetch_group_name(tid) or tid
                before = {e["id"] for e in _read_entries()}
                _kick_thread(tid)
                if tid not in before:
                    lines.append(f"• {name} (vốn không trong list)")
                else:
                    lines.append(f"• {name}")
        if lines:
            lines.append("Thêm lại + lấy tên: !zalo approve @tag  |  !zalo allow")
            lines.append("Hoặc chỉ refresh tên: !zalo refresh")
            return {"ok": True, "handled": True, "reply": "\n".join(lines)}

        # Kick CURRENT group if no args
        if not rest and kind == "group" and thread:
            name = here_name or _fetch_group_name(thread) or thread
            cur = _kick_thread(thread)
            return {
                "ok": True,
                "handled": True,
                "reply": f"đã kick nhóm: {name}\n({len(cur)} nhóm còn lại)",
            }

        return {
            "ok": True,
            "handled": True,
            "reply": (
                "usage:\n"
                "!zalo kick @tag\n"
                "!zalo kick <id> [<id>…]   (user trong !zalo users)\n"
                "!zalo kick thread:<id>    (nhóm)\n"
                "!zalo kick <Tên>\n"
                "!zalo refresh             (lấy lại tên, không cần kick)"
            ),
        }

    if cmd in {"users", "userlist"}:
        mode = _users_mode()
        users = _read_allowed_users()
        if arg0 in {"on", "strict", "lock"}:
            _set_users_mode("strict")
            return {
                "ok": True,
                "handled": True,
                "reply": (
                    "users mode=strict\n"
                    "Chỉ người trong list (+ admin) được chat trong group allow.\n"
                    f"list={len(users)} — thêm: !zalo approve @tag"
                ),
            }
        if arg0 in {"off", "open", "all"}:
            _set_users_mode("open")
            return {
                "ok": True,
                "handled": True,
                "reply": "users mode=open\nMọi người trong group đã allow đều @bot được.",
            }
        force_refresh = arg0 in {"refresh", "sync", "names"}
        # Backfill / refresh Zalo names
        changed = False
        for u in users:
            if force_refresh or not u.get("name"):
                nm = _fetch_user_name(u["id"])
                if nm and nm != u.get("name"):
                    u["name"] = nm
                    changed = True
                elif nm and not u.get("name"):
                    u["name"] = nm
                    changed = True
        if changed:
            _write_allowed_users(users)
        lines = [f"users mode={mode}"]
        if mode == "open":
            lines.append("(open = ai trong group allow cũng chat được)")
        else:
            lines.append("(strict = chỉ list dưới + admin)")
        if not users:
            lines.append("approved: (empty)")
        else:
            lines.append(f"approved ({len(users)}):")
            for i, u in enumerate(users, 1):
                lines.append(f"{i}. {_format_user_line(u)}")
        lines.append("Approve: !zalo approve @tag  |  Kick: !zalo kick <Tên>")
        return {"ok": True, "handled": True, "reply": "\n".join(lines)}

    if cmd == "approve":
        user_targets = list(mention_uids)
        if reply_uid and reply_uid not in user_targets:
            user_targets.append(reply_uid)
        if user_targets or (rest.startswith("@") and not _looks_like_thread_id(arg0)):
            if not user_targets:
                return {
                    "ok": True,
                    "handled": True,
                    "reply": "Tag Zalo thật:\n@bot !zalo approve @NgườiĐó\nhoặc reply tin họ + !zalo approve",
                }
            lines = ["đã approve:"]
            for uid in user_targets:
                if uid in {e["id"] for e in entries}:
                    lines.append(f"• (bỏ qua — đây là id nhóm, dùng !zalo allow)")
                    continue
                # Primary: zca-js getUserInfo via bridge; fallback: @tag text / mention
                nm = (
                    _fetch_user_name(uid)
                    or mention_names.get(uid)
                    or _name_from_at_text(rest, uid, mention_uids)
                    or _name_from_at_text(raw_text, uid, mention_uids)
                )
                _add_allowed_user(uid, name=nm)
                lines.append(f"• {nm}" if nm else f"• (uid …{uid[-6:]} — chưa có tên)")
            mode = _users_mode()
            tip = (
                "\n(mode=open → họ vốn chat được trong group allow)"
                if mode == "open"
                else "\n(mode=strict → đã mở chat)"
            )
            where = f"from={kind}:{here_name or thread}"
            detail = "\n".join(lines) + tip + f"\n({where})"
            return _approve_ack(detail, kind=kind)

        uid_arg = ""
        if rest.lower().startswith("user:"):
            uid_arg = rest.split(":", 1)[1].strip()
        elif _looks_like_thread_id(arg0):
            uid_arg = arg0
        if uid_arg:
            if uid_arg in {e["id"] for e in entries} or (
                uid_arg == thread and kind == "group"
            ):
                return {
                    "ok": True,
                    "handled": True,
                    "reply": (
                        "Đây là id NHÓM, không phải người.\n"
                        "Allow nhóm: mở group → !zalo allow\n"
                        "Approve người: !zalo approve @tag"
                    ),
                }
            nm = _fetch_user_name(uid_arg)
            _add_allowed_user(uid_arg, name=nm)
            mode = _users_mode()
            tip = "\n(mode=strict → đã mở chat)" if mode == "strict" else ""
            detail = f"approved: {nm or 'user'}{tip}\n(from={kind}:{here_name or thread})"
            return _approve_ack(detail, kind=kind)

        if not arg0:
            return {
                "ok": True,
                "handled": True,
                "reply": "usage:\n!zalo approve @tag\n!zalo approve <pairing-code>",
            }
        ok, detail = _pairing_approve(arg0)
        msg = f"approve code: {'ok' if ok else 'fail'} {detail}".strip()
        if ok:
            return _approve_ack(msg + f"\n(from={kind}:{here_name or thread})", kind=kind)
        return {"ok": True, "handled": True, "reply": msg}

    return {"ok": True, "handled": True, "reply": f"unknown: !zalo {cmd}\n!zalo help"}


def _chat_reply(reply: str, *, reply_dm: bool = False, group_ack: str = "") -> dict[str, Any]:
    """Build /v1/zalo/chat response. reply_dm → adapter DMs the admin from a group."""
    out: dict[str, Any] = {"ok": True, "handled": True, "reply": reply}
    if reply_dm:
        out["reply_dm"] = True
    ack = (group_ack or "").strip()
    if ack:
        out["group_ack"] = ack
    return out


def _notify_admin(title: str, body: str, *, severity: str = "info") -> bool:
    """Send via NotificationManager → sole Zalo admin (file) or NOTIFY_ZALO_THREAD."""
    if not NOTIFY_URL:
        return False
    admins = _admin_users()
    dest = next(iter(admins), "")
    payload: dict[str, Any] = {
        "title": title,
        "body": body,
        "severity": severity,
        "channels": ["zalo"],
        "kind": "alert",
    }
    if dest:
        payload["zalo_thread_id"] = dest
        payload["zalo_thread_type"] = "user"
    try:
        with httpx.Client(timeout=20) as c:
            r = c.post(
                f"{NOTIFY_URL}/v1/notify",
                json=payload,
            )
            if r.status_code >= 300:
                return False
            data = r.json() if r.content else {}
            return bool((data.get("results") or {}).get("zalo"))
    except Exception:
        return False


def _approve_ack(detail: str, *, kind: str) -> dict[str, Any]:
    """Approve success: prefer notify → admin Zalo; else fallback DM/in-thread."""
    if NOTIFY_ON_APPROVE and _notify_admin("Zalo — user approved", detail):
        # Silent in the channel where !zalo approve was typed.
        return {"ok": True, "handled": True, "reply": ""}
    # Fallback if notify down / no dest
    return _chat_reply(
        detail + "\n(notify chưa gửi — kiểm tra notify + Zalo admin)",
        reply_dm=(kind == "group"),
        group_ack="",
    )


def _normalize_mentions(
    mentions: list[Any],
    *,
    text: str = "",
    exclude: Optional[set[str]] = None,
) -> list[dict[str, str]]:
    """Return [{uid, name}] from bridge mentions and/or @Name in text.

    Zalo mentions are often {uid, pos, len} — display name is text[pos:pos+len].
    """
    exclude = {str(x) for x in (exclude or set()) if x}
    out: list[dict[str, str]] = []
    seen: set[str] = set()
    raw_text = text or ""

    for m in mentions or []:
        uid = ""
        name = ""
        if isinstance(m, dict):
            uid = str(m.get("uid") or m.get("userId") or m.get("id") or "").strip()
            name = _dig_name(m) or str(
                m.get("dName") or m.get("displayName") or m.get("name") or ""
            ).strip()
            # Slice display name from message using pos/len
            try:
                pos = m.get("pos")
                length = m.get("len") or m.get("length")
                if pos is not None and length is not None:
                    pos_i, len_i = int(pos), int(length)
                    if 0 <= pos_i < len(raw_text) and len_i > 0:
                        slice_name = raw_text[pos_i : pos_i + len_i].strip()
                        slice_name = slice_name.lstrip("@").strip()
                        if slice_name:
                            name = name or slice_name
            except Exception:
                pass
        else:
            uid = str(m or "").strip()
        if not uid or uid in exclude or uid in seen or not uid.isdigit():
            continue
        seen.add(uid)
        out.append({"uid": uid, "name": name})

    # Pair leftover @Names in command text with mention uids (by order)
    at_names = re.findall(r"@([^\s@]+)", raw_text)
    # Drop bot-ish first tags already excluded; keep names for unnamed uids
    unnamed = [x for x in out if not x.get("name")]
    name_i = 0
    for label in at_names:
        label = label.strip()
        if not label or label.isdigit():
            continue
        # skip if looks like bot mention already handled
        while name_i < len(unnamed) and unnamed[name_i].get("name"):
            name_i += 1
        if name_i < len(unnamed):
            unnamed[name_i]["name"] = label
            name_i += 1

    return out


def _normalize_mention_uids(
    mentions: list[Any], exclude: Optional[set[str]] = None
) -> list[str]:
    return [m["uid"] for m in _normalize_mentions(mentions, exclude=exclude)]


def _name_from_at_text(rest: str, uid: str, mention_uids: list[str]) -> str:
    """Map @Name tokens in approve text onto mention uids by order."""
    names = [n for n in re.findall(r"@([^\s@]+)", rest or "") if n and not n.isdigit()]
    if not names or uid not in mention_uids:
        return ""
    try:
        idx = mention_uids.index(uid)
    except ValueError:
        return ""
    # If bot was also tagged earlier in full text, names may be offset — prefer last names
    if len(names) >= len(mention_uids):
        names = names[-len(mention_uids) :]
    if 0 <= idx < len(names):
        return names[idx].strip()
    if len(names) == 1 and len(mention_uids) == 1:
        return names[0].strip()
    return ""


def _resolve_thread_ref(ref: str, entries: list[dict[str, str]]) -> Optional[str]:
    ref = ref.strip()
    if _looks_like_thread_id(ref):
        return ref
    low = ref.lower()
    for e in entries:
        if e["name"] and e["name"].lower() == low:
            return e["id"]
    matches = [e for e in entries if e["name"] and low in e["name"].lower()]
    if len(matches) == 1:
        return matches[0]["id"]
    return None


def _allow_thread(tid: str, label: str = "") -> list[dict[str, str]]:
    tid = tid.strip()
    _undeny_thread(tid)  # clear prior !zalo kick
    entries = _read_entries()
    found = False
    for e in entries:
        if e["id"] == tid:
            found = True
            if label.strip():
                e["name"] = label.strip()
            break
    if not found:
        entries.append({"id": tid, "name": label.strip()})
    _write_entries(entries)
    try:
        with httpx.Client(timeout=10) as c:
            c.post(
                f"{AUTHZ_URL}/v1/threads/approve",
                json={"thread_id": tid, "note": label},
            )
    except Exception:
        pass
    return entries


def _read_denied_threads() -> set[str]:
    out: set[str] = set()
    try:
        if os.path.isfile(DENIED_THREADS_FILE):
            with open(DENIED_THREADS_FILE, encoding="utf-8") as f:
                for line in f:
                    t = line.strip()
                    if not t or t.startswith("#"):
                        continue
                    if "|" in t:
                        t = t.split("|", 1)[0].strip()
                    if t:
                        out.add(t)
    except Exception:
        pass
    return out


def _write_denied_threads(ids: set[str]) -> None:
    os.makedirs(os.path.dirname(DENIED_THREADS_FILE) or ".", exist_ok=True)
    with open(DENIED_THREADS_FILE, "w", encoding="utf-8") as f:
        f.write("# managed by zalo-api — kicked threads (overrides .env allow)\n")
        for tid in sorted(ids):
            f.write(tid + "\n")


def _deny_thread(tid: str) -> None:
    d = _read_denied_threads()
    d.add(tid.strip())
    _write_denied_threads(d)


def _undeny_thread(tid: str) -> None:
    d = _read_denied_threads()
    d.discard(tid.strip())
    _write_denied_threads(d)


def _scrub_admin_from_deny() -> None:
    """Never keep admin DM uids in the kicked-threads deny list."""
    admins = _admin_users()
    if not admins:
        return
    d = _read_denied_threads()
    before = set(d)
    for a in admins:
        d.discard(a)
    if d != before:
        _write_denied_threads(d)


def _kick_thread(tid: str) -> list[dict[str, str]]:
    """Remove from file allowlist + deny so .env ZALO_ALLOWED_THREADS cannot re-add."""
    tid = tid.strip()
    if tid in _admin_users():
        return _read_entries()
    # Rewrite allow file without this id (ignore deny filter for the write source)
    raw: list[dict[str, str]] = []
    seen: set[str] = set()
    for t in os.environ.get("ZALO_ALLOWED_THREADS", "").split(","):
        t = t.strip()
        if t and t != tid and t not in seen:
            seen.add(t)
            raw.append({"id": t, "name": ""})
    try:
        if os.path.isfile(ALLOWED_FILE):
            with open(ALLOWED_FILE, encoding="utf-8") as f:
                for line in f:
                    s = line.strip()
                    if not s or s.startswith("#"):
                        continue
                    if "|" in s:
                        i, n = s.split("|", 1)
                    elif " #" in s:
                        i, n = s.split(" #", 1)
                    else:
                        i, n = s, ""
                    i = i.strip()
                    if i and i != tid and i not in seen:
                        seen.add(i)
                        raw.append({"id": i, "name": n.strip()})
    except Exception:
        pass
    _write_entries(raw)
    _deny_thread(tid)
    return _read_entries()


def _pairing_approve(code: str) -> tuple[bool, str]:
    try:
        r = subprocess.run(
            ["docker", "exec", HERMES_CONTAINER, "hermes", "pairing", "approve", "zalo", code],
            capture_output=True,
            text=True,
            timeout=60,
        )
        detail = ((r.stdout or "") + (r.stderr or "")).strip()[:200]
        return r.returncode == 0, detail
    except Exception as e:
        return False, type(e).__name__


def _pairing_revoke(user_id: str) -> tuple[bool, str]:
    attempts = [
        ["docker", "exec", HERMES_CONTAINER, "hermes", "pairing", "revoke", "zalo", user_id],
        ["docker", "exec", HERMES_CONTAINER, "hermes", "pairing", "reject", "zalo", user_id],
        ["docker", "exec", HERMES_CONTAINER, "hermes", "pairing", "remove", "zalo", user_id],
    ]
    last = "unsupported"
    for cmd in attempts:
        try:
            r = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
            detail = ((r.stdout or "") + (r.stderr or "")).strip()[:200]
            if r.returncode == 0:
                return True, detail
            last = detail or f"exit {r.returncode}"
        except Exception as e:
            last = type(e).__name__
    return False, last


def _read_entries() -> list[dict[str, str]]:
    """Parse allowlist: 'id' or 'id | name' (also legacy 'id # name')."""
    ordered: list[dict[str, str]] = []
    seen: set[str] = set()

    def add(tid: str, name: str = "") -> None:
        tid = tid.strip()
        if not tid or tid in seen:
            if tid in seen and name:
                for e in ordered:
                    if e["id"] == tid and name and not e["name"]:
                        e["name"] = name
            return
        seen.add(tid)
        ordered.append({"id": tid, "name": name.strip()})

    denied = _read_denied_threads()

    for t in os.environ.get("ZALO_ALLOWED_THREADS", "").split(","):
        if t.strip() and t.strip() not in denied:
            add(t.strip(), "")

    try:
        if os.path.isfile(ALLOWED_FILE):
            with open(ALLOWED_FILE, encoding="utf-8") as f:
                for line in f:
                    raw = line.strip()
                    if not raw or raw.startswith("#"):
                        continue
                    if "|" in raw:
                        tid, name = raw.split("|", 1)
                        tid = tid.strip()
                        if tid not in denied:
                            add(tid, name.strip())
                    elif " #" in raw:
                        tid, name = raw.split(" #", 1)
                        tid = tid.strip()
                        if tid not in denied:
                            add(tid, name.strip())
                    else:
                        if raw not in denied:
                            add(raw, "")
    except Exception:
        pass
    return ordered


def _write_entries(entries: list[dict[str, str]]) -> None:
    os.makedirs(os.path.dirname(ALLOWED_FILE) or ".", exist_ok=True)
    with open(ALLOWED_FILE, "w", encoding="utf-8") as f:
        f.write("# managed by zalo-api — format: threadId | display name\n")
        for e in entries:
            if e.get("name"):
                f.write(f"{e['id']} | {e['name']}\n")
            else:
                f.write(f"{e['id']}\n")
    try:
        sync_from_allowlist("zalo", entries, kind="group")
    except Exception:
        pass


USERS_MODE_FILE = os.environ.get(
    "ZALO_USERS_MODE_FILE", "/data/hermes/zalo_users_mode.txt"
)


def _users_mode() -> str:
    """open = anyone in allowed threads; strict = only approved user ids (+ admins)."""
    env = (os.environ.get("ZALO_USERS_STRICT") or "").strip().lower()
    if env in {"1", "true", "yes", "on", "strict"}:
        return "strict"
    try:
        if os.path.isfile(USERS_MODE_FILE):
            raw = open(USERS_MODE_FILE, encoding="utf-8").read().strip().lower()
            if raw in {"strict", "on", "lock"}:
                return "strict"
            if raw in {"open", "off", "all"}:
                return "open"
    except Exception:
        pass
    return "open"


def _set_users_mode(mode: str) -> None:
    mode = "strict" if mode == "strict" else "open"
    os.makedirs(os.path.dirname(USERS_MODE_FILE) or ".", exist_ok=True)
    with open(USERS_MODE_FILE, "w", encoding="utf-8") as f:
        f.write(mode + "\n")


def _read_allowed_users() -> list[dict[str, str]]:
    out: list[dict[str, str]] = []
    seen: set[str] = set()
    for u in os.environ.get("ZALO_ALLOWED_USERS", "").split(","):
        uid = u.strip()
        if uid and uid not in seen:
            seen.add(uid)
            out.append({"id": uid, "name": ""})
    try:
        if os.path.isfile(ALLOWED_USERS_FILE):
            with open(ALLOWED_USERS_FILE, encoding="utf-8") as f:
                for line in f:
                    raw = line.strip()
                    if not raw or raw.startswith("#"):
                        continue
                    if "|" in raw:
                        uid, name = raw.split("|", 1)
                    else:
                        uid, name = raw, ""
                    uid = uid.strip()
                    if uid and uid not in seen:
                        seen.add(uid)
                        out.append({"id": uid, "name": name.strip()})
    except Exception:
        pass
    return out


def _write_allowed_users(users: list[dict[str, str]]) -> None:
    os.makedirs(os.path.dirname(ALLOWED_USERS_FILE) or ".", exist_ok=True)
    with open(ALLOWED_USERS_FILE, "w", encoding="utf-8") as f:
        f.write("# managed by zalo-api — format: uid | optional name\n")
        for u in users:
            if u.get("name"):
                f.write(f"{u['id']} | {u['name']}\n")
            else:
                f.write(f"{u['id']}\n")


def _add_allowed_user(uid: str, name: str = "") -> list[dict[str, str]]:
    users = _read_allowed_users()
    for u in users:
        if u["id"] == uid:
            if name:
                u["name"] = name
            _write_allowed_users(users)
            return users
    users.append({"id": uid, "name": name.strip()})
    _write_allowed_users(users)
    return users


def _remove_allowed_user(uid: str) -> None:
    users = [u for u in _read_allowed_users() if u["id"] != uid]
    _write_allowed_users(users)
