# -*- coding: utf-8 -*-
"""Authoritative host wall-clock labels for Hermes turns."""
from __future__ import annotations

import os
from datetime import datetime


def host_timezone() -> str:
    """Operator TZ for wall-clock labels (default Vietnam)."""
    return (
        os.getenv("ASSISTANT_TZ") or os.getenv("TZ") or "Asia/Ho_Chi_Minh"
    ).strip() or "Asia/Ho_Chi_Minh"


def local_now_label(tz_name: str | None = None) -> str:
    """Authoritative host Local now — agents must not invent observation clocks."""
    from zoneinfo import ZoneInfo

    name = (tz_name or host_timezone()).strip() or "Asia/Ho_Chi_Minh"
    try:
        now = datetime.now(ZoneInfo(name))
    except Exception:
        now = datetime.now()
    return now.strftime("%Y-%m-%d %H:%M")


def with_host_clock_context(text: str, *, tz_name: str | None = None) -> str:
    """Prepend host Timezone + Local now for Hermes turns (idempotent)."""
    body = str(text or "")
    if not body.strip():
        return body
    marker = "Local now:"
    if marker in body[:240]:
        return body
    tz = (tz_name or host_timezone()).strip() or "Asia/Ho_Chi_Minh"
    stamp = local_now_label(tz)
    prefix = (
        f"[Host clock — authoritative]\n"
        f"Timezone: {tz}\n"
        f"Local now: {stamp}\n\n"
    )
    return prefix + body


def strip_host_clock_context(text: str) -> str:
    """Remove host-clock wrapper so classify/schedule see the bare user ask."""
    body = str(text or "")
    if not body.strip():
        return body
    marker = "[Host clock — authoritative]"
    idx = body.find(marker)
    if idx >= 0:
        body = body[idx + len(marker) :]
    elif not (
        "Timezone:" in body[:160] and "Local now:" in body[:240]
    ):
        return body.strip() or (text or "").strip()
    lines = body.lstrip("\n").splitlines()
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        if not line or line.startswith("Timezone:") or line.startswith("Local now:"):
            i += 1
            continue
        break
    cleaned = "\n".join(lines[i:]).strip()
    return cleaned or (text or "").strip()
