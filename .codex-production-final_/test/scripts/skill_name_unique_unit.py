#!/usr/bin/env python3
"""Every installed skill has a unique registry name."""
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def skill_name(path: Path) -> str:
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.startswith("name:"):
            return line.partition(":")[2].strip().strip('"').strip("'")
    return ""


def main() -> int:
    owners: dict[str, list[str]] = {}
    for path in sorted((ROOT / "hermes" / "main" / "skills").rglob("SKILL.md")):
        name = skill_name(path)
        assert name, f"missing skill name: {path.relative_to(ROOT)}"
        owners.setdefault(name, []).append(str(path.relative_to(ROOT)))
    duplicates = {name: paths for name, paths in owners.items() if len(paths) > 1}
    assert not duplicates, f"duplicate skill names: {duplicates}"
    print(f"skill_name_unique_unit: PASS skills={len(owners)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
