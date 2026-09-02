"""LLM classify — structured task_hint + instructions. No NLU in this module.

Parses JSON protocol from the model. Validates enums and cron tokens only.
Prompt SoT: Hermes skill parts under skills/classify/ (assembled into one system hop).
"""
from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Any

import httpx

ROOT = Path(__file__).resolve().parent


def _repo_skills_root() -> Path | None:
    # …/architect/models/model-router → parents[2] = repo root (dev checkout only).
    try:
        return ROOT.parents[2] / "hermes" / "main" / "skills"
    except IndexError:
        return None


def _resolve_skill_cfg(env_name: str, skill_rel: str, bake_name: str) -> Path:
    """Prefer Hermes skill JSON; fall back to baked config/ copy."""
    env = (os.environ.get(env_name) or "").strip()
    if env:
        p = Path(env)
        if p.is_file():
            return p
    candidates: list[Path] = [Path("/opt/data/skills") / skill_rel]
    repo = _repo_skills_root()
    if repo is not None:
        candidates.append(repo / skill_rel)
    candidates.append(ROOT / "config" / bake_name)
    for p in candidates:
        try:
            if p.is_file():
                return p
        except OSError:
            continue
    return ROOT / "config" / bake_name


CFG_PATH = _resolve_skill_cfg(
    "MODEL_ROUTER_CLASSIFY", "classify/classify.json", "classify.json"
)
OUTBOUND_CFG_PATH = _resolve_skill_cfg(
    "MODEL_ROUTER_OUTBOUND", "outbound/outbound.json", "outbound.json"
)

TASK_HINTS = ("normal", "schedule", "coding", "tool", "search", "file", "knowledge", "unknown")
OUTBOUND_ACTION_MAP = {
    "send": "send",
    "drop": "drop",
}
OUTBOUND_ACTIONS = tuple(OUTBOUND_ACTION_MAP.keys())
CADENCES = ("once", "daily", "weekly", "monthly", "yearly")
EXECUTION_CLASSES = ("interactive", "async", "schedule")
TASK_TYPES = (
    "chat",
    "media_generation",
    "file_processing",
    "create_schedule",
    "list_schedule",
    "delete_schedule",
    "pause_schedule",
    "resume_schedule",
    "update_schedule",
    "run_schedule",
    "knowledge",
    "search",
    "tool",
    "coding",
)
RESPONSE_MODES = ("direct", "ack_then_deliver", "confirm")
ATTACHMENT_TYPES = ("image", "file", "audio", "video")
SKILLS = ("media_file", "web_search", "schedule", "security", "knowledge")
# Prefer final answer first; then provider-specific chain-of-thought fields when content is empty.
MESSAGE_TEXT_KEYS = (
    "content",
    "reasoning_content",  # DeepSeek / Qwen / Moonshot / Zhipu
    "reasoning",  # Groq gpt-oss / OpenRouter / vLLM convention
    "thinking",  # some OpenAI-compat / Claude-style shims
    "thinking_content",
    "thought",
    "reasoning_text",
)
HINT_SKILL = {
    "search": ("web_search", "search"),
    "schedule": ("schedule", "create"),
    "file": ("media_file", "process_file"),
    "knowledge": ("knowledge", "lookup"),
}
HINT_EXECUTION = {
    "schedule": ("schedule", "create_schedule", "confirm"),
    "file": ("async", "file_processing", "ack_then_deliver"),
    "knowledge": ("interactive", "knowledge", "ack_then_deliver"),
    "coding": ("interactive", "coding", "ack_then_deliver"),
    "search": ("async", "search", "ack_then_deliver"),
    "normal": ("interactive", "chat", "ack_then_deliver"),
    "unknown": ("interactive", "chat", "ack_then_deliver"),
    "tool": ("interactive", "tool", "ack_then_deliver"),
}
HINT_ALIASES = {"chat": "normal", "qna": "normal", "question": "normal", "general": "normal"}
MAX_INSTRUCTIONS = 32
CRON_CHARS = set("0123456789*,/-")
SCHEDULE_RESOLUTIONS = ("clear", "needs_confirmation", "ambiguous", "invalid")
TIMEZONE_SOURCES = ("user_default", "explicit")
REFERENCE_TIME_SOURCES = ("schedule_request_received_at",)
SCHEDULE_DELIVERIES = ("verbatim", "process", "transform")
LIFECYCLE_TASK_TYPES = (
    "pause_schedule",
    "resume_schedule",
    "update_schedule",
    "run_schedule",
)
LIFECYCLE_ACTIONS = ("pause", "resume", "update", "run_now", "run")


