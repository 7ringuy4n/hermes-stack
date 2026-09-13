# -*- coding: utf-8 -*-
"""Dispatcher HTTP for classified office-file jobs (and search→office).

Intent lives in classify JSON. This module does not phrase-scan user prose.
The adapter calls run_office_create when plan_allows_office_shortcut is true,
or run_search_then_office when plan_allows_search_then_office is true.
"""
from __future__ import annotations

import base64
import hashlib
import json
import logging
import mimetypes
import os
import time
import urllib.error
import urllib.request
from datetime import datetime
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, Optional
from zoneinfo import ZoneInfo

log = logging.getLogger("hermes_plugins.zalo_platform.media_shortcuts")

_COMPOSITION_MAX_LINES = 8

_MEDIA_FAIL_LINE_VI = (
    "Hiện chưa tạo được file này. Bạn thử lại sau hoặc rút gọn yêu cầu giúp mình."
)


def shortcut_consumed() -> dict[str, Any]:
    """Signal adapter: host owned this media turn but delivery failed — do not call Hermes."""
    return {"ok": False, "shortcut_consumed": True}


def shortcut_ok(out: dict[str, Any] | None) -> bool:
    return isinstance(out, dict) and out.get("ok") is True


def shortcut_was_consumed(out: dict[str, Any] | None) -> bool:
    return isinstance(out, dict) and out.get("shortcut_consumed") is True


def media_fail_line() -> str:
    return _MEDIA_FAIL_LINE_VI


def dispatcher_url() -> str:
    return (os.getenv("DISPATCHER_URL") or "http://dispatcher:8090").rstrip("/")


def router_worker_url() -> str:
    return (os.getenv("ROUTER_WORKER_URL") or "http://router-worker:8096").rstrip("/")


