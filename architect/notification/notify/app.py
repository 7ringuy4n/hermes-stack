"""NotificationManager — alerts + digests to Zalo / Telegram / Email / SMS.

Never used for background self-learn chatter to end users.
"""
from __future__ import annotations

import os
import re
import smtplib
import time
from email.message import EmailMessage
from enum import Enum
from typing import Any, Optional

import httpx
from fastapi import FastAPI
from pydantic import BaseModel, Field

ZALO_BRIDGE = os.environ.get("ZALO_BRIDGE_URL", "http://host.docker.internal:8787").rstrip("/")
ZALO_TOKEN = os.environ.get("ZALO_PLUGIN_TOKEN", "")
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
SMTP_HOST = os.environ.get("SMTP_HOST", "")
SMTP_PORT = int(os.environ.get("SMTP_PORT", "587"))
SMTP_USER = os.environ.get("SMTP_USER", "")
SMTP_PASS = os.environ.get("SMTP_PASS", "")
SMTP_FROM = os.environ.get("SMTP_FROM", SMTP_USER)
DEFAULT_ZALO_THREAD = os.environ.get("NOTIFY_ZALO_THREAD", "").strip()
# user = DM admin; group = group thread. Default user when unset (admin inbox).
DEFAULT_ZALO_THREAD_TYPE = (
    os.environ.get("NOTIFY_ZALO_THREAD_TYPE", "user").strip().lower() or "user"
)
DEFAULT_TELEGRAM_CHAT = os.environ.get("NOTIFY_TELEGRAM_CHAT", "")

app = FastAPI(title="assistant-notify", version="1.1.0")
_log: list[dict[str, Any]] = []


class Severity(str, Enum):
    info = "info"
    warning = "warning"
    critical = "critical"


class Channel(str, Enum):
    zalo = "zalo"
    telegram = "telegram"
    email = "email"
    sms = "sms"
    log = "log"


class NotifyReq(BaseModel):
    title: str
    body: str
    severity: Severity = Severity.info
    channels: list[Channel] = Field(default_factory=lambda: [Channel.log])
    zalo_thread_id: Optional[str] = None
    zalo_thread_type: Optional[str] = None  # user | group
    telegram_chat_id: Optional[str] = None
    email_to: Optional[str] = None
    sms_to: Optional[str] = None
    kind: str = "alert"  # alert | summary


def _norm_thread_type(raw: Optional[str]) -> str:
    t = (raw or DEFAULT_ZALO_THREAD_TYPE or "user").strip().lower()
    if t in {"group", "groups"}:
        return "group"
    return "user"


def _zalo_send(thread_id: str, text: str, thread_type: str = "user") -> bool:
    headers = {"content-type": "application/json"}
    if ZALO_TOKEN:
        headers["x-bridge-token"] = ZALO_TOKEN
    tt = _norm_thread_type(thread_type)
    try:
        with httpx.Client(timeout=30) as c:
            r = c.post(
                f"{ZALO_BRIDGE}/send",
                headers=headers,
                json={
                    "threadId": thread_id,
                    "threadType": tt,
                    "text": text[:3500],
                },
            )
            return r.status_code < 300
    except Exception:
        return False


def _telegram_send(chat_id: str, text: str) -> bool:
    if not TELEGRAM_BOT_TOKEN:
        return False
    try:
        with httpx.Client(timeout=30) as c:
            r = c.post(
                f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage",
                json={"chat_id": chat_id, "text": text[:4000]},
            )
            return r.status_code < 300
    except Exception:
        return False


def _email_send(to: str, subject: str, body: str) -> bool:
    if not SMTP_HOST or not to:
        return False
    try:
        msg = EmailMessage()
        msg["From"] = SMTP_FROM
        msg["To"] = to
        msg["Subject"] = subject
        msg.set_content(body)
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=30) as s:
            s.starttls()
            if SMTP_USER:
                s.login(SMTP_USER, SMTP_PASS)
            s.send_message(msg)
        return True
    except Exception:
        return False


