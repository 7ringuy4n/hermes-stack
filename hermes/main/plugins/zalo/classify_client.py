"""HTTP client for model-router POST /v1/classify (Zalo classify skill).

Prompt SoT: hermes/main/skills/classify/classify.json — loaded by router-worker.
This module validates/normalizes the JSON protocol only. Do not add Vietnamese NLU.
Keep schema enums in sync with model-router classify.py.
"""
from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from typing import Any, Callable

Planner = Callable[..., dict[str, Any]]
_planner: Planner | None = None

TASK_HINTS = ("normal", "schedule", "coding", "tool", "search", "file", "knowledge", "unknown")
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
DEFAULT_TIMEOUT_S = 70.0
HTTP_ATTEMPTS = 1
_PRIOR_START = "[prior conversation]"
_PRIOR_END = "[/prior conversation]"
_OUTPUT_TYPES = {"image", "pdf", "txt", "docx", "xlsx", "csv", "md"}


def strip_prior_for_classify(text: str) -> str:
    """Current user ask only — drop Valkey hydrate wrappers (keep in sync with model-router)."""
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
    cleaned = blob.strip()
    return cleaned or (text or "").strip()


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


def sanitize_instructions(raw: Any, fallback: str) -> list[str]:
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


def set_planner(fn: Planner | None) -> None:
    global _planner
    _planner = fn


def valid_cron(expr: str) -> str | None:
    parts = (expr or "").strip().split()
    if len(parts) != 5:
        return None
    for p in parts:
        if not p or any(ch not in CRON_CHARS for ch in p):
            return None
    return " ".join(parts)


def normalize_execution(
    src: dict[str, Any], hint: str, *, wrapper: bool = True
) -> tuple[str, str, str]:
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
    del count
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


def plan_compound_sequential(plan: dict[str, Any] | None) -> bool:
    """True when classify split this bubble into multiple immediate parts (Zalo FIFO order)."""
    src = plan if isinstance(plan, dict) else {}
    if str(src.get("task_hint") or "").strip().lower() == "schedule":
        return False
    parts = [str(x).strip() for x in (src.get("instructions") or []) if str(x).strip()]
    return len(parts) >= 2


def plan_skips_media_shortcut(plan: dict[str, Any] | None) -> bool:
    """True when Dispatcher office shortcut must not run.

    Classify JSON owns mixed image+file, live-data files, schedules, and delivers.
    """
    src = plan if isinstance(plan, dict) else {}
    if src.get("ok") is False:
        return True
    hint = str(src.get("task_hint") or "").strip().lower()
    if hint == "schedule":
        return True
    action = str(src.get("skill_action") or "").strip().lower()
    if action in {"deliver", "send", "send_message"}:
        return True
    if str(src.get("skill") or "").strip().lower() == "web_search":
        return True
    parts = [str(x).strip() for x in (src.get("instructions") or []) if str(x).strip()]
    if len(parts) >= 2:
        return True
    types: set[str] = set()
    if str(src.get("task_type") or "").strip().lower():
        types.add(str(src.get("task_type") or "").strip().lower())
    for detail in src.get("task_details") or []:
        if not isinstance(detail, dict):
            continue
        if str(detail.get("task_type") or "").strip():
            types.add(str(detail.get("task_type") or "").strip().lower())
        if str(detail.get("skill") or "").strip().lower() == "web_search":
            return True
    if "media_generation" in types or "search" in types:
        return True
    return False


def plan_allows_office_shortcut(plan: dict[str, Any] | None) -> bool:
    """Single file-create job from classify — Dispatcher may run without phrase-scan."""
    src = plan if isinstance(plan, dict) else {}
    if plan_skips_media_shortcut(src):
        return False
    if str(src.get("task_hint") or "").strip().lower() == "file":
        return True
    if str(src.get("task_type") or "").strip().lower() == "file_processing":
        return True
    return False


