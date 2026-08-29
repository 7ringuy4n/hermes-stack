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


def build_office_body_from_search(
    *,
    file_instruction: str,
    user_ask: str,
    search: dict[str, Any] | None,
) -> str:
    """Assemble TITLE/ICON/fact lines for styled office-file (no user-prose NLU)."""
    fi = (file_instruction or "").strip()
    ask = (user_ask or "").strip()
    lines: list[str] = []
    has_title = False
    if fi:
        for raw in fi.splitlines():
            s = raw.strip()
            if not s:
                continue
            if s.upper().startswith("TITLE:") or s.upper().startswith("SUBTITLE:") or s.upper().startswith("ICON:"):
                lines.append(s)
                if s.upper().startswith("TITLE:"):
                    has_title = True
            elif s.startswith(("- ", "• ", "* ")):
                lines.append(s if s.startswith("- ") else f"- {s[2:].strip()}")
            else:
                # Seed title from first non-marker line of the file instruction
                if not has_title:
                    lines.insert(0, f"TITLE: {s[:72]}")
                    has_title = True
                else:
                    lines.append(f"- {s[:120]}")
    if not has_title:
        seed = ask[:72] if ask else "Report"
        lines.insert(0, f"TITLE: {seed}")
    markers = "\n".join(lines).upper()
    if "SUBTITLE:" not in markers:
        lines.insert(1 if has_title or lines else 0, "SUBTITLE: Live data")
    if "ICON:" not in markers:
        # Insert after title/subtitle block
        insert_at = 0
        for i, ln in enumerate(lines):
            u = ln.upper()
            if u.startswith("TITLE:") or u.startswith("SUBTITLE:"):
                insert_at = i + 1
        lines.insert(insert_at, "ICON: cloud")

    facts: list[str] = []
    if isinstance(search, dict):
        ans = search.get("answer")
        if ans is not None and str(ans).strip():
            for part in str(ans).replace("\r", "\n").split("\n"):
                p = part.strip()
                if p:
                    facts.append(p[:140])
        rows = search.get("results") if isinstance(search.get("results"), list) else []
        for row in rows:
            if not isinstance(row, dict):
                continue
            title = str(row.get("title") or "").strip()
            snip = str(
                row.get("content")
                or row.get("snippet")
                or row.get("body")
                or ""
            ).strip()
            if title and snip:
                facts.append(f"{title}: {snip[:100]}")
            elif title:
                facts.append(title[:120])
            elif snip:
                facts.append(snip[:120])
            if len(facts) >= 12:
                break
    if not facts:
        facts.append(fi[:140] if fi else (ask[:140] if ask else "No live details"))
    for f in facts:
        bullet = f if f.startswith("- ") else f"- {f}"
        if bullet not in lines:
            lines.append(bullet)
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
