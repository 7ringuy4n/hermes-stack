"""LLM classify — structured task_hint + instructions. No NLU in this module.

Parses JSON protocol from the model. Validates enums and cron tokens only.
"""
from __future__ import annotations

import json
import os
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
    "knowledge": ("interactive", "knowledge", "direct"),
    "coding": ("interactive", "coding", "direct"),
    "search": ("interactive", "search", "direct"),
    "normal": ("interactive", "chat", "direct"),
    "unknown": ("interactive", "chat", "direct"),
    "tool": ("interactive", "tool", "direct"),
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
    d_cls, d_type, d_mode = HINT_EXECUTION.get(hint, ("interactive", "chat", "direct"))
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
            body = {"execution_class": "interactive", "task_type": "chat", "response_mode": "direct"}
        else:
            body = src
        cls, typ, mode = normalize_execution(body, hint, wrapper=False)
        details.append(
            {
                "execution_class": cls,
                "task_type": typ,
                "response_mode": mode,
                "depends_on": normalize_depends(item.get("depends_on") if item else [], i),
            }
        )
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
    if skill is None and inferred:
        skill, default_action = inferred
        if not action:
            action = default_action
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
    if str(plan.get("task_hint") or "") == "schedule" and not plan.get("cron_expr"):
        return False
    return True


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


def _classify_model_candidates(cfg: dict[str, Any], override: str | None = None) -> list[str]:
    """Primary classify combo, then chat combo when they differ (403/empty failover)."""
    out: list[str] = []
    for candidate in (
        _router_llm_model(cfg, override),
        _default_chat_combo_alias(),
    ):
        name = str(candidate or "").strip()
        if name and name not in out:
            out.append(name)
    return out or [_default_chat_combo_alias()]


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
    """Local fallback when classify LLM returns garbage (Omni free-tier weak models)."""
    blob = (text or "").strip()
    if not blob or len(blob) > 400:
        return None
    low = blob.lower()
    if any(
        tok in low
        for tok in (
            "đặt lịch",
            "dat lich",
            "schedule",
            "cron",
            "hằng ngày",
            "hang ngay",
            "daily at",
            "mỗi sáng",
            "moi sang",
        )
    ):
        return None
    if any(tok in low for tok in ("vẽ", "ve ", "draw", "image", "hình", "poster", "ocr", "pdf")):
        return None
    numbered = [ln.strip() for ln in blob.splitlines() if ln.strip()]
    if len(numbered) >= 2 and all(
        __import__("re").match(r"^\d+[.)]\s+", ln) for ln in numbered[: min(4, len(numbered))]
    ):
        return None
    return {
        "task_hint": "normal",
        "instructions": [blob],
        "process_original_message": True,
    }


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
    cadence = str(src.get("cadence") or "").strip().lower()
    if cadence not in CADENCES:
        cadence = "daily" if hint == "schedule" else "once"
    cron = valid_cron(str(src.get("cron_expr") or ""))
    tz = (timezone or "Asia/Ho_Chi_Minh").strip() or "Asia/Ho_Chi_Minh"
    exec_cls, task_type, response_mode = normalize_execution(src, hint)
    skill, skill_action = normalize_skill(src, hint, task_type)
    message = str(src.get("message") or "").strip()
    if not message:
        if len(instructions) == 1:
            message = instructions[0]
        elif instructions:
            message = "\n".join(instructions)
        else:
            message = fallback
    process_original = src.get("process_original_message")
    if not isinstance(process_original, bool):
        process_original = hint != "schedule"
    attachments_required = src.get("attachments_required")
    if not isinstance(attachments_required, bool):
        attachments_required = False
    return {
        "ok": True,
        "task_hint": hint,
        "instructions": instructions,
        "task_details": normalize_task_details(src, instructions, hint),
        "cadence": cadence if hint == "schedule" else None,
        "cron_expr": cron if hint == "schedule" else None,
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
    blob = (text or "").strip()
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
                    # Auth/quota on this combo → try next model immediately.
                    if resp.status_code in {401, 403, 404, 429}:
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
        return {"ok": False, "action": "drop", "error": "outbound_llm_failed"}
    parsed = _json_object(content) or _loads_first(content)
    if not parsed:
        return {"ok": False, "action": "drop", "error": "outbound_llm_failed"}
    return normalize_outbound(parsed)
