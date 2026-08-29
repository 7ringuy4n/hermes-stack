# -*- coding: utf-8 -*-
"""Dispatcher HTTP for classified office-file jobs (and search→office).

Intent lives in classify JSON. This module does not phrase-scan user prose.
The adapter calls run_office_create when plan_allows_office_shortcut is true,
or run_search_then_office when plan_allows_search_then_office is true.
"""
from __future__ import annotations

import json
import logging
import os
import urllib.error
import urllib.request
from typing import Any, Dict, Optional

log = logging.getLogger("hermes_plugins.zalo_platform.media_shortcuts")

# Classify/Hermes contract markers (not user NLU).
_MARKERS = ("TITLE:", "SUBTITLE:", "ICON:", "STYLE:", "OVERVIEW:", "BACKGROUND:")


def dispatcher_url() -> str:
    return (os.getenv("DISPATCHER_URL") or "http://dispatcher:8090").rstrip("/")


def model_router_url() -> str:
    return (os.getenv("MODEL_ROUTER_URL") or "http://model-router:8096").rstrip("/")


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


def extract_contract_markers(text: str) -> dict[str, str]:
    """Pull TITLE/SUBTITLE/ICON/STYLE/OVERVIEW/BACKGROUND from classify contract text.

    Markers may sit mid-line after a create-verb wrapper. Values run until the
    next marker or end of string. Not user-prose NLU.
    """
    src = (text or "").replace("\r", "\n")
    upper = src.upper()
    # Longer keys first so SUBTITLE: is not mistaken for TITLE:
    ordered = ("BACKGROUND:", "OVERVIEW:", "SUBTITLE:", "STYLE:", "TITLE:", "ICON:")
    hits: list[tuple[int, str]] = []
    claimed: set[int] = set()
    for m in ordered:
        start = 0
        while True:
            i = upper.find(m, start)
            if i < 0:
                break
            start = i + 1
            # Skip mid-token (e.g. TITLE: inside SUBTITLE:)
            if i > 0 and upper[i - 1].isalnum():
                continue
            if any(i <= c < i + len(m) for c in claimed):
                continue
            for j in range(i, i + len(m)):
                claimed.add(j)
            hits.append((i, m))
    hits.sort(key=lambda x: x[0])
    out: dict[str, str] = {}
    for idx, (pos, key) in enumerate(hits):
        val_start = pos + len(key)
        val_end = hits[idx + 1][0] if idx + 1 < len(hits) else len(src)
        val = src[val_start:val_end].strip().strip(" .;—-|")
        if "\n" in val:
            val = val.split("\n", 1)[0].strip()
        if key == "TITLE:" and len(val) > 80:
            val = val[:80].rstrip()
        if key in {"OVERVIEW:", "BACKGROUND:"} and len(val) > 160:
            val = val[:160].rstrip()
        if key == "ICON:":
            val = val.split()[0].lower() if val else "cloud"
            if "|" in val:
                val = val.split("|", 1)[0].strip() or "cloud"
        out[key[:-1].lower()] = val
    return out


def _is_serp_noise(text: str) -> bool:
    """Drop SEO / JSON / markdown / wire junk. String checks only (no intent regex)."""
    s = (text or "").strip()
    if not s or len(s) < 3:
        return True
    low = s.lower()
    # Raw JSON / Python-dict dumps must never appear on the card
    if s.startswith(("{", "[", "'{", '"{')):
        return True
    if "{'" in s or '{"' in s or "': {" in s or '": {' in s:
        return True
    if any(
        k in low
        for k in (
            "'location'",
            '"location"',
            "'tz_id'",
            '"tz_id"',
            "'lat'",
            '"lon"',
            "weather parameters",
        )
    ):
        return True
    if low.startswith("http://") or low.startswith("https://"):
        return True
    if s.startswith("#") or low.startswith("title:"):
        return True
    if " | " in s:
        return True
    # Label-only rows with no value
    if ":" not in s and low in {
        "direction",
        "wind speed",
        "gust speed",
        "gust spee",
        "temperature",
        "precipitation",
        "humidity",
        "nhiệt độ",
        "độ ẩm",
        "áp suất",
        "ngày/đêm",
        "sáng/tối",
        "pressure",
        "dawn",
        "mặt",
    }:
        return True
    # Truncated / chrome leftovers
    if low.endswith(" image") or low.endswith(" spee") or low.endswith(" temp"):
        return True
    noise_bits = (
        "dubaothoitiet",
        "accuweather",
        "weather.com",
        "xem dự báo thời tiết tỉnh",
        "dự báo thời tiết hôm nay, ngày m",
        "cập nhật lần cuối",
        "gust speed image",
        "feels like temperature",
    )
    for bit in noise_bits:
        if bit in low:
            # Allow "Nhiệt độ: 31" / "Feels like: 36°C"
            if ":" in s and not low.startswith(bit):
                continue
            return True
    if s in {"Ngày/đêm", "Nhiệt độ", "Sáng/tối", "Áp suất", "Mặt", "pressure", "dawn"}:
        return True
    return False


