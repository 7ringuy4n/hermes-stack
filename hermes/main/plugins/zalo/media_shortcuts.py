# -*- coding: utf-8 -*-
"""Dispatcher HTTP for classified office-file jobs (and search→office).

Intent lives in classify JSON. This module does not phrase-scan user prose.
The adapter calls run_office_create when plan_allows_office_shortcut is true,
or run_search_then_office when plan_allows_search_then_office is true.
"""
from __future__ import annotations

import base64
import json
import logging
import os
import time
import urllib.error
import urllib.request
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional
from zoneinfo import ZoneInfo

log = logging.getLogger("hermes_plugins.zalo_platform.media_shortcuts")

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


def model_router_url() -> str:
    return (os.getenv("ROUTER_WORKER_URL") or os.getenv("MODEL_ROUTER_URL") or "http://router-worker:8096").rstrip("/")


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
    """POST model-router /v1/search. Returns payload or None."""
    q = (query or "").strip()
    if not q:
        return None
    try:
        out = _post(
            "/v1/search",
            {"query": q, "max_results": max(1, min(int(max_results), 8))},
            timeout=45.0,
            base=model_router_url(),
        )
    except Exception as e:  # noqa: BLE001
        log.warning("search_then_office search failed: %s", type(e).__name__)
        return None
    if isinstance(out, dict) and (out.get("results") or out.get("answer") is not None):
        return out
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


def _search_notes_blob(search: dict[str, Any] | None, *, limit: int = 4) -> str:
    """Concat result content fields for LLM synthesis (not titles; not host NLU)."""
    if not isinstance(search, dict):
        return ""
    chunks: list[str] = []
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
    return "\n---\n".join(chunks)[:2400]


def _parse_label_value_lines(text: str) -> list[str]:
    """Keep short Label: value lines from model output (structural colon split only)."""
    out: list[str] = []
    seen: set[str] = set()
    for raw in (text or "").replace("\r", "\n").split("\n"):
        line = _clean_fact_line(raw)
        if not line or _skip_structural_junk(line):
            continue
        if ":" not in line:
            continue
        left, right = line.split(":", 1)
        if not left.strip() or not right.strip():
            continue
        if len(line) > 72:
            line = line[:72].rstrip()
        key = line.lower()
        if key in seen:
            continue
        seen.add(key)
        out.append(line)
        if len(out) >= 4:
            break
    return out


