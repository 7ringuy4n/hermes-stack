"""LLM classify — structured task_hint + instructions. No NLU in this module.

Parses JSON protocol from the model. Validates enums and cron tokens only.
Timed schedule detection (đặt lịch + HH:MM) is a protocol guard so weak classify
models cannot demote a once-at-clock message into immediate async workflow.
"""
from __future__ import annotations

import json
import os
import re
import time
from pathlib import Path
from typing import Any

import httpx

ROOT = Path(__file__).resolve().parent
CFG_PATH = Path(os.environ.get("MODEL_ROUTER_CLASSIFY", str(ROOT / "config" / "classify.json")))
OUTBOUND_CFG_PATH = Path(
    os.environ.get("MODEL_ROUTER_OUTBOUND", str(ROOT / "config" / "outbound.json"))
)

TASK_HINTS = ("normal", "schedule", "coding", "tool", "search", "file", "knowledge", "unknown")
OUTBOUND_ACTIONS = ("send", "drop")
CADENCES = ("once", "daily", "weekly", "monthly", "yearly")
EXECUTION_CLASSES = ("interactive", "async", "schedule")
TASK_TYPES = (
    "chat",
    "media_generation",
    "file_processing",
    "create_schedule",
    "delete_schedule",
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
        if raw_type == "delete_schedule":
            return "schedule", "delete_schedule", "confirm"
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
    if skill is None and inferred:
        skill, default_action = inferred
        if not action:
            action = default_action
    if skill == "schedule" and task_type == "delete_schedule":
        action = "delete"
    if skill and not action:
        action = (inferred or (None, "run"))[1] or "run"
    return skill, action


def normalize_tasks(raw: Any, count: int) -> list[dict[str, Any]]:
    if not isinstance(raw, list):
        return []
    rows = raw[:count] if count else raw
    out: list[dict[str, Any]] = []
    for item in rows:
        if not isinstance(item, dict):
            continue
        hint = str(item.get("task_hint") or "").strip().lower()
        if hint not in TASK_HINTS:
            continue
        ttype = str(item.get("task_type") or "").strip().lower()
        if ttype not in TASK_TYPES:
            ttype = HINT_EXECUTION.get(hint, ("interactive", "chat", "direct"))[1]
        out.append({"task_hint": hint, "task_type": ttype})
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
    # once_after / once_at may omit cron_expr — host resolves fire time from delay or clock text.
    if _coerce_delay_seconds(plan.get("delay_seconds")) is not None:
        return True
    form = str(plan.get("schedule_form") or "").strip().lower()
    if form in {"once_after", "once_at"}:
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
_PRIOR_BLOCK = re.compile(
    r"\[Prior conversation\].*?\[/Prior conversation\]\s*",
    re.I | re.S,
)


def strip_prior_for_classify(text: str) -> str:
    """Classify must see the current user ask only — not Valkey hydrate wrappers."""
    blob = (text or "").strip()
    if not blob:
        return ""
    cleaned = _PRIOR_BLOCK.sub("", blob).strip()
    return cleaned or blob


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


def _load_cfg() -> dict[str, Any]:
    try:
        return json.loads(CFG_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {
            "timeout_s": 8,
            "temperature": 0,
            "system": "Return JSON with task_hint, instructions, cadence, cron_expr.",
            "user_template": "Timezone: {timezone}\nMessage:\n{text}",
        }


def valid_cron(expr: str) -> str | None:
    parts = (expr or "").strip().split()
    if len(parts) != 5:
        return None
    for p in parts:
        if not p or any(ch not in CRON_CHARS for ch in p):
            return None
    return " ".join(parts)


_SCHEDULE_TRIGGER = re.compile(
    r"(?:đặt\s*lịch|dat\s*lich|ặt\s*lịch|schedule|chạy\s+một\s+lần|"
    r"chay\s+mot\s+lan|one[\s-]?shot|run\s+once)",
    re.I,
)
_CLOCK_HM = re.compile(
    r"(?:lúc|luc|at|@)\s*(\d{1,2})\s*[:hH]\s*(\d{2})\b|"
    r"\b(\d{1,2})\s*[:hH]\s*(\d{2})\b",
    re.I,
)


def extract_clock_cron(text: str) -> str | None:
    """Build once-daily cron ``M H * * *`` from the first HH:MM in prose."""
    blob = text or ""
    m = _CLOCK_HM.search(blob)
    if not m:
        return None
    h_raw = m.group(1) or m.group(3)
    min_raw = m.group(2) or m.group(4)
    try:
        hour = int(h_raw)
        minute = int(min_raw)
    except (TypeError, ValueError):
        return None
    if not (0 <= hour <= 23 and 0 <= minute <= 59):
        return None
    return valid_cron(f"{minute} {hour} * * *")


def looks_like_timed_schedule(text: str) -> bool:
    """True when user prose asks to schedule work at a clock time."""
    blob = (text or "").strip()
    if not blob:
        return False
    if not _SCHEDULE_TRIGGER.search(blob):
        return False
    return extract_clock_cron(blob) is not None


def force_timed_schedule_plan(
    src: dict[str, Any],
    text: str,
) -> dict[str, Any]:
    """Override weak LLM demotions: timed đặt-lịch must stay task_hint=schedule.

    Lab failure: mixed greeting+fuel+weather with ``đặt lịch lúc HH:MM`` was
    classified as immediate async → 3 sequential compound jobs instead of one
    lịch confirm + fire later.
    """
    out = dict(src) if isinstance(src, dict) else {}
    if not looks_like_timed_schedule(text):
        return out
    cron = valid_cron(str(out.get("cron_expr") or "")) or extract_clock_cron(text)
    if not cron:
        return out
    out["task_hint"] = "schedule"
    out["cron_expr"] = cron
    cadence = str(out.get("cadence") or "").strip().lower()
    if cadence not in CADENCES:
        out["cadence"] = "once"
    out["execution_class"] = "schedule"
    out["task_type"] = "create_schedule"
    out["response_mode"] = "confirm"
    out["process_original_message"] = False
    out["skill"] = "schedule"
    if out.get("skill_action") in (None, "", "null"):
        out["skill_action"] = "create"
    exact = verbatim_schedule_body(text)
    if exact:
        out["message"] = exact
        existing: list[str] = []
        raw_ins = out.get("instructions")
        if isinstance(raw_ins, list):
            existing = [str(x).strip() for x in raw_ins if str(x).strip()]
        # Preserve LLM/heuristic multi-skill splits; only collapse single-blob paraphrases.
        if len(existing) < 2:
            out["instructions"] = [exact]
    return out


def verbatim_schedule_body(text: str) -> str | None:
    """Exact reminder body after nội dung: — never trust a paraphrased LLM rewrite."""
    blob = (text or "").strip()
    if not blob:
        return None
    m = _CONTENT_AFTER.search(blob)
    if not m:
        return None
    body = (m.group(1) or "").strip().strip("\"' ")
    return body or None


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


_SCHEDULE_HINT = re.compile(
    r"đặt\s*lịch|dat\s*lich|\bschedule\b|\bcron\b|hằng\s*ngày|hang\s*ngay|"
    r"daily\s+at|mỗi\s*sáng|moi\s*sang|chạy\s*một\s*lần|chay\s*mot\s*lan|"
    r"\d+\s*(?:phút|giây|giờ|phut|giay|gio|minutes?|seconds?|hours?)\s*(?:nữa|nua)?|"
    r"(?:sau|in|trong)\s+\d+\s*(?:phút|giây|giờ|phut|giay|gio|minutes?|seconds?|hours?)",
    re.I,
)
# Protocol parse for relative delay — not NLU; mirrors schedule_client runtime resolver.
_RELATIVE_DELAY = re.compile(
    r"(?:sau\s+|in\s+|trong\s+)?(\d+)\s*"
    r"(phút|giây|giờ|phut|giay|gio|minutes?|seconds?|hours?)\s*(?:nữa|nua)?",
    re.I,
)
_RELATIVE_UNIT_SECONDS = {
    "phút": 60,
    "phut": 60,
    "minute": 60,
    "minutes": 60,
    "giây": 1,
    "giay": 1,
    "second": 1,
    "seconds": 1,
    "giờ": 3600,
    "gio": 3600,
    "hour": 3600,
    "hours": 3600,
}
_ONCE_AT = re.compile(
    r"(?:một\s*lần|mot\s*lan|once|chạy)?\s*(?:lúc|luc|at)\s*(\d{1,2})\s*[:hH]\s*(\d{2})",
    re.I,
)
_DAILY_AT = re.compile(
    r"(?:hằng\s*ngày|hang\s*ngay|mỗi\s*ngày|moi\s*ngay|daily)\s*(?:lúc|luc|at)?\s*(\d{1,2})\s*[:hH]\s*(\d{2})",
    re.I,
)
_CONTENT_AFTER = re.compile(
    r"(?:với\s*nội\s*dung|voi\s*noi\s*dung|nội\s*dung|noi\s*dung)\s*[:\-]?\s*(.+)$",
    re.I | re.S,
)
_NUMBERED_LINE = re.compile(r"^\s*\d+[.)]\s+(.+)$", re.MULTILINE)
_FUEL_KW = ("xăng", "xang", "ron92", "ron95", "e5", "e10", "gasoline", "fuel")
_WEATHER_KW = ("thời tiết", "thoi tiet", "weather")
_DRAW_KW = ("vẽ", "ve ", "draw", "hình", "hinh", "poster", "infographic", "video")
_CITY_KW = ("hồ chí minh", "ho chi minh", "hcmc", "tp.hcm", "thành phố", "thanh pho")
# Task-work verbs in schedule body → process + split (fallback when LLM is down).
_TASK_BODY_VERB = re.compile(
    r"(?:mô\s*tả|mo\s*ta|describe|cập\s*nhật|cap\s*nhat|update|"
    r"dự\s*báo|du\s*bao|forecast|tìm\b|tim\b|search|vẽ|draw|"
    r"giá\s*xăng|gia\s*xang|thời\s*tiết|thoi\s*tiet|weather|"
    r"ocr|pdf|docx|xlsx)",
    re.I,
)
_SPLIT_TASK_CLAUSE = re.compile(
    r",\s*(?=(?:mô\s*tả|mo\s*ta|describe|cập\s*nhật|cap\s*nhat|update|"
    r"dự\s*báo|du\s*bao|forecast|tìm\b|tim\b|search|vẽ|draw))",
    re.I,
)
# "vào Zalo LC Group nội dung:" / "into group Family:"
_INTO_CHANNEL = re.compile(
    r"(?:vào|vao|into|to)\s+(?:(?:zalo|telegram|lark|discord|slack)\s+)?"
    r"(?:nhóm\s+|nhom\s+|group\s+)?"
    r"([^\n,;:]{2,80}?)"
    r"(?=\s+(?:nội\s*dung|noi\s*dung|content|với\s*nội|voi\s*noi|,|;|:|$))",
    re.I,
)


def _clean_heuristic_channel(raw: str) -> str:
    ref = (raw or "").strip(" \t\"'“”.:-")
    if not ref:
        return ""
    low = ref.lower()
    for prefix in (
        "zalo ",
        "telegram ",
        "lark ",
        "discord ",
        "slack ",
        "whatsapp ",
        "nhóm ",
        "nhom ",
        "group ",
    ):
        if low.startswith(prefix):
            stripped = ref[len(prefix) :].strip(" \t\"'“”.:-")
            if stripped:
                ref = stripped
                low = ref.lower()
            break
    return ref.strip()


def _heuristic_target_channel(blob: str) -> str | None:
    m = _INTO_CHANNEL.search(blob or "")
    if not m:
        return None
    cleaned = _clean_heuristic_channel(m.group(1) or "")
    if not cleaned or cleaned.lower() in {"nội dung", "noi dung", "content"}:
        return None
    return cleaned


def _schedule_body_is_task(body: str) -> bool:
    return bool(_TASK_BODY_VERB.search(body or ""))


def _split_schedule_task_body(body: str) -> list[str]:
    """Split multi-skill schedule body for fallback heuristic (LLM owns primary split)."""
    raw = (body or "").strip()
    if not raw:
        return []
    numbered = _parse_numbered_instructions(raw)
    if len(numbered) >= 2:
        return numbered
    if not _schedule_body_is_task(raw):
        return [raw]
    parts = [p.strip(" ,.-") for p in _SPLIT_TASK_CLAUSE.split(raw) if p.strip(" ,.-")]
    return parts if len(parts) >= 2 else [raw]


def delay_seconds_from_text(text: str) -> int | None:
    """Protocol extract of relative delay seconds from user prose (host authority)."""
    m = _RELATIVE_DELAY.search(text or "")
    if not m:
        return None
    try:
        n = int(m.group(1))
    except (TypeError, ValueError):
        return None
    unit = (m.group(2) or "").lower()
    secs = n * _RELATIVE_UNIT_SECONDS.get(unit, 0)
    if secs <= 0 or secs > 86400 * 30:
        return None
    return secs


def schedule_heuristic_plan(text: str) -> dict[str, Any] | None:
    """Deterministic once/daily schedule when LLM classify is down (503/timeout).

    Enriched with target_channel, schedule_delivery, and skill-split instructions so
    fallback still matches classify.json process/split rules. Prefer LLM first —
    do not early-return this before classify_with_llm attempts.
    """
    blob = (text or "").strip()
    if not blob or len(blob) > 2000:
        return None
    if not _SCHEDULE_HINT.search(blob):
        return None
    # Relative once_after: delay_seconds only — never invent cron / next_run_at here.
    delay = delay_seconds_from_text(blob)
    if delay is not None and not extract_clock_cron(blob):
        body = blob
        m_body = _CONTENT_AFTER.search(blob)
        if m_body:
            body = m_body.group(1).strip()
        else:
            m_rel = _RELATIVE_DELAY.search(blob)
            if m_rel:
                body = blob[m_rel.end() :].strip(" ,.-:")
        body = body or blob
        delivery = "process" if _schedule_body_is_task(body) else "verbatim"
        instructions = _split_schedule_task_body(body) if delivery == "process" else [body]
        out: dict[str, Any] = {
            "task_hint": "schedule",
            "task_type": "create_schedule",
            "execution_class": "schedule",
            "response_mode": "confirm",
            "process_original_message": False,
            "skill": "schedule",
            "skill_action": "create",
            "cadence": "once",
            "schedule_form": "once_after",
            "delay_seconds": delay,
            "cron_expr": None,
            "next_run_at": None,
            "message": body,
            "instructions": instructions,
            "schedule_delivery": delivery,
        }
        channel = _heuristic_target_channel(blob)
        if channel:
            out["target_channel"] = channel
        return out
    cadence = "once"
    hh = mm = None
    m_daily = _DAILY_AT.search(blob)
    m_once = _ONCE_AT.search(blob)
    if m_daily:
        cadence = "daily"
        hh, mm = int(m_daily.group(1)), int(m_daily.group(2))
    elif m_once:
        hh, mm = int(m_once.group(1)), int(m_once.group(2))
    if hh is None or mm is None or not (0 <= hh <= 23 and 0 <= mm <= 59):
        return None
    cron = f"{mm} {hh} * * *"
    body = blob
    m_body = _CONTENT_AFTER.search(blob)
    if m_body:
        body = m_body.group(1).strip()
    else:
        # Drop the schedule wrapper; keep work after the clock.
        cut = m_daily or m_once
        if cut:
            body = blob[cut.end() :].strip(" ,.-:")
            body = re.sub(
                r"^(?:với\s*nội\s*dung|voi\s*noi\s*dung|nội\s*dung|noi\s*dung)\s*[:\-]?\s*",
                "",
                body,
                flags=re.I,
            ).strip()
    if not body:
        body = blob
    instructions = _split_schedule_task_body(body)
    delivery = "process" if (
        len(instructions) > 1 or _schedule_body_is_task(body)
    ) else "verbatim"
    target = _heuristic_target_channel(blob)
    out: dict[str, Any] = {
        "task_hint": "schedule",
        "execution_class": "schedule",
        "task_type": "create_schedule",
        "response_mode": "confirm",
        "process_original_message": False,
        "message": body,
        "instructions": instructions,
        "cadence": cadence,
        "cron_expr": cron,
        "skill": "schedule",
        "skill_action": "create",
        "schedule_delivery": delivery,
    }
    if target:
        out["target_channel"] = target
    return out


def _parse_numbered_instructions(blob: str) -> list[str]:
    items: list[str] = []
    for m in _NUMBERED_LINE.finditer(blob):
        s = m.group(1).strip()
        if s:
            items.append(s)
    return items


def infographic_weather_fuel_plan(text: str) -> dict[str, Any] | None:
    """One-shot weather+fuel infographic when classify LLM is down (case 26)."""
    blob = (text or "").strip()
    if not blob or len(blob) > 4000:
        return None
    if len(_parse_numbered_instructions(blob)) >= 2:
        return None
    low = blob.lower()
    fuel = any(k in low for k in _FUEL_KW)
    weather = any(k in low for k in _WEATHER_KW)
    draw = any(k in low for k in _DRAW_KW)
    city = any(k in low for k in _CITY_KW)
    if not (fuel and (weather or draw) and (city or draw)):
        return None
    return {
        "task_hint": "tool",
        "execution_class": "async",
        "task_type": "media_generation",
        "response_mode": "ack_then_deliver",
        "process_original_message": True,
        "instructions": [blob],
    }


def numbered_list_heuristic_plan(text: str) -> dict[str, Any] | None:
    """Multi-part numbered asks when classify LLM returns garbage (case 25 / FIFO)."""
    blob = (text or "").strip()
    if not blob or len(blob) > 8000:
        return None
    items = _parse_numbered_instructions(blob)
    if len(items) < 2:
        return None
    m_daily = _DAILY_AT.search(blob)
    if m_daily:
        try:
            hh, mm = int(m_daily.group(1)), int(m_daily.group(2))
        except (TypeError, ValueError):
            hh = mm = None
        if hh is not None and mm is not None and 0 <= hh <= 23 and 0 <= mm <= 59:
            cron = valid_cron(f"{mm} {hh} * * *")
            if cron:
                return {
                    "task_hint": "schedule",
                    "execution_class": "schedule",
                    "task_type": "create_schedule",
                    "response_mode": "confirm",
                    "process_original_message": False,
                    "instructions": items,
                    "cadence": "daily",
                    "cron_expr": cron,
                    "skill": "schedule",
                    "skill_action": "create",
                }
    return {
        "task_hint": "tool",
        "execution_class": "async",
        "task_type": "tool",
        "response_mode": "ack_then_deliver",
        "process_original_message": True,
        "instructions": items,
    }


def heuristic_plan(text: str) -> dict[str, Any] | None:
    """Local fallback when classify LLM returns garbage (Omni free-tier weak models)."""
    blob = (text or "").strip()
    if not blob:
        return None
    sched = schedule_heuristic_plan(blob)
    if sched:
        return sched
    info = infographic_weather_fuel_plan(blob)
    if info:
        return info
    numbered = numbered_list_heuristic_plan(blob)
    if numbered:
        return numbered
    if len(blob) > 400:
        return None
    low = blob.lower()
    if _SCHEDULE_HINT.search(blob):
        return None
    if any(tok in low for tok in ("vẽ", "ve ", "draw", "image", "hình", "poster", "ocr", "pdf")):
        return None
    numbered = [ln.strip() for ln in blob.splitlines() if ln.strip()]
    if len(numbered) >= 2 and all(
        re.match(r"^\d+[.)]\s+", ln) for ln in numbered[: min(4, len(numbered))]
    ):
        return None
    return {
        "task_hint": "normal",
        "instructions": [blob],
        "process_original_message": True,
    }


def normalize_plan(data: dict[str, Any] | None, text: str, timezone: str) -> dict[str, Any]:
    src = force_timed_schedule_plan(data if isinstance(data, dict) else {}, text or "")
    hint = str(src.get("task_hint") or "").strip().lower()
    if hint in {"secret", "blocked", "sensitive"}:
        hint = "unknown"
    hint = HINT_ALIASES.get(hint, hint)
    if hint not in TASK_HINTS:
        hint = "unknown"
    fallback = (text or "").strip()
    instructions = sanitize_instructions(src.get("instructions"), fallback)
    cadence = str(src.get("cadence") or "").strip().lower()
    if cadence not in CADENCES:
        cadence = "daily" if hint == "schedule" else "once"
    delay = _coerce_delay_seconds(src.get("delay_seconds"))
    schedule_form = str(src.get("schedule_form") or "").strip().lower()
    if schedule_form not in {"once_at", "once_after", "recurring"}:
        schedule_form = ""
    if delay is not None:
        schedule_form = "once_after"
        cadence = "once"
        cron = None
    else:
        # Classifier must not invent cron for one-shot; discard LLM cron for once_at.
        llm_cron = valid_cron(str(src.get("cron_expr") or ""))
        host_clock = extract_clock_cron(fallback)
        if schedule_form == "once_after":
            cron = None
        elif schedule_form == "once_at" or (
            not schedule_form
            and hint == "schedule"
            and cadence == "once"
            and host_clock
            and not any(
                tok in (fallback or "").lower()
                for tok in (
                    "hằng ngày",
                    "hang ngay",
                    "mỗi ngày",
                    "moi ngay",
                    "daily",
                    "mỗi tuần",
                    "hang tuần",
                    "weekly",
                    "mỗi tháng",
                    "monthly",
                )
            )
        ):
            schedule_form = "once_at"
            cadence = "once"
            # Host protocol fill for worker storage — not classifier invention.
            cron = host_clock
        elif schedule_form == "recurring" or cadence in {"daily", "weekly", "monthly", "yearly"}:
            if not schedule_form:
                schedule_form = "recurring"
            cron = llm_cron or host_clock
        else:
            cron = llm_cron
            if hint == "schedule" and not cron:
                cron = host_clock
            if schedule_form == "once_after":
                cron = None
    tz = (timezone or "Asia/Ho_Chi_Minh").strip() or "Asia/Ho_Chi_Minh"
    exec_cls, task_type, response_mode = normalize_execution(src, hint)
    skill, skill_action = normalize_skill(src, hint, task_type)
    is_delete = hint == "schedule" and (
        skill_action == "delete" or task_type == "delete_schedule"
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
    message = str(src.get("message") or "").strip()
    if not message:
        if len(instructions) == 1:
            message = instructions[0]
        elif instructions:
            message = "\n".join(instructions)
        else:
            message = fallback
    if is_delete:
        process_original = False
    else:
        process_original = src.get("process_original_message")
        if not isinstance(process_original, bool):
            process_original = hint != "schedule"
    attachments_required = src.get("attachments_required")
    if not isinstance(attachments_required, bool):
        attachments_required = False
    delivery_raw = str(src.get("schedule_delivery") or "").strip().lower()
    schedule_delivery = delivery_raw if delivery_raw in {"verbatim", "process"} else None
    return {
        "ok": True,
        "task_hint": hint,
        "instructions": instructions,
        "task_details": normalize_task_details(src, instructions, hint),
        "cadence": None if is_delete else (cadence if hint == "schedule" else None),
        "cron_expr": None if is_delete else (cron if hint == "schedule" else None),
        "delay_seconds": None if is_delete else (delay if hint == "schedule" else None),
        "schedule_form": (
            None
            if is_delete
            else ((schedule_form or None) if hint == "schedule" else None)
        ),
        # Classifier must not invent absolute fire time; host resolves once_after.
        "next_run_at": None,
        "timezone": tz,
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
        "schedule_delivery": schedule_delivery,
    }


async def classify_with_llm(
    text: str,
    *,
    timezone: str,
    client: httpx.AsyncClient,
    n9_base: str,
    n9_key: str,
    model: str | None = None,
) -> dict[str, Any]:
    cfg = _load_cfg()
    tz = (timezone or "Asia/Ho_Chi_Minh").strip() or "Asia/Ho_Chi_Minh"
    blob = strip_prior_for_classify((text or "").strip())
    if not blob:
        return normalize_plan({"task_hint": "unknown", "instructions": []}, "", tz)
    # Ultra-short probes (e.g. "ê", "hi") — skip LLM; weak models misclassify these.
    if len(blob) <= 4:
        plan = normalize_plan(
            {"task_hint": "normal", "instructions": [blob], "process_original_message": True},
            blob,
            tz,
        )
        if plan_schema_ok(plan):
            return plan
    # Do NOT early-return schedule_heuristic_plan here: complex daily/task schedules
    # need classify.json for target_channel + schedule_delivery=process + skill split.
    # Heuristic remains the post-LLM fallback via heuristic_plan().
    tmpl = str(cfg.get("user_template") or "Timezone: {timezone}\nMessage:\n{text}")
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
                    "content": tmpl.replace("{timezone}", tz).replace("{text}", blob),
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
    guess = heuristic_plan(blob)
    if guess:
        plan = normalize_plan(guess, blob, tz)
        if plan_schema_ok(plan):
            return plan
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
    action = str(src.get("action") or "send").strip().lower()
    if action not in OUTBOUND_ACTIONS:
        action = "send"
    return {"ok": True, "action": action}


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
        "max_tokens": int(cfg.get("max_tokens") or 64),
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
