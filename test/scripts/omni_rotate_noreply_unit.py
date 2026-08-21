# -*- coding: utf-8 -*-
"""Unit: Omni rotate + subscription failover + OCR image ack (no VPS)."""
from __future__ import annotations

import io
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "architect" / "models" / "model-router"))
sys.path.insert(0, str(ROOT / "hermes" / "main" / "plugins" / "zalo"))

from chat_norm import chat_body_should_failover, completion_to_sse  # noqa: E402
from route_expand import expand_chat_candidates  # noqa: E402
from attachment import image_ocr_ack_message, ocr_excerpt_for_ack  # noqa: E402

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
    sse = completion_to_sse(
        {"choices": [{"message": {"role": "assistant", "content": "hi"}}]}
    ).decode()
    if "hi" not in sse or "[DONE]" not in sse:
        raise SystemExit("FAIL sse")
    print("OK subscription failover + sse")


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
    print("OK OCR image ack")


def main() -> int:
    test_rotate_then_failover()
    test_subscription_failover()
    test_ocr_ack()
    print("PASS omni_rotate_noreply_unit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
