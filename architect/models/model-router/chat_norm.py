"""Normalize OpenAI-compatible chat JSON for Hermes (no NLU)."""
from __future__ import annotations

from typing import Any


def parts_to_text(content: Any) -> str:
    if content is None:
        return ""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        bits: list[str] = []
        for item in content:
            if isinstance(item, str) and item.strip():
                bits.append(item.strip())
            elif isinstance(item, dict):
                t = item.get("text")
                if isinstance(t, str) and t.strip():
                    bits.append(t.strip())
        return "\n".join(bits)
    return str(content)


def sanitize_chat_payload(payload: dict[str, Any]) -> dict[str, Any]:
    """Deterministic OpenAI body cleanup before upstream."""
    out = dict(payload)
    out["stream"] = bool(out.get("stream"))
    msgs = out.get("messages")
    if isinstance(msgs, list):
        clean: list[dict[str, Any]] = []
        for m in msgs:
            if not isinstance(m, dict):
                continue
            m2 = dict(m)
            m2["content"] = parts_to_text(m2.get("content"))
            clean.append(m2)
        out["messages"] = clean
    tools = out.get("tools")
    if isinstance(tools, list):
        out["tools"] = [t for t in tools if isinstance(t, dict)]
    return out


def openai_chat_ok(data: Any) -> bool:
    if not isinstance(data, dict):
        return False
    if data.get("error") and not data.get("choices"):
        return False
    choices = data.get("choices")
    return isinstance(choices, list) and bool(choices)


def _error_text(data: Any) -> str:
    if not isinstance(data, dict):
        return ""
    err = data.get("error")
    if isinstance(err, dict):
        return str(err.get("message") or err.get("code") or err)
    if err is not None:
        return str(err)
    return str(data.get("message") or "")


def chat_body_should_failover(status: int, data: Any) -> bool:
    """True when the upstream chat response must not be returned to Hermes.

    OmniRouter often returns HTTP 200 with an error payload (or a paid-model
    subscription refuse). Streaming that through leaves Hermes with a 403 and
    no Zalo reply — failover must happen here instead.
    """
    if status >= 500 or status in {401, 403, 413, 429}:
        return True
    if not isinstance(data, dict):
        return True
    if data.get("error") and not data.get("choices"):
        return True
    msg = _error_text(data).lower()
    if any(
        needle in msg
        for needle in (
            "requires a subscription",
            "upgrade for access",
            "payment required",
            "insufficient_quota",
            "model not found",
        )
    ):
        return True
    return normalize_chat_completion(data) is None


def completion_to_sse(data: dict[str, Any]) -> bytes:
    """One-shot OpenAI SSE body from a non-stream chat.completion object."""
    import json as _json

    choice0 = (data.get("choices") or [{}])[0]
    msg = choice0.get("message") if isinstance(choice0, dict) else {}
    if not isinstance(msg, dict):
        msg = {"role": "assistant", "content": parts_to_text(msg)}
    delta: dict[str, Any] = {
        "role": str(msg.get("role") or "assistant"),
        "content": parts_to_text(msg.get("content")),
    }
    if isinstance(msg.get("tool_calls"), list):
        delta["tool_calls"] = msg["tool_calls"]
    chunk = {
        "id": data.get("id") or "chatcmpl-router",
        "object": "chat.completion.chunk",
        "created": data.get("created") or 0,
        "model": data.get("model") or "",
        "choices": [
            {
                "index": 0,
                "delta": delta,
                "finish_reason": choice0.get("finish_reason") or "stop",
            }
        ],
    }
    return (f"data: {_json.dumps(chunk, ensure_ascii=False)}\n\ndata: [DONE]\n\n").encode(
        "utf-8"
    )


def normalize_chat_completion(data: Any) -> dict[str, Any] | None:
    """Return a Chat Completions object Hermes/openai can vars()-parse, or None."""
    if not openai_chat_ok(data):
        return None
    assert isinstance(data, dict)
    out_choices: list[dict[str, Any]] = []
    for ch in data.get("choices") or []:
        if not isinstance(ch, dict):
            continue
        msg = ch.get("message")
        if isinstance(msg, str):
            msg = {"role": "assistant", "content": msg}
        elif not isinstance(msg, dict):
            msg = {"role": "assistant", "content": parts_to_text(msg)}
        else:
            msg = dict(msg)
        msg["content"] = parts_to_text(msg.get("content"))
        if not str(msg.get("role") or "").strip():
            msg["role"] = "assistant"
        tc = msg.get("tool_calls")
        if tc is not None and not isinstance(tc, list):
            msg.pop("tool_calls", None)
        elif isinstance(tc, list):
            fixed = []
            for item in tc:
                if not isinstance(item, dict):
                    continue
                item = dict(item)
                fn = item.get("function")
                if isinstance(fn, dict):
                    fn = dict(fn)
                    args = fn.get("arguments")
                    if args is not None and not isinstance(args, str):
                        fn["arguments"] = str(args)
                    item["function"] = fn
                fixed.append(item)
            msg["tool_calls"] = fixed
        ch2 = dict(ch)
        ch2["message"] = msg
        if not ch2.get("finish_reason"):
            ch2["finish_reason"] = "stop"
        out_choices.append(ch2)
    if not out_choices:
        return None
    result = dict(data)
    result["choices"] = out_choices
    result.setdefault("object", "chat.completion")
    return result