def _looks_like_wind_bearing(token: str) -> bool:
    """246°WSW / 90°N — compass after degree, not Celsius."""
    t = (token or "").strip()
    if "°" not in t and "º" not in t:
        return False
    sep = "°" if "°" in t else "º"
    after = t.split(sep, 1)[1].upper()
    if not after:
        return False
    if after.startswith("C") or after.startswith("F"):
        return False
    return after[0].isalpha()


def _clean_fact_line(text: str) -> str:
    s = (text or "").strip()
    if s.startswith(("- ", "• ", "* ")):
        s = s[2:].strip()
    # Strip markdown heading markers
    while s.startswith("#"):
        s = s.lstrip("#").strip()
    # Prefer right-hand side when SERP glued "Page Title: actual fact"
    if ": " in s and " | " not in s:
        left, right = s.split(": ", 1)
        if len(left) > 48 and len(right) >= 8:
            s = right.strip()
    return s[:140]


# Known weather API / Open-Meteo / WeatherAPI field → display label (data map, not NLU).
_WEATHER_KEY_LABELS: dict[str, str] = {
    "temp_c": "Nhiệt độ",
    "temp_f": "Nhiệt độ (°F)",
    "temperature": "Nhiệt độ",
    "temperature_2m": "Nhiệt độ",
    "feelslike_c": "Cảm giác như",
    "feelslike_f": "Cảm giác như (°F)",
    "apparent_temperature": "Cảm giác như",
    "humidity": "Độ ẩm",
    "relativehumidity_2m": "Độ ẩm",
    "relative_humidity": "Độ ẩm",
    "wind_kph": "Gió",
    "wind_mph": "Gió (mph)",
    "windspeed_10m": "Gió",
    "wind_speed": "Gió",
    "wind_degree": "Hướng gió",
    "wind_dir": "Hướng gió",
    "precip_mm": "Mưa",
    "precipitation": "Mưa",
    "uv": "Chỉ số UV",
    "cloud": "Mây",
    "cloudcover": "Mây",
    "pressure_mb": "Áp suất",
    "vis_km": "Tầm nhìn",
    "condition": "Tình trạng",
    "text": "Tình trạng",
    "weathercode": "Mã thời tiết",
}


def _facts_from_weather_obj(obj: Any, *, prefix: str = "") -> list[str]:
    """Flatten known weather keys from a parsed JSON/dict into label: value lines."""
    out: list[str] = []
    if isinstance(obj, list):
        for item in obj[:5]:
            out.extend(_facts_from_weather_obj(item, prefix=prefix))
        return out
    if not isinstance(obj, dict):
        return out
    # Prefer nested current/now blocks first
    for nest in ("current", "now", "current_weather", "data"):
        nested = obj.get(nest)
        if isinstance(nested, dict):
            out.extend(_facts_from_weather_obj(nested, prefix=prefix))
    for key, val in obj.items():
        k = str(key or "").strip().lower()
        if k in {"location", "forecast", "alerts", "request", "astro"}:
            if k == "location" and isinstance(val, dict):
                name = val.get("name") or val.get("city")
                if name:
                    out.append(f"Địa điểm: {name}")
            continue
        if k == "condition" and isinstance(val, dict):
            text = val.get("text") or val.get("description")
            if text:
                out.append(f"Tình trạng: {text}")
            continue
        if isinstance(val, (dict, list)):
            out.extend(_facts_from_weather_obj(val, prefix=k))
            continue
        label = _WEATHER_KEY_LABELS.get(k)
        if not label:
            continue
        if val is None or val == "":
            continue
        unit = ""
        if k.endswith("_c") or k in {"temperature", "temperature_2m", "apparent_temperature"}:
            unit = "°C"
        elif k.endswith("_kph") or k in {"windspeed_10m", "wind_speed"}:
            unit = " km/h"
        elif k in {"humidity", "relativehumidity_2m", "relative_humidity", "cloud", "cloudcover"}:
            unit = "%"
        elif k.endswith("_mm") or k == "precipitation":
            unit = " mm"
        elif k == "uv":
            unit = ""
        out.append(f"{label}: {val}{unit}")
    return out


