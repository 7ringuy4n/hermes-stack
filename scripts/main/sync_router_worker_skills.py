#!/usr/bin/env python3
"""Bake router-worker fallback configuration from Hermes skill sources."""
from __future__ import annotations

import json
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SKILLS = ROOT / "hermes" / "main" / "skills"
DESTINATION = ROOT / "architect" / "models" / "router-worker" / "config"


def _atomic_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        "w", encoding="utf-8", newline="\n", dir=path.parent, delete=False
    ) as handle:
        handle.write(content)
        temporary = Path(handle.name)
    temporary.replace(path)


def _atomic_copy(src: Path, dst: Path) -> None:
    """Replace dst via rename so a root-owned bake file can be updated in a
    writable directory without opening the existing inode for write."""
    dst.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        "wb", dir=dst.parent, delete=False
    ) as handle:
        handle.write(src.read_bytes())
        temporary = Path(handle.name)
    temporary.replace(dst)


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
    _atomic_copy(SKILLS / "outbound" / "outbound.json", DESTINATION / "outbound.json")
    for retired in ("web-search-combo.json", "heuristic.json"):
        candidate = DESTINATION / retired
        if candidate.is_file():
            try:
                candidate.unlink()
            except PermissionError:
                # Root-owned retired bake: leave for the shell wrapper repair path.
                pass
    print(f"synced router-worker skill fallbacks to {DESTINATION}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