def normalize_execution(
    src: dict[str, Any], hint: str, *, wrapper: bool = True
) -> tuple[str, str, str]:
    """Validate Fast Dispatcher enums. Fallback is from task_hint, not user prose."""
    raw_cls = str(src.get("execution_class") or "").strip().lower()
    raw_type = str(src.get("task_type") or "").strip().lower()
    raw_mode = str(src.get("response_mode") or "").strip().lower()
    if raw_mode == "direct":
        raw_mode = "ack_then_deliver"
    d_cls, d_type, d_mode = HINT_EXECUTION.get(hint, ("interactive", "chat", "ack_then_deliver"))
    if raw_type not in TASK_TYPES:
        raw_type = d_type
    if raw_cls not in EXECUTION_CLASSES:
        raw_cls = d_cls
        if hint == "tool" and raw_type == "media_generation":
            raw_cls = "async"
    if raw_mode not in RESPONSE_MODES:
        raw_mode = d_mode
        if raw_cls == "async":
            raw_mode = "ack_then_deliver"
        elif raw_cls == "schedule":
            raw_mode = "confirm"
    if wrapper and hint == "schedule":
        action = str(src.get("skill_action") or "").strip().lower()
        if raw_type == "delete_schedule" or action == "delete":
            return "schedule", "delete_schedule", "confirm"
        if raw_type == "list_schedule" or action in {"list", "inspect", "show", "status"}:
            return "schedule", "list_schedule", "confirm"
        if raw_type == "pause_schedule" or action == "pause":
            return "schedule", "pause_schedule", "confirm"
        if raw_type == "resume_schedule" or action == "resume":
            return "schedule", "resume_schedule", "confirm"
        if raw_type == "update_schedule" or action == "update":
            return "schedule", "update_schedule", "confirm"
        if raw_type == "run_schedule" or action in {"run_now", "run"}:
            return "schedule", "run_schedule", "confirm"
        return "schedule", "create_schedule", "confirm"
    return raw_cls, raw_type, raw_mode


def normalize_depends(raw: Any, index: int) -> list[int]:
    nums: list[int] = []
    if not isinstance(raw, list):
        return []
    for item in raw:
        try:
            nums.append(int(item))
        except (TypeError, ValueError):
            continue
    out: list[int] = []
    for v in nums:
        if 0 <= v < index and v not in out:
            out.append(v)
    return out


def normalize_task_details(
    src: dict[str, Any],
    instructions: list[str],
    hint: str,
) -> list[dict[str, Any]]:
    n = len(instructions)
    raw = src.get("task_details")
    rows: list[dict[str, Any]] = []
    if isinstance(raw, list):
        for item in raw:
            rows.append(item if isinstance(item, dict) else {})
    while len(rows) < n:
        rows.append({})
    rows = rows[:n]
    details: list[dict[str, Any]] = []
    for i, item in enumerate(rows):
        if item:
            body = item
        elif hint == "schedule":
            body = {"execution_class": "interactive", "task_type": "chat", "response_mode": "ack_then_deliver"}
        else:
            body = src
        cls, typ, mode = normalize_execution(body, hint, wrapper=False)
        out_type = str((item or {}).get("output_type") or (item or {}).get("file_format") or "").strip().lower()
        if out_type in {"text", "txt."}:
            out_type = "txt"
        if out_type not in {"image", "pdf", "txt", "docx", "xlsx", "csv", "md"}:
            out_type = ""
        row_out = {
            "execution_class": cls,
            "task_type": typ,
            "response_mode": mode,
            "depends_on": normalize_depends(item.get("depends_on") if item else [], i),
        }
        if out_type:
            row_out["output_type"] = out_type
        details.append(row_out)
    return details


def normalize_attachment_types(raw: Any) -> list[str]:
    out: list[str] = []
    if not isinstance(raw, list):
        return out
    for item in raw:
        val = str(item).strip().lower()
        if val in ATTACHMENT_TYPES and val not in out:
            out.append(val)
    return out


def normalize_skill(src: dict[str, Any], hint: str, task_type: str) -> tuple[str | None, str | None]:
    skill = str(src.get("skill") or "").strip().lower() or None
    action = str(src.get("skill_action") or "").strip().lower() or None
    if skill not in SKILLS:
        skill = None
    inferred = HINT_SKILL.get(hint)
    if hint == "tool" and task_type == "media_generation":
        inferred = ("media_file", "generate_media")
    elif hint == "tool" and task_type == "file_processing":
        inferred = ("media_file", "process_file")
    elif hint == "schedule" and task_type == "delete_schedule":
        inferred = ("schedule", "delete")
    elif hint == "schedule" and task_type == "list_schedule":
        inferred = ("schedule", "list")
    elif hint == "schedule" and task_type == "pause_schedule":
        inferred = ("schedule", "pause")
    elif hint == "schedule" and task_type == "resume_schedule":
        inferred = ("schedule", "resume")
    elif hint == "schedule" and task_type == "update_schedule":
        inferred = ("schedule", "update")
    elif hint == "schedule" and task_type == "run_schedule":
        inferred = ("schedule", "run_now")
    if skill is None and inferred:
        skill, default_action = inferred
        if not action:
            action = default_action
    if skill == "schedule" and task_type == "delete_schedule":
        action = "delete"
    if skill == "schedule" and task_type == "list_schedule":
        action = "list"
    if skill == "schedule" and task_type == "pause_schedule":
        action = "pause"
    if skill == "schedule" and task_type == "resume_schedule":
        action = "resume"
    if skill == "schedule" and task_type == "update_schedule":
        action = "update"
    if skill == "schedule" and task_type == "run_schedule":
        action = "run_now"
    if skill and not action:
        action = (inferred or (None, "run"))[1] or "run"
    return skill, action