@app.get("/health")
def health() -> dict[str, Any]:
    return {
        "ok": True,
        "zalo_bridge": bool(ZALO_BRIDGE),
        "zalo_thread": bool(DEFAULT_ZALO_THREAD),
        "zalo_thread_type": _norm_thread_type(DEFAULT_ZALO_THREAD_TYPE),
        "telegram": bool(TELEGRAM_BOT_TOKEN),
        "smtp": bool(SMTP_HOST),
    }


_LLM_NOISE_RE = re.compile(
    r"llm provider|lastError|model_not_found|was retired|no longer available|"
    r"provider test not supported|test not supported|kilo-gateway|kilo-john|"
    r"minimax|gpt-oss-120b|kimi-k2|ollama-ntri|Provider ollama|"
    r"request too large|oneOf at '/' not met|AiError: Bad input|"
    r"\[410\]|\[413\]|\[400\]",
    re.I,
)


def _llm_noise(req: NotifyReq) -> bool:
    """LLM provider chatter (retired model, 400, 410, 413, unsupported) — CRITICAL only."""
    if req.severity == Severity.critical:
        blob = f"{req.title}\n{req.body}"
        if re.search(r"429|quota|billing|insufficient.?quota|rate.?limit", blob, re.I):
            return False
        # Non-quota "critical" mis-tags still suppressed
        if _LLM_NOISE_RE.search(blob):
            return True
        return False
    title = (req.title or "").lower()
    body = (req.body or "")
    kind = (req.kind or "").lower()
    if title.startswith("llm ") or "llm provider" in title or kind == "llm":
        return True
    return bool(_LLM_NOISE_RE.search(f"{req.title}\n{body}"))


@app.post("/v1/notify")
def notify(req: NotifyReq) -> dict[str, Any]:
    if _llm_noise(req):
        entry = {
            "ts": time.time(),
            "kind": req.kind,
            "severity": req.severity.value,
            "title": req.title,
            "results": {"skipped": True, "reason": "llm_non_critical"},
        }
        _log.append(entry)
        return {"ok": True, "results": {"skipped": True}, "reason": "llm_non_critical"}
    prefix = {"info": "ℹ️", "warning": "⚠️", "critical": "🚨"}.get(req.severity.value, "")
    text = f"{prefix} [{req.severity.value.upper()}] {req.title}\n{req.body}".strip()
    results: dict[str, bool] = {}
    for ch in req.channels:
        if ch == Channel.log:
            results["log"] = True
        elif ch == Channel.zalo:
            tid = (req.zalo_thread_id or DEFAULT_ZALO_THREAD or "").strip()
            tt = _norm_thread_type(req.zalo_thread_type)
            results["zalo"] = bool(tid) and _zalo_send(tid, text, tt)
        elif ch == Channel.telegram:
            cid = req.telegram_chat_id or DEFAULT_TELEGRAM_CHAT
            results["telegram"] = bool(cid) and _telegram_send(cid, text)
        elif ch == Channel.email:
            results["email"] = _email_send(req.email_to or "", req.title, req.body)
        elif ch == Channel.sms:
            # Provider hook — log only until SMS gateway configured
            results["sms"] = False
    entry = {
        "ts": time.time(),
        "kind": req.kind,
        "severity": req.severity.value,
        "title": req.title,
        "results": results,
    }
    _log.append(entry)
    if len(_log) > 500:
        del _log[:250]
    return {"ok": True, "results": results}


@app.post("/v1/alert")
def alert(req: NotifyReq) -> dict[str, Any]:
    """Immediate operational alert (virus, quota, unusual access, …)."""
    req.kind = "alert"
    if not req.channels or req.channels == [Channel.log]:
        req.channels = [Channel.log, Channel.zalo, Channel.telegram]
    return notify(req)


@app.post("/v1/summary")
def summary(req: NotifyReq) -> dict[str, Any]:
    """Weekly / scheduled digest (e.g. Sunday backup summary)."""
    req.kind = "summary"
    req.severity = Severity.info
    return notify(req)


@app.get("/v1/recent")
def recent(limit: int = 20) -> dict[str, Any]:
    return {"items": _log[-limit:]}