def _try_json_facts(raw: str) -> list[str]:
    """If blob is JSON (or close), return structured weather facts; else []."""
    s = (raw or "").strip()
    if not s:
        return []
    # Find a JSON object/array start
    start_obj = s.find("{")
    start_arr = s.find("[")
    starts = [i for i in (start_obj, start_arr) if i >= 0]
    if not starts:
        return []
    i = min(starts)
    blob = s[i:]
    try:
        data = json.loads(blob)
    except Exception:
        # Python-repr style single quotes — only attempt when it looks like a dict dump
        if "{'" in blob or "': " in blob:
            return []  # do not put raw dict on the card
        return []
    return _facts_from_weather_obj(data)


def _facts_from_search(search: dict[str, Any] | None) -> list[str]:
    facts: list[str] = []
    seen: set[str] = set()

    def add(raw: str) -> None:
        # Prefer structured JSON extraction over dumping the blob
        structured = _try_json_facts(raw)
        if structured:
            for line in structured:
                add_line(line)
            return
        add_line(raw)

    def add_line(raw: str) -> None:
        line = _clean_fact_line(raw)
        if _is_serp_noise(line):
            return
        if _looks_like_wind_bearing(line.split()[0] if line.split() else ""):
            # Bare bearing token as whole fact
            if ":" not in line and _looks_like_wind_bearing(line.replace(" ", "")):
                return
        key = line.lower()
        if key in seen:
            return
        seen.add(key)
        facts.append(line)

    if not isinstance(search, dict):
        return facts

    # Direct structured answer (dict) from search backends
    ans = search.get("answer")
    if isinstance(ans, (dict, list)):
        for line in _facts_from_weather_obj(ans):
            add_line(line)
        if len(facts) >= 6:
            return facts[:8]
    elif ans is not None and str(ans).strip():
        text = str(ans).strip()
        structured = _try_json_facts(text)
        if structured:
            for line in structured:
                add_line(line)
        else:
            for part in text.replace("\r", "\n").split("\n"):
                p = part.strip()
                if p:
                    add(p)
                if len(facts) >= 8:
                    return facts

    rows = search.get("results") if isinstance(search.get("results"), list) else []
    for row in rows:
        if not isinstance(row, dict):
            continue
        # Some backends put structured weather on the row itself
        for line in _facts_from_weather_obj(row):
            add_line(line)
        snip = str(
            row.get("content") or row.get("snippet") or row.get("body") or ""
        ).strip()
        title = str(row.get("title") or "").strip()
        if snip:
            add(snip)
        elif title and not _is_serp_noise(title):
            add(title)
        if len(facts) >= 8:
            break
    return facts[:8]


def _infer_icon(facts: list[str], fallback: str = "cloud") -> str:
    blob = " ".join(facts).lower()
    if any(w in blob for w in ("storm", "giông", "thunder", "sét")):
        return "storm"
    if any(w in blob for w in ("rain", "mưa", "mua", "shower", "drizzle")):
        return "rain"
    if any(w in blob for w in ("sun", "sunny", "clear", "nắng", "nang", "quang")):
        return "sun"
    if any(w in blob for w in ("cloud", "cloudy", "mây", "overcast", "nhiều mây")):
        return "cloud"
    return fallback or "cloud"