def _synthesize_overlay_facts(
    search: dict[str, Any] | None,
    *,
    query: str = "",
) -> list[str]:
    """When search has no structured answer, ask chat combo for Label: value overlay lines."""
    notes = _search_notes_blob(search)
    if not notes.strip():
        return []
    try:
        from .omni_env import resolve_omni_api_key, resolve_omni_base_url
    except ImportError:
        from omni_env import resolve_omni_api_key, resolve_omni_base_url  # type: ignore

    base = resolve_omni_base_url()
    key = resolve_omni_api_key()
    if not base or not key:
        return []
    model = (
        os.getenv("OMNIROUTER_DEFAULT_COMBO")
        or os.getenv("HERMES_CHAT_COMBO")
        or "hermes"
    ).strip() or "hermes"
    q = (query or "").strip()[:120]
    system = (
        "You extract live facts for a small image overlay from the user query and notes. "
        "Reply with 3 or 4 lines only. Each line MUST be Label: value. "
        "Use concise English labels unless the query explicitly requests another overlay "
        "language. Choose labels that match the query topic (weather, scores, prices, "
        "rates, or other metrics — do not force a fixed weather-only schema). "
        "Values must come from the notes. Never invent. Never placeholders. "
        "No markdown, no bullets, no SCENE, no policy tokens, no extra prose."
    )
    user = f"Query: {q or 'live facts'}\nNotes:\n{notes}"
    body = json.dumps(
        {
            "model": model,
            "stream": False,
            "temperature": 0,
            "max_tokens": 180,
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
        with urllib.request.urlopen(req, timeout=35) as resp:
            data = json.loads(resp.read().decode("utf-8") or "{}")
    except Exception as e:  # noqa: BLE001
        log.warning("overlay fact synthesize failed: %s", type(e).__name__)
        return []
    text = ""
    try:
        choices = data.get("choices") if isinstance(data, dict) else None
        if isinstance(choices, list) and choices:
            msg = (choices[0] or {}).get("message") if isinstance(choices[0], dict) else {}
            if isinstance(msg, dict):
                text = str(msg.get("content") or "").strip()
    except Exception:
        text = ""
    lines = _parse_label_value_lines(text)
    if not lines:
        log.warning("overlay fact synthesize empty model=%r", model)
    return lines


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
    search = run_web_search(query or user_ask)
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


def _strip_diffusion_policy_tokens(scene: str) -> str:
    """Remove policy tokens that must never become readable on-image text."""
    s = (scene or "").strip()
    if not s:
        return ""
    for token in (
        "SAFE-FOR-WORK",
        "safe-for-work",
        "Safe-for-work",
        "safe for work",
        "Safe for work",
    ):
        s = s.replace(token, " ")
    parts = [p for p in s.replace(";", ",").split(",") if p.strip()]
    cleaned: list[str] = []
    for part in parts:
        bit = " ".join(part.split())
        if not bit:
            continue
        low = bit.lower()
        if "safe" in low and "work" in low:
            continue
        cleaned.append(bit)
    return ", ".join(cleaned) if cleaned else " ".join(s.split())


def scene_prompt_from_instruction(text: str) -> str:
    """English diffusion scene from classify SCENE: marker (not user NLU)."""
    for raw in (text or "").splitlines():
        line = raw.strip()
        if line.upper().startswith("SCENE:"):
            return _strip_diffusion_policy_tokens(line.split(":", 1)[1].strip())
    src = (text or "").strip()
    up = src.upper()
    if src and "TITLE:" not in up and "RENDER:" not in up:
        return _strip_diffusion_policy_tokens(src)
    return ""


def overlay_heading_from_instruction(text: str) -> str:
    """Read the classifier-owned overlay heading marker without interpreting user prose."""
    for raw in (text or "").splitlines():
        line = raw.strip()
        if line.upper().startswith("OVERLAY_HEADING:"):
            heading = " ".join(line.split(":", 1)[1].split())
            return heading[:48]
    return ""


def _overlay_header(user_ask: str = "", heading: str = "") -> str:
    """Use the classifier heading; compact literal asks remain a compatibility fallback."""
    clean_heading = " ".join((heading or "").split())
    if clean_heading:
        return clean_heading[:48]
    ask = " ".join((user_ask or "").split())
    if not ask:
        return "Facts"
    if len(ask) <= 28:
        return ask
    return "Facts"


def _live_overlay_lines(
    facts: list[str], *, scene: str = "", user_ask: str = "", heading: str = ""
) -> list[str]:
    """Compact lines for Pillow overlay — facts from classify/search only."""
    del scene
    header = _overlay_header(user_ask=user_ask, heading=heading)
    tz_name = (os.getenv("ASSISTANT_TZ") or os.getenv("TZ") or "Asia/Ho_Chi_Minh").strip()
    try:
        now = datetime.now(ZoneInfo(tz_name)).strftime("%H:%M · %d/%m/%Y")
    except Exception:  # noqa: BLE001
        now = datetime.now(ZoneInfo("Asia/Ho_Chi_Minh")).strftime("%H:%M · %d/%m/%Y")
    lines = [header or "Facts"]
    for raw in facts or []:
        s = str(raw or "").strip()
        if not s or _skip_structural_junk(s):
            continue
        low = s.lower()
        if "unavailable" in low or "details unavailable" in low:
            continue
        lines.append(s[:72])
        if len(lines) >= 5:
            break
    lines.append(f"Updated: {now}")
    return lines[:6]


def _apply_live_overlay(out: dict[str, Any], lines: list[str]) -> dict[str, Any]:
    """Post-process scenic still with Unicode-safe bottom-left badge."""
    if not lines:
        return out
    path = str(out.get("path") or out.get("file") or "")
    name = Path(path).name if path else ""
    if not name:
        return out
    try:
        _post(
            "/v1/overlay",
            {
                "filename": name,
                "overlay": lines,
                "overlay_corner": "bottom-left",
                "prompt": "",
            },
            timeout=45.0,
        )
        out["overlay"] = len(lines)
    except Exception as e:  # noqa: BLE001
        log.warning("live overlay failed: %s", type(e).__name__)
    return out


# Compat aliases (weather was the first live-facts topic).
_weather_overlay_lines = _live_overlay_lines
_apply_weather_overlay = _apply_live_overlay


def _photoreal_scene_prompt(prompt: str) -> str:
    """Ensure diffusion prompts ask for real photos, not cartoon/anime styles."""
    p = (prompt or "").strip()
    low = p.lower()
    extras = [
        "photorealistic photograph",
        "real camera photo",
        "natural lighting",
        "highly detailed",
        "not cartoon",
        "not anime",
        "not illustration",
        "not stylized 3d render",
    ]
    missing = [x for x in extras if x not in low]
    if not missing:
        return p
    if not p:
        return ", ".join(extras)
    return f"{p}, " + ", ".join(missing)


def _live_scene_visual_prompt(scene: str, facts: list[str]) -> str:
    """Live-facts scenic diffusion — SCENE from classify; facts as atmospheric reference only."""
    base = _photoreal_scene_prompt(_strip_diffusion_policy_tokens(scene or ""))
    clean = [
        str(f).strip()
        for f in (facts or [])
        if str(f).strip() and not _skip_structural_junk(str(f))
    ]
    extra = ""
    if clean:
        extra = (
            " Reflect live conditions through environment and atmosphere: "
            + "; ".join(clean[:4])
            + "."
        )
    return (
        f"{base}{extra} "
        "Express live conditions only through sky, lighting, environment, and atmosphere. "
        "No readable text, no letters, no signs, no captions, no watermarks, no labels in the image. "
        "No close-up people, not cartoon, not anime, not illustration"
    )


_weather_scene_visual_prompt = _live_scene_visual_prompt


def _labeled_scene_prompt(scene: str, facts: list[str]) -> str:
    """Scenic still for labeled asks — no burned-in text; facts go to /v1/overlay."""
    del facts
    base = _photoreal_scene_prompt(_strip_diffusion_policy_tokens(scene or ""))
    return (
        f"{base} "
        "No readable text, no letters, no signs, no captions, no watermarks, "
        "no labels, no information board in the image. "
        "No close-up people, not cartoon, not anime, not illustration"
    )


def _scene_prompt_with_facts(scene: str, facts: list[str]) -> str:
    """Scenic diffusion only — live facts are applied via Pillow overlay."""
    return _labeled_scene_prompt(scene, facts)


def _omni_image_gen_timeout_s() -> int:
    import os

    # Default 300s (5 minutes) per combo image-gen member; clamp 60..600.
    raw = (os.getenv("OMNI_IMAGE_GEN_TIMEOUT_S") or "300").strip()
    try:
        return max(60, min(int(raw), 600))
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
    combo = (model or "").strip()
    members = [m for m in (combo_members or []) if m and "/" in m]
    # Prefer concrete members so Omni UI shows Requested Model and so we bypass
    # broken combo-level "images-capable" gating.
    if members:
        candidates.extend(members)
    elif combo:
        candidates.append(combo)
    for candidate in candidates:
        if not candidate or candidate in tried:
            continue
        tried.append(candidate)
        blob = _omni_request_image_blob_once(
            base=base,
            key=key,
            model=candidate,
            scene=scene,
            size=size,
            timeout=timeout,
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
    deadline = time.monotonic() + max(60, int(timeout))
    soft_5xx = 0
    while time.monotonic() < deadline:
        wait_s = max(5, min(90, int(deadline - time.monotonic())))
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


def _omni_generate_still(prompt: str, *, filename: str) -> dict[str, Any] | None:
    """Scenic diffusion via OmniRouter combo image-gen (not dispatcher /v1/image)."""
    try:
        from .omni_env import resolve_omni_api_key, resolve_omni_base_url
    except ImportError:
        from omni_env import resolve_omni_api_key, resolve_omni_base_url  # type: ignore

    base = resolve_omni_base_url()
    key = resolve_omni_api_key()
    if not key:
        log.warning("omni generate: missing OMNIROUTER_API_KEY")
        return None
    scene = _photoreal_scene_prompt(prompt or "")
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
    skill = str((plan or {}).get("skill") or "").strip().lower()
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
        elif skill in {"video_gen", "video-gen"}:
            topic = "video_generate"
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
        scene = (
            "Photorealistic photograph of a cityscape with visible sky and urban skyline, "
            "real camera photo, natural lighting, wide view, not cartoon, not anime"
        )
    prompt = _photoreal_scene_prompt(scene)
    # Unique per turn — avoid concurrent scenic jobs overwriting the same path.
    import uuid

    fname = f"scene-{str(thread_id)[-8:] or 'zalo'}-{uuid.uuid4().hex[:8]}.webp"
    out = _omni_generate_still(prompt, filename=fname)
    if isinstance(out, dict) and out.get("ok"):
        return out
    return shortcut_consumed()


def run_search_then_live_scene(
    user_ask: str,
    plan: dict[str, Any],
    thread_id: str,
    thread_type: str = "user",
    *,
    classified: bool = False,
) -> Optional[dict]:
    """Host search → Omni scenic image-gen → Pillow /v1/overlay with live facts (any topic)."""
    del thread_type
    if not classified:
        return None
    try:
        from .classify_client import plan_image_instruction, plan_search_query
    except ImportError:
        from classify_client import (  # type: ignore
            plan_image_instruction,
            plan_search_query,
        )
    query = plan_search_query(plan, user_ask)
    img_ins = plan_image_instruction(plan, user_ask)
    search = run_web_search(query or user_ask)
    scene = scene_prompt_from_instruction(img_ins)
    if not scene:
        scene = (
            "Photorealistic photograph of a cityscape with visible sky and urban skyline, "
            "real camera photo, natural lighting, wide view, not cartoon, not anime"
        )
    facts = _collect_host_facts(img_ins or "", search)
    if not facts:
        facts = _synthesize_overlay_facts(search, query=query or user_ask)
    prompt = _live_scene_visual_prompt(scene, facts)
    import uuid

    fname = f"live-scene-{str(thread_id)[-8:] or 'zalo'}-{uuid.uuid4().hex[:8]}.jpg"
    out = _omni_generate_still(prompt, filename=fname)
    if isinstance(out, dict) and out.get("ok"):
        overlay = _live_overlay_lines(
            facts,
            scene=scene,
            user_ask=user_ask,
            heading=overlay_heading_from_instruction(img_ins),
        )
        return _apply_live_overlay(out, overlay)
    return shortcut_consumed()


# Compat: weather was the first live-facts topic.
run_search_then_weather_scene = run_search_then_live_scene


def run_search_then_info_card(
    user_ask: str,
    plan: dict[str, Any],
    thread_id: str,
    thread_type: str = "user",
    *,
    classified: bool = False,
) -> Optional[dict]:
    """Host search → scenic still (no diffusion text) → bottom-left Pillow overlay."""
    del thread_type
    if not classified:
        return None
    try:
        from .classify_client import plan_image_instruction, plan_search_query
    except ImportError:
        from classify_client import (  # type: ignore
            plan_image_instruction,
            plan_search_query,
        )
    query = plan_search_query(plan, user_ask)
    img_ins = plan_image_instruction(plan, user_ask)
    search = run_web_search(query or user_ask)
    scene = scene_prompt_from_instruction(img_ins) or (
        "Photorealistic photograph of a city plaza with visible sky, "
        "real camera photo, natural light, not cartoon"
    )
    facts = _collect_host_facts(img_ins or "", search)
    if not facts:
        facts = _search_answer_lines(search, limit=4)
    if not facts:
        facts = _synthesize_overlay_facts(search, query=query or user_ask)
    prompt = _scene_prompt_with_facts(scene, facts)
    import uuid

    fname = f"info-scene-{str(thread_id)[-8:] or 'zalo'}-{uuid.uuid4().hex[:8]}.jpg"
    out = _omni_generate_still(prompt, filename=fname)
    if isinstance(out, dict) and out.get("ok"):
        overlay = _live_overlay_lines(
            facts,
            scene=scene,
            user_ask=user_ask,
            heading=overlay_heading_from_instruction(img_ins),
        )
        return _apply_live_overlay(out, overlay)
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
