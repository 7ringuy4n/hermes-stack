#!/usr/bin/env python3
"""Scrape 9Router / OmniRoute dashboard usage APIs → Prometheus metrics.

Env:
  LISTEN, SCRAPE_INTERVAL
  METRIC_PREFIX   default n9router  (use omnirouter for OmniRoute)
  ROUTER_URL      default N9ROUTER_URL / http://9router:20128
  ROUTER_PASSWORD default N9ROUTER_PASSWORD
"""
from __future__ import annotations

import json
import os
import threading
import time
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any

LISTEN = os.environ.get("LISTEN", "0.0.0.0:9101")
METRIC_PREFIX = os.environ.get("METRIC_PREFIX", "n9router").strip() or "n9router"
ROUTER_URL = (
    os.environ.get("ROUTER_URL")
    or os.environ.get("N9ROUTER_URL")
    or "http://9router:20128"
).rstrip("/")
ROUTER_PASSWORD = os.environ.get("ROUTER_PASSWORD") or os.environ.get("N9ROUTER_PASSWORD") or ""
SCRAPE_INTERVAL = float(os.environ.get("SCRAPE_INTERVAL", "30"))

_lock = threading.Lock()
_metrics_text = "# scrape pending\n"
_cookie = ""
_cookie_at = 0.0


def _m(name: str) -> str:
    return f"{METRIC_PREFIX}_{name}"