def _plan_types(src: dict[str, Any]) -> set[str]:
    types: set[str] = set()
    if str(src.get("task_type") or "").strip().lower():
        types.add(str(src.get("task_type") or "").strip().lower())
    for detail in src.get("task_details") or []:
        if not isinstance(detail, dict):
            continue
        if str(detail.get("task_type") or "").strip():
            types.add(str(detail.get("task_type") or "").strip().lower())
    return types


def _plan_has_search(src: dict[str, Any]) -> bool:
    if str(src.get("skill") or "").strip().lower() == "web_search":
        return True
    if str(src.get("task_hint") or "").strip().lower() == "search":
        return True
    types = _plan_types(src)
    if "search" in types:
        return True
    for detail in src.get("task_details") or []:
        if not isinstance(detail, dict):
            continue
        if str(detail.get("skill") or "").strip().lower() == "web_search":
            return True
    return False


def _plan_has_media_generation(src: dict[str, Any]) -> bool:
    return "media_generation" in _plan_types(src)


def _plan_has_file_processing(src: dict[str, Any]) -> bool:
    if str(src.get("task_hint") or "").strip().lower() == "file":
        return True
    return "file_processing" in _plan_types(src)


def plan_search_then_office_output(plan: dict[str, Any] | None) -> str:
    """Office kind for search→office host path (pdf/docx/…). Empty if not applicable."""
    src = plan if isinstance(plan, dict) else {}
    ot = _coerce_output_type(src.get("output_type"))
    if ot in _OUTPUT_TYPES and ot != "image":
        return ot
    for detail in src.get("task_details") or []:
        if not isinstance(detail, dict):
            continue
        if str(detail.get("task_type") or "").strip().lower() != "file_processing":
            continue
        ot2 = _coerce_output_type(detail.get("output_type"))
        if ot2 in _OUTPUT_TYPES and ot2 != "image":
            return ot2
    if _plan_has_file_processing(src):
        return "pdf"
    return ""


def plan_allows_search_then_office(plan: dict[str, Any] | None) -> bool:
    """Live-data office create (search sibling + one file) — host search then office-file.

    Plain office shortcut must stay skipped (search present). Hermes often answers
    chat-only after search; host owns the PDF delivery for this family.
    """
    src = plan if isinstance(plan, dict) else {}
    if src.get("ok") is False:
        return False
    if str(src.get("task_hint") or "").strip().lower() == "schedule":
        return False
    action = str(src.get("skill_action") or "").strip().lower()
    if action in {"deliver", "send", "send_message"}:
        return False
    if _plan_has_media_generation(src):
        return False
    if not _plan_has_search(src):
        return False
    if not plan_search_then_office_output(src):
        return False
    return True


_LABELED_SCENE_RENDER = frozenset({"labeled-scene", "labeled_scene", "info-card", "info_card", "card", "dashboard"})
_SCENE_OVERLAY_RENDER = frozenset(
    {"scene-overlay", "scene_overlay", "weather-scene", "weather_scene", "scenic-overlay"}
)
_INFO_CARD_RENDER = _LABELED_SCENE_RENDER  # legacy alias


def _plan_instruction_blob(plan: dict[str, Any] | None) -> str:
    src = plan if isinstance(plan, dict) else {}
    parts = [str(x).strip() for x in (src.get("instructions") or []) if str(x).strip()]
    return "\n".join(parts)


def plan_image_render_mode(plan: dict[str, Any] | None) -> str:
    """RENDER: contract from classify (scene | scene-overlay | info-card)."""
    blob = _plan_instruction_blob(plan)
    for raw in blob.splitlines():
        line = raw.strip()
        if line.upper().startswith("RENDER:"):
            return line.split(":", 1)[1].strip().lower()
    up = blob.upper()
    if "TITLE:" in up or "STYLE:" in up:
        return "info-card"
    if "SCENE:" in up:
        return "scene"
    return ""


