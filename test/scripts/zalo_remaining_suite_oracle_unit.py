#!/usr/bin/env python3
"""Keep the remaining live suite on the durable delivery oracle."""
from __future__ import annotations

import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
TARGET = ROOT / "test" / "scripts" / "zalo_tn_remaining_suite_remote.py"
SPEC = importlib.util.spec_from_file_location("remaining_suite_remote", TARGET)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)

calls: list[list[str]] = []


def fake_check_output(cmd, **_kwargs):
    calls.append(list(cmd))
    if cmd[:3] == ["docker", "ps", "-q"]:
        return "zalo-api-container\n"
    if cmd[:2] == ["docker", "exec"]:
        probe = cmd[-1]
        assert "event='delivered'" in probe
        if "delivery_kind'='gate'" in probe:
            return "1\n"
        assert "attachment_kind" in probe
        assert "queue_recovery" in probe
        return '{"content":"accepted result","meta":{"attachment_kind":"image"}}\n'
    raise AssertionError(cmd)


MODULE.TN = "runtime-test-id"
MODULE.subprocess.check_output = fake_check_output
MODULE.plugin_logs = lambda *_args, **_kwargs: (_ for _ in ()).throw(
    AssertionError("journal echo must not be the delivery oracle")
)

result = MODULE.wait_zalo_delivery(
    123.5, source_id="suite-source", photo=True, wait_s=1
)
assert result["content"] == "accepted result"
assert MODULE.schedule_ack_count(123.5, "schedule-source") == 1
assert any("LAB_SOURCE_ID=suite-source" in item for cmd in calls for item in cmd)
assert any("LAB_SOURCE_ID=schedule-source" in item for cmd in calls for item in cmd)
assert any(cmd[:2] == ["docker", "exec"] for cmd in calls)
print("zalo_remaining_suite_oracle_unit: PASS")
