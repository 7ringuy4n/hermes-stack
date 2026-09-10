#!/usr/bin/env python3
"""One-time / repeatable: partition scripts/HISTORY.md into history/YYYY-MM-DD/README.md.

Run from repo root:
  python3 scripts/main/backfill-root-history.py
  python3 scripts/main/backfill-root-history.py --since 2026-08-01
"""
from __future__ import annotations

import argparse
import re
from collections import defaultdict
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "scripts" / "HISTORY.md"
DEST = ROOT / "history"

HEADING = re.compile(
    r"^## (?P<ts>\d{4}-\d{2}-\d{2}) (?P<hm>\d{2}:\d{2}) \+07 — (?P<title>.+)$"
)
SUB = re.compile(r"^### (?P<name>.+)$")


def _slug(title: str) -> str:
    out: list[str] = []
    dash = False
    for ch in title.lower():
        if ch.isalnum():
            out.append(ch)
            dash = False
        elif not dash:
            out.append("-")
            dash = True
    return "".join(out).strip("-")[:72] or "incident"


def parse_entries(text: str) -> list[dict[str, str]]:
    entries: list[dict[str, str]] = []
    cur: dict[str, str] | None = None
    section = ""
    buf: list[str] = []

    def flush_section() -> None:
        nonlocal buf, section
        if cur is not None and section:
            cur[section] = "\n".join(buf).strip()
        buf = []

    def flush_entry() -> None:
        nonlocal cur
        flush_section()
        if cur is not None:
            entries.append(cur)
        cur = None

    for raw in text.splitlines():
        m = HEADING.match(raw.strip())
        if m:
            flush_entry()
            cur = {
                "date": m.group("ts"),
                "time": m.group("hm"),
                "title": m.group("title").strip(),
                "slug": _slug(m.group("title")),
            }
            section = ""
            continue
        sm = SUB.match(raw.strip())
        if sm and cur is not None:
            flush_section()
            name = sm.group("name").strip().lower()
            if "symptom" in name:
                section = "symptom"
            elif "root" in name:
                section = "root_cause"
            elif "fix" in name:
                section = "fix"
            elif "prevent" in name:
                section = "prevent"
            elif "decision" in name:
                section = "ai_decision"
            elif "todo" in name:
                section = "todos"
            elif "technical" in name:
                section = "technical"
            else:
                section = name.replace(" ", "_")
            continue
        if cur is not None:
            buf.append(raw)
    flush_entry()
    return entries


def render_entry(e: dict[str, str]) -> str:
    lines = [f"## {e['time']} — {e['title']}", ""]
    for key, label in (
        ("symptom", "Symptom"),
        ("root_cause", "Root cause"),
        ("technical", "Technical detail"),
        ("ai_decision", "AI decision"),
        ("fix", "Fix (core)"),
        ("todos", "Todo list"),
        ("prevent", "Prevent recurrence"),
    ):
        body = (e.get(key) or "").strip()
        if not body and key == "technical":
            body = (
                "_Backfilled — add function names, env keys (bad → fixed), API fields, "
                "and line anchors (`path:Lstart–Lend`) per AGENT_RULES §4.1._"
            )
        if not body and key == "ai_decision":
            body = (
                "Backfilled from legacy log. At fix time: prioritize durable core change "
                "over VPS hotpatch; align classify/skills when intent routing was involved."
            )
        if not body and key == "todos":
            body = "- Reproduce\n- Fix core\n- Regression test\n- Verify on lab/VPS"
        if body:
            lines.extend([f"### {label}", "", body, ""])
    return "\n".join(lines).rstrip() + "\n"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--since", default="2026-08-01", help="YYYY-MM-DD inclusive")
    ap.add_argument("--source", default=str(SRC))
    ap.add_argument("--dest", default=str(DEST))
    ap.add_argument(
        "--force",
        action="store_true",
        help="Overwrite existing history/YYYY-MM-DD/README.md (default: skip existing days)",
    )
    args = ap.parse_args()
    since = date.fromisoformat(args.since)
    src = Path(args.source)
    dest = Path(args.dest)
    if not src.is_file():
        raise SystemExit(f"missing {src}")
    entries = parse_entries(src.read_text(encoding="utf-8", errors="replace"))
    by_day: dict[str, list[dict[str, str]]] = defaultdict(list)
    for e in entries:
        d = date.fromisoformat(e["date"])
        if d < since:
            continue
        by_day[e["date"]].append(e)
    if not by_day:
        print(f"no entries since {since}")
        return 0
    dest.mkdir(parents=True, exist_ok=True)
    readme = dest / "README.md"
    readme.write_text(
        "# Root-cause history (partitioned by date)\n\n"
        "Agent-facing incident log. See [`AGENT_RULES.md`](../AGENT_RULES.md) §4.1.\n\n"
        "Each incident **must** include **Technical detail**: functions, env/config keys "
        "(bad → fixed values), API/JSON fields, and line anchors (`path:Lstart–Lend`).\n\n"
        "Legacy source: [`scripts/HISTORY.md`](../scripts/HISTORY.md) (append-only ops log).\n\n"
        + "\n".join(f"- [{d}](./{d}/README.md)" for d in sorted(by_day))
        + "\n",
        encoding="utf-8",
    )
    for day, items in sorted(by_day.items()):
        day_dir = dest / day
        day_readme = day_dir / "README.md"
        if day_readme.is_file() and not args.force:
            print(f"SKIP {day} (exists; use --force to overwrite)")
            continue
        day_dir.mkdir(parents=True, exist_ok=True)
        parts = [
            f"# {day}",
            "",
            f"{len(items)} incident(s). Times are UTC+7.",
            "",
        ]
        for e in sorted(items, key=lambda x: x["time"]):
            parts.append(render_entry(e))
        (day_dir / "README.md").write_text("\n".join(parts).rstrip() + "\n", encoding="utf-8")
        print(f"OK {day} n={len(items)}")
    print(f"OK history index {readme}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