def _plan_allows_search_then_image_base(plan: dict[str, Any] | None) -> bool:
    """Search + one image job — shared gate for weather-scene and info-card host paths."""
    src = plan if isinstance(plan, dict) else {}
    if src.get("ok") is False:
        return False
    if str(src.get("task_hint") or "").strip().lower() == "schedule":
        return False
    action = str(src.get("skill_action") or "").strip().lower()
    if action in {"deliver", "send", "send_message"}:
        return False
    if src.get("poster_n") is not None or src.get("poster_phrase"):
        return False
    if _plan_has_file_processing(src):
        return False
    if not _plan_has_search(src):
        return False
    if not _plan_has_media_generation(src):
        return False
    ot = _coerce_output_type(src.get("output_type"))
    if ot and ot != "image":
        return False
    for detail in src.get("task_details") or []:
        if not isinstance(detail, dict):
            continue
        if str(detail.get("task_type") or "").strip().lower() != "media_generation":
            continue
        ot2 = _coerce_output_type(detail.get("output_type"))
        if ot2 and ot2 != "image":
            return False
    return True


def plan_allows_search_then_image(plan: dict[str, Any] | None) -> bool:
    """Live-data image (search + media_generation) — weather scene or info-card."""
    return _plan_allows_search_then_image_base(plan)


def plan_allows_search_then_weather_scene(plan: dict[str, Any] | None) -> bool:
    """City/place scene + small weather overlay (not info-card dashboard)."""
    if not _plan_allows_search_then_image_base(plan):
        return False
    return plan_image_render_mode(plan) in _SCENE_OVERLAY_RENDER


def plan_allows_search_then_info_card(plan: dict[str, Any] | None) -> bool:
    """Metrics dashboard info-card (search + media_generation, not scene-overlay)."""
    if not _plan_allows_search_then_image_base(plan):
        return False
    mode = plan_image_render_mode(plan)
    if mode in _SCENE_OVERLAY_RENDER:
        return False
    if mode in _LABELED_SCENE_RENDER or mode == "labeled-scene":
        return True
    blob = _plan_instruction_blob(plan).upper()
    if "OVERVIEW:" in blob and "SCENE:" in blob:
        return True
    return "TITLE:" in blob


def plan_allows_scene_image(plan: dict[str, Any] | None) -> bool:
    """Pure scenic image — diffusion only, no live-data search sibling."""
    src = plan if isinstance(plan, dict) else {}
    if src.get("ok") is False:
        return False
    if str(src.get("task_hint") or "").strip().lower() == "schedule":
        return False
    action = str(src.get("skill_action") or "").strip().lower()
    if action in {"deliver", "send", "send_message"}:
        return False
    if src.get("poster_n") is not None or src.get("poster_phrase"):
        return False
    if _plan_has_file_processing(src):
        return False
    if _plan_has_search(src):
        return False
    if not _plan_has_media_generation(src):
        return False
    mode = plan_image_render_mode(plan)
    if mode in _SCENE_OVERLAY_RENDER or mode in _LABELED_SCENE_RENDER or mode in {"info-card", "labeled-scene"}:
        return False
    ot = _coerce_output_type(src.get("output_type"))
    if ot and ot != "image":
        return False
    return True


def plan_sheet_ref(plan: dict[str, Any] | None) -> str:
    """SHEET_REF from classify instructions (workbook follow-up contract)."""
    src = plan if isinstance(plan, dict) else {}
    parts: list[str] = []
    for x in src.get("instructions") or []:
        s = str(x or "").strip()
        if s:
            parts.append(s)
    for detail in src.get("task_details") or []:
        if not isinstance(detail, dict):
            continue
        for key in ("instruction", "body", "text"):
            s = str(detail.get(key) or "").strip()
            if s:
                parts.append(s)
    blob = "\n".join(parts)
    for raw in blob.splitlines():
        line = raw.strip()
        if line.upper().startswith("SHEET_REF:"):
            return line.split(":", 1)[1].strip()
    up = blob.upper()
    key = "SHEET_REF:"
    j = up.find(key)
    if j >= 0:
        return blob[j + len(key) :].splitlines()[0].strip()
    return ""


