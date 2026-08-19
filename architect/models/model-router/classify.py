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
CRON_CHARS = set("0123456789*,/-")


def _load_cfg() -> dict[str, Any]:
    try:
        return json.loads(CFG_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {
            "timeout_s": 90,
            "max_tokens": 32768,
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


def _message_text(data: dict[str, Any]) -> str:
    choices = data.get("choices") if isinstance(data, dict) else None
    if not isinstance(choices, list) or not choices:
        return ""
    ch = choices[0] if isinstance(choices[0], dict) else {}
    msg = ch.get("message") if isinstance(ch.get("message"), dict) else {}
    for key in ("content", "reasoning_content"):
        val = msg.get(key)
        if isinstance(val, str) and val.strip():
            return val
        if isinstance(val, list):
            parts: list[str] = []
            for item in val:
                if isinstance(item, str) and item.strip():
                    parts.append(item.strip())
                elif isinstance(item, dict):
                    t = item.get("text")
                    if isinstance(t, str) and t.strip():
                        parts.append(t.strip())
            if parts:
                return "\n".join(parts)
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


def normalize_plan(data: dict[str, Any] | None, text: str, timezone: str) -> dict[str, Any]:
    src = data if isinstance(data, dict) else {}
    hint = str(src.get("task_hint") or "").strip().lower()
    if hint in {"secret", "blocked", "sensitive"}:
        hint = "unknown"
    if hint not in TASK_HINTS:
        hint = "unknown"
    instructions: list[str] = []
    raw_inst = src.get("instructions")
    if isinstance(raw_inst, list):
        for item in raw_inst:
            s = str(item).strip()
            if s:
                instructions.append(s)
    fallback = (text or "").strip()
    if not instructions and fallback:
        instructions = [fallback]
    cadence = str(src.get("cadence") or "").strip().lower()
    if cadence not in CADENCES:
        cadence = "daily" if hint == "schedule" else "once"
    cron = valid_cron(str(src.get("cron_expr") or ""))
    tz = (timezone or "Asia/Ho_Chi_Minh").strip() or "Asia/Ho_Chi_Minh"
    return {
        "ok": True,
        "task_hint": hint,
        "instructions": instructions,
        "cadence": cadence if hint == "schedule" else None,
        "cron_expr": cron if hint == "schedule" else None,
        "timezone": tz,
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
    tmpl = str(cfg.get("user_template") or "Timezone: {timezone}\nMessage:\n{text}")
    payload = {
        "model": (model or os.environ.get("MODEL_ROUTER_CLASSIFY_MODEL") or "hermes").strip() or "hermes",
        "stream": False,
        "temperature": float(cfg.get("temperature") or 0),
        "max_tokens": int(cfg.get("max_tokens") or 32768),
        "messages": [
            {"role": "system", "content": str(cfg.get("system") or "")},
            {"role": "user", "content": tmpl.replace("{timezone}", tz).replace("{text}", blob)},
        ],
    }
    headers = {"Content-Type": "application/json"}
    if n9_key:
        headers["Authorization"] = f"Bearer {n9_key}"
    timeout = float(cfg.get("timeout_s") or 90)
    url = f"{n9_base.rstrip('/')}/chat/completions"
    content = ""
    llm_attempts = 2
    for attempt in range(llm_attempts):
        try:
            resp = await client.post(url, headers=headers, json=payload, timeout=timeout)
            raw = resp.text
            data = _loads_first(raw) or {}
            content = _message_text(data)
            if content:
                break
            print(
                f"[classify] empty content attempt={attempt + 1} "
                f"finish={((data.get('choices') or [{}])[0] or {}).get('finish_reason')}",
                flush=True,
            )
        except Exception as exc:
            print(f"[classify] llm_err {type(exc).__name__} attempt={attempt + 1}", flush=True)
            content = ""
    parsed = _json_object(content) or _loads_first(content)
    if not parsed:
        return {
            "ok": False,
            "task_hint": "unknown",
            "instructions": [],
            "cadence": None,
            "cron_expr": None,
            "timezone": tz,
            "error": "classify_llm_failed",
        }
    return normalize_plan(parsed, blob, tz)


def _load_outbound_cfg() -> dict[str, Any]:
    try:
        return json.loads(OUTBOUND_CFG_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {
            "timeout_s": 8,
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
        "model": (model or os.environ.get("MODEL_ROUTER_CLASSIFY_MODEL") or "hermes").strip() or "hermes",
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
    timeout = float(cfg.get("timeout_s") or 8)
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
