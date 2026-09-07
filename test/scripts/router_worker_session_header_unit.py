#!/usr/bin/env python3
"""Contract checks for privacy-preserving OpenCode session correlation."""
from __future__ import annotations

import importlib.util
import os
from pathlib import Path


def load_module(path: Path):
    spec = importlib.util.spec_from_file_location("router_worker_session_headers", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main() -> int:
    root = Path(__file__).resolve().parents[2]
    module = load_module(
        root / "architect" / "models" / "router-worker" / "session_headers.py"
    )
    previous = os.environ.get("OPENCODE_SESSION_NAMESPACE")
    os.environ["OPENCODE_SESSION_NAMESPACE"] = "unit-namespace"
    try:
        raw_a = "private-conversation-a"
        raw_b = "private-conversation-b"
        first = module.opencode_session({}, {"conversation_id": raw_a})
        repeat = module.opencode_session({}, {"conversation_id": raw_a})
        other = module.opencode_session({}, {"conversation_id": raw_b})
        assert first == repeat
        assert first != other
        assert first.startswith("ocg-") and len(first) == 44
        assert raw_a not in first and raw_b not in other

        incoming = module.opencode_session(
            {"x-opencode-session": "caller-session"}, {"conversation_id": raw_a}
        )
        assert incoming != first
        assert "caller-session" not in incoming

        history = {
            "messages": [
                {"role": "system", "content": "system"},
                {"role": "user", "content": "first turn"},
                {"role": "assistant", "content": "answer"},
            ]
        }
        assert module.opencode_session({}, history) == module.opencode_session({}, history)
        stateless_now = module.opencode_session({}, {"text": "current request"})
        stateless_repeat = module.opencode_session({}, {"text": "current request"})
        stateless_other = module.opencode_session({}, {"text": "scheduled request"})
        assert stateless_now == stateless_repeat
        assert stateless_now != stateless_other
        assert "current request" not in stateless_now
        structured_a = module.opencode_session({}, {"input": [{"value": "a"}]})
        structured_b = module.opencode_session({}, {"input": [{"value": "b"}]})
        assert structured_a != structured_b
        headers = module.with_opencode_session({"Authorization": "Bearer redacted"}, first)
        assert headers["x-opencode-session"] == first
        assert headers["Authorization"] == "Bearer redacted"

        app_source = (
            root / "architect" / "models" / "router-worker" / "app.py"
        ).read_text(encoding="utf-8")
        classify_source = (
            root / "architect" / "models" / "router-worker" / "classify.py"
        ).read_text(encoding="utf-8")
        client_source = (
            root / "hermes" / "main" / "plugins" / "zalo" / "classify_client.py"
        ).read_text(encoding="utf-8")
        dockerfile = (
            root / "architect" / "models" / "router-worker" / "Dockerfile"
        ).read_text(encoding="utf-8")
        assert app_source.count("opencode_session(request.headers, body)") == 3
        assert "request_headers = with_opencode_session(headers, provider_session)" in app_source
        assert classify_source.count("headers.update(extra_headers)") == 2
        assert '"conversation_id": conversation_id or ""' in client_source
        assert "session_headers.py" in dockerfile
    finally:
        if previous is None:
            os.environ.pop("OPENCODE_SESSION_NAMESPACE", None)
        else:
            os.environ["OPENCODE_SESSION_NAMESPACE"] = previous
    print("router_worker_session_header_unit: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
