"""Bounded classifier protocol repair uses the versioned prompt asset."""
from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "architect" / "models" / "router-worker"))

from classify import classify_with_llm, plan_schema_failure  # noqa: E402


class Response:
    status_code = 200

    def __init__(self, content: str):
        self.text = json.dumps(
            {"choices": [{"message": {"content": content}, "finish_reason": "stop"}]}
        )


class Client:
    def __init__(self, responses: list[Response]):
        self.responses = responses
        self.payloads: list[dict] = []

    async def post(self, _url, *, headers, json, timeout):
        assert headers.get("x-opencode-session") == "stable-conversation"
        assert timeout > 0
        self.payloads.append(json)
        return self.responses.pop(0)


async def run() -> None:
    multi_search_composed = {
        "ok": True,
        "task_hint": "file",
        "instructions": [
            "Retrieve current conditions",
            "Retrieve current product values",
            "RENDER: composed-image\nSCENE: balanced background",
        ],
        "task_details": [
            {"task_type": "search", "depends_on": []},
            {"task_type": "search", "depends_on": []},
            {"task_type": "media_generation", "depends_on": [0, 1]},
        ],
    }
    assert plan_schema_failure(multi_search_composed) == ""
    missing_dependency = json.loads(json.dumps(multi_search_composed))
    missing_dependency["task_details"][2]["depends_on"] = [0]
    assert (
        plan_schema_failure(missing_dependency)
        == "composed_image_media_must_depend_on_all_searches"
    )
    reversed_graph = json.loads(json.dumps(multi_search_composed))
    reversed_graph["task_details"] = [
        {"task_type": "media_generation", "depends_on": [1, 2]},
        {"task_type": "search", "depends_on": []},
        {"task_type": "search", "depends_on": []},
    ]
    assert (
        plan_schema_failure(reversed_graph)
        == "composed_image_searches_must_precede_media"
    )

    corrected = json.dumps(
        {
            "task_hint": "normal",
            "execution_class": "interactive",
            "task_type": "chat",
            "response_mode": "ack_then_deliver",
            "process_original_message": True,
            "instructions": ["Answer the request."],
            "reasoning_effort": "low",
        }
    )
    client = Client([Response("not-json"), Response(corrected)])
    plan = await classify_with_llm(
        "A normal request",
        timezone="Asia/Ho_Chi_Minh",
        client=client,
        n9_base="http://router.invalid/v1",
        n9_key="",
        model="classifier",
        extra_headers={"x-opencode-session": "stable-conversation"},
    )
    assert plan.get("ok") is True, plan
    assert len(client.payloads) == 2, len(client.payloads)
    repair_messages = client.payloads[1].get("messages") or []
    assert len(repair_messages) == 4, repair_messages
    assert repair_messages[-2] == {"role": "assistant", "content": "not-json"}
    assert "invalid_json" in str(repair_messages[-1].get("content") or "")
    assert "corrected minified JSON" in str(repair_messages[-1].get("content") or "")

    invalid_schedule = json.dumps(
        {
            "task_hint": "schedule",
            "execution_class": "schedule",
            "task_type": "create_schedule",
            "response_mode": "confirm",
            "process_original_message": False,
            "instructions": ["Run later."],
            "skill": "schedule",
            "skill_action": "create",
            "schedule_resolution": "clear",
            "reasoning_effort": "low",
        }
    )
    corrected_schedule = json.dumps(
        {
            "task_hint": "schedule",
            "execution_class": "schedule",
            "task_type": "create_schedule",
            "response_mode": "confirm",
            "process_original_message": False,
            "instructions": ["Run later."],
            "skill": "schedule",
            "skill_action": "create",
            "schedule_form": "once_after",
            "delay_seconds": 60,
            "schedule_resolution": "clear",
            "reasoning_effort": "low",
        }
    )
    schedule_client = Client(
        [Response(invalid_schedule), Response(corrected_schedule)]
    )
    schedule_plan = await classify_with_llm(
        "A timed request",
        timezone="Asia/Ho_Chi_Minh",
        client=schedule_client,
        n9_base="http://router.invalid/v1",
        n9_key="",
        model="classifier",
        extra_headers={"x-opencode-session": "stable-conversation"},
    )
    assert schedule_plan.get("delay_seconds") == 60, schedule_plan
    schedule_repair = schedule_client.payloads[1].get("messages") or []
    assert "schedule_requires_timing_or_explicit_uncertainty" in str(
        schedule_repair[-1].get("content") or ""
    )


if __name__ == "__main__":
    asyncio.run(run())
    print("router_worker_classify_repair_unit: PASS")