def _login() -> str:
    global _cookie, _cookie_at
    if not ROUTER_PASSWORD:
        raise RuntimeError("ROUTER_PASSWORD is empty")
    body = json.dumps({"password": ROUTER_PASSWORD}).encode()
    req = urllib.request.Request(
        f"{ROUTER_URL}/api/auth/login",
        data=body,
        headers={"content-type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=15) as resp:
        raw = resp.headers.get("Set-Cookie") or ""
        token = raw.split(";")[0].strip()
        if not token.startswith("auth_token="):
            raise RuntimeError(f"login missing auth_token cookie: {raw!r}")
        _cookie = token
        _cookie_at = time.time()
        return _cookie


def _get_json(path: str, optional: bool = False) -> Any:
    global _cookie
    if not _cookie or (time.time() - _cookie_at) > 20 * 3600:
        _login()
    req = urllib.request.Request(
        f"{ROUTER_URL}{path}",
        headers={"Cookie": _cookie, "Accept": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            return json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        if e.code in (401, 403):
            _login()
            req = urllib.request.Request(
                f"{ROUTER_URL}{path}",
                headers={"Cookie": _cookie, "Accept": "application/json"},
            )
            with urllib.request.urlopen(req, timeout=20) as resp:
                return json.loads(resp.read().decode())
        if optional and e.code == 404:
            return {}
        raise


def _esc(label: str) -> str:
    return (
        label.replace("\\", "\\\\")
        .replace("\n", "\\n")
        .replace('"', '\\"')
    )


def _line(name: str, value: float, labels: dict[str, str] | None = None) -> str:
    if labels:
        parts = ",".join(f'{k}="{_esc(v)}"' for k, v in labels.items())
        return f"{name}{{{parts}}} {value}"
    return f"{name} {value}"


def _as_breakdown_map(
    raw: Any, *, prefer: tuple[str, ...] = ("provider", "model", "name", "key", "id")
) -> dict[str, dict[str, Any]]:
    """Normalize byProvider/byModel from dict or list-of-rows into a dict map."""
    out: dict[str, dict[str, Any]] = {}
    if isinstance(raw, dict):
        for key, row in raw.items():
            if isinstance(row, dict):
                out[str(key)] = row
        return out
    if isinstance(raw, list):
        for row in raw:
            if not isinstance(row, dict):
                continue
            key = ""
            for field in prefer:
                val = row.get(field)
                if val is not None and str(val).strip():
                    key = str(val).strip()
                    break
            if not key:
                continue
            out[key] = row
    return out


def _coerce_usage(payload: Any) -> dict[str, Any]:
    """Map OmniRoute/9Router usage JSON into the flat fields Grafana panels expect."""
    if not isinstance(payload, dict) or not payload:
        return {}
    summary = payload.get("summary") if isinstance(payload.get("summary"), dict) else {}
    # Prefer nested analytics.summary totals when present; else top-level history fields.
    total_requests = payload.get("totalRequests")
    if total_requests is None:
        total_requests = summary.get("totalRequests")
    prompt = payload.get("totalPromptTokens")
    if prompt is None:
        prompt = summary.get("promptTokens", summary.get("totalPromptTokens"))
    completion = payload.get("totalCompletionTokens")
    if completion is None:
        completion = summary.get("completionTokens", summary.get("totalCompletionTokens"))
    cached = payload.get("totalCachedTokens")
    if cached is None:
        cached = summary.get("cachedTokens", summary.get("totalCachedTokens"))
    cost = payload.get("totalCost")
    if cost is None:
        cost = summary.get("totalCost")
    by_provider = _as_breakdown_map(
        payload.get("byProvider"), prefer=("provider", "name", "key", "id", "model")
    )
    by_model = _as_breakdown_map(
        payload.get("byModel"), prefer=("model", "rawModel", "key", "name", "id", "provider")
    )
    # Treat empty analytics shells as miss so older paths can still be tried.
    if (
        total_requests is None
        and prompt is None
        and completion is None
        and cost is None
        and not by_provider
        and not by_model
    ):
        return {}
    return {
        "totalRequests": float(total_requests or 0),
        "totalPromptTokens": float(prompt or 0),
        "totalCompletionTokens": float(completion or 0),
        "totalCachedTokens": float(cached or 0),
        "totalCost": float(cost or 0),
        "byProvider": by_provider,
        "byModel": by_model,
    }


def _fetch_usage() -> dict[str, Any]:
    # OmniRoute current: /api/usage/history (flat) and /api/usage/analytics (summary+lists).
    # Older 9Router paths kept for compatibility.
    for path in (
        "/api/usage/history",
        "/api/usage/analytics",
        "/api/usage/stats",
        "/api/stats/usage",
        "/api/analytics/usage",
    ):
        raw = _get_json(path, optional=True) or {}
        usage = _coerce_usage(raw)
        if usage:
            return usage
    return {}


def render_metrics() -> str:
    lines: list[str] = [
        f"# HELP {_m('scrape_success')} 1 if last scrape ok",
        f"# TYPE {_m('scrape_success')} gauge",
        f"# HELP {_m('scrape_timestamp_seconds')} Unix time of last successful scrape",
        f"# TYPE {_m('scrape_timestamp_seconds')} gauge",
        f"# HELP {_m('requests_total')} Cumulative LLM requests",
        f"# TYPE {_m('requests_total')} counter",
        f"# HELP {_m('prompt_tokens_total')} Cumulative prompt tokens",
        f"# TYPE {_m('prompt_tokens_total')} counter",
        f"# HELP {_m('completion_tokens_total')} Cumulative completion tokens",
        f"# TYPE {_m('completion_tokens_total')} counter",
        f"# HELP {_m('cached_tokens_total')} Cumulative cached tokens",
        f"# TYPE {_m('cached_tokens_total')} counter",
        f"# HELP {_m('cost_usd_total')} Cumulative estimated cost USD",
        f"# TYPE {_m('cost_usd_total')} counter",
        f"# HELP {_m('provider_requests_total')} Requests by provider",
        f"# TYPE {_m('provider_requests_total')} counter",
        f"# HELP {_m('provider_cost_usd_total')} Cost by provider",
        f"# TYPE {_m('provider_cost_usd_total')} counter",
        f"# HELP {_m('model_requests_total')} Requests by model",
        f"# TYPE {_m('model_requests_total')} counter",
        f"# HELP {_m('model_cost_usd_total')} Cost by model",
        f"# TYPE {_m('model_cost_usd_total')} counter",
        f"# HELP {_m('provider_active')} Provider connection active (1/0)",
        f"# TYPE {_m('provider_active')} gauge",
        f"# HELP {_m('provider_expires_unix')} OAuth/token expiry unix seconds",
        f"# TYPE {_m('provider_expires_unix')} gauge",
        f"# HELP {_m('provider_has_error')} 1 if lastError set",
        f"# TYPE {_m('provider_has_error')} gauge",
        f"# HELP {_m('combos')} Combo count",
        f"# TYPE {_m('combos')} gauge",
        f"# HELP {_m('models')} Model count from /v1/models",
        f"# TYPE {_m('models')} gauge",
    ]
    try:
        usage = _fetch_usage()
        providers = _get_json("/api/providers", optional=True) or {}
        combos = _get_json("/api/combos", optional=True) or {}
        models_payload = _get_json("/v1/models", optional=True) or {}
        now = time.time()
        lines.append(_line(_m("scrape_success"), 1))
        lines.append(_line(_m("scrape_timestamp_seconds"), now))
        lines.append(_line(_m("requests_total"), float(usage.get("totalRequests") or 0)))
        lines.append(_line(_m("prompt_tokens_total"), float(usage.get("totalPromptTokens") or 0)))
        lines.append(
            _line(_m("completion_tokens_total"), float(usage.get("totalCompletionTokens") or 0))
        )
        lines.append(_line(_m("cached_tokens_total"), float(usage.get("totalCachedTokens") or 0)))
        lines.append(_line(_m("cost_usd_total"), float(usage.get("totalCost") or 0)))
        lines.append(_line(_m("combos"), float(combos.get("total") or len(combos.get("combos") or []))))
        model_rows = models_payload.get("data") or []
        lines.append(_line(_m("models"), float(len(model_rows) if isinstance(model_rows, list) else 0)))

        for provider, row in (usage.get("byProvider") or {}).items():
            labels = {"provider": str(provider)}
            lines.append(
                _line(_m("provider_requests_total"), float(row.get("requests") or 0), labels)
            )
            lines.append(_line(_m("provider_cost_usd_total"), float(row.get("cost") or 0), labels))

        for model, row in (usage.get("byModel") or {}).items():
            labels = {
                "model": str(model),
                "provider": str(row.get("provider") or "unknown"),
                "raw_model": str(row.get("rawModel") or model),
            }
            lines.append(
                _line(_m("model_requests_total"), float(row.get("requests") or 0), labels)
            )
            lines.append(_line(_m("model_cost_usd_total"), float(row.get("cost") or 0), labels))

        for conn in providers.get("connections") or []:
            labels = {
                "provider": str(conn.get("provider") or "unknown"),
                "name": str(conn.get("name") or conn.get("email") or conn.get("id") or ""),
                "auth_type": str(conn.get("authType") or ""),
                "plan": str(
                    (conn.get("providerSpecificData") or {}).get("chatgptPlanType") or ""
                ),
            }
            lines.append(
                _line(_m("provider_active"), 1.0 if conn.get("isActive") else 0.0, labels)
            )
            exp = conn.get("expiresAt")
            exp_unix = 0.0
            if isinstance(exp, str) and exp:
                try:
                    from datetime import datetime

                    exp_unix = datetime.fromisoformat(exp.replace("Z", "+00:00")).timestamp()
                except Exception:
                    exp_unix = 0.0
            lines.append(_line(_m("provider_expires_unix"), exp_unix, labels))
            lines.append(
                _line(_m("provider_has_error"), 1.0 if conn.get("lastError") else 0.0, labels)
            )
    except Exception as e:
        lines.append(_line(_m("scrape_success"), 0))
        lines.append(f"# HELP {_m('scrape_error_info')} Last scrape error (always 1 with label)")
        lines.append(f"# TYPE {_m('scrape_error_info')} gauge")
        lines.append(_line(_m("scrape_error_info"), 1, {"error": str(e)[:180]}))
    lines.append("")
    return "\n".join(lines)


def scraper_loop() -> None:
    global _metrics_text
    while True:
        text = render_metrics()
        with _lock:
            _metrics_text = text
        time.sleep(SCRAPE_INTERVAL)


class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt: str, *args: Any) -> None:
        return

    def do_GET(self) -> None:  # noqa: N802
        if self.path not in ("/metrics", "/"):
            self.send_response(404)
            self.end_headers()
            return
        with _lock:
            body = _metrics_text.encode()
        self.send_response(200)
        self.send_header("Content-Type", "text/plain; version=0.0.4; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def main() -> None:
    host, _, port_s = LISTEN.partition(":")
    port = int(port_s or "9101")
    threading.Thread(target=scraper_loop, daemon=True).start()
    time.sleep(0.2)
    httpd = ThreadingHTTPServer((host or "0.0.0.0", port), Handler)
    print(f"router-exporter {METRIC_PREFIX} on {host}:{port} -> {ROUTER_URL}", flush=True)
    httpd.serve_forever()


if __name__ == "__main__":
    main()
