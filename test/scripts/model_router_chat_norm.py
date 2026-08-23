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
    chat_omni_skip_remaining,
    completion_to_sse,
    normalize_chat_completion,
    openai_chat_ok,
    sanitize_chat_payload,
    sanitize_for_ollama,
    should_strip_ollama_thinking,
)
from route_expand import direct_ollama_allowed, expand_chat_candidates, upstream_url  # noqa: E402


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
    omni = [("omni-router", "http://omni/v1", {}, None)]
    with_tools = expand_chat_candidates(
        omni,
        requested_model="hermes",
        failover_models=["auto/best-free"],
        rotate_attempts=5,
        has_tools=True,
    )
    tool_models = [m for _, _, _, m in with_tools if m]
    if "auto/best-free" in tool_models:
        print("FAIL auto/best-free must be skipped when tools present")
        return 1
    without_tools = expand_chat_candidates(
        omni,
        requested_model="hermes",
        failover_models=["auto/best-free"],
        rotate_attempts=2,
        has_tools=False,
    )
    if "auto/best-free" not in [m for _, _, _, m in without_tools if m]:
        print("FAIL auto/best-free should remain when no tools")
        return 1
    thinking_payload = sanitize_for_ollama(
        {"messages": [{"role": "user", "content": "hi"}], "thinking": {"type": "enabled"}}
    )
    if "thinking" in thinking_payload:
        print("FAIL ollama sanitize must drop thinking")
        return 1
    keep_thinking = sanitize_for_ollama(
        {"messages": [{"role": "user", "content": "hi"}], "thinking": {"type": "enabled"}},
        strip_thinking=False,
    )
    if "thinking" not in keep_thinking:
        print("FAIL ollama sanitize strip_thinking=False must keep thinking")
        return 1
    if not should_strip_ollama_thinking(enable_qwen_thinking=True, ollama_model="qwen3.5:2b-instruct"):
        pass
    else:
        print("FAIL qwen3.5 + thinking enabled must not strip")
        return 1
    if should_strip_ollama_thinking(enable_qwen_thinking=True, ollama_model="qwen2.5:7b"):
        pass
    else:
        print("FAIL qwen2.5 must always strip thinking")
        return 1
    if should_strip_ollama_thinking(enable_qwen_thinking=False, ollama_model="qwen3.5:2b-instruct"):
        pass
    else:
        print("FAIL thinking off must strip on ollama path")
        return 1
    if direct_ollama_allowed(task="normal", enable_omni=True, omni_ok=True):
        pass
    else:
        print("FAIL normal+omni must still allow Ollama as last-hop fallback")
        return 1
    if not direct_ollama_allowed(task="coding", enable_omni=True, omni_ok=True):
        print("FAIL coding may use direct ollama when configured")
        return 1
    # After Omni hermes 503 inactive, skip remaining Omni hops (then Ollama).
    ordered = expand_chat_candidates(
        [
            ("omni-router", "http://omni/v1", {}, None),
            ("ollama", "http://ollama/v1", {}, "qwen3:4b"),
        ],
        requested_model="hermes",
        failover_models=[],
        rotate_attempts=1,
        has_tools=True,
    )
    if ordered[0][0] != "omni-router" or ordered[0][3] != "hermes":
        print("FAIL first hop must be Omni hermes combo")
        return 1
    if ordered[-1][0] != "ollama":
        print("FAIL last hop must remain Ollama fallback")
        return 1
    inactive = {"error": {"message": "Service temporarily unavailable: all upstream accounts are inactive"}}
    if not chat_omni_skip_remaining(503, inactive):
        print("FAIL inactive omni must skip remaining hops")
        return 1
    tpm413 = {
        "error": {
            "message": (
                "[413]: Request too large for model `openai/gpt-oss-120b` "
                "on tokens per minute (TPM): Limit 8000, Requested 35520"
            )
        }
    }
    if not chat_omni_skip_remaining(413, tpm413):
        print("FAIL Groq TPM 413 must skip remaining Omni hops")
        return 1
    tools_err = {"error": {"message": "No target in combo auto/best-free supports tool calling"}}
    if not chat_omni_skip_remaining(400, tools_err):
        print("FAIL tool-calling combo error must skip remaining omni hops")
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
