# -*- coding: utf-8 -*-
"""Unit tests for model-router OpenAI chat JSON normalize."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "architect" / "models" / "model-router"))

from chat_norm import (  # noqa: E402
    chat_body_should_failover,
    chat_busy_capacity,
    completion_to_sse,
    normalize_chat_completion,
    openai_chat_ok,
    sanitize_chat_payload,
)
from route_expand import upstream_url  # noqa: E402


def main() -> int:
    if upstream_url("http://host.docker.internal:11434/v1", "v1/chat/completions") != (
        "http://host.docker.internal:11434/v1/chat/completions"
    ):
        print("FAIL duplicate v1 must be stripped from upstream url")
        return 1
    if upstream_url("http://omni-router:20129/v1", "chat/completions") != (
        "http://omni-router:20129/v1/chat/completions"
    ):
        print("FAIL normal upstream url join")
        return 1
    if openai_chat_ok({"error": {"message": "nope"}}):
        print("FAIL error body must not be ok")
        return 1
    if normalize_chat_completion({"choices": [{"message": "hello"}]}) is None:
        print("FAIL string message must normalize")
        return 1
    got = normalize_chat_completion(
        {"choices": [{"message": {"role": "assistant", "content": [{"type": "text", "text": "ok"}]}}]}
    )
    if not got or got["choices"][0]["message"]["content"] != "ok":
        print("FAIL list content must join")
        return 1
    payload = sanitize_chat_payload({"stream": None, "messages": [{"role": "user", "content": {"x": 1}}]})
    if payload["stream"] is not False:
        print("FAIL stream None -> False")
        return 1
    if not isinstance(payload["messages"][0]["content"], str):
        print("FAIL message content must be str")
        return 1
    if not chat_body_should_failover(
        200,
        {"error": {"message": "this model requires a subscription, upgrade for access"}},
    ):
        print("FAIL subscription refuse must failover")
        return 1
    if not chat_body_should_failover(403, {"error": {"message": "forbidden"}}):
        print("FAIL HTTP 403 must failover")
        return 1
    if chat_body_should_failover(
        200, {"choices": [{"message": {"role": "assistant", "content": "ok"}}]}
    ):
        print("FAIL good chat must not failover")
        return 1
    busy = {
        "error": {
            "message": "Structurally heavy chat request capacity is busy; retry shortly."
        }
    }
    if not chat_body_should_failover(503, busy):
        print("FAIL capacity-busy 503 must failover")
        return 1
    if not chat_busy_capacity(503, busy):
        print("FAIL chat_busy_capacity")
        return 1
    sse = completion_to_sse(
        {
            "id": "x",
            "created": 1,
            "model": "m",
            "choices": [{"message": {"role": "assistant", "content": "hi"}}],
        }
    ).decode("utf-8")
    if "data: " not in sse or "[DONE]" not in sse or "hi" not in sse:
        print("FAIL sse shape", sse[:200])
        return 1
    print("PASS chat_norm")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
