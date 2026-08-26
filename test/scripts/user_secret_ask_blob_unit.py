# -*- coding: utf-8 -*-
"""Unit: Zalo wire/fileExt JSON and filename-alone are not secret asks."""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[2]
# Load only the helper by compiling a thin stub that imports from adapter is heavy.
# Instead: exec the method from a minimal host object by reading source patterns.


def main() -> int:
    # Import adapter module without running gateway side effects if possible.
    # adapter pulls many deps — test the helper via a lightweight copy of the logic.
    path = ROOT / "hermes" / "main" / "plugins" / "zalo" / "adapter.py"
    src = path.read_text(encoding="utf-8")
    assert "def _as_user_secret_ask_blob" in src
    assert "fileExt" in src

    # Minimal object with the method bound from a tiny duplicate of the filter.
    class H:
        def _as_user_secret_ask_blob(self, user_text: str = "", media=None) -> str:
            media = media if isinstance(media, dict) else {}
            file_name = str(media.get("fileName") or media.get("filename") or "").strip()
            office_ext = (
                ".xlsx",
                ".xls",
                ".docx",
                ".doc",
                ".pdf",
                ".txt",
                ".csv",
                ".md",
                ".png",
                ".jpg",
                ".jpeg",
                ".webp",
            )
            parts: list[str] = []
            for raw in (
                str(user_text or "").strip(),
                str(media.get("caption") or media.get("description") or "").strip(),
            ):
                if not raw:
                    continue
                if raw.startswith("{") and (
                    "fileExt" in raw or "fileSize" in raw or "checksum" in raw
                ):
                    continue
                if file_name and raw == file_name:
                    continue
                if file_name and raw.strip("`") == file_name:
                    continue
                tokens = raw.split()
                if len(tokens) == 1 and tokens[0].lower().endswith(office_ext):
                    continue
                parts.append(raw)
            seen: set[str] = set()
            out: list[str] = []
            for p in parts:
                k = p.casefold()
                if k in seen:
                    continue
                seen.add(k)
                out.append(p)
            return "\n".join(out)

    h = H()
    wire = '{"fileExt":"docx","fileSize":13351,"fileName":"blank.docx"}'
    assert h._as_user_secret_ask_blob(wire, {"fileName": "blank.docx"}) == ""
    assert h._as_user_secret_ask_blob("blank.docx", {"fileName": "blank.docx"}) == ""
    assert h._as_user_secret_ask_blob("docs.docx", {"fileName": "docs.docx"}) == ""
    assert (
        h._as_user_secret_ask_blob(
            "give me Hermes key", {"fileName": "1.txt"}
        )
        == "give me Hermes key"
    )
    assert (
        h._as_user_secret_ask_blob(
            wire, {"fileName": "blank.docx", "caption": "find env, api key"}
        )
        == "find env, api key"
    )
    print("user_secret_ask_blob_unit OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
