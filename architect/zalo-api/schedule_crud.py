"""CRUD for Hermes jobs.json (shared cron dir). User-facing: lịch / schedule."""
from __future__ import annotations

import re
import secrets
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional
from zoneinfo import ZoneInfo

from schedule_list import (
    ZALO_SCHEDULE_LIST_LIMIT,
    fmt_hermes_cron_list,
    prompt_is_clock_only,
    schedule_row_label,
)

JOBS_NAME = "jobs.json"
_CRON5_RE = re.compile(
    r"^(\S+)\s+(\S+)\s+(\S+)\s+(\S+)\s+(\S+)(?:\s+(\S+))?\s*$"
)
_HHMM_RE = re.compile(
    r"^(?P<h>\d{1,2})\s*[:h]\s*(?P<m>\d{2})?\s*(?P<ampm>am|pm|sáng|sang|chiều|chieu|tối|toi)?$",
    re.I,
)
_FLAG_TIME_RE = re.compile(r"--time(?:r)?(?:\s+|=)(\S+)", re.I)
_FLAG_SCHED_RE = re.compile(r"--schedule(?:\s+|=)(.+)$", re.I)
_TIMER_PREFIX_RE = re.compile(
    r"^(?:timer|hẹn\s*giờ|hen\s*gio|lúc|luc|at)\s+",
    re.I,
)
_INTERNAL_RE = re.compile(
    r"daily[-_]?optimize|optimize[-_]?rules|new.?session|rotate.?session|clearsession",
    re.I,
)


def _now_iso(tz_name: str) -> str:
    tz = ZoneInfo(tz_name)
    return datetime.now(tz).isoformat()


def jobs_file(data_dir: str) -> Path:
    return Path(data_dir) / "cron" / JOBS_NAME


def _relax_jobs_perms(path: Path) -> None:
    """Hermes ticks as UID 1000; zalo-api writes as root. Keep the file writable."""
    import os

    try:
        os.chmod(path, 0o664)
    except OSError:
        pass
    try:
        uid = int(os.getenv("HERMES_UID") or "1000")
        gid = int(os.getenv("HERMES_GID") or "1000")
        os.chown(path, uid, gid)
    except (OSError, ValueError):
        try:
            os.chmod(path, 0o666)
        except OSError:
            pass