def _post(path: str, body: dict, timeout: float = 60.0, *, base: str = "") -> Dict[str, Any]:
    root = (base or dispatcher_url()).rstrip("/")
    data = json.dumps(body, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(
        root + path,
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8") or "{}")


def run_web_search(query: str, max_results: int = 6) -> Optional[dict]:
    """POST router-worker /v1/search. Returns payload or None."""
    q = (query or "").strip()
    if not q:
        return None
    try:
        out = _post(
            "/v1/search",
            {"query": q, "max_results": max(1, min(int(max_results), 8))},
            timeout=45.0,
            base=router_worker_url(),
        )
    except Exception as e:  # noqa: BLE001
        log.warning("search_then_office search failed: %s", type(e).__name__)
        return None
    if isinstance(out, dict) and (out.get("results") or out.get("answer") is not None):
        return out
    log.warning(
        "web search returned no usable result backend=%r error=%r",
        (out or {}).get("backend") if isinstance(out, dict) else None,
        (out or {}).get("error") if isinstance(out, dict) else None,
    )
    return None


def _skip_structural_junk(line: str) -> bool:
    """Drop empty lines, URLs, JSON blobs, and unfilled template placeholders."""
    s = (line or "").strip()
    if not s or len(s) < 2:
        return True
    if s.startswith(("{", "[", "'{", '"{')):
        return True
    if "{'" in s or '{"' in s:
        return True
    low = s.lower()
    if low.startswith("http://") or low.startswith("https://"):
        return True
    if "<" in s or ">" in s:
        return True
    if "value after" in low:
        return True
    if "safe-for-work" in low or "safe for work" in low:
        return True
    # Label-only bullets with no value: "Nhiệt độ:" / "Humidity:"
    if s.endswith(":") and ":" == s[-1:] and s.count(":") == 1:
        return True
    if ": " in s:
        _left, right = s.split(": ", 1)
        if not right.strip():
            return True
    return False


def _clean_fact_line(text: str) -> str:
    s = (text or "").strip()
    if s.startswith(("- ", "• ", "* ")):
        s = s[2:].strip()
    while s.startswith("#"):
        s = s.lstrip("#").strip()
    return s[:200]


def _search_answer_lines(search: dict[str, Any] | None, *, limit: int = 8) -> list[str]:
    """Plain answer prose lines only — never scrape SERP result titles/snippets."""
    if not isinstance(search, dict):
        return []
    ans = search.get("answer")
    if not isinstance(ans, str) or not ans.strip():
        return []
    out: list[str] = []
    seen: set[str] = set()
    for part in ans.replace("\r", "\n").split("\n"):
        line = _clean_fact_line(part)
        if _skip_structural_junk(line):
            continue
        key = line.lower()
        if key in seen:
            continue
        seen.add(key)
        out.append(line)
        if len(out) >= limit:
            break
    return out


def _bullets_from_instruction(text: str) -> list[str]:
    out: list[str] = []
    for raw in (text or "").splitlines():
        s = raw.strip()
        if s.startswith(("- ", "• ", "* ")):
            line = _clean_fact_line(s)
            if line and not _skip_structural_junk(line):
                out.append(line)
    return out


def _collect_host_facts(instruction: str, search: dict[str, Any] | None) -> list[str]:
    """Classify fact bullets + search answer lines (LLM/search own content quality)."""
    facts: list[str] = []
    seen: set[str] = set()

    def add(line: str) -> None:
        if not line:
            return
        key = line.lower()
        if key in seen:
            return
        seen.add(key)
        facts.append(line)

    for line in _bullets_from_instruction(instruction):
        add(line)
    for line in _search_answer_lines(search):
        add(line)
    return facts[:8]


def _search_notes_blob(search: Any, *, limit: int = 8) -> str:
    """Concat result content fields for LLM synthesis (not titles; not host NLU)."""
    if isinstance(search, list):
        blocks = [_search_notes_blob(item, limit=limit) for item in search]
        return "\n===\n".join(block for block in blocks if block)[:6400]
    if not isinstance(search, dict):
        return ""
    chunks: list[str] = []
    source_query = str(search.get("_request_query") or "").strip()
    if source_query:
        chunks.append(f"Requested evidence: {source_query[:500]}")
    ans = search.get("answer")
    if isinstance(ans, str) and ans.strip():
        chunks.append(ans.strip()[:800])
    for row in search.get("results") or []:
        if not isinstance(row, dict):
            continue
        content = str(row.get("content") or row.get("snippet") or "").strip()
        if not content or len(content) < 8:
            continue
        chunks.append(content[:400])
        if len(chunks) >= limit + (1 if ans else 0):
            break
    return "\n---\n".join(chunks)[:3200]


@lru_cache(maxsize=1)
def _image_prompt_assets() -> dict[str, Any]:
    """Load editable image-composition prompts; runtime Python owns no prompt prose."""
    configured = (os.getenv("CLASSIFY_IMAGE_PROMPTS_FILE") or "").strip()
    candidates = [
        Path(configured) if configured else None,
        Path("/opt/data/skills/classify/parts/image-runtime.json"),
        Path(__file__).resolve().parents[2]
        / "skills"
        / "classify"
        / "parts"
        / "image-runtime.json",
    ]
    for candidate in candidates:
        if candidate is None or not candidate.is_file():
            continue
        try:
            payload = json.loads(candidate.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            log.warning("image prompt asset unreadable path=%s error=%s", candidate, type(exc).__name__)
            continue
        if isinstance(payload, dict):
            return payload
    log.error("image prompt asset missing")
    return {}


def _safe_composition_design(raw: Any) -> dict[str, Any]:
    assets = _image_prompt_assets()
    defaults = assets.get("default_design")
    base = dict(defaults) if isinstance(defaults, dict) else {}
    source = raw if isinstance(raw, dict) else {}
    allowed = {
        "placement": {
            "auto", "top-left", "top-center", "top-right", "center-left", "center",
            "center-right", "bottom-left", "bottom-center", "bottom-right", "top-bar",
            "bottom-bar", "left-column", "right-column",
        },
        "theme": {"auto", "light", "dark"},
        "alignment": {"left", "center", "right"},
        "font_family": {"auto", "inter", "noto-sans", "serif", "mono"},
        "title_weight": {"regular", "medium", "semibold", "bold"},
        "body_weight": {"regular", "medium", "semibold", "bold"},
        "important_weight": {"regular", "medium", "semibold", "bold"},
        "accent": {"auto", "cool", "warm", "neutral", "vibrant"},
        "density": {"compact", "comfortable"},
    }
    out: dict[str, Any] = {}
    for key, choices in allowed.items():
        value = str(source.get(key) or base.get(key) or "auto").strip().lower()
        out[key] = value if value in choices else str(base.get(key) or "auto")
    region = source.get("region")
    if isinstance(region, dict):
        try:
            min_width = 0.18
            min_height = 0.28
            x = max(0.0, min(float(region.get("x")), 1.0 - min_width))
            y = max(0.0, min(float(region.get("y")), 1.0 - min_height))
            width = max(min_width, min(float(region.get("width")), 1.0 - x))
            height = max(min_height, min(float(region.get("height")), 1.0 - y))
            out["region"] = {
                "x": round(x, 4), "y": round(y, 4),
                "width": round(width, 4), "height": round(height, 4),
            }
        except (TypeError, ValueError):
            pass
    return out


def _json_object(text: str) -> dict[str, Any]:
    raw = (text or "").strip()
    start = raw.find("{")
    end = raw.rfind("}")
    if start < 0 or end <= start:
        return {}
    try:
        value = json.loads(raw[start : end + 1])
    except ValueError:
        return {}
    return value if isinstance(value, dict) else {}


def _composition_plan_timeout_s() -> int:
    """Allow normal router queueing without an unbounded Zalo turn."""
    raw = (os.getenv("OMNI_COMPOSITION_PLAN_TIMEOUT_S") or "120").strip()
    try:
        return max(30, min(int(raw), 180))
    except ValueError:
        return 120


_COMPOSITION_PLAN_MAX_TOKENS = 4096


def _composition_plan_model() -> str:
    """Return the configured priority combo for short structured planning."""
    return (
        os.getenv("OMNIROUTER_CLASSIFY_COMBO")
        or os.getenv("ROUTER_WORKER_CLASSIFY_MODEL")
        or "classifier"
    ).strip() or "classifier"


def _omni_json_plan(system: str, user: str, *, max_tokens: int) -> dict[str, Any]:
    """Run one prompt-asset-owned structured planning call."""
    try:
        from .omni_env import resolve_media_router_api_key, resolve_media_router_base_url
    except ImportError:
        from omni_env import resolve_media_router_api_key, resolve_media_router_base_url  # type: ignore

    base = resolve_media_router_base_url()
    key = resolve_media_router_api_key()
    if not base or not key or not system or not user:
        return {}
    model = _composition_plan_model()
    body = json.dumps(
        {
            "model": model,
            "stream": False,
            "temperature": 0,
            "max_tokens": max_tokens,
            "metadata": {"task_hint": "file", "task_type": "file_processing"},
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
        },
        ensure_ascii=False,
    ).encode("utf-8")
    req = urllib.request.Request(
        f"{base.rstrip('/')}/chat/completions",
        data=body,
        method="POST",
        headers={
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=_composition_plan_timeout_s()) as resp:
            data = json.loads(resp.read().decode("utf-8") or "{}")
    except Exception as exc:  # noqa: BLE001
        log.warning("image structured planning failed: %s", type(exc).__name__)
        return {}
    choices = data.get("choices") if isinstance(data, dict) else None
    if not isinstance(choices, list) or not choices or not isinstance(choices[0], dict):
        return {}
    message = choices[0].get("message")
    text = str(message.get("content") or "").strip() if isinstance(message, dict) else ""
    parsed = _json_object(text)
    if not parsed:
        finish_reason = str(choices[0].get("finish_reason") or "unknown")
        log.warning(
            "image structured planning invalid model=%r finish_reason=%r "
            "content_chars=%s max_tokens=%s",
            model,
            finish_reason,
            len(text),
            max_tokens,
        )
    return parsed


def _evidence_queries(query: str, instruction: str) -> list[str]:
    """Use an editable LLM prompt to decompose unrelated evidence domains."""
    assets = _image_prompt_assets()
    system = str(assets.get("evidence_system") or "").strip()
    template = str(assets.get("evidence_user_template") or "").strip()
    user = template.replace("{query}", (query or "").strip()[:1200])
    user = user.replace("{instruction}", (instruction or "").strip()[:1200])
    parsed = _omni_json_plan(system, user, max_tokens=320)
    return _validated_evidence_queries(parsed)


def _validated_evidence_queries(parsed: Any) -> list[str]:
    """Validate a model-authored query list without interpreting its language."""
    source = parsed if isinstance(parsed, dict) else {}
    queries: list[str] = []
    seen: set[str] = set()
    for raw in source.get("queries") or []:
        value = " ".join(str(raw or "").split())[:500]
        key = value.casefold()
        if len(value) < 8 or key in seen:
            continue
        seen.add(key)
        queries.append(value)
        if len(queries) >= 4:
            break
    return queries


def _synthesize_composition_plan(
    search: Any,
    *,
    query: str = "",
    instruction: str = "",
) -> dict[str, Any]:
    """Ask the chat combo for grounded content and generic visual-design decisions."""
    notes = _search_notes_blob(search)
    if not notes.strip():
        return {}
    assets = _image_prompt_assets()
    system = str(assets.get("composition_system") or "").strip()
    user_template = str(assets.get("composition_user_template") or "").strip()
    if not system or not user_template:
        return {}
    system = system + "\n\n" + str(assets.get("typography_policy") or "").strip()
    user = user_template.replace("{query}", (query or "").strip()[:240])
    user = user.replace("{instruction}", (instruction or "").strip()[:1200])
    user = user.replace("{notes}", notes)
    parsed = _omni_json_plan(
        system,
        user,
        # This is a protocol bound, not an operator tuning knob. The validator
        # below caps every collection and string, so one fixed budget covers the
        # largest accepted plan and keeps deployments configuration-free.
        max_tokens=_COMPOSITION_PLAN_MAX_TOKENS,
    )
    facts: list[dict[str, str]] = []
    seen: set[str] = set()
    for item in parsed.get("facts") or []:
        if not isinstance(item, dict):
            continue
        label = " ".join(str(item.get("label") or "").split())[:40]
        value = " ".join(str(item.get("value") or "").split())[:72]
        emphasis = str(item.get("emphasis") or "normal").strip().lower()
        if not label or not value or _skip_structural_junk(value):
            continue
        key2 = f"{label.casefold()}:{value.casefold()}"
        if key2 in seen:
            continue
        seen.add(key2)
        facts.append(
            {
                "label": label,
                "value": value,
                "emphasis": emphasis if emphasis in {"primary", "important", "normal"} else "normal",
            }
        )
        if len(facts) >= 6:
            break
    title = " ".join(str(parsed.get("title") or "").split())[:64]
    background_scene = " ".join(str(parsed.get("background_scene") or "").split())[:1200]
    panels: list[dict[str, Any]] = []
    for raw_panel in parsed.get("panels") or []:
        if not isinstance(raw_panel, dict):
            continue
        panel_facts: list[dict[str, str]] = []
        for item in raw_panel.get("facts") or []:
            if not isinstance(item, dict):
                continue
            label = " ".join(str(item.get("label") or "").split())[:40]
            value = " ".join(str(item.get("value") or "").split())[:72]
            emphasis = str(item.get("emphasis") or "normal").strip().lower()
            if not label or not value or _skip_structural_junk(value):
                continue
            panel_facts.append({
                "label": label,
                "value": value,
                "emphasis": emphasis if emphasis in {"primary", "important", "normal"} else "normal",
            })
            if len(panel_facts) >= 6:
                break
        if not panel_facts:
            continue
        panels.append({
            "title": " ".join(str(raw_panel.get("title") or "").split())[:64],
            "facts": panel_facts,
            "design": _safe_composition_design(raw_panel.get("design")),
        })
        if len(panels) >= 6:
            break
    if not facts and not panels:
        log.warning("composition plan is empty model=%r", _composition_plan_model())
        return {}
    return {
        "title": title,
        "facts": facts,
        "panels": panels,
        "design": _safe_composition_design(parsed.get("design")),
        "include_timestamp": bool(parsed.get("include_timestamp", True)),
        "timestamp_label": " ".join(str(parsed.get("timestamp_label") or "").split())[:24],
        "background_scene": background_scene,
    }


def build_office_body_from_search(
    *,
    file_instruction: str,
    user_ask: str,
    search: dict[str, Any] | None,
) -> str:
    """Trivial host shortcut — literal body + classify bullets + search answer lines."""
    del user_ask
    fi = (file_instruction or "").strip()
    base = fi
    if not base or "\n" in base or len(base) > 48:
        base = ""
    else:
        up = base.upper()
        for prefix in (
            "TITLE:",
            "SUBTITLE:",
            "ICON:",
            "STYLE:",
            "OVERVIEW:",
            "BACKGROUND:",
            "RENDER:",
            "SCENE:",
        ):
            if up.startswith(prefix):
                base = ""
                break

    facts = _collect_host_facts(fi, search)
    parts: list[str] = []
    if base:
        parts.append(base)
    for f in facts[:8]:
        parts.append(f"- {f}")
    if not parts:
        return " "
    return "\n".join(parts).strip()


def run_office_create(
    text: str,
    thread_id: str,
    thread_type: str = "user",
    *,
    classified: bool = False,
    output_type: str = "",
) -> Optional[dict]:
    """POST /v1/office-file. Caller must already have a single file-create plan."""
    if not classified:
        return None
    prompt = (text or "").strip()
    if not prompt:
        return None
    body: dict[str, Any] = {
        "prompt": prompt,
        "thread_id": str(thread_id),
        "thread_type": "group" if str(thread_type).lower() in {"group", "g"} else "user",
        "caption": "",
        # Delivery remains in the cancellable adapter task. Dispatcher writes
        # the artifact only, so a stopped request cannot send a late file.
        "send_zalo": False,
    }
    if (output_type or "").strip():
        body["output_type"] = output_type.strip().lower()
    try:
        out = _post("/v1/office-file", body, timeout=120.0)
    except Exception as e:  # noqa: BLE001
        log.warning("office shortcut failed: %s", type(e).__name__)
        return shortcut_consumed()
    if isinstance(out, dict) and out.get("ok"):
        return out
    return shortcut_consumed()


def run_search_then_office(
    user_ask: str,
    plan: dict[str, Any],
    thread_id: str,
    thread_type: str = "user",
    *,
    classified: bool = False,
    output_type: str = "",
) -> Optional[dict]:
    """Host search → structured office-file. Used when classify has search + one file."""
    if not classified:
        return None
    try:
        from .classify_client import (
            plan_file_instruction,
            plan_search_query,
            plan_search_then_office_output,
        )
    except ImportError:
        from classify_client import (  # type: ignore
            plan_file_instruction,
            plan_search_query,
            plan_search_then_office_output,
        )
    query = plan_search_query(plan, user_ask)
    file_ins = plan_file_instruction(plan, user_ask)
    kind = (output_type or "").strip().lower() or plan_search_then_office_output(plan) or "pdf"
    search_query = query or user_ask
    search = run_web_search(search_query)
    if not search:
        # A combo can transiently exhaust one free backend while still returning
        # an HTTP-success envelope. Retry once without sleeping; use the complete
        # request as the fallback query when the classifier supplied a narrower
        # query. The web-search combo retains ownership of provider failover.
        fallback_query = user_ask if user_ask.strip() != search_query.strip() else search_query
        search = run_web_search(fallback_query)
    prompt = build_office_body_from_search(
        file_instruction=file_ins or user_ask,
        user_ask=user_ask,
        search=search,
    )
    return run_office_create(
        prompt,
        thread_id,
        thread_type,
        classified=True,
        output_type=kind,
    )


def scene_prompt_from_instruction(text: str) -> str:
    """Read the classifier-owned scene field without interpreting user prose."""
    for raw in (text or "").splitlines():
        line = raw.strip()
        if line.upper().startswith("SCENE:"):
            return line.split(":", 1)[1].strip()
    src = (text or "").strip()
    up = src.upper()
    if src and "TITLE:" not in up and "RENDER:" not in up:
        return src
    return ""


def _composition_timestamp(
    assets: dict[str, Any] | None = None, *, label: Any = ""
) -> str:
    source = assets if isinstance(assets, dict) else _image_prompt_assets()
    stamp = " ".join(str(label or source.get("timestamp_label") or "").split())[:24]
    if not stamp:
        return ""
    tz_name = (os.getenv("ASSISTANT_TZ") or os.getenv("TZ") or "Asia/Ho_Chi_Minh").strip()
    try:
        now = datetime.now(ZoneInfo(tz_name)).strftime("%H:%M · %Y-%m-%d")
    except Exception:  # noqa: BLE001
        now = datetime.now(ZoneInfo("Asia/Ho_Chi_Minh")).strftime("%H:%M · %Y-%m-%d")
    return f"{stamp}: {now}"


def _composition_image_prompt(scene: str, composition: dict[str, Any]) -> str:
    """Build one model-rendered image prompt from validated grounded content."""
    assets = _image_prompt_assets()
    template = str(assets.get("composition_render_template") or "").strip()
    if not template:
        log.error("composition render prompt asset missing")
        return ""
    spec = {
        "title": composition.get("title") or "",
        "facts": list(composition.get("facts") or [])[:_COMPOSITION_MAX_LINES],
        "panels": list(composition.get("panels") or [])[:6],
        "design": _safe_composition_design(composition.get("design")),
    }
    if composition.get("include_timestamp", True):
        stamp = _composition_timestamp(assets, label=composition.get("timestamp_label"))
        if stamp:
            spec["timestamp"] = stamp
    prompt = template.replace("{scene}", " ".join((scene or "").split())[:1200]).replace(
        "{composition}", json.dumps(spec, ensure_ascii=False, separators=(",", ":"))
    )
    return prompt + "\n\n" + str(assets.get("typography_policy") or "").strip()


def _scene_visual_prompt(scene: str) -> str:
    """Build a scene prompt entirely from classifier output and editable prompt assets."""
    assets = _image_prompt_assets()
    parts = [" ".join((scene or "").split())]
    suffix = str(assets.get("scene_suffix") or "").strip()
    if suffix:
        parts.append(suffix)
    return " ".join(part for part in parts if part).strip()


def _omni_image_gen_timeout_s() -> int:
    import os

    # Default and maximum: 300s (5 minutes) per combo image-gen member.
    raw = (os.getenv("OMNI_IMAGE_GEN_TIMEOUT_S") or "300").strip()
    try:
        return max(60, min(int(raw), 300))
    except ValueError:
        return 300


def _omni_image_gen_size() -> str:
    import os

    return (os.getenv("OMNI_IMAGE_GEN_SIZE") or "1280x720").strip() or "1280x720"


def _omni_image_gen_model() -> str:
    try:
        from .omni_env import resolve_env_var
    except ImportError:
        from omni_env import resolve_env_var  # type: ignore

    combo = (resolve_env_var("IMAGE_GEN_COMBO", "image-gen") or "image-gen").strip()
    return combo


def _omni_decode_image_blob(item: dict[str, Any]) -> bytes:
    blob = b""
    if item.get("b64_json"):
        blob = base64.b64decode(item["b64_json"])
    elif item.get("url"):
        try:
            with urllib.request.urlopen(item["url"], timeout=60) as r2:
                blob = r2.read()
        except Exception:  # noqa: BLE001
            return b""
    return blob


def _omni_image_quality_mins(size: str) -> tuple[int, int, int]:
    """Scale minimum acceptable dimensions from the requested canvas."""
    parts = (size or "1280x720").lower().split("x")
    try:
        w_req = int(parts[0])
        h_req = int(parts[1]) if len(parts) > 1 else w_req
    except (ValueError, IndexError):
        w_req, h_req = 1024, 1024
    min_w = max(512, w_req // 2)
    min_h = max(360, h_req // 2)
    return min_w, min_h, 80_000


def _omni_image_quality_ok(blob: bytes, *, size: str) -> bool:
    if not blob:
        return False
    min_w, min_h, min_bytes = _omni_image_quality_mins(size)
    try:
        from io import BytesIO

        from PIL import Image

        with Image.open(BytesIO(blob)) as im:
            w, h = im.size
        if w < min_w or h < min_h or len(blob) < min_bytes:
            log.warning(
                "omni generate: low-quality payload (%sx%s, %s bytes; need >=%sx%s, >=%s)",
                w,
                h,
                len(blob),
                min_w,
                min_h,
                min_bytes,
            )
            return False
        return True
    except Exception:
        if len(blob) < min_bytes:
            log.warning("omni generate: small payload (%s bytes)", len(blob))
            return False
        return True


def _omni_v1_combo_member_models(base: str, key: str, combo_name: str) -> list[str]:
    """Ordered combo members for a combo name (API key auth).

    Omni /v1/combos payloads vary (``data`` list vs ``combos``, ``model`` vs
    ``fullModel``). Prefer real provider/model ids so /images/generations can
    target a member directly — combo aliases often report
    ``No images-capable targets`` even when members work.
    """
    root = (base or "").rstrip("/")
    if root.endswith("/v1"):
        url = f"{root}/combos"
    else:
        url = f"{root}/v1/combos"
    req = urllib.request.Request(
        url,
        headers={"Authorization": f"Bearer {key}", "Accept": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read().decode() or "{}")
    except Exception as e:  # noqa: BLE001
        log.warning("omni combos list failed: %s", type(e).__name__)
        return []
    want = (combo_name or "").strip()
    rows = data.get("data") or data.get("combos") or data.get("items") or []
    if isinstance(data, list):
        rows = data
    combo = next(
        (c for c in rows if isinstance(c, dict) and (c.get("name") or "") == want),
        None,
    )
    if not combo:
        return []
    out: list[str] = []
    for row in combo.get("models") or combo.get("members") or []:
        if isinstance(row, str) and row.strip():
            mid = row.strip()
        elif isinstance(row, dict):
            mid = str(
                row.get("model")
                or row.get("fullModel")
                or row.get("id")
                or row.get("name")
                or ""
            ).strip()
        else:
            mid = ""
        # Skip nested combo aliases and blanks.
        if not mid or "/" not in mid:
            continue
        if mid not in out:
            out.append(mid)
    return out


def _omni_request_image_blob(
    *,
    base: str,
    key: str,
    model: str,
    scene: str,
    size: str,
    timeout: int,
    combo_members: list[str] | None = None,
) -> bytes | None:
    tried: list[str] = []
    candidates: list[str] = []
    deadline = time.monotonic() + max(1, int(timeout))
    combo = (model or "").strip()
    members = [m for m in (combo_members or []) if m and "/" in m]
    # Prefer concrete members so Omni UI shows Requested Model and so we bypass
    # broken combo-level "images-capable" gating.
    if members:
        candidates.extend(members)
    elif combo:
        candidates.append(combo)
    for candidate in candidates:
        remaining = int(deadline - time.monotonic())
        if remaining <= 0:
            break
        if not candidate or candidate in tried:
            continue
        tried.append(candidate)
        blob = _omni_request_image_blob_once(
            base=base,
            key=key,
            model=candidate,
            scene=scene,
            size=size,
            timeout=remaining,
        )
        if blob:
            return blob
    return None


def _omni_request_image_blob_once(
    *,
    base: str,
    key: str,
    model: str,
    scene: str,
    size: str,
    timeout: int,
) -> bytes | None:
    body = json.dumps({"model": model, "prompt": scene, "n": 1, "size": size}).encode()
    headers = {
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }
    deadline = time.monotonic() + max(1, int(timeout))
    soft_5xx = 0
    while time.monotonic() < deadline:
        wait_s = max(1, min(300, int(deadline - time.monotonic())))
        req = urllib.request.Request(
            f"{base}/images/generations",
            data=body,
            method="POST",
            headers=headers,
        )
        try:
            with urllib.request.urlopen(req, timeout=wait_s) as resp:
                data = json.loads(resp.read().decode() or "{}")
        except urllib.error.HTTPError as e:
            code = int(getattr(e, "code", 0) or 0)
            err_body = ""
            try:
                err_body = (e.read() or b"").decode("utf-8", "replace")[:400]
            except Exception:
                err_body = ""
            detail = f"HTTPError {code}"
            if err_body:
                detail = f"{detail} body={err_body!r}"
            log.warning("omni generate failed model=%r: %s", model, detail)
            # Combo alias with no image targets (400) → next member immediately.
            if code == 400:
                return None
            # Provider 5xx: brief retry then failover to next combo member (do not
            # burn the full OMNI_IMAGE_GEN_TIMEOUT_S on one stuck upstream).
            if code >= 500 and soft_5xx < 2 and time.monotonic() < deadline:
                soft_5xx += 1
                time.sleep(min(8.0, max(0.0, deadline - time.monotonic())))
                continue
            return None
        except Exception as e:  # noqa: BLE001
            detail = type(e).__name__
            log.warning("omni generate failed model=%r: %s", model, detail)
            return None
        items = data if isinstance(data, list) else (data.get("data") or data.get("images") or [])
        if not items or not isinstance(items[0], dict):
            log.warning("omni generate: empty response model=%r", model)
            return None
        blob = _omni_decode_image_blob(items[0])
        if not blob:
            log.warning("omni generate: empty image payload model=%r", model)
            return None
        if not _omni_image_quality_ok(blob, size=size):
            return None
        return blob
    log.warning("omni generate: budget exhausted model=%r timeout=%ss", model, timeout)
    return None


def _media_out_candidates() -> list:
    """Writable media/out dirs — shared SoT first (matches Zalo autosend scan)."""
    import os
    from pathlib import Path

    out: list = []
    seen: set[str] = set()

    def _add(path: str) -> None:
        p = (path or "").strip()
        if not p:
            return
        key = str(Path(p))
        if key in seen:
            return
        seen.add(key)
        out.append(Path(p))

    shared = (
        os.getenv("HERMES_SHARED_DATA")
        or os.getenv("HERMES_DATA_DIR")
        or os.getenv("ASSISTANT_DATA_DIR")
        or "/opt/data"
    ).strip()
    _add(str(Path(shared) / "media" / "out"))
    home = (os.getenv("HERMES_HOME") or "").strip()
    if home:
        _add(str(Path(home) / "media" / "out"))
    extra = (os.getenv("MEDIA_OUT_DIR") or "").strip()
    if extra:
        _add(extra)
    _add("/opt/data/media/out")
    _add("/data/assistant/media/out")
    return out


def _omni_generate_still(
    prompt: str,
    *,
    filename: str,
) -> dict[str, Any] | None:
    """Scenic diffusion via OmniRoute combo image-gen (not dispatcher /v1/image)."""
    try:
        from .omni_env import resolve_media_router_api_key, resolve_media_router_base_url
    except ImportError:
        from omni_env import resolve_media_router_api_key, resolve_media_router_base_url  # type: ignore

    base = resolve_media_router_base_url()
    key = resolve_media_router_api_key()
    if not key:
        log.warning("omni generate: missing OMNIROUTER_API_KEY")
        return None
    scene = (prompt or "").strip()
    size = _omni_image_gen_size()
    timeout = _omni_image_gen_timeout_s()
    model = _omni_image_gen_model()
    if not model:
        log.warning("omni generate: no IMAGE_GEN_COMBO")
        return None
    combo_members = _omni_v1_combo_member_models(base, key, model) if "/" not in model else []
    blob = _omni_request_image_blob(
        base=base,
        key=key,
        model=model,
        scene=scene,
        size=size,
        timeout=timeout,
        combo_members=combo_members,
    )
    if blob:
        for cand in _media_out_candidates():
            try:
                cand.mkdir(parents=True, exist_ok=True)
                dest = cand / filename
                dest.write_bytes(blob)
                return {
                    "ok": True,
                    "file": str(dest),
                    "path": str(dest),
                    "provider": model,
                    "model": model,
                }
            except OSError:
                continue
    return None


def _multipart_image_edit_body(
    *, source: Path, prompt: str, model: str, boundary: str
) -> bytes:
    """Build one standards-compliant multipart image-edit request body."""
    chunks: list[bytes] = []
    for name, value in (("model", model), ("prompt", prompt)):
        chunks.extend(
            [
                f"--{boundary}\r\n".encode(),
                f'Content-Disposition: form-data; name="{name}"\r\n\r\n'.encode(),
                str(value).encode("utf-8"),
                b"\r\n",
            ]
        )
    mime = mimetypes.guess_type(source.name)[0] or "application/octet-stream"
    chunks.extend(
        [
            f"--{boundary}\r\n".encode(),
            (
                'Content-Disposition: form-data; name="image"; '
                f'filename="{source.name}"\r\n'
            ).encode("utf-8"),
            f"Content-Type: {mime}\r\n\r\n".encode(),
            source.read_bytes(),
            b"\r\n",
            f"--{boundary}--\r\n".encode(),
        ]
    )
    return b"".join(chunks)


def run_image_edit(
    instruction: str,
    source_path: str,
    thread_id: str = "",
    thread_type: str = "user",
    *,
    classified: bool = False,
) -> Optional[dict]:
    """Edit one classifier-owned local image through the image-edit combo."""
    del thread_type
    if not classified:
        return None
    source = Path(str(source_path or "").strip())
    prompt = str(instruction or "").strip()
    if not prompt or not source.is_file():
        return shortcut_consumed()
    try:
        from .omni_env import resolve_env_var, resolve_media_router_api_key, resolve_media_router_base_url
    except ImportError:
        from omni_env import (  # type: ignore
            resolve_env_var,
            resolve_media_router_api_key,
            resolve_media_router_base_url,
        )
    key = resolve_media_router_api_key()
    if not key:
        log.warning("omni image edit: missing OMNIROUTER_API_KEY")
        return shortcut_consumed()
    model = (resolve_env_var("IMAGE_EDIT_COMBO", "image-edit") or "image-edit").strip()
    base = resolve_media_router_base_url().rstrip("/")
    import uuid

    boundary = "hermes-" + uuid.uuid4().hex
    body = _multipart_image_edit_body(
        source=source, prompt=prompt, model=model, boundary=boundary
    )
    req = urllib.request.Request(
        f"{base}/images/edits",
        data=body,
        method="POST",
        headers={
            "Authorization": f"Bearer {key}",
            "Content-Type": f"multipart/form-data; boundary={boundary}",
            "Accept": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=_omni_image_gen_timeout_s()) as resp:
            data = json.loads(resp.read().decode("utf-8") or "{}")
    except Exception as exc:  # noqa: BLE001
        log.warning("omni image edit failed: %s", type(exc).__name__)
        return shortcut_consumed()
    items = data if isinstance(data, list) else (data.get("data") or data.get("images") or [])
    if not items or not isinstance(items[0], dict):
        return shortcut_consumed()
    blob = _omni_decode_image_blob(items[0])
    if not blob:
        return shortcut_consumed()
    suffix = ".png"
    if blob.startswith(b"\xff\xd8\xff"):
        suffix = ".jpg"
    elif blob.startswith(b"RIFF") and blob[8:12] == b"WEBP":
        suffix = ".webp"
    filename = f"image-edit-{str(thread_id)[-8:] or 'zalo'}-{uuid.uuid4().hex[:8]}{suffix}"
    for directory in _media_out_candidates():
        try:
            directory.mkdir(parents=True, exist_ok=True)
            dest = directory / filename
            dest.write_bytes(blob)
            return {"ok": True, "file": str(dest), "path": str(dest), "model": model}
        except OSError:
            continue
    return shortcut_consumed()


def run_video_policy_refuse(
    user_ask: str,
    plan: dict[str, Any],
    thread_id: str,
    thread_type: str = "user",
    *,
    classified: bool = False,
) -> Optional[dict]:
    """Host owns video/music/URL-transcript refuse — never scenic image-gen."""
    del thread_id, thread_type
    if not classified:
        return None
    try:
        from .classify_client import plan_is_media_policy_refuse
    except ImportError:
        from classify_client import plan_is_media_policy_refuse  # type: ignore
    if not plan_is_media_policy_refuse(plan):
        return None
    # Topic from classify contract fields only — not user-phrase NLU.
    action = str((plan or {}).get("skill_action") or "").strip().lower()
    topic = str((plan or {}).get("refuse_topic") or "").strip().lower()
    if not topic:
        if "music" in action:
            topic = "music_generate"
        elif "audio" in action:
            topic = "audio_generate"
        elif "summary" in action or "social" in action:
            topic = "social_summary"
        elif "transcript" in action:
            topic = "transcript"
        else:
            topic = "transcript"
    ask = (user_ask or "").strip()
    try:
        out = _post(
            "/v1/video-policy-refuse",
            {"topic": topic, "context": ask[:2000], "language": "vi"},
            timeout=45.0,
        )
    except Exception as e:  # noqa: BLE001
        log.warning("video-policy-refuse failed: %s", type(e).__name__)
        return shortcut_consumed()
    msg = ""
    if isinstance(out, dict):
        msg = str(out.get("message") or out.get("text") or "").strip()
    if not msg:
        msg = (
            "This stack does not download or transcribe video/music links. "
            "Use the native app, or ask for a still image / office file instead."
        )
    return {"ok": True, "kind": "text_refuse", "text": msg}


def run_scene_image(
    user_ask: str,
    plan: dict[str, Any],
    thread_id: str,
    thread_type: str = "user",
    *,
    classified: bool = False,
) -> Optional[dict]:
    """Host scenic diffusion — no search sibling, no Hermes shell curl|python."""
    del thread_type
    if not classified:
        return None
    try:
        from .classify_client import plan_image_instruction, plan_is_media_policy_refuse
    except ImportError:
        from classify_client import (  # type: ignore
            plan_image_instruction,
            plan_is_media_policy_refuse,
        )
    if plan_is_media_policy_refuse(plan):
        return run_video_policy_refuse(
            user_ask, plan, thread_id, thread_type="user", classified=True
        )
    img_ins = plan_image_instruction(plan, user_ask)
    scene = scene_prompt_from_instruction(img_ins)
    if not scene:
        for ins in plan.get("instructions") or []:
            scene = scene_prompt_from_instruction(str(ins))
            if scene:
                break
    if not scene:
        return shortcut_consumed()
    prompt = _scene_visual_prompt(scene)
    # Unique per turn — avoid concurrent scenic jobs overwriting the same path.
    import uuid

    fname = f"scene-{str(thread_id)[-8:] or 'zalo'}-{uuid.uuid4().hex[:8]}.webp"
    out = _omni_generate_still(prompt, filename=fname)
    if isinstance(out, dict) and out.get("ok"):
        return out
    return shortcut_consumed()


def run_search_then_composed_image(
    user_ask: str,
    plan: dict[str, Any],
    thread_id: str,
    thread_type: str = "user",
    *,
    classified: bool = False,
) -> Optional[dict]:
    """Search, generate a scene, then render the model-authored information design."""
    del thread_type
    if not classified:
        return None
    try:
        from .classify_client import plan_image_instruction, plan_search_queries
    except ImportError:
        from classify_client import plan_image_instruction, plan_search_queries  # type: ignore
    queries = plan_search_queries(plan, user_ask)
    img_ins = plan_image_instruction(plan, user_ask)
    planned_queries = _evidence_queries(user_ask, img_ins)
    if planned_queries:
        queries = planned_queries
    log.info(
        "composed image evidence plan queries=%s classifier_queries=%s",
        len(queries),
        len(plan_search_queries(plan, user_ask)),
    )
    query = queries[0] if queries else user_ask
    searches: list[dict[str, Any]] = []
    for search_query in queries or [user_ask]:
        result = run_web_search(search_query)
        if not result:
            result = run_web_search(search_query)
        if isinstance(result, dict):
            result = dict(result)
            result["_request_query"] = search_query
            searches.append(result)
        else:
            log.warning("composed image evidence unavailable query_index=%s", len(searches))
            return shortcut_consumed()
    search: Any = searches
    scene = scene_prompt_from_instruction(img_ins)
    if not scene:
        return shortcut_consumed()
    composition = _synthesize_composition_plan(
        search,
        query=user_ask,
        instruction=img_ins or user_ask,
    )
    if not composition:
        return shortcut_consumed()
    panels = composition.get("panels") if isinstance(composition.get("panels"), list) else []
    design = composition.get("design") if isinstance(composition.get("design"), dict) else {}
    log.info(
        "composed image layout request=%s panels=%s facts=%s placement=%s panel_placements=%s",
        hashlib.sha256(user_ask.encode("utf-8")).hexdigest()[:12],
        len(panels),
        len(composition.get("facts") or []),
        str(design.get("placement") or "auto"),
        ",".join(
            str((panel.get("design") or {}).get("placement") or "auto")
            for panel in panels
            if isinstance(panel, dict)
        )
        or "none",
    )
    # Grounded composition owns both the exact visible copy and the full-scene
    # design. Generate one coherent bitmap; do not resize or paint host panels.
    visual_scene = str(composition.get("background_scene") or "").strip() or scene
    prompt = _composition_image_prompt(visual_scene, composition)
    if not prompt:
        return shortcut_consumed()
    import uuid

    fname = f"composed-image-{str(thread_id)[-8:] or 'zalo'}-{uuid.uuid4().hex[:8]}.jpg"
    out = _omni_generate_still(
        prompt,
        filename=fname,
    )
    if isinstance(out, dict) and out.get("ok"):
        out["composition"] = "model-rendered"
        log.info("composed image rendered mode=model full_bleed=true")
        return out
    return shortcut_consumed()


def run_text_poster(
    text: str,
    thread_id: str = "",
    thread_type: str = "user",
    *,
    classified: bool = False,
    poster_n: int | None = None,
    poster_phrase: str = "",
    poster_bw: bool | None = None,
) -> Optional[dict]:
    """POST /v1/text-poster. Caller must already have a media_generation plan."""
    del thread_id, thread_type
    if not classified:
        return None
    prompt = (text or "").strip()
    if not prompt:
        return None
    body: dict[str, Any] = {
        "prompt": prompt,
        "filename": "poster.png",
        "refine": False,
        "mode": "text-poster",
    }
    if poster_phrase:
        body["poster_phrase"] = poster_phrase
    if poster_n is not None:
        body["poster_n"] = poster_n
    if poster_bw is not None:
        body["poster_bw"] = poster_bw
    try:
        out = _post("/v1/text-poster", body, timeout=60.0)
    except Exception as e:  # noqa: BLE001
        log.warning("text-poster shortcut failed: %s", type(e).__name__)
        return shortcut_consumed()
    if isinstance(out, dict) and out.get("ok"):
        return out
    return shortcut_consumed()