def normalize_tasks(raw: Any, count: int) -> list[dict[str, Any]]:
    if not isinstance(raw, list):
        return []
    del count  # independent schedule objects must not be truncated by wrapper instruction count
    out: list[dict[str, Any]] = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        hint = str(item.get("task_hint") or "").strip().lower()
        if hint not in TASK_HINTS:
            continue
        ttype = str(item.get("task_type") or "").strip().lower()
        if ttype not in TASK_TYPES:
            ttype = HINT_EXECUTION.get(hint, ("interactive", "chat", "ack_then_deliver"))[1]
        skill, action = normalize_skill(item, hint, ttype)
        form = str(item.get("schedule_form") or "").strip().lower()
        if form not in {"once_at", "once_after", "recurring"}:
            form = ""
        delay = _coerce_delay_seconds(item.get("delay_seconds"))
        cron = valid_cron(str(item.get("cron_expr") or ""))
        if delay is not None:
            form = "once_after"
            cron = None
        elif form in {"once_after", "once_at"}:
            cron = None
        cadence = str(item.get("cadence") or "").strip().lower()
        if cadence not in CADENCES:
            cadence = "once" if delay is not None or form in {"once_after", "once_at"} else ""
        delivery = str(item.get("schedule_delivery") or "").strip().lower()
        if delivery not in SCHEDULE_DELIVERIES:
            delivery = ""
        channel = str(item.get("target_channel") or "").strip() or None
        instr = sanitize_instructions(item.get("instructions"), "")
        row: dict[str, Any] = {"task_hint": hint, "task_type": ttype}
        if skill:
            row["skill"] = skill
        if action:
            row["skill_action"] = action
        if instr:
            row["instructions"] = instr
        if form:
            row["schedule_form"] = form
        if delay is not None:
            row["delay_seconds"] = delay
        clock_hm = _coerce_clock_hm(item.get("clock_hm"))
        if clock_hm:
            row["clock_hm"] = clock_hm
        if cron:
            row["cron_expr"] = cron
        ot = _coerce_output_type(item.get("output_type"))
        if ot:
            row["output_type"] = ot
        poster_n = _coerce_poster_n(item.get("poster_n"))
        if poster_n is not None:
            row["poster_n"] = poster_n
        phrase = str(item.get("poster_phrase") or "").strip()
        if phrase:
            row["poster_phrase"] = phrase[:80]
        if cadence:
            row["cadence"] = cadence
        if channel:
            row["target_channel"] = channel
        if delivery:
            row["schedule_delivery"] = delivery
        extra = _schedule_contract_fields(item, hint)
        for key, val in extra.items():
            if val not in (None, "", [], {}):
                row[key] = val
        out.append(row)
    return out


def failed_plan(timezone: str, error: str = "classify_llm_failed") -> dict[str, Any]:
    tz = (timezone or "Asia/Ho_Chi_Minh").strip() or "Asia/Ho_Chi_Minh"
    return {
        "ok": False,
        "task_hint": "unknown",
        "instructions": [],
        "task_details": [],
        "cadence": None,
        "cron_expr": None,
        "timezone": tz,
        "error": error,
        "execution_class": "interactive",
        "task_type": "chat",
        "response_mode": "confirm",
        "process_original_message": False,
        "message": "",
        "attachments_required": False,
        "attachment_types": [],
        "skill": None,
        "skill_action": None,
        "tasks": [],
        "target_channel": None,
        "uncertain": False,
        "missing": [],
    }


def plan_schema_ok(plan: dict[str, Any]) -> bool:
    if not isinstance(plan, dict) or plan.get("ok") is False:
        return False
    if str(plan.get("task_hint") or "") != "schedule":
        return True
    action = str(plan.get("skill_action") or "").strip().lower()
    task_type = str(plan.get("task_type") or "").strip().lower()
    if action == "delete" or task_type == "delete_schedule":
        return True
    if action in {"list", "inspect", "show", "status"} or task_type == "list_schedule":
        return True
    if action in LIFECYCLE_ACTIONS or task_type in LIFECYCLE_TASK_TYPES:
        return True
    if plan.get("uncertain") is True:
        return True
    resolution = str(plan.get("schedule_resolution") or "").strip().lower()
    if resolution in {"needs_confirmation", "ambiguous", "invalid"}:
        return True
    if _task_has_schedule_timing(plan):
        return True
    tasks = plan.get("tasks")
    if isinstance(tasks, list):
        for item in tasks:
            if isinstance(item, dict) and _task_has_schedule_timing(item):
                return True
    return bool(plan.get("cron_expr"))


def _coerce_delay_seconds(raw: Any) -> int | None:
    """Accept positive int delay_seconds from classify JSON; reject junk."""
    if raw is None or raw == "":
        return None
    try:
        n = int(raw)
    except (TypeError, ValueError):
        return None
    if n <= 0 or n > 86400 * 30:
        return None
    return n


def _default_chat_combo_alias() -> str:
    """Chat/outbound combo alias (``hermes`` by default — not a vendor model id)."""
    for key in ("OMNIROUTER_DEFAULT_COMBO", "N9ROUTER_DEFAULT_COMBO"):
        val = (os.environ.get(key) or "").strip()
        if val:
            return val
    return "hermes"


def _default_classify_combo_alias() -> str:
    """Classify combo alias — dedicated OpenCode ``classifier`` combo by default."""
    for key in ("MODEL_ROUTER_CLASSIFY_MODEL", "OMNIROUTER_CLASSIFY_COMBO"):
        val = (os.environ.get(key) or "").strip()
        if val:
            return val
    return "classifier"


