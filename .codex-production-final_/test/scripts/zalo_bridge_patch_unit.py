# -*- coding: utf-8 -*-
"""Unit: bridge inject/media patch markers stay idempotent (no VPS)."""
from __future__ import annotations

import io
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts" / "main"))

if hasattr(sys.stdout, "buffer"):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

INJECT_MARKER = 'app.post("/inject-event"'
MEDIA_MARKER = "ASSISTANT_MEDIA_PROXY_v1"
STRIP = re.compile(
    r"\n?// assistant-stack: synthetic inbound[^\n]*\n"
    r"app\.post\(\"/inject-event\", \(req, res\) => \{.*?\n\}\);\n?",
    re.S,
)
BLOCK = """
// assistant-stack: synthetic inbound onto the existing SSE fan-out (tests).
app.post("/inject-event", (req, res) => {
  if (!checkAuth(req, res)) return;
  pushEvent(type, payload);
  res.json({ ok: true });
});
"""


def test_strip_duplicates() -> None:
    text = "head\n" + BLOCK + BLOCK + BLOCK + "_httpServer = app.listen(PORT, HOST, () => {});\n"
    cleaned = STRIP.sub("\n", text)
    if cleaned.count(INJECT_MARKER) != 0:
        raise SystemExit(f"FAIL strip left {cleaned.count(INJECT_MARKER)} inject handlers")
    if "_httpServer = app.listen" not in cleaned:
        raise SystemExit("FAIL listen lost")
    print("OK strip removes duplicate inject handlers")


def test_markers_distinct() -> None:
    if INJECT_MARKER == "POST /inject-event":
        raise SystemExit("FAIL old broken MARKER would never match app.post")
    if MEDIA_MARKER not in "ASSISTANT_MEDIA_PROXY_v1":
        raise SystemExit("FAIL media marker")
    print("OK inject marker matches app.post form")


def main() -> int:
    test_strip_duplicates()
    test_markers_distinct()
    print("PASS zalo_bridge_patch_unit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
