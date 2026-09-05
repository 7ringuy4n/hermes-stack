# -*- coding: utf-8 -*-
"""Office create must not collide on skill name pdf|docx|xlsx."""
from __future__ import annotations

import re
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SKILLS = ROOT / "hermes" / "main" / "skills"
FORBIDDEN = {"pdf", "docx", "xlsx"}
NAME_RE = re.compile(r"(?m)^name:\s*[\"']?([^\s\"']+)[\"']?\s*$")


def main() -> int:
    if not SKILLS.is_dir():
        print(f"FAIL missing {SKILLS}", file=sys.stderr)
        return 1
    names: Counter[str] = Counter()
    paths: dict[str, list[str]] = {}
    for skill in SKILLS.rglob("SKILL.md"):
        text = skill.read_text(encoding="utf-8", errors="replace")
        m = NAME_RE.search(text)
        if not m:
            continue
        name = m.group(1).strip()
        names[name] += 1
        paths.setdefault(name, []).append(str(skill.relative_to(ROOT)))

    bad = [n for n in FORBIDDEN if names.get(n, 0)]
    if bad:
        print("FAIL reserved office skill names still present:", bad, file=sys.stderr)
        for n in bad:
            for p in paths.get(n, []):
                print(f"  {n}: {p}", file=sys.stderr)
        return 1

    office_local = [n for n in names if n.endswith("-tools-local") and any(x in n for x in ("pdf", "docx", "xlsx"))]
    for n in office_local:
        if names[n] > 1:
            print(f"FAIL duplicate office-local name {n}:", paths[n], file=sys.stderr)
            return 1

    file_gen = SKILLS / "file-gen" / "SKILL.md"
    body = file_gen.read_text(encoding="utf-8", errors="replace")
    if "/v1/office-file" not in body:
        print("FAIL file-gen must require /v1/office-file", file=sys.stderr)
        return 1
    entry = ROOT / "hermes" / "main" / "docker" / "hermes-replica-entry.sh"
    sh = entry.read_text(encoding="utf-8", errors="replace")
    if "productivity" not in sh or '"${_dst_skills}/${_n}"' not in sh or "rm -rf" not in sh:
        print("FAIL entrypoint must exclude local office toolkits and clones", file=sys.stderr)
        return 1
    print("OK office skill names unique; file-gen uses office-file; runtime excludes local toolkits")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
