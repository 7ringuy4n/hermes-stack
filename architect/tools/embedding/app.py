"""Embedding + lightweight rerank layer (OpenAI-compatible upstream via 9Router)."""
from __future__ import annotations

import math
import os
from typing import Any, Optional

import httpx
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

UPSTREAM = os.environ.get("EMBED_UPSTREAM", "http://9router:20128/v1").rstrip("/")
API_KEY = os.environ.get("EMBED_API_KEY", os.environ.get("OPENAI_API_KEY", ""))
MODEL = os.environ.get("EMBED_MODEL", "openai/text-embedding-3-small")

app = FastAPI(title="assistant-embedding", version="1.1.0")


class EmbedReq(BaseModel):
    input: str | list[str]
    model: Optional[str] = None


class RerankDoc(BaseModel):
    id: str
    text: str


class RerankReq(BaseModel):
    query: str
    documents: list[RerankDoc]
    top_k: int = 5


def _headers() -> dict[str, str]:
    h = {"Content-Type": "application/json"}
    if API_KEY:
        h["Authorization"] = f"Bearer {API_KEY}"
    return h


def _cosine(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a)) or 1e-9
    nb = math.sqrt(sum(y * y for y in b)) or 1e-9
    return dot / (na * nb)


def _err_detail(resp: httpx.Response) -> str:
    try:
        data = resp.json()
        if isinstance(data, dict):
            return str(data.get("error") or data.get("detail") or data.get("message") or data)[:240]
    except Exception:
        pass
    return (resp.text or resp.reason_phrase or "")[:240]


def _embed_once(model: str, payload_input: str | list[str]) -> dict[str, Any]:
    with httpx.Client(timeout=60) as c:
        resp = c.post(
            f"{UPSTREAM}/embeddings",
            headers=_headers(),
            json={"model": model, "input": payload_input},
        )
        if resp.status_code >= 300:
            raise httpx.HTTPStatusError(
                f"upstream {resp.status_code}: {_err_detail(resp)}",
                request=resp.request,
                response=resp,
            )
        return resp.json()


def _list_embed_models() -> list[str]:
    ids: list[str] = []
    with httpx.Client(timeout=10) as c:
        for path in ("/models/embedding", "/models"):
            try:
                r = c.get(f"{UPSTREAM}{path}", headers=_headers())
                if r.status_code >= 300:
                    continue
                data = r.json().get("data") or []
                for d in data:
                    mid = str((d or {}).get("id") or "").strip()
                    if mid and mid not in ids:
                        ids.append(mid)
                if path == "/models/embedding" and ids:
                    return ids
            except Exception:
                continue
    return [i for i in ids if "embed" in i.lower() or "voyage" in i.lower() or "jina" in i.lower()]


def _candidates(requested: str) -> list[str]:
    raw = (requested or MODEL or "").strip()
    out: list[str] = []
    for m in (raw, MODEL):
        if m and m not in out:
            out.append(m)
    if raw and "/" not in raw:
        for p in (f"openai/{raw}", f"openai-compatible/{raw}"):
            if p not in out:
                out.append(p)
    try:
        catalog = _list_embed_models()
    except Exception:
        catalog = []
    prefer = [m for m in catalog if "text-embedding-3-small" in m or m.endswith("/text-embedding-3-small")]
    for m in prefer + catalog:
        if m not in out:
            out.append(m)
    return out


@app.get("/health")
def health() -> dict[str, Any]:
    return {
        "ok": True,
        "upstream": UPSTREAM,
        "model": MODEL,
        "has_key": bool(API_KEY),
    }


@app.post("/v1/embeddings")
@app.post("/embeddings")
def embeddings(req: EmbedReq) -> dict[str, Any]:
    if not API_KEY:
        raise HTTPException(503, "EMBED_API_KEY not configured")
    last = "embedding upstream unavailable"
    for model in _candidates(req.model or MODEL):
        try:
            data = _embed_once(model, req.input)
            if isinstance(data, dict) and data.get("data"):
                data.setdefault("model", model)
                return data
            last = f"{model}: empty response"
        except httpx.HTTPStatusError as exc:
            last = f"{model}: {exc}"[:240]
            continue
        except Exception as exc:
            last = f"{model}: {type(exc).__name__}: {exc}"[:240]
            continue
    raise HTTPException(502, last)


@app.post("/v1/rerank")
def rerank(req: RerankReq) -> dict[str, Any]:
    """Local cosine rerank using embeddings (no extra model required)."""
    if not req.documents:
        return {"results": []}
    try:
        q = embeddings(EmbedReq(input=req.query))
        qv = q["data"][0]["embedding"]
        texts = [d.text for d in req.documents]
        emb = embeddings(EmbedReq(input=texts))
        scored = []
        for doc, item in zip(req.documents, emb["data"]):
            scored.append(
                {
                    "id": doc.id,
                    "score": _cosine(qv, item["embedding"]),
                    "text": doc.text[:500],
                }
            )
        scored.sort(key=lambda x: x["score"], reverse=True)
        return {"results": scored[: max(1, req.top_k)]}
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(502, "rerank failed") from None