def plan_image_instruction(plan: dict[str, Any] | None, fallback: str = "") -> str:
    """Pick the info-card body instruction from classify (markers preferred)."""
    src = plan if isinstance(plan, dict) else {}
    parts = [str(x).strip() for x in (src.get("instructions") or []) if str(x).strip()]
    details = src.get("task_details") if isinstance(src.get("task_details"), list) else []
    # Prefer scene/weather contract, then info-card markers
    for p in parts:
        up = p.upper()
        if "RENDER:" in up or "SCENE:" in up:
            return p
        if "TITLE:" in up or "OVERVIEW:" in up:
            return p
    for i, detail in enumerate(details):
        if not isinstance(detail, dict):
            continue
        tt = str(detail.get("task_type") or "").strip().lower()
        if tt == "media_generation":
            if i < len(parts):
                return parts[i]
    if len(parts) >= 2:
        return parts[-1]
    if parts:
        return parts[0]
    return str(fallback or "").strip()


def plan_search_query(plan: dict[str, Any] | None, fallback: str = "") -> str:
    """Pick the search query from classify instructions (structured indexes, not NLU)."""
    src = plan if isinstance(plan, dict) else {}
    parts = [str(x).strip() for x in (src.get("instructions") or []) if str(x).strip()]
    details = src.get("task_details") if isinstance(src.get("task_details"), list) else []

    def _usable_search_query(text: str) -> bool:
        s = (text or "").strip()
        if not s or len(s) < 8:
            return False
        up = s.upper()
        if "TITLE:" in up or "OVERVIEW:" in up or "BACKGROUND:" in up:
            return False
        if "SCENE:" in up or "RENDER:" in up:
            return False
        # Label-only stubs ("Nhiệt độ:") are not search queries
        if "\n" not in s and s.endswith(":") and len(s) < 48:
            return False
        return True

    for i, detail in enumerate(details):
        if not isinstance(detail, dict):
            continue
        tt = str(detail.get("task_type") or "").strip().lower()
        sk = str(detail.get("skill") or "").strip().lower()
        if tt == "search" or sk == "web_search":
            if i < len(parts) and _usable_search_query(parts[i]):
                return parts[i]
    for p in parts:
        if _usable_search_query(p):
            return p
    return str(fallback or "").strip()


def plan_file_instruction(plan: dict[str, Any] | None, fallback: str = "") -> str:
    """Pick the office-file body instruction from classify."""
    src = plan if isinstance(plan, dict) else {}
    parts = [str(x).strip() for x in (src.get("instructions") or []) if str(x).strip()]
    details = src.get("task_details") if isinstance(src.get("task_details"), list) else []
    for i, detail in enumerate(details):
        if not isinstance(detail, dict):
            continue
        if str(detail.get("task_type") or "").strip().lower() == "file_processing":
            if i < len(parts):
                return parts[i]
    if len(parts) >= 2:
        return parts[-1]
    if parts:
        return parts[0]
    return str(fallback or "").strip()


def plan_output_type(plan: dict[str, Any] | None) -> str:
    src = plan if isinstance(plan, dict) else {}
    ot = _coerce_output_type(src.get("output_type"))
    if ot:
        return ot
    details = src.get("task_details")
    if isinstance(details, list) and details and isinstance(details[0], dict):
        return _coerce_output_type(details[0].get("output_type"))
    return ""


def plan_allows_poster_shortcut(plan: dict[str, Any] | None) -> bool:
    src = plan if isinstance(plan, dict) else {}
    if src.get("ok") is False:
        return False
    if str(src.get("task_hint") or "").strip().lower() == "schedule":
        return False
    parts = [str(x).strip() for x in (src.get("instructions") or []) if str(x).strip()]
    if len(parts) >= 2:
        return False
    if str(src.get("skill") or "").strip().lower() == "web_search":
        return False
    if str(src.get("poster_phrase") or "").strip():
        return True
    return _coerce_poster_n(src.get("poster_n")) is not None


