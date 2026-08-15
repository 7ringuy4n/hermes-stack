"""SIEM sink (lab) — normalize security/ops events → Loki (+ local ring buffer).

Not a full enterprise SIEM; provides /v1/event ingest + query for lab correlation.
"""
from __future__ import annotations

import json
import os
import time
import urllib.request
from collections import deque
from typing import Any, Optional

from fastapi import FastAPI
from pydantic import BaseModel, Field

LOKI_URL = os.environ.get("LOKI_URL", "http://loki:3100").rstrip("/")
LISTEN = os.environ.get("LISTEN", "0.0.0.0:8105")
MAX_BUF = int(os.environ.get("SIEM_BUFFER", "2000"))

app = FastAPI(title="assistant-siem", version="1.0.0")
_buf: deque[dict[str, Any]] = deque(maxlen=MAX_BUF)


class Event(BaseModel):
    event: str
    fields: dict[str, Any] = Field(default_factory=dict)
    severity: str = "info"
    ts: Optional[float] = None
    source: str = "assistant"


def _loki_push(ev: dict[str, Any]) -> None:
    if not LOKI_URL:
        return
    try:
        ts_ns = str(int((ev.get("ts") or time.time()) * 1e9))
        line = json.dumps(ev, ensure_ascii=False)
        body = {
            "streams": [
                {
                    "stream": {
                        "job": "assistant-siem",
                        "event": ev.get("event") or "event",
                        "severity": ev.get("severity") or "info",
                        "source": ev.get("source") or "assistant",
                    },
                    "values": [[ts_ns, line]],
                }
            ]
        }
        req = urllib.request.Request(
            f"{LOKI_URL}/loki/api/v1/push",
            data=json.dumps(body).encode(),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        urllib.request.urlopen(req, timeout=5)
    except Exception:
        pass


@app.get("/health")
def health() -> dict[str, Any]:
    return {"ok": True, "buffered": len(_buf), "loki": LOKI_URL}


@app.post("/v1/event")
def ingest(ev: Event) -> dict[str, Any]:
    row = ev.model_dump()
    row["ts"] = row.get("ts") or time.time()
    _buf.append(row)
    _loki_push(row)
    return {"ok": True}


@app.get("/v1/events")
def recent(limit: int = 50, event: Optional[str] = None) -> dict[str, Any]:
    items = list(_buf)
    if event:
        items = [i for i in items if i.get("event") == event]
    return {"ok": True, "items": items[-limit:]}
