#!/usr/bin/env python3
"""Exercise actual adapter send ordering without booting a gateway."""
import ast
import asyncio
import logging
import sys
import types
from pathlib import Path
from typing import Any, Dict, Optional
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "hermes/main/plugins/zalo"))
tree = ast.parse((ROOT / "hermes/main/plugins/zalo/adapter.py").read_text(encoding="utf-8"))
adapter = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == "ZaloAdapter")
send = next(n for n in adapter.body if isinstance(n, ast.AsyncFunctionDef) and n.name == "send")
scope = dict(__name__="adapter_send_test", Any=Any, Dict=Dict, Optional=Optional, logger=logging.getLogger(__name__),
             _replica_count=lambda: 1, SendResult=lambda **kw: types.SimpleNamespace(**kw))
exec(compile(ast.Module(body=[send], type_ignores=[]), str(ROOT / "hermes/main/plugins/zalo/adapter.py"), "exec"), scope)


async def case(silent, pending):
    calls = []
    host = types.SimpleNamespace(_as_pending_note_persist={"dm": {"silent": silent}} if pending else {})
    host._as_autosend_wrong_thread = lambda *a: False
    async def autosend(*a):
        calls.append("autosend")
        return a[1]
    async def persist(*a):
        calls.append("persist")
        return "" if pending else a[1]
    host._as_autosend_turn_files = autosend
    host._as_kick_late_autosend = lambda *a: None
    host._rewrite_gateway_user_notice = lambda *a: None
    host._as_is_media_ack_only = lambda *a: False
    host._as_job_already_sent_file = lambda *a: calls.append("media-mute") or True
    host._as_persist_deferred_notes = persist
    probe = types.SimpleNamespace(is_blocked=lambda *a, **kw: False)
    with patch.dict(sys.modules, secret_probe=probe):
        result = await scope["send"](host, "dm", "Research body " * 20)
    assert result.success
    if pending:
        assert "persist" in calls and "media-mute" not in calls, calls
        if silent:
            assert "autosend" not in calls, calls
    else:
        assert calls == ["autosend", "persist", "media-mute"], calls


def main():
    for index, args in enumerate(((True, True), (False, True), (False, False)), 1):
        print(f"running test case {index}/3: note side effects versus media transport")
        asyncio.run(case(*args))
    print("PASS notes_media_silence_unit")


if __name__ == "__main__":
    main()