def plan_media_shortcut_gate(plan: dict[str, Any] | None) -> str:
    """Host media shortcut kind when the adapter must own the turn (no Hermes fallthrough)."""
    if plan_allows_office_shortcut(plan) and not plan_skips_media_shortcut(plan):
        return "office"
    if plan_allows_search_then_office(plan):
        return "search_office"
    if plan_allows_search_then_weather_scene(plan):
        return "weather_scene"
    if plan_allows_search_then_info_card(plan):
        return "info_card"
    # Scenic-only image is Hermes + image-gen (not a host shortcut).
    if plan_allows_poster_shortcut(plan):
        return "poster"
    return ""


def plan_is_immediate_deliver(plan: dict[str, Any] | None) -> bool:
    src = plan if isinstance(plan, dict) else {}
    if src.get("ok") is False:
        return False
    if str(src.get("task_hint") or "").strip().lower() == "schedule":
        return False
    action = str(src.get("skill_action") or "").strip().lower()
    return action in {"deliver", "send", "send_message"}


def plan_is_host_direct_reply(plan: dict[str, Any] | None) -> bool:
    """Classify already wrote the user-facing line; host must send it (no Hermes).

    Used for secret/env refuse and similar: process_original_message false, no
    schedule/deliver/knowledge skill path, skill null or security.
    """
    src = plan if isinstance(plan, dict) else {}
    if src.get("ok") is False:
        return False
    if src.get("process_original_message") is not False:
        return False
    hint = str(src.get("task_hint") or "").strip().lower()
    if hint == "schedule":
        return False
    if plan_is_immediate_deliver(src):
        return False
    skill = str(src.get("skill") or "").strip().lower()
    if skill and skill not in {"security", "none", "null"}:
        return False
    body = str(src.get("message") or "").strip()
    if not body:
        body = "\n".join(
            str(x).strip() for x in (src.get("instructions") or []) if str(x).strip()
        )
    return bool(body)


def plan_is_async(plan: dict[str, Any] | None) -> bool:
    src = plan if isinstance(plan, dict) else {}
    if src.get("ok") is False:
        return False
    for detail in src.get("task_details") or []:
        if not isinstance(detail, dict):
            continue
        if str(detail.get("execution_class") or "").strip().lower() == "async":
            return True
        if str(detail.get("response_mode") or "").strip().lower() == "ack_then_deliver":
            return True
        if str(detail.get("task_type") or "").strip().lower() in {"media_generation", "file_processing"}:
            return True
    if str(src.get("execution_class") or "").strip().lower() == "async":
        return True
    return str(src.get("response_mode") or "").strip().lower() == "ack_then_deliver"


def failed_plan(timezone: str, error: str = "classify_unavailable") -> dict[str, Any]:
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



def _coerce_delay_seconds(raw):
    if raw is None or raw == "":
        return None
    try:
        n = int(raw)
    except (TypeError, ValueError):
        return None
    if n <= 0 or n > 86400 * 30:
        return None
    return n


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


def normalize_plan(data: dict[str, Any] | None, text: str, timezone: str) -> dict[str, Any]:
    src = data if isinstance(data, dict) else {}
    if src.get("ok") is False:
        return failed_plan(timezone, str(src.get("error") or "classify_unavailable"))
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
    plan = {
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
        "uncertain": bool(src.get("uncertain") is True),
        "missing": [
            str(x).strip().lower()
            for x in (src.get("missing") or [])
            if str(x).strip().lower() in {"time", "destination", "output_type"}
        ],
    }
    if not plan_schema_ok(plan):
        return failed_plan(tz, "classify_invalid")
    return plan


