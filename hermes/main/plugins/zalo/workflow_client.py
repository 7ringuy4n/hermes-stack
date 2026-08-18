"""HTTP client for the generic workflow service (Zalo adapter)."""
from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from typing import Any, Optional

DEFAULT_URL = "http://workflow:8108"


def workflow_url() -> str:
    return (os.getenv("WORKFLOW_URL") or DEFAULT_URL).rstrip("/")


def workflow_enabled() -> bool:
    raw = (os.getenv("HERMES_WORKFLOW") or os.getenv("ZALO_WORKFLOW") or "1").strip().lower()
    if raw in {"0", "off", "false", "no"}:
        return False
    return bool(workflow_url())


def _req(method: str, path: str, payload: Optional[dict] = None, timeout: float = 8.0) -> dict[str, Any]:
    url = workflow_url() + path
    data = None if payload is None else json.dumps(payload, ensure_ascii=False).encode("utf-8")
    r = urllib.request.Request(
        url,
        data=data,
        method=method,
        headers={"Content-Type": "application/json"} if data else {},
    )
    try:
        with urllib.request.urlopen(r, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8") or "{}")
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, OSError):
        return {}


def create_workflow(
    *,
    instructions: list[str],
    origin: dict[str, Any],
    context: dict[str, Any],
) -> dict[str, Any]:
    return _req(
        "POST",
        "/v1/workflows",
        {
            "instructions": instructions,
            "origin": origin,
            "context": context,
            "sequential": False,
            "wrap": True,
        },
    )


def create_schedule(
    *,
    cron_expr: str,
    text: str,
    name: str = "",
    origin: dict[str, Any] | None = None,
    context: dict[str, Any] | None = None,
    schedule_id: str | None = None,
    cadence: str = "",
) -> dict[str, Any]:
    body: dict[str, Any] = {
        "cron_expr": cron_expr,
        "text": text,
        "name": name,
        "origin": origin or {},
        "context": context or {},
        "timezone": "Asia/Ho_Chi_Minh",
        "cadence": cadence,
    }
    if schedule_id:
        body["id"] = schedule_id
    return _req("POST", "/v1/schedules", body)


def list_schedules() -> list[dict[str, Any]]:
    data = _req("GET", "/v1/schedules")
    rows = data.get("schedules") if isinstance(data, dict) else None
    return rows if isinstance(rows, list) else []


def delete_schedule(sid: str) -> dict[str, Any]:
    return _req("DELETE", f"/v1/schedules/{sid}")


def claim_job(worker_id: str) -> Optional[dict[str, Any]]:
    data = _req("POST", f"/v1/worker/claim?worker_id={worker_id}&execute=hermes")
    job = data.get("job") if isinstance(data, dict) else None
    return job if isinstance(job, dict) else None


def complete_job(job_id: str, result: dict[str, Any] | None = None) -> dict[str, Any]:
    return _req("POST", f"/v1/jobs/{job_id}/complete", {"result": result or {"ok": True}})


def fail_job(job_id: str, error: str) -> dict[str, Any]:
    return _req("POST", f"/v1/jobs/{job_id}/fail", {"error": error[:500]})


def heartbeat(job_id: str, worker_id: str) -> None:
    _req("POST", f"/v1/jobs/{job_id}/heartbeat?worker_id={worker_id}", {})
