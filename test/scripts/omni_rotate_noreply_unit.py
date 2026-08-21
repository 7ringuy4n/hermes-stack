# -*- coding: utf-8 -*-
"""Unit: Omni rotate + subscription failover + OCR image ack (no VPS)."""
from __future__ import annotations

import io
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "architect" / "models" / "model-router"))
sys.path.insert(0, str(ROOT / "hermes" / "main" / "plugins" / "zalo"))

from chat_norm import (  # noqa: E402
    chat_body_should_failover,
    chat_busy_capacity,
    completion_to_sse,
)
from route_expand import expand_chat_candidates  # noqa: E402
from attachment import (  # noqa: E402
    file_extract_ack_message,
    image_ocr_ack_message,
    ocr_excerpt_for_ack,
)

if hasattr(sys.stdout, "buffer"):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")


def test_rotate_then_failover() -> None:
    cands = [
        ("omni-router", "http://omni/v1", {"Authorization": "Bearer x"}, None),
        ("openai-fallback", "http://fb/v1", {}, "gpt-4o-mini"),
    ]
    out = expand_chat_candidates(
        cands,
        requested_model="hermes",
        default_model="hermes",
        failover_models=["auto/best-free", "hermes"],
        rotate_attempts=3,
    )
    models = [m for _, _, _, m in out]
    # 3x hermes (Omni RR), then auto/best-free once, then openai-fallback
    if models[:3] != ["hermes", "hermes", "hermes"]:
        raise SystemExit(f"FAIL rotate primary={models[:3]!r}")
    if "auto/best-free" not in models:
        raise SystemExit(f"FAIL missing failover in {models!r}")
    if models.count("auto/best-free") != 1:
        raise SystemExit(f"FAIL failover dup {models!r}")
    if models[-1] != "gpt-4o-mini":
        raise SystemExit(f"FAIL fallback last={models[-1]!r}")
    print("OK rotate then failover")


def test_subscription_failover() -> None:
    if not chat_body_should_failover(
        200,
        {"error": {"message": "[ollama-cloud/deepseek-v4-pro] [403]: requires a subscription"}},
    ):
        raise SystemExit("FAIL subscription body")
    if chat_body_should_failover(
        200, {"choices": [{"message": {"role": "assistant", "content": "ok"}}]}
    ):
        raise SystemExit("FAIL good body")
    busy = {
        "error": {
            "message": "Structurally heavy chat request capacity is busy; retry shortly."
        }
    }
    if not chat_body_should_failover(503, busy):
        raise SystemExit("FAIL busy 503 must failover")
    if not chat_busy_capacity(503, busy):
        raise SystemExit("FAIL busy capacity detect")
    if chat_busy_capacity(200, {"choices": [{"message": {"content": "ok"}}]}):
        raise SystemExit("FAIL good body not busy")
    sse = completion_to_sse(
        {"choices": [{"message": {"role": "assistant", "content": "hi"}}]}
    ).decode()
    if "hi" not in sse or "[DONE]" not in sse:
        raise SystemExit("FAIL sse")
    print("OK subscription failover + busy + sse")


def test_ocr_ack() -> None:
    empty = image_ocr_ack_message("")
    if "OCR không đọc được" not in empty:
        raise SystemExit(f"FAIL empty ack={empty!r}")
    full = image_ocr_ack_message("HOA DON 1250000 VND")
    if "HOA DON 1250000 VND" not in full or "Đã đọc chữ" not in full:
        raise SystemExit(f"FAIL text ack={full!r}")
    long = image_ocr_ack_message("x" * 5000, max_chars=100)
    if "…" not in long or len(long) > 250:
        raise SystemExit(f"FAIL truncate={long!r}")
    noise = "\n".join(list("naotoeeeeeeie"))
    if ocr_excerpt_for_ack(noise) != "":
        raise SystemExit(f"FAIL noise excerpt={noise!r}")
    if "OCR không đọc được" not in image_ocr_ack_message(noise):
        raise SystemExit("FAIL noise should empty-ack")
    csv_ack = file_extract_ack_message("a.csv", "x,y\n1,2", kind="text")
    if "a.csv" not in csv_ack or "x,y" not in csv_ack:
        raise SystemExit(f"FAIL csv ack={csv_ack!r}")
    empty_mp4 = file_extract_ack_message("v.mp4", "", kind="av")
    if "Chưa lấy được transcript" not in empty_mp4:
        raise SystemExit(f"FAIL empty av={empty_mp4!r}")
    print("OK OCR/file extract ack")


def main() -> int:
    test_rotate_then_failover()
    test_subscription_failover()
    test_ocr_ack()
    print("PASS omni_rotate_noreply_unit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
