# -*- coding: utf-8 -*-
"""Unit: Zalo autosend file window (no VPS)."""
from __future__ import annotations

import io
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "hermes" / "main" / "plugins" / "zalo"))

from autosend import file_in_send_window  # noqa: E402

if hasattr(sys.stdout, "buffer"):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")


def main() -> int:
    t0 = 1_000_000.0
    # File during the part
    if not file_in_send_window(t0 + 10, t0, t0):
        print("FAIL in-part file")
        return 1
    # File just before part clock (dispatcher write vs send race)
    if not file_in_send_window(t0 - 3, t0, t0, grace_s=8):
        print("FAIL grace")
        return 1
    # Next compound part: part_t0 jumped; seq_t0 keeps the image eligible
    part2 = t0 + 120
    img = t0 + 110
    if not file_in_send_window(img, part2, t0, grace_s=8):
        print("FAIL seq window")
        return 1
    # Unrelated old file
    if file_in_send_window(t0 - 600, part2, t0, grace_s=8):
        print("FAIL old file kept")
        return 1
    # Isolated job ceiling: later file belongs to the next job
    if file_in_send_window(t0 + 800, t0, t0, grace_s=8, ceiling=t0 + 100):
        print("FAIL ceiling leaked later file")
        return 1
    if not file_in_send_window(t0 + 50, t0, t0, grace_s=8, ceiling=t0 + 100):
        print("FAIL in-job file under ceiling")
        return 1
    from autosend import (  # noqa: E402
        bridge_response_ok,
        existing_media_path,
        file_ready_for_send,
        looks_invalid_param,
        prefer_remuxed_video,
        video_dedupe_stem,
    )

    if file_ready_for_send(t0, t0 + 0.1, min_age_s=0.8):
        print("FAIL growing file treated ready")
        return 1
    if not file_ready_for_send(t0, t0 + 2.0, min_age_s=0.8):
        print("FAIL settled file not ready")
        return 1
    if not looks_invalid_param("Tham số không hợp lệ"):
        print("FAIL invalid param detect")
        return 1

    if not bridge_response_ok({"success": True, "result": {"msgId": "1"}}):
        print("FAIL plugin success")
        return 1
    if bridge_response_ok({"error": "file not found: x"}):
        print("FAIL plugin error body")
        return 1
    if bridge_response_ok({"success": True, "error": "file not found"}):
        print("FAIL success+error")
        return 1
    if bridge_response_ok({}):
        print("FAIL empty body")
        return 1
    import tempfile

    if video_dedupe_stem("city.mp4") != video_dedupe_stem("city.zalo.mp4"):
        print("FAIL video stem")
        return 1
    with tempfile.TemporaryDirectory() as tmp:
        raw = Path(tmp) / "city.mp4"
        remux = Path(tmp) / "city.zalo.mp4"
        raw.write_bytes(b"x" * 2000)
        remux.write_bytes(b"y" * 2000)
        if Path(prefer_remuxed_video(str(raw))).name != "city.zalo.mp4":
            print("FAIL prefer remux")
            return 1

    with tempfile.TemporaryDirectory() as tmp:
        png = Path(tmp) / "scene.png"
        png.write_bytes(b"png")
        hit = existing_media_path(str(Path(tmp) / "scene.jpg"))
        if Path(hit).name != "scene.png":
            print("FAIL sibling png")
            return 1
    print("PASS autosend window")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
