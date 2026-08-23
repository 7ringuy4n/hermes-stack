"""Zalo uses LLM classify for multi-task / schedule intent. No regex NLU."""
from __future__ import annotations

import os
import re
import sys
from pathlib import Path
from typing import List, Tuple

_d = Path(__file__).resolve().parent
_shared = Path(os.getenv("HERMES_SHARED_DATA") or "/opt/data") / "plugins" / "zalo"
for _p in (_d, _shared):
    _s = str(_p)
    if _p.is_dir() and _s not in sys.path:
        sys.path.insert(0, _s)

from classify_client import classify_text

_CLOCK_HM = re.compile(
    r"(?:(?:lúc|luc|at|@)\s*)?(\d{1,2})\s*[:hH]\s*(\d{2})\b",
    re.I,
)


def looks_like_schedule_job(text: str) -> bool:
    plan = classify_text(text or "")
    return plan.get("task_hint") == "schedule"


def _clock_pairs(text: str) -> List[Tuple[int, int]]:
    out: List[Tuple[int, int]] = []
    seen: set[Tuple[int, int]] = set()
    for m in _CLOCK_HM.finditer(text or ""):
        try:
            hour = int(m.group(1))
            minute = int(m.group(2))
        except (TypeError, ValueError):
            continue
        if not (0 <= hour <= 23 and 0 <= minute <= 59):
            continue
        key = (hour, minute)
        if key in seen:
            continue
        seen.add(key)
        out.append(key)
    return out


def _split_multi_clock_schedule(raw: str, instructions: List[str]) -> List[str] | None:
    clocks = _clock_pairs(raw)
    if len(clocks) < 2:
        return None
    items = [str(x).strip() for x in instructions if str(x).strip()]
    if len(items) < 2:
        lines = [
            ln.strip()
            for ln in re.split(r"\n+", raw)
            if ln.strip() and _clock_pairs(ln)
        ]
        distinct = {_clock_pairs(x)[0] for x in lines if _clock_pairs(x)}
        if len(lines) >= 2 and len(distinct) >= 2:
            return lines
        return None

    per_clock: list[str] = []
    used: set[Tuple[int, int]] = set()
    for instr in items:
        own = _clock_pairs(instr)
        if len(own) == 1 and own[0] not in used:
            per_clock.append(instr)
            used.add(own[0])
        elif len(own) >= 1:
            per_clock.append(instr)
            used.update(own[:1])

    if len(per_clock) >= 2 and len(used) >= 2:
        return per_clock

    if len(items) >= 2 and len(clocks) >= 2:
        n = min(len(items), len(clocks))
        if n >= 2:
            paired: list[str] = []
            for i in range(n):
                h, m = clocks[i]
                body = items[i]
                if not _clock_pairs(body):
                    body = f"lúc {h:02d}:{m:02d}: {body}"
                paired.append(body)
            distinct = {_clock_pairs(x)[0] for x in paired if _clock_pairs(x)}
            if len(distinct) >= 2:
                return paired
    return None


def split_compound_requests(text: str) -> List[str]:
    raw = (text or "").strip()
    if not raw:
        return []
    plan = classify_text(raw)
    items = [str(x).strip() for x in (plan.get("instructions") or []) if str(x).strip()]
    if plan.get("task_hint") == "schedule":
        multi = _split_multi_clock_schedule(raw, items)
        if multi:
            return multi
        return [raw]
    return items or [raw]


def wrap_compound_part(index: int, total: int, body: str) -> str:
    text = (body or "").strip()
    if not text:
        return text
    low = text.lower()
    topic = (
        "Nếu đây là tìm/tóm tắt giá xăng: chỉ báo giá nhiên liệu (E5/E10…), không mô tả thời tiết.\n"
        if any(k in low for k in ("xăng", "xang", "e5", "e10", "ron92", "ron95", "fuel"))
        else "Nếu đây là thời tiết: chỉ báo thời tiết/địa điểm được hỏi, không báo giá xăng.\n"
        if any(k in low for k in ("thời tiết", "thoi tiet", "weather"))
        else "Nếu đây là chào/chúc: chỉ gửi lời chào/chúc, không tìm kiếm web.\n"
        if any(k in low for k in ("chào", "chao", "chúc", "chuc", "greeting", "hello"))
        else ""
    )
    return (
        f"Yêu cầu {index}/{total} — chỉ làm đúng việc này, rồi dừng. "
        f"Không làm các mục khác.\n"
        f"{topic}"
        f"{text}"
    )


def plan_instructions(text: str) -> List[str]:
    raw = (text or "").strip()
    if not raw:
        return []
    plan = classify_text(raw)
    items = [str(x).strip() for x in (plan.get("instructions") or []) if str(x).strip()]
    return items or [raw]
