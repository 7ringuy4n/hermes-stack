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
_MARKERS = ("TITLE:", "SUBTITLE:", "ICON:", "STYLE:")


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
    """Pull TITLE/SUBTITLE/ICON/STYLE from classify-authored contract text.

    Markers may sit mid-line after a create-verb wrapper. Values run until the
    next marker or end of string. Not user-prose NLU.
    """
    src = (text or "").replace("\r", "\n")
    upper = src.upper()
    # Longer keys first so SUBTITLE: is not mistaken for TITLE:
    ordered = ("SUBTITLE:", "STYLE:", "TITLE:", "ICON:")
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
        if key == "ICON:":
            val = val.split()[0].lower() if val else "cloud"
            if "|" in val:
                val = val.split("|", 1)[0].strip() or "cloud"
        out[key[:-1].lower()] = val
    return out


def _is_serp_noise(text: str) -> bool:
    """Drop SEO page titles / wire junk. String checks only (no intent regex)."""
    s = (text or "").strip()
    if not s or len(s) < 3:
        return True
    low = s.lower()
    if low.startswith("http://") or low.startswith("https://"):
        return True
    if s.startswith("#") or low.startswith("title:"):
        return True
    if " | " in s:
        return True
    # Generic SERP chrome
    noise_bits = (
        "dubaothoitiet",
        "accuweather",
        "weather.com",
        "xem dự báo thời tiết tỉnh",
        "dự báo thời tiết hôm nay, ngày m",
        "cập nhật lần cuối",
        "pressure",
        "dawn",
        "desiged document",
    )
    for bit in noise_bits:
        if bit in low and (":" not in s or low.startswith(bit)):
            # Allow "Nhiệt độ: 31" style; block bare site chrome
            if bit in {"pressure", "dawn"} and len(s) < 24:
                return True
            if bit not in {"pressure", "dawn"}:
                return True
    # Truncated one-word leftovers
    if s in {"Ngày/đêm", "Nhiệt độ", "Sáng/tối", "Áp suất", "Mặt", "pressure", "dawn"}:
        return True
    return False


def _clean_fact_line(text: str) -> str:
    s = (text or "").strip()
    if s.startswith(("- ", "• ", "* ")):
        s = s[2:].strip()
    # Prefer right-hand side when SERP glued "Page Title: actual fact"
    if ": " in s and " | " not in s:
        left, right = s.split(": ", 1)
        if len(left) > 48 and len(right) >= 8:
            s = right.strip()
    return s[:140]


def _facts_from_search(search: dict[str, Any] | None) -> list[str]:
    facts: list[str] = []
    seen: set[str] = set()

    def add(raw: str) -> None:
        line = _clean_fact_line(raw)
        if _is_serp_noise(line):
            return
        key = line.lower()
        if key in seen:
            return
        seen.add(key)
        facts.append(line)

    if not isinstance(search, dict):
        return facts
    ans = search.get("answer")
    if ans is not None and str(ans).strip():
        for part in str(ans).replace("\r", "\n").split("\n"):
            p = part.strip()
            if p:
                add(p)
            if len(facts) >= 8:
                return facts
    rows = search.get("results") if isinstance(search.get("results"), list) else []
    for row in rows:
        if not isinstance(row, dict):
            continue
        snip = str(
            row.get("content") or row.get("snippet") or row.get("body") or ""
        ).strip()
        title = str(row.get("title") or "").strip()
        # Prefer snippet; title alone is usually SEO chrome
        if snip:
            add(snip)
        elif title and not _is_serp_noise(title):
            add(title)
        if len(facts) >= 8:
            break
    return facts


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


def build_office_body_from_search(
    *,
    file_instruction: str,
    user_ask: str,
    search: dict[str, Any] | None,
) -> str:
    """Assemble clean TITLE/ICON/fact lines for styled office-file."""
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
        # Prefer a short place-oriented default from file instruction markers only
        title = "Thời tiết hiện tại"

    subtitle = (markers.get("subtitle") or "").strip() or "Cập nhật trực tiếp"
    icon = (markers.get("icon") or "").strip().lower() or "cloud"

    facts = _facts_from_search(search)
    # Keep classify-authored fact bullets (lines starting with -) if present
    for raw in fi.splitlines():
        s = raw.strip()
        if s.startswith(("- ", "• ", "* ")):
            line = _clean_fact_line(s)
            if line and not _is_serp_noise(line) and line not in facts:
                facts.append(line)

    if not facts:
        facts = ["Chưa lấy được chi tiết thời tiết — thử lại sau."]

    icon = _infer_icon(facts, icon)

    lines = [
        f"TITLE: {title[:72]}",
        f"SUBTITLE: {subtitle[:80]}",
        f"ICON: {icon}",
    ]
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