def _router_llm_model(cfg: dict[str, Any], override: str | None = None) -> str:
    """Resolve classify LLM id — must be a combo alias or real provider/model id."""
    for candidate in (
        override,
        os.environ.get("MODEL_ROUTER_CLASSIFY_MODEL"),
        str(cfg.get("model") or "").strip() or None,
        _default_classify_combo_alias(),
    ):
        if candidate and str(candidate).strip():
            return str(candidate).strip()
    return _default_classify_combo_alias()


# model_id -> unix time until which we skip that classify combo after auth/quota/503 storms
_classify_skip_until: dict[str, float] = {}
_CLASSIFY_SKIP_TTL_S = float(os.environ.get("CLASSIFY_SKIP_TTL_S") or "300")
# Upstream dead / inactive / bad gateway / wrong-schema members — skip that combo briefly.
_CLASSIFY_SKIP_HTTP = {400, 401, 403, 404, 429, 502, 503}
REASONING_EFFORTS = ("low", "medium", "high", "max")
_OUTPUT_TYPES = {"image", "pdf", "txt", "docx", "xlsx", "csv", "md"}
_PRIOR_START = "[prior conversation]"
_PRIOR_END = "[/prior conversation]"
_ATTACH_RECALL_START = "[recent attachments in this chat"


def strip_prior_for_classify(text: str) -> str:
    """Classify must see the current user ask only — not Valkey hydrate wrappers."""
    blob = text or ""
    while True:
        low = blob.lower()
        start = low.find(_PRIOR_START)
        if start < 0:
            break
        end = low.find(_PRIOR_END, start)
        if end < 0:
            break
        blob = blob[:start] + blob[end + len(_PRIOR_END) :]
    low = blob.lower()
    attach = low.find(_ATTACH_RECALL_START)
    if attach >= 0:
        blob = blob[:attach]
    cleaned = blob.strip()
    return cleaned or (text or "").strip()


def _coerce_reasoning_effort(raw: Any) -> str | None:
    s = str(raw or "").strip().lower()
    return s if s in REASONING_EFFORTS else None


def infer_reasoning_effort(hint: str, task_type: str, execution_class: str) -> str:
    h = (hint or "").strip().lower()
    tt = (task_type or "").strip().lower()
    ec = (execution_class or "").strip().lower()
    if h == "coding" or tt == "coding":
        return "high"
    if h == "schedule" or ec == "schedule" or tt.endswith("_schedule") or tt == "create_schedule":
        return "low"
    if tt in {"search", "knowledge", "file_processing"} or h in {"search", "file", "knowledge"}:
        return "low"
    if h in {"tool", "unknown"} and tt == "media_generation":
        return "low"
    if h == "normal" and tt == "chat":
        return "low"
    return "medium"


def _classify_has_thread_context(raw: str, *, attachments: str, quoted: str) -> bool:
    if attachments and attachments.strip().lower() not in {"", "none"}:
        return True
    if quoted and quoted.strip().lower() not in {"", "none"}:
        return True
    low = (raw or "").lower()
    return (
        _PRIOR_START in low
        or _ATTACH_RECALL_START in low
        or "[quoted message]" in low
    )


def _coerce_output_type(raw: Any) -> str:
    ot = str(raw or "").strip().lower()
    if ot in {"text", "txt."}:
        ot = "txt"
    return ot if ot in _OUTPUT_TYPES else ""


def _coerce_clock_hm(raw: Any) -> str | None:
    s = str(raw or "").strip().replace("h", ":").replace("H", ":")
    if not s or s.count(":") != 1:
        return None
    left, right = s.split(":", 1)
    if not left.isdigit() or not right.isdigit():
        return None
    hour, minute = int(left), int(right)
    if not (0 <= hour <= 23 and 0 <= minute <= 59):
        return None
    return f"{hour:02d}:{minute:02d}"


def _task_has_schedule_timing(item: dict[str, Any]) -> bool:
    if _coerce_delay_seconds(item.get("delay_seconds")) is not None:
        return True
    form = str(item.get("schedule_form") or "").strip().lower()
    if form in {"once_after", "once_at"}:
        return True
    if _coerce_clock_hm(item.get("clock_hm")):
        return True
    return bool(valid_cron(str(item.get("cron_expr") or "")))


def _coerce_schedule_selector(raw: Any) -> dict[str, Any] | None:
    if not isinstance(raw, dict):
        return None
    name = str(raw.get("name") or "").strip() or None
    match_raw = raw.get("match") if isinstance(raw.get("match"), dict) else {}
    content_hint = str(match_raw.get("content_hint") or "").strip() or None
    time_hint = str(match_raw.get("time_hint") or "").strip() or None
    if not name and not content_hint and not time_hint:
        return None
    return {
        "id": None,
        "name": name,
        "match": {"content_hint": content_hint, "time_hint": time_hint},
    }


def _schedule_contract_fields(src: dict[str, Any], hint: str) -> dict[str, Any]:
    if hint != "schedule":
        return {
            "timezone_source": None,
            "reference_time_source": None,
            "schedule_resolution": None,
            "confirmation_required": None,
            "schedule_selector": None,
        }
    tz_source = str(src.get("timezone_source") or "").strip().lower()
    if tz_source not in TIMEZONE_SOURCES:
        tz_source = "user_default"
    rts = str(src.get("reference_time_source") or "").strip().lower()
    form = str(src.get("schedule_form") or "").strip().lower()
    delay = _coerce_delay_seconds(src.get("delay_seconds"))
    if rts not in REFERENCE_TIME_SOURCES:
        rts = (
            "schedule_request_received_at"
            if delay is not None or form == "once_after"
            else None
        )
    resolution = str(src.get("schedule_resolution") or "").strip().lower()
    if resolution not in SCHEDULE_RESOLUTIONS:
        resolution = None
    cr = src.get("confirmation_required")
    if not isinstance(cr, bool):
        cr = True if resolution in {"needs_confirmation", "ambiguous", "invalid"} else None
    return {
        "timezone_source": tz_source,
        "reference_time_source": rts,
        "schedule_resolution": resolution,
        "confirmation_required": cr,
        "schedule_selector": _coerce_schedule_selector(src.get("schedule_selector")),
    }


