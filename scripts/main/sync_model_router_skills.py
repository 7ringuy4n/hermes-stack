#!/usr/bin/env python3
"""Bake model-router fallback configuration from Hermes skill sources."""
from __future__ import annotations

import json
import shutil
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SKILLS = ROOT / "hermes" / "main" / "skills"
DESTINATION = ROOT / "architect" / "models" / "model-router" / "config"


def _atomic_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        "w", encoding="utf-8", newline="\n", dir=path.parent, delete=False
    ) as handle:
        handle.write(content)
        temporary = Path(handle.name)
    temporary.replace(path)


def _classify_payload() -> dict:
    source = SKILLS / "classify"
    payload = json.loads((source / "classify.json").read_text(encoding="utf-8"))
    chunks: list[str] = []
    for raw_name in payload.get("parts") or []:
        name = str(raw_name or "").strip()
        if not name or name.startswith(".") or "/" in name or "\\" in name:
            raise ValueError(f"invalid classify part name: {name!r}")
        part = source / "parts" / f"{name}.txt"
        content = part.read_text(encoding="utf-8").strip()
        if not content:
            raise ValueError(f"empty classify part: {part}")
        chunks.append(content)
    if not chunks:
        raise ValueError("classify parts produced an empty system prompt")
    payload["system"] = "\n\n".join(chunks)
    return payload


def main() -> int:
    DESTINATION.mkdir(parents=True, exist_ok=True)
    baked = json.dumps(_classify_payload(), ensure_ascii=False, indent=2) + "\n"
    _atomic_text(DESTINATION / "classify.json", baked)
    shutil.copyfile(SKILLS / "outbound" / "outbound.json", DESTINATION / "outbound.json")
    for retired in ("web-search-combo.json", "heuristic.json"):
        candidate = DESTINATION / retired
        if candidate.is_file():
            candidate.unlink()
    print(f"synced model-router skill fallbacks to {DESTINATION}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