def load_bundle(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {"jobs": [], "updated_at": None}
    try:
        data = __import__("json").loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {"jobs": [], "updated_at": None}
    if isinstance(data, dict):
        jobs = data.get("jobs") if isinstance(data.get("jobs"), list) else []
        return {"jobs": [j for j in jobs if isinstance(j, dict)], "updated_at": data.get("updated_at")}
    if isinstance(data, list):
        return {"jobs": [j for j in data if isinstance(j, dict)], "updated_at": None}
    return {"jobs": [], "updated_at": None}


def save_bundle(path: Path, jobs: list[dict[str, Any]], tz_name: str) -> None:
    """Write jobs.json (zalo-api image — no backup-restore import)."""
    import json
    import os
    import tempfile

    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {"jobs": jobs, "updated_at": _now_iso(tz_name)}
    raw = json.dumps(payload, ensure_ascii=False, indent=2) + "\n"
    fd, tmp = tempfile.mkstemp(prefix="jobs.", suffix=".json", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as f:
            f.write(raw)
        os.replace(tmp, path)
        _relax_jobs_perms(path)
    except Exception:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def visible_jobs(jobs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for job in jobs:
        label = schedule_row_label(job)
        if not label:
            continue
        name = str(job.get("name") or job.get("id") or "")
        prompt = str(job.get("prompt") or "")
        if _INTERNAL_RE.search(name) or _INTERNAL_RE.search(prompt):
            continue
        out.append(job)
    return out


def job_origin_thread_ids(job: dict[str, Any]) -> set[str]:
    origin = job.get("origin") if isinstance(job.get("origin"), dict) else {}
    out: set[str] = set()
    for key in ("chat_id", "thread_id"):
        val = str(origin.get(key) or "").strip()
        if val:
            out.add(val)
    return out


def jobs_for_thread(jobs: list[dict[str, Any]], thread_id: str) -> list[dict[str, Any]]:
    """User jobs whose origin is this Zalo thread (DM or group)."""
    tid = (thread_id or "").strip()
    vis = visible_jobs(jobs)
    if not tid:
        return vis
    return [j for j in vis if tid in job_origin_thread_ids(j)]


def take_all_flag(rest: str) -> tuple[bool, str]:
    """Split leading all/*/--all from schedule rest (admin global scope)."""
    raw = (rest or "").strip()
    if not raw:
        return False, ""
    tokens = raw.split(None, 1)
    if tokens[0].lower() in {"all", "*", "--all"}:
        return True, tokens[1].strip() if len(tokens) > 1 else ""
    return False, raw


SCOPE_THREAD = "thread"
SCOPE_GLOBAL = "global"
SCOPE_GROUP = "group"
_ALL_TOKENS = {"all", "*", "--all"}
_GROUP_TOKENS = {"group", "nhom", "nhóm", "--group"}
_INDEX_RANGE_RE = re.compile(r"^(\d+)\s*[-–]\s*(\d+)$")
REMOVE_BULK_CAP = 100


def parse_remove_request(rest: str) -> dict[str, Any]:
    """Parse `!zalo schedule remove …` into a deterministic delete request.

    | Input | scope | selectors | every |
    |---|---|---|---|
    | `3` | thread | `["3"]` | no |
    | `1 3 5` / `1,3,5` / `1-3` | thread | expanded indexes | no |
    | `all` | global | `[]` | yes |
    | `all 2` | global | `["2"]` | no |
    | `group LC group` | group | `[]` | yes |
    | `group LC group 1-2` | group | expanded indexes | no |
    """
    raw = (rest or "").strip()
    req: dict[str, Any] = {
        "scope": SCOPE_THREAD,
        "group_ref": "",
        "selectors": [],
        "every": False,
    }
    if not raw:
        return req
    tokens = raw.split()
    head = tokens[0].lower()
    if head in _GROUP_TOKENS:
        rest_tokens = tokens[1:]
        idx = len(rest_tokens)
        while idx > 0 and _is_index_token(rest_tokens[idx - 1]):
            idx -= 1
        req["scope"] = SCOPE_GROUP
        req["group_ref"] = " ".join(rest_tokens[:idx]).strip()
        tail = rest_tokens[idx:]
        req["selectors"] = expand_index_selectors(tail)
        req["every"] = not tail
        return req
    if head in _ALL_TOKENS:
        tail = tokens[1:]
        req["scope"] = SCOPE_GLOBAL
        if not tail:
            req["every"] = True
            return req
        if all(_is_index_token(t) for t in tail):
            req["selectors"] = expand_index_selectors(tail)
        else:
            req["selectors"] = [" ".join(tail).strip()]
        return req
    if all(_is_index_token(t) for t in tokens):
        req["selectors"] = expand_index_selectors(tokens)
        return req
    req["selectors"] = [raw]
    return req


def _is_index_token(token: str) -> bool:
    """True for `3`, `6-8`, and comma-joined forms such as `1,3,5`."""
    raw = (token or "").strip()
    if not raw:
        return False
    pieces = [p.strip() for p in raw.split(",")]
    pieces = [p for p in pieces if p]
    if not pieces:
        return False
    return all(p.isdigit() or _INDEX_RANGE_RE.match(p) for p in pieces)


def expand_index_selectors(tokens: list[str]) -> list[str]:
    """`['1', '3,4', '6-8']` → `['1','3','4','6','7','8']` (deduped, ordered)."""
    out: list[str] = []
    for token in tokens or []:
        for piece in str(token).split(","):
            item = piece.strip()
            if not item:
                continue
            hit = _INDEX_RANGE_RE.match(item)
            if hit:
                lo, hi = int(hit.group(1)), int(hit.group(2))
                if lo > hi:
                    lo, hi = hi, lo
                for n in range(lo, min(hi, lo + REMOVE_BULK_CAP) + 1):
                    if str(n) not in out:
                        out.append(str(n))
                continue
            if item not in out:
                out.append(item)
    return out[:REMOVE_BULK_CAP]


def resolve_jobs(
    pool: list[dict[str, Any]], selectors: list[str]
) -> tuple[list[dict[str, Any]], list[str]]:
    """Resolve several selectors at once. Indexes are 1-based on `pool` order."""
    picked: list[dict[str, Any]] = []
    seen: set[str] = set()
    errors: list[str] = []
    visible = visible_jobs(pool)
    for sel in selectors or []:
        if sel.isdigit():
            idx = int(sel)
            if not 1 <= idx <= len(visible):
                errors.append(f"Không có lịch số {idx} (đang có {len(visible)}).")
                continue
            job = visible[idx - 1]
        else:
            job, err = resolve_job(pool, sel)
            if err or job is None:
                errors.append(err or f"Không tìm thấy lịch “{sel}”.")
                continue
        jid = str(job.get("id") or "")
        if jid and jid in seen:
            continue
        seen.add(jid)
        picked.append(job)
    return picked, errors


def parse_hhmm_cron(text: str) -> Optional[str]:
    t = (text or "").strip().lower()
    m = _HHMM_RE.match(t)
    if not m:
        return None
    hour = int(m.group("h"))
    minute = int(m.group("m") or 0)
    ampm = (m.group("ampm") or "").lower()
    if ampm in {"pm", "chiều", "chieu", "tối", "toi"} and hour < 12:
        hour += 12
    if ampm in {"am", "sáng", "sang"} and hour == 12:
        hour = 0
    if hour > 23 or minute > 59:
        return None
    return f"{minute} {hour} * * *"


def extract_clock_payload(text: str) -> Optional[str]:
    """If the whole payload is a clock (optionally after timer/lúc), return cron expr."""
    t = _TIMER_PREFIX_RE.sub("", (text or "").strip()).strip()
    if not t:
        return None
    return parse_hhmm_cron(t) or parse_cron_expr(t)


def parse_cron_expr(text: str) -> Optional[str]:
    t = (text or "").strip()
    if not t:
        return None
    hhmm = parse_hhmm_cron(t)
    if hhmm:
        return hhmm
    m = _CRON5_RE.match(t)
    if m:
        parts = [p for p in m.groups() if p is not None]
        if len(parts) >= 5:
            return " ".join(parts[:5])
    return None


def split_add_args(rest: str) -> tuple[Optional[str], str, str]:
    """Return (cron_expr, name, prompt)."""
    raw = (rest or "").strip()
    if not raw:
        return None, "", ""
    name = ""
    if " -- " in raw:
        left, prompt = raw.split(" -- ", 1)
        left, prompt = left.strip(), prompt.strip()
    else:
        left, prompt = raw, ""
    tokens = left.split()
    joined = " ".join(tokens)
    tm = _TIMER_PREFIX_RE.match(joined)
    if tm:
        rest_t = joined[tm.end() :].strip()
        bits = rest_t.split(None, 1)
        if bits:
            expr = parse_hhmm_cron(bits[0])
            if expr:
                leftover = bits[1].strip() if len(bits) > 1 else ""
                if leftover and not prompt:
                    prompt = leftover
                elif leftover:
                    name = leftover
                return expr, name, prompt
    # 5-field cron at start
    if len(tokens) >= 5 and all(re.match(r"^[\d*/,-]+$", t) or t == "*" for t in tokens[:5]):
        expr = " ".join(tokens[:5])
        leftover = " ".join(tokens[5:]).strip()
        if leftover and not prompt:
            prompt = leftover
        elif leftover:
            name = leftover
        return expr, name, prompt
    # HH:MM then the rest is prompt (or name + prompt)
    if tokens:
        expr = parse_hhmm_cron(tokens[0])
        if expr:
            leftover = " ".join(tokens[1:]).strip()
            if leftover and not prompt:
                prompt = leftover
            elif leftover:
                name = leftover
            return expr, name, prompt
    expr = parse_cron_expr(left)
    return expr, name, prompt


def resolve_job_prefix(
    jobs: list[dict[str, Any]], rest: str
) -> tuple[Optional[dict[str, Any]], str, str]:
    """Match list index, exact name/id, or longest name/id prefix of rest.

    Returns (job, leftover_after_selector, err). Leftover is the remainder of
    rest after the matched name (for `update Tên : payload`).
    """
    s = (rest or "").strip()
    if not s:
        return None, "", "usage: !zalo schedule show|update|remove <số|tên>"
    visible = visible_jobs(jobs)
    tokens = s.split(None, 1)
    head = tokens[0]
    tail = tokens[1] if len(tokens) > 1 else ""
    if head.isdigit():
        idx = int(head)
        if 1 <= idx <= len(visible):
            return visible[idx - 1], tail, ""
        return None, "", f"Không có lịch số {idx} (đang có {len(visible)})."
    sl = s.lower()
    best: Optional[dict[str, Any]] = None
    best_len = 0
    for job in visible:
        name = str(job.get("name") or "").strip()
        jid = str(job.get("id") or "").strip()
        for key in (name, jid):
            if not key:
                continue
            kl = key.lower()
            if sl == kl:
                return job, "", ""
            if sl.startswith(kl) and len(kl) > best_len:
                best = job
                best_len = len(kl)
    if best is not None and best_len:
        leftover = s[best_len:].strip()
        return best, leftover, ""
    for job in visible:
        name = str(job.get("name") or "").lower()
        jid = str(job.get("id") or "").lower()
        if sl in name or sl == jid:
            return job, "", ""
    shown = s if len(s) <= 80 else s[:77] + "…"
    return None, "", f"Không tìm thấy lịch “{shown}”."


def resolve_job(jobs: list[dict[str, Any]], sel: str) -> tuple[Optional[dict[str, Any]], str]:
    job, _leftover, err = resolve_job_prefix(jobs, sel)
    return job, err


def _strip_prompt_sep(text: str) -> str:
    t = (text or "").strip()
    if t.startswith(":"):
        t = t[1:].strip()
    if t.startswith("--"):
        t = t[2:].strip()
    return t


def parse_update_args(
    rest: str, jobs: list[dict[str, Any]]
) -> tuple[Optional[dict[str, Any]], Optional[str], str, str]:
    """Parse `update` rest into (job, new_cron_expr, new_prompt, err).

    Accepts:
      update <n|tên> --time 7:00
      update <n|tên> --timer 12:35
      update <n|tên> -- <nội dung>
      update <tên> : <nội dung>   (colon; keeps a following numbered list whole)
    """
    raw = (rest or "").strip()
    if not raw:
        return None, None, "", (
            "usage:\n!zalo schedule update <số|tên> --time 7:00\n"
            "!zalo schedule update <số|tên> -- <nội dung>\n"
            "!zalo schedule update <tên> : <nội dung>"
        )
    new_time = ""
    tm = _FLAG_TIME_RE.search(raw)
    if tm:
        new_time = tm.group(1)
        raw = (raw[: tm.start()] + raw[tm.end() :]).strip()
    ts = _FLAG_SCHED_RE.search(raw)
    if ts and not new_time:
        new_time = ts.group(1).strip().strip('"')
        raw = raw[: ts.start()].strip()
    new_prompt = ""
    if " -- " in raw:
        sel, new_prompt = raw.split(" -- ", 1)
        sel, new_prompt = sel.strip(), new_prompt.strip()
        job, err = resolve_job(jobs, sel)
    else:
        job, leftover, err = resolve_job_prefix(jobs, raw)
        new_prompt = _strip_prompt_sep(leftover)
    if err or job is None:
        return None, None, "", err or (
            "usage:\n!zalo schedule update <số|tên> --time 7:00\n"
            "!zalo schedule update <số|tên> -- <nội dung>"
        )
    expr: Optional[str] = None
    if new_time:
        expr = parse_hhmm_cron(new_time) or parse_cron_expr(new_time)
        if not expr:
            return job, None, new_prompt, "Lịch không hợp lệ. Dùng 6:00 hoặc 0 6 * * *"
    elif new_prompt:
        clock = extract_clock_payload(new_prompt)
        if clock:
            expr = clock
            new_prompt = ""
    if not new_time and not expr and not new_prompt:
        return job, None, "", (
            "usage:\n!zalo schedule update <số|tên> --time 7:00\n"
            "!zalo schedule update <số|tên> -- <nội dung>\n"
            "!zalo schedule update <tên> : <nội dung>"
        )
    return job, expr, new_prompt, ""


def apply_schedule_update(job: dict[str, Any], expr: Optional[str], new_prompt: str) -> None:
    """Write time and/or prompt. Clock-only old prompt is not a real task — drop it."""
    if expr:
        job["schedule"] = {"kind": "cron", "expr": expr, "display": expr}
        job["schedule_display"] = expr
        job["next_run_at"] = None
        if not new_prompt and prompt_is_clock_only(str(job.get("prompt") or "")):
            job["prompt"] = ""
    if new_prompt:
        job["prompt"] = new_prompt


def new_job(
    *,
    prompt: str,
    expr: str,
    name: str = "",
    tz_name: str = "Asia/Ho_Chi_Minh",
    sender: str = "",
    thread: str = "",
    sender_name: str = "",
) -> dict[str, Any]:
    jid = secrets.token_hex(6)
    display = expr
    return {
        "id": jid,
        "name": (name or prompt[:24] or jid).strip(),
        "prompt": prompt.strip(),
        "skills": [],
        "skill": None,
        "model": None,
        "provider": None,
        "provider_snapshot": None,
        "model_snapshot": None,
        "base_url": None,
        "script": None,
        "no_agent": True,
        "monitor_script": None,
        "monitor_url": None,
        "monitor_state": None,
        "context_from": None,
        "schedule": {"kind": "cron", "expr": expr, "display": display},
        "schedule_display": display,
        "repeat": {"times": None, "completed": 0},
        "enabled": True,
        "state": "scheduled",
        "paused_at": None,
        "paused_reason": None,
        "created_at": _now_iso(tz_name),
        "deliver": "origin",
        "origin": {
            "platform": "zalo",
            "chat_id": thread or sender,
            "chat_name": sender_name or "",
            "thread_id": thread or None,
            "user_id": sender or None,
        },
        "workdir": None,
        "enabled_toolsets": None,
        "last_run_at": None,
        "last_status": None,
        "last_error": None,
        "last_delivery_error": None,
        "next_run_at": None,
        "fire_claim": None,
        "run_claim": None,
    }


def fmt_show(job: dict[str, Any]) -> str:
    label = schedule_row_label(job) or str(job.get("name") or "lịch")
    prompt = re.sub(r"\s+", " ", str(job.get("prompt") or "")).strip()
    if prompt_is_clock_only(prompt):
        prompt = ""
    enabled = "bật" if job.get("enabled") else "tắt"
    state = str(job.get("state") or "")
    lines = [label, f"trạng thái: {enabled}" + (f" / {state}" if state else "")]
    if prompt:
        lines.append(prompt[:500])
    else:
        lines.append("Chưa có nội dung. Đặt việc: !zalo schedule update <tên> : <việc>")
    return "\n".join(lines)


def fmt_list(
    jobs: list[dict[str, Any]],
    *,
    limit: int | None = None,
    heading: str | None = None,
) -> str:
    cap = limit if limit is not None else ZALO_SCHEDULE_LIST_LIMIT
    return fmt_hermes_cron_list(
        __import__("json").dumps(visible_jobs(jobs), ensure_ascii=False),
        limit=cap,
        heading=heading,
    )


USAGE = (
    "!zalo schedule list\n"
    "!zalo schedule list all\n"
    "!zalo schedule show <số|tên>\n"
    "!zalo schedule show all <số|tên>\n"
    "!zalo schedule add <lịch> <nội dung>\n"
    "  ví dụ: !zalo schedule add 6:00 Gửi giá xăng\n"
    "  ví dụ: !zalo schedule add 0 6 * * * Gửi giá xăng\n"
    "!zalo schedule update <số|tên> --time 7:00\n"
    "!zalo schedule update <số|tên> --timer 12:35\n"
    "!zalo schedule update <số|tên> -- <nội dung mới>\n"
    "!zalo schedule update <tên> : <nội dung mới>\n"
    "!zalo schedule update all <số|tên> --time 7:00\n"
    "!zalo schedule remove <số|tên>\n"
    "!zalo schedule remove 1 3 5   (nhiều lịch)\n"
    "!zalo schedule remove 1-4     (khoảng)\n"
    "!zalo schedule remove all <số|tên>\n"
    "!zalo schedule remove all     (xóa mọi lịch)\n"
    "!zalo schedule remove group <tên nhóm>        (xóa mọi lịch của nhóm)\n"
    "!zalo schedule remove group <tên nhóm> 1 2    (chọn trong nhóm)"
)