def _coerce_poster_n(raw: Any) -> int | None:
    if raw is None or raw == "":
        return None
    try:
        n = int(raw)
    except (TypeError, ValueError):
        return None
    if n < 1 or n > 80:
        return None
    return n


def _classify_body_is_schema_dead(status: int, body: str) -> bool:
    """True when Omni/upstream rejects chat/completions shape (CF AiError prompt/text/audio)."""
    if status in _CLASSIFY_SKIP_HTTP:
        return True
    low = (body or "").lower()
    if "aierror" in low and any(
        tok in low
        for tok in (
            "required properties",
            "missing field",
            "'prompt'",
            '"prompt"',
            "'text'",
            "'audio'",
            "multipart",
            "oneof",
        )
    ):
        return True
    return False


def _mark_classify_model_bad(model_id: str) -> None:
    name = str(model_id or "").strip()
    if not name:
        return
    _classify_skip_until[name] = time.time() + max(30.0, _CLASSIFY_SKIP_TTL_S)


def _classify_model_candidates(cfg: dict[str, Any], override: str | None = None) -> list[str]:
    """Primary classify combo, then chat combo when they differ (403/empty failover).

    When the dedicated classify combo recently returned auth/quota errors, prefer the
    chat combo first so schedule/create acks stay fast.
    """
    primary = _router_llm_model(cfg, override)
    chat = _default_chat_combo_alias()
    out: list[str] = []
    skip_until = float(_classify_skip_until.get(primary) or 0)
    prefer_chat = skip_until > time.time() and primary != chat
    ordered = (chat, primary) if prefer_chat else (primary, chat)
    for candidate in ordered:
        name = str(candidate or "").strip()
        if name and name not in out:
            out.append(name)
    return out or [chat]


def _outbound_llm_model(cfg: dict[str, Any], override: str | None = None) -> str:
    for candidate in (
        override,
        os.environ.get("MODEL_ROUTER_OUTBOUND_MODEL"),
        str(cfg.get("model") or "").strip() or None,
        _default_chat_combo_alias(),
    ):
        if candidate and str(candidate).strip():
            return str(candidate).strip()
    return _default_chat_combo_alias()


def assemble_classify_system(skill_dir: Path, data: dict[str, Any]) -> str:
    """Join classify parts/*.txt into one system prompt. Bake JSON may already have system."""
    names = data.get("parts")
    chunks: list[str] = []
    if isinstance(names, list):
        for raw in names:
            name = str(raw or "").strip()
            if not name or "/" in name or "\\" in name or name.startswith("."):
                continue
            path = skill_dir / "parts" / f"{name}.txt"
            try:
                if path.is_file():
                    text = path.read_text(encoding="utf-8").strip()
                    if text:
                        chunks.append(text)
            except OSError:
                continue
    if chunks:
        return "\n\n".join(chunks)
    return str(data.get("system") or "").strip()


