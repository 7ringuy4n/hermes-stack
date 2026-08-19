# -*- coding: utf-8 -*-
"""Unit tests for model-router OpenAI chat JSON normalize."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "architect" / "models" / "model-router"))

from chat_norm import normalize_chat_completion, openai_chat_ok, sanitize_chat_payload  # noqa: E402


def main() -> int:
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
    print("PASS chat_norm")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