def _prose_snippets_from_search(search: dict[str, Any] | None, *, limit: int = 2) -> list[str]:
    """Short clean sentences from search answer/snippets for OVERVIEW/BACKGROUND."""
    if not isinstance(search, dict):
        return []
    chunks: list[str] = []
    ans = search.get("answer")
    if isinstance(ans, str) and ans.strip():
        chunks.append(ans.strip())
    for key in ("snippets", "results"):
        block = search.get(key)
        if isinstance(block, list):
            for item in block[:6]:
                if isinstance(item, str):
                    chunks.append(item)
                elif isinstance(item, dict):
                    for k in ("snippet", "content", "description", "text", "answer"):
                        v = item.get(k)
                        if isinstance(v, str) and v.strip():
                            chunks.append(v.strip())
                            break
    out: list[str] = []
    for chunk in chunks:
        # Split on sentence enders without regex NLU
        parts: list[str] = []
        buf = ""
        for ch in chunk.replace("\n", " "):
            buf += ch
            if ch in ".!?。" and len(buf.strip()) >= 24:
                parts.append(buf.strip())
                buf = ""
        if buf.strip():
            parts.append(buf.strip())
        for p in parts:
            line = _clean_fact_line(p)
            if not line or _is_serp_noise(line):
                continue
            if ":" in line and len(line.split(":", 1)[0]) <= 24:
                # Prefer label:value for facts, not overview
                continue
            if line not in out:
                out.append(line[:160])
            if len(out) >= limit:
                return out
    return out


def build_office_body_from_search(
    *,
    file_instruction: str,
    user_ask: str,
    search: dict[str, Any] | None,
) -> str:
    """Assemble clean TITLE/ICON/OVERVIEW/BACKGROUND/fact lines for styled office-file."""
    fi = (file_instruction or "").strip()
    ask = (user_ask or "").strip()
    markers = extract_contract_markers(fi) if fi else {}
    if not markers.get("title"):
        markers.update(extract_contract_markers(ask))

    title = (markers.get("title") or "").strip()
    # Reject create-verb wrappers mistakenly used as title
    low_t = title.lower()
    if (
        not title
        or low_t.startswith("tạo ")
        or low_t.startswith("tao ")
        or low_t.startswith("create ")
        or low_t.startswith("design ")
        or low_t.startswith("hãy ")
        or low_t.startswith("hay ")
        or "file pdf" in low_t
    ):
        title = ""
    if not title:
        title = "Cập nhật"

    subtitle = (markers.get("subtitle") or "").strip() or "Cập nhật trực tiếp"
    icon = (markers.get("icon") or "").strip().lower() or "cloud"
    overview = (markers.get("overview") or "").strip()
    background = (markers.get("background") or "").strip()
    style = (markers.get("style") or "").strip().lower()

    facts = _facts_from_search(search)
    # Keep classify-authored fact bullets (lines starting with -) if present
    for raw in fi.splitlines():
        s = raw.strip()
        if s.startswith(("- ", "• ", "* ")):
            line = _clean_fact_line(s)
            if line and not _is_serp_noise(line) and line not in facts:
                facts.append(line)

    if not facts:
        facts = ["Chưa lấy được chi tiết — thử lại sau."]

    # Place-oriented sheets: fill OVERVIEW/BACKGROUND from search prose when classify
    # opened those markers (or STYLE hints place context). No city-name dictionary.
    fi_u = fi.upper()
    wants_place_context = (
        bool(overview or background)
        or "OVERVIEW:" in fi_u
        or "BACKGROUND:" in fi_u
        or style in {"place", "city", "overview", "landmark", "region"}
    )
    if wants_place_context:
        prose = _prose_snippets_from_search(search, limit=2)
        if not overview and prose:
            overview = prose[0]
        if not background and len(prose) > 1:
            background = prose[1]

    icon = _infer_icon(facts, icon)

    lines = [
        f"TITLE: {title[:72]}",
        f"SUBTITLE: {subtitle[:80]}",
        f"ICON: {icon}",
    ]
    if overview:
        lines.append(f"OVERVIEW: {overview[:160]}")
    if background:
        lines.append(f"BACKGROUND: {background[:160]}")
    for f in facts[:10]:
        lines.append(f"- {f}")
    return "\n".join(lines)


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
        return None
    if isinstance(out, dict) and out.get("ok"):
        return out
    return None


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
    """POST /v1/image text-poster. Caller must already have a media_generation plan."""
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
        out = _post("/v1/image", body, timeout=60.0)
    except Exception as e:  # noqa: BLE001
        log.warning("text-poster shortcut failed: %s", type(e).__name__)
        return None
    if isinstance(out, dict) and out.get("ok"):
        return out
    return None