def classify_text(
    text: str,
    *,
    timezone: str = "Asia/Ho_Chi_Minh",
    thread: str = "unknown",
    attachments: str = "none",
    quoted: str = "none",
) -> dict[str, Any]:
    tz = (timezone or "Asia/Ho_Chi_Minh").strip() or "Asia/Ho_Chi_Minh"
    blob = strip_prior_for_classify(text or "")
    if _planner is not None:
        try:
            return normalize_plan(_planner(blob, timezone=tz), blob, tz)
        except TypeError:
            return normalize_plan(_planner(blob), blob, tz)
    if not blob:
        return normalize_plan({"task_hint": "unknown", "instructions": []}, "", tz)
    base = (os.environ.get("MODEL_ROUTER_URL") or "http://model-router:8096").rstrip("/")
    payload = json.dumps(
        {
            "text": blob,
            "timezone": tz,
            "thread": thread or "unknown",
            "attachments": attachments or "none",
            "quoted": quoted or "none",
        },
        ensure_ascii=False,
    ).encode("utf-8")
    timeout = float(os.environ.get("MODEL_ROUTER_CLASSIFY_TIMEOUT_S") or DEFAULT_TIMEOUT_S)
    last_error = "classify_unavailable"
    for _attempt in range(HTTP_ATTEMPTS):
        req = urllib.request.Request(
            base + "/v1/classify",
            data=payload,
            method="POST",
            headers={"Content-Type": "application/json"},
        )
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                data = json.loads(resp.read().decode("utf-8") or "{}")
            if isinstance(data, dict) and data.get("ok"):
                plan = normalize_plan(data, blob, tz)
                if plan_schema_ok(plan):
                    return plan
                last_error = "classify_invalid"
                continue
            if isinstance(data, dict) and data.get("ok") is False:
                last_error = str(data.get("error") or "classify_unavailable")
                continue
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, OSError):
            last_error = "classify_http_error"
            continue
    return failed_plan(tz, last_error)


OUTBOUND_ACTION_MAP = {
    "send": "send",
    "drop": "drop",
}
OUTBOUND_ACTIONS = tuple(OUTBOUND_ACTION_MAP.keys())
_outbound_planner: Planner | None = None


def set_outbound_planner(fn: Planner | None) -> None:
    global _outbound_planner
    _outbound_planner = fn


def normalize_outbound(data: dict[str, Any] | None) -> dict[str, Any]:
    src = data if isinstance(data, dict) else {}
    raw_action = str(src.get("action") or "send").strip().lower()
    action = OUTBOUND_ACTION_MAP.get(raw_action, "send")
    if src.get("ok") is False:
        return {
            "ok": False,
            "action": action,
            "error": str(src.get("error") or "outbound_failed"),
        }
    out: dict[str, Any] = {"ok": True, "action": action}
    cleaned = src.get("text")
    if action == "send" and isinstance(cleaned, str) and cleaned.strip():
        out["text"] = cleaned.strip()
    return out


def classify_outbound(text: str) -> dict[str, Any]:
    blob = (text or "").strip()
    if not blob:
        return {"ok": True, "action": "drop"}
    if _outbound_planner is not None:
        try:
            return normalize_outbound(_outbound_planner(blob))
        except TypeError:
            return normalize_outbound(_outbound_planner(blob, timezone="Asia/Ho_Chi_Minh"))
    base = (os.environ.get("MODEL_ROUTER_URL") or "http://model-router:8096").rstrip("/")
    payload = json.dumps({"text": blob}, ensure_ascii=False).encode("utf-8")
    timeout = float(os.environ.get("MODEL_ROUTER_OUTBOUND_TIMEOUT_S") or 30.0)
    try:
        req = urllib.request.Request(
            base + "/v1/outbound",
            data=payload,
            method="POST",
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read().decode("utf-8") or "{}")
        if isinstance(data, dict):
            return normalize_outbound(data)
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, OSError):
        pass
    return {"ok": False, "action": "send", "error": "outbound_unavailable"}
