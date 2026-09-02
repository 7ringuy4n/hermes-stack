"""Normalize OpenAI-compatible chat JSON for Hermes (no NLU)."""
from __future__ import annotations

from typing import Any

_VISION_PART_TYPES = frozenset({"image_url", "input_image", "image"})


def _is_vision_part(item: Any) -> bool:
    if not isinstance(item, dict):
        return False
    ptype = str(item.get("type") or "").strip().lower()
    if ptype in _VISION_PART_TYPES:
        return True
    if item.get("image_url") is not None or item.get("input_image") is not None:
        return True
    return False


def content_has_vision_parts(content: Any) -> bool:
    if not isinstance(content, list):
        return False
    return any(_is_vision_part(item) for item in content)


def normalize_message_content(content: Any) -> Any:
    """Text-only messages become str; multimodal vision turns keep image parts."""
    if content is None:
        return ""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        if content_has_vision_parts(content):
            clean: list[Any] = []
            for item in content:
                if isinstance(item, str) and item.strip():
                    clean.append({"type": "text", "text": item.strip()})
                elif isinstance(item, dict):
                    clean.append(dict(item))
            return clean if clean else ""
        return parts_to_text(content)
    return str(content)


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
            m2["content"] = normalize_message_content(m2.get("content"))
            clean.append(m2)
        out["messages"] = clean
    tools = out.get("tools")
    if isinstance(tools, list):
        out["tools"] = [t for t in tools if isinstance(t, dict)]
    return out


# Hermes may send OpenAI/Anthropic extended-thinking fields; host Ollama rejects them.
OLLAMA_STRIP_KEYS = (
    "thinking",
    "reasoning_effort",
    "reasoning",
    "include_reasoning",
    "effort",
)


def sanitize_for_ollama(payload: dict[str, Any], *, strip_thinking: bool = True) -> dict[str, Any]:
    out = sanitize_chat_payload(payload)
    if strip_thinking:
        for key in OLLAMA_STRIP_KEYS:
            out.pop(key, None)
    return out


def ollama_model_rejects_thinking(model: str) -> bool:
    """Host Ollama chat models that 400 on extended-thinking request fields."""
    m = (model or "").lower()
    return "qwen2" in m or "qwen-2" in m


def should_strip_ollama_thinking(*, enable_qwen_thinking: bool, ollama_model: str) -> bool:
    if ollama_model_rejects_thinking(ollama_model):
        return True
    return not enable_qwen_thinking


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
            "capacity is busy",
            "retry shortly",
            "structurally heavy",
        )
    ):
        return True
    return normalize_chat_completion(data) is None


def chat_busy_capacity(status: int, data: Any) -> bool:
    """Omni free-tier capacity busy — worth sleeping before the next rotate hop."""
    if status not in {429, 503} and not (
        isinstance(data, dict) and data.get("error")
    ):
        return False
    msg = _error_text(data).lower()
    return any(
        needle in msg
        for needle in ("capacity is busy", "retry shortly", "structurally heavy")
    )


def chat_omni_skip_remaining(status: int, data: Any) -> bool:
    """Omni errors where retrying the same combo/failover id cannot succeed."""
    msg = _error_text(data).lower()
    # Omni UI / API variants for empty or dead hermes combo members.
    if "all upstream accounts are inactive" in msg:
        return True
    if "no available accounts" in msg or "no active accounts" in msg:
        return True
    if status == 503 and ("temporarily unavailable" in msg or "service unavailable" in msg):
        # Instant 503 on hermes/classifier (TI:0) — further Omni hops waste time.
        return True
    # Groq free TPM / request-too-large: Omni marks the whole Groq provider
    # exhausted and RR only hits more groq/* members (413 again). Skip Omni.
    if status == 413:
        return True
    if "request too large" in msg or "tokens per minute" in msg or "tpm" in msg:
        return True
    if "supports tool calling" in msg:
        return True
    return False


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