def _load_cfg() -> dict[str, Any]:
    try:
        data = json.loads(CFG_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        data = {}
    if not isinstance(data, dict):
        data = {}
    system = assemble_classify_system(CFG_PATH.parent, data)
    if not system:
        system = "Return JSON with task_hint, instructions, cadence, cron_expr."
    data["system"] = system
    if not str(data.get("user_template") or "").strip():
        data["user_template"] = (
            "Timezone: {timezone}\nLocal now: {local_now}\nThread: {thread}\n"
            "Attachments: {attachments}\nQuoted: {quoted}\nMessage:\n{text}"
        )
    data.setdefault("timeout_s", 20)
    data.setdefault("temperature", 0)
    return data


def _local_now_label(timezone: str) -> str:
    """Wall-clock label for classify context (host TZ, default Vietnam)."""
    from datetime import datetime

    tz_name = (timezone or "Asia/Ho_Chi_Minh").strip() or "Asia/Ho_Chi_Minh"
    try:
        from zoneinfo import ZoneInfo

        now = datetime.now(ZoneInfo(tz_name))
    except Exception:
        now = datetime.now()
    return now.strftime("%Y-%m-%d %H:%M")


def _fill_user_template(
    tmpl: str,
    *,
    timezone: str,
    local_now: str,
    text: str,
    thread: str = "unknown",
    attachments: str = "none",
    quoted: str = "none",
) -> str:
    """Replace known placeholders only — user text may contain braces."""
    return (
        tmpl.replace("{timezone}", timezone)
        .replace("{local_now}", local_now)
        .replace("{thread}", thread or "unknown")
        .replace("{attachments}", attachments or "none")
        .replace("{quoted}", quoted or "none")
        .replace("{text}", text)
    )


def valid_cron(expr: str) -> str | None:
    parts = (expr or "").strip().split()
    if len(parts) != 5:
        return None
    for p in parts:
        if not p or any(ch not in CRON_CHARS for ch in p):
            return None
    return " ".join(parts)


def _coerce_message_field(val: Any) -> str:
    """Turn a message field (str / list parts / reasoning_details) into text."""
    if isinstance(val, str) and val.strip():
        return val.strip()
    if isinstance(val, list):
        parts: list[str] = []
        for item in val:
            if isinstance(item, str) and item.strip():
                parts.append(item.strip())
            elif isinstance(item, dict):
                for sub in ("text", "content", "reasoning", "reasoning_text"):
                    t = item.get(sub)
                    if isinstance(t, str) and t.strip():
                        parts.append(t.strip())
                        break
        if parts:
            return "\n".join(parts)
    return ""


def _message_field_keys(msg: dict[str, Any]) -> list[str]:
    """Known CoT keys first, then any other message keys that look like reasoning."""
    keys = list(MESSAGE_TEXT_KEYS)
    known = set(MESSAGE_TEXT_KEYS)
    for k in msg:
        if not isinstance(k, str) or k in known:
            continue
        kl = k.lower()
        if "reason" in kl or "think" in kl or kl.endswith("_thought"):
            keys.append(k)
    # OpenRouter may put structured CoT under reasoning_details
    if "reasoning_details" in msg and "reasoning_details" not in known:
        keys.append("reasoning_details")
    return keys


def _message_text(data: dict[str, Any]) -> str:
    choices = data.get("choices") if isinstance(data, dict) else None
    if not isinstance(choices, list) or not choices:
        return ""
    ch = choices[0] if isinstance(choices[0], dict) else {}
    msg = ch.get("message") if isinstance(ch.get("message"), dict) else {}
    for key in _message_field_keys(msg):
        text = _coerce_message_field(msg.get(key))
        if text:
            return text
    text = ch.get("text")
    if isinstance(text, str) and text.strip():
        return text
    return ""


def _json_object(raw: str) -> dict[str, Any] | None:
    blob = (raw or "").strip()
    start = blob.find("{")
    end = blob.rfind("}")
    if start < 0 or end <= start:
        return None
    try:
        data = json.loads(blob[start : end + 1])
    except json.JSONDecodeError:
        return None
    return data if isinstance(data, dict) else None


def _loads_first(raw: str) -> dict[str, Any] | None:
    blob = (raw or "").strip()
    if not blob:
        return None
    try:
        data, _idx = json.JSONDecoder().raw_decode(blob)
    except json.JSONDecodeError:
        return None
    return data if isinstance(data, dict) else None


def sanitize_instructions(raw: Any, fallback: str) -> list[str]:
    """Dedupe/cap instruction spam from weak classify models."""
    items: list[str] = []
    if isinstance(raw, list):
        for item in raw:
            s = str(item).strip()
            if s:
                items.append(s)
    if len(items) > 3 and len(set(items)) == 1:
        items = [items[0]]
    out: list[str] = []
    seen: set[str] = set()
    for s in items:
        if s in seen:
            continue
        seen.add(s)
        out.append(s)
        if len(out) >= MAX_INSTRUCTIONS:
            break
    fb = (fallback or "").strip()
    if not out and fb:
        return [fb]
    return out


def heuristic_plan(text: str) -> dict[str, Any] | None:
    """LLM classify owns intent. Offline phrase scan is not a fallback."""
    del text
    return None


def normalize_plan(data: dict[str, Any] | None, text: str, timezone: str) -> dict[str, Any]:
    src = data if isinstance(data, dict) else {}
    hint = str(src.get("task_hint") or "").strip().lower()
    if hint in {"secret", "blocked", "sensitive"}:
        hint = "unknown"
    hint = HINT_ALIASES.get(hint, hint)
    if hint not in TASK_HINTS:
        hint = "unknown"
    fallback = (text or "").strip()
    instructions = sanitize_instructions(src.get("instructions"), fallback)
    delay = _coerce_delay_seconds(src.get("delay_seconds"))
    schedule_form = str(src.get("schedule_form") or "").strip().lower()
    if schedule_form not in {"once_at", "once_after", "recurring"}:
        schedule_form = ""
    cadence = str(src.get("cadence") or "").strip().lower()
    if cadence not in CADENCES:
        cadence = ""
    if delay is not None:
        schedule_form = "once_after"
        cadence = "once"
        cron = None
    else:
        llm_cron = valid_cron(str(src.get("cron_expr") or ""))
        if schedule_form == "once_after":
            cron = None
            if not cadence:
                cadence = "once"
        elif schedule_form == "once_at":
            cadence = "once"
            cron = None
        elif schedule_form == "recurring" or cadence in {"daily", "weekly", "monthly", "yearly"}:
            if not schedule_form:
                schedule_form = "recurring"
            cron = llm_cron
        else:
            cron = llm_cron
            if not cadence and hint != "schedule":
                cadence = "once"
    tz = (timezone or "Asia/Ho_Chi_Minh").strip() or "Asia/Ho_Chi_Minh"
    exec_cls, task_type, response_mode = normalize_execution(src, hint)
    skill, skill_action = normalize_skill(src, hint, task_type)
    is_delete = hint == "schedule" and (
        skill_action == "delete" or task_type == "delete_schedule"
    )
    is_list = hint == "schedule" and (
        skill_action in {"list", "inspect", "show", "status"} or task_type == "list_schedule"
    )
    is_lifecycle = hint == "schedule" and (
        skill_action in LIFECYCLE_ACTIONS or task_type in LIFECYCLE_TASK_TYPES
    )
    if is_delete:
        task_type = "delete_schedule"
        skill = "schedule"
        skill_action = "delete"
        cadence = None
        cron = None
        delay = None
        schedule_form = ""
        process_original = False
    elif is_list:
        task_type = "list_schedule"
        skill = "schedule"
        skill_action = "list"
        cadence = None
        cron = None
        delay = None
        schedule_form = ""
        process_original = False
    elif is_lifecycle and skill_action != "update":
        cadence = None
        cron = None
        delay = None
        schedule_form = ""
        process_original = False
    message = str(src.get("message") or "").strip()
    if not message:
        if len(instructions) == 1:
            message = instructions[0]
        elif instructions:
            message = "\n".join(instructions)
        else:
            message = fallback
    if is_delete or is_list or (is_lifecycle and skill_action != "update"):
        process_original = False
    else:
        process_original = src.get("process_original_message")
        if not isinstance(process_original, bool):
            process_original = hint != "schedule"
    attachments_required = src.get("attachments_required")
    if not isinstance(attachments_required, bool):
        attachments_required = False
    delivery_raw = str(src.get("schedule_delivery") or "").strip().lower()
    schedule_delivery = delivery_raw if delivery_raw in SCHEDULE_DELIVERIES else None
    contract = _schedule_contract_fields(src, hint)
    llm_tz = str(src.get("timezone") or "").strip()
    if (
        contract.get("timezone_source") == "explicit"
        and llm_tz
        and "/" in llm_tz
        and " " not in llm_tz
        and llm_tz.count("/") <= 2
    ):
        tz = llm_tz
    skip_timing = is_delete or is_list or (is_lifecycle and skill_action != "update")
    return {
        "ok": True,
        "task_hint": hint,
        "instructions": instructions,
        "task_details": normalize_task_details(src, instructions, hint),
        "cadence": None if skip_timing else (cadence if hint == "schedule" else None),
        "cron_expr": None if skip_timing else (cron if hint == "schedule" else None),
        "delay_seconds": None if skip_timing else (delay if hint == "schedule" else None),
        "schedule_form": (
            None if skip_timing else ((schedule_form or None) if hint == "schedule" else None)
        ),
        # Classifier must not invent absolute fire time; host resolves once_after.
        "next_run_at": None,
        "timezone": tz,
        "timezone_source": None if skip_timing else contract.get("timezone_source"),
        "reference_time_source": None if skip_timing else contract.get("reference_time_source"),
        "schedule_resolution": contract.get("schedule_resolution") if hint == "schedule" else None,
        "confirmation_required": contract.get("confirmation_required") if hint == "schedule" else None,
        "schedule_selector": contract.get("schedule_selector") if hint == "schedule" else None,
        "execution_class": exec_cls,
        "task_type": task_type,
        "response_mode": response_mode,
        "process_original_message": process_original,
        "message": message,
        "attachments_required": attachments_required,
        "attachment_types": normalize_attachment_types(src.get("attachment_types")),
        "skill": skill,
        "skill_action": skill_action,
        "tasks": normalize_tasks(src.get("tasks"), len(instructions)),
        "target_channel": (
            str(
                src.get("target_channel")
                or src.get("deliver_to")
                or src.get("target_group")
                or src.get("group_name")
                or ""
            ).strip()
            or None
        ),
        "schedule_delivery": None if skip_timing else schedule_delivery,
        "output_type": _coerce_output_type(src.get("output_type")) or None,
        "clock_hm": None if skip_timing else _coerce_clock_hm(src.get("clock_hm")),
        "poster_n": _coerce_poster_n(src.get("poster_n")),
        "poster_phrase": (str(src.get("poster_phrase") or "").strip()[:80] or None),
        "poster_bw": src.get("poster_bw") if isinstance(src.get("poster_bw"), bool) else None,
        "reasoning_effort": (
            _coerce_reasoning_effort(src.get("reasoning_effort"))
            or infer_reasoning_effort(hint, task_type, exec_cls)
        ),
        "uncertain": bool(src.get("uncertain") is True),
        "missing": [
            str(x).strip().lower()
            for x in (src.get("missing") or [])
            if str(x).strip().lower() in {"time", "destination", "output_type"}
        ],
    }


async def classify_with_llm(
    text: str,
    *,
    timezone: str,
    client: httpx.AsyncClient,
    n9_base: str,
    n9_key: str,
    model: str | None = None,
    thread: str = "unknown",
    attachments: str = "none",
    quoted: str = "none",
) -> dict[str, Any]:
    cfg = _load_cfg()
    tz = (timezone or "Asia/Ho_Chi_Minh").strip() or "Asia/Ho_Chi_Minh"
    raw = (text or "").strip()
    blob = strip_prior_for_classify(raw)
    if not blob:
        return normalize_plan({"task_hint": "unknown", "instructions": []}, "", tz)
    # Ultra-short probes (e.g. "ê", "hi") — skip LLM unless thread still carries context.
    if len(blob) <= 4 and not _classify_has_thread_context(
        raw, attachments=attachments, quoted=quoted
    ):
        plan = normalize_plan(
            {"task_hint": "normal", "instructions": [blob], "process_original_message": True},
            blob,
            tz,
        )
        if plan_schema_ok(plan):
            return plan
    tmpl = str(
        cfg.get("user_template")
        or "Timezone: {timezone}\nLocal now: {local_now}\nMessage:\n{text}"
    )
    local_now = _local_now_label(tz)
    headers = {"Content-Type": "application/json"}
    if n9_key:
        headers["Authorization"] = f"Bearer {n9_key}"
    timeout = float(cfg.get("timeout_s") or 20)
    url = f"{n9_base.rstrip('/')}/chat/completions"
    last_err = "classify_llm_failed"
    llm_attempts = max(1, int(cfg.get("retry") or 1))
    for model_id in _classify_model_candidates(cfg, model):
        payload = {
            "model": model_id,
            "stream": False,
            "temperature": float(cfg.get("temperature") or 0),
            "messages": [
                {"role": "system", "content": str(cfg.get("system") or "")},
                {
                    "role": "user",
                    "content": _fill_user_template(
                        tmpl,
                        timezone=tz,
                        local_now=local_now,
                        text=blob,
                        thread=str(thread or "unknown"),
                        attachments=str(attachments or "none"),
                        quoted=str(quoted or "none"),
                    ),
                },
            ],
        }
        if cfg.get("max_tokens") not in (None, ""):
            payload["max_tokens"] = int(cfg["max_tokens"])
        for attempt in range(llm_attempts):
            content = ""
            try:
                resp = await client.post(url, headers=headers, json=payload, timeout=timeout)
                raw = resp.text
                if resp.status_code >= 400:
                    print(
                        f"[classify] http={resp.status_code} model={model_id} "
                        f"attempt={attempt + 1}",
                        flush=True,
                    )
                    last_err = "classify_llm_failed"
                    # Auth/quota/upstream-dead/wrong-schema combo → skip briefly, try next.
                    if _classify_body_is_schema_dead(resp.status_code, raw):
                        _mark_classify_model_bad(model_id)
                        break
                    continue
                data = _loads_first(raw) or {}
                content = _message_text(data)
                if not content:
                    print(
                        f"[classify] empty content model={model_id} attempt={attempt + 1} "
                        f"finish={((data.get('choices') or [{}])[0] or {}).get('finish_reason')}",
                        flush=True,
                    )
                    last_err = "classify_llm_failed"
                    continue
            except Exception as exc:
                print(
                    f"[classify] llm_err {type(exc).__name__} model={model_id} "
                    f"attempt={attempt + 1} budget={timeout}",
                    flush=True,
                )
                last_err = "classify_llm_failed"
                continue
            parsed = _json_object(content) or _loads_first(content)
            if not parsed:
                last_err = "classify_llm_failed"
                continue
            plan = normalize_plan(parsed, blob, tz)
            if plan_schema_ok(plan):
                if model_id != _router_llm_model(cfg, model):
                    print(f"[classify] ok via fallback model={model_id}", flush=True)
                return plan
            last_err = "classify_invalid"
    return failed_plan(tz, last_err)


def _load_outbound_cfg() -> dict[str, Any]:
    try:
        return json.loads(OUTBOUND_CFG_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {
            "timeout_s": 30,
            "max_tokens": 64,
            "temperature": 0,
            "system": 'Return JSON {"action":"send"} or {"action":"drop"}.',
            "user_template": "Line:\n{text}",
        }


def normalize_outbound(data: dict[str, Any] | None) -> dict[str, Any]:
    src = data if isinstance(data, dict) else {}
    raw_action = str(src.get("action") or "send").strip().lower()
    action = OUTBOUND_ACTION_MAP.get(raw_action, "send")
    out: dict[str, Any] = {"ok": True, "action": action}
    cleaned = src.get("text")
    if action == "send" and isinstance(cleaned, str) and cleaned.strip():
        out["text"] = cleaned.strip()
    return out


async def outbound_with_llm(
    text: str,
    *,
    client: httpx.AsyncClient,
    n9_base: str,
    n9_key: str,
    model: str | None = None,
) -> dict[str, Any]:
    cfg = _load_outbound_cfg()
    blob = (text or "").strip()
    if not blob:
        return {"ok": True, "action": "drop"}
    tmpl = str(cfg.get("user_template") or "Line:\n{text}")
    payload = {
        "model": _outbound_llm_model(cfg, model),
        "stream": False,
        "temperature": float(cfg.get("temperature") or 0),
        "max_tokens": int(cfg.get("max_tokens") or 512),
        "messages": [
            {"role": "system", "content": str(cfg.get("system") or "")},
            {"role": "user", "content": tmpl.replace("{text}", blob[:4000])},
        ],
    }
    headers = {"Content-Type": "application/json"}
    if n9_key:
        headers["Authorization"] = f"Bearer {n9_key}"
    timeout = float(cfg.get("timeout_s") or 30)
    url = f"{n9_base.rstrip('/')}/chat/completions"
    content = ""
    try:
        resp = await client.post(url, headers=headers, json=payload, timeout=timeout)
        raw = resp.text
        data = _loads_first(raw) or {}
        content = _message_text(data)
    except Exception as exc:
        print(f"[outbound] llm_err {type(exc).__name__}", flush=True)
        return {"ok": False, "action": "send", "error": "outbound_llm_failed"}
    parsed = _json_object(content) or _loads_first(content)
    if not parsed:
        return {"ok": False, "action": "send", "error": "outbound_llm_failed"}
    return normalize_outbound(parsed)
