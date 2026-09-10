"""Policy Center — Day-2 lab policy store + evaluate (not Keycloak).

Stores named policies; /v1/evaluate returns allow/deny for resource actions.
Authz remains source of workspace ACL; this adds cross-cutting policy rules.
"""
from __future__ import annotations

import json
import os
import time
import uuid
from typing import Any, Optional

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

STORE = os.environ.get("POLICY_STORE", "/data/policies.json")
SIEM_URL = os.environ.get("SIEM_URL", "").rstrip("/")

app = FastAPI(title="assistant-policy-center", version="1.0.0")


def _store_path() -> str:
    path = STORE
    try:
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        # probe write without leaving an empty JSON file
        probe = path + ".writetest"
        with open(probe, "w", encoding="utf-8") as f:
            f.write("ok")
        os.remove(probe)
        return path
    except Exception:
        fb = "/tmp/policies.json"
        print(f"[policy] WARN cannot write {path} — using {fb}", flush=True)
        return fb


def _load() -> dict[str, Any]:
    path = _store_path()
    if not os.path.isfile(path) or os.path.getsize(path) == 0:
        return {"policies": {}}
    with open(path, "r", encoding="utf-8") as f:
        try:
            data = json.load(f)
        except json.JSONDecodeError:
            return {"policies": {}}
    if not isinstance(data, dict):
        return {"policies": {}}
    data.setdefault("policies", {})
    return data


def _save(data: dict[str, Any]) -> None:
    path = _store_path()
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


def _siem(event: str, **fields: Any) -> None:
    if not SIEM_URL:
        return
    try:
        import urllib.request

        body = json.dumps({"event": event, "fields": fields, "ts": time.time()}).encode()
        req = urllib.request.Request(
            f"{SIEM_URL}/v1/event",
            data=body,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        urllib.request.urlopen(req, timeout=3)
    except Exception:
        pass


class Policy(BaseModel):
    name: str
    description: str = ""
    effect: str = "deny"  # allow | deny
    actions: list[str] = Field(default_factory=lambda: ["*"])
    resources: list[str] = Field(default_factory=lambda: ["*"])
    enabled: bool = True


class EvaluateReq(BaseModel):
    action: str
    resource: str
    subject: Optional[str] = None
    workspace_id: Optional[str] = None
    context: dict[str, Any] = Field(default_factory=dict)


@app.on_event("startup")
def startup() -> None:
    data = _load()
    if not data.get("policies"):
        # default deny-sensitive + allow knowledge read in-workspace
        data["policies"] = {
            "default-deny-export": Policy(
                name="default-deny-export",
                description="Deny outbound document export",
                effect="deny",
                actions=["export", "outbound.doc"],
                resources=["*"],
            ).model_dump(),
            "allow-knowledge-read": Policy(
                name="allow-knowledge-read",
                description="Allow knowledge search when workspace set",
                effect="allow",
                actions=["knowledge.search", "rag.query"],
                resources=["knowledge_chunks"],
            ).model_dump(),
        }
        _save(data)


@app.get("/health")
def health() -> dict[str, Any]:
    return {"ok": True, "store": STORE, "count": len(_load().get("policies", {}))}


@app.get("/v1/policies")
def list_policies() -> dict[str, Any]:
    return {"ok": True, "policies": list(_load().get("policies", {}).values())}


@app.put("/v1/policies/{name}")
def upsert(name: str, pol: Policy) -> dict[str, Any]:
    pol.name = name
    data = _load()
    data.setdefault("policies", {})[name] = pol.model_dump()
    _save(data)
    _siem("policy.upsert", name=name, effect=pol.effect)
    return {"ok": True, "policy": pol.model_dump()}


@app.post("/v1/evaluate")
def evaluate(req: EvaluateReq) -> dict[str, Any]:
    """First matching deny wins; else first allow; else deny (default-deny)."""
    policies = [p for p in _load().get("policies", {}).values() if p.get("enabled", True)]
    matched = []
    for p in policies:
        acts = p.get("actions") or ["*"]
        ress = p.get("resources") or ["*"]
        act_ok = "*" in acts or req.action in acts
        res_ok = "*" in ress or req.resource in ress
        if act_ok and res_ok:
            matched.append(p)
            if p.get("effect") == "deny":
                _siem("policy.deny", action=req.action, resource=req.resource, policy=p.get("name"))
                return {"ok": True, "decision": "deny", "policy": p.get("name"), "matched": matched}
    for p in matched:
        if p.get("effect") == "allow":
            # knowledge read requires workspace when resource is knowledge_chunks
            if req.resource == "knowledge_chunks" and not req.workspace_id and not req.context.get("thread_id"):
                return {"ok": True, "decision": "deny", "policy": p.get("name"), "reason": "workspace_required"}
            _siem("policy.allow", action=req.action, resource=req.resource, policy=p.get("name"))
            return {"ok": True, "decision": "allow", "policy": p.get("name"), "matched": matched}
    _siem("policy.default_deny", action=req.action, resource=req.resource)
    return {"ok": True, "decision": "deny", "policy": "default-deny", "matched": matched}
