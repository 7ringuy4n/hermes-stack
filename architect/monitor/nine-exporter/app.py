#!/usr/bin/env python3
"""Scrape 9Router dashboard usage APIs → Prometheus metrics."""
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
N9ROUTER_URL = os.environ.get("N9ROUTER_URL", "http://9router:20128").rstrip("/")
N9ROUTER_PASSWORD = os.environ.get("N9ROUTER_PASSWORD", "")
SCRAPE_INTERVAL = float(os.environ.get("SCRAPE_INTERVAL", "30"))

_lock = threading.Lock()
_metrics_text = "# scrape pending\n"
_cookie = ""
_cookie_at = 0.0


def _login() -> str:
    global _cookie, _cookie_at
    if not N9ROUTER_PASSWORD:
        raise RuntimeError("N9ROUTER_PASSWORD is empty")
    body = json.dumps({"password": N9ROUTER_PASSWORD}).encode()
    req = urllib.request.Request(
        f"{N9ROUTER_URL}/api/auth/login",
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


def _get_json(path: str) -> Any:
    global _cookie
    if not _cookie or (time.time() - _cookie_at) > 20 * 3600:
        _login()
    req = urllib.request.Request(
        f"{N9ROUTER_URL}{path}",
        headers={"Cookie": _cookie, "Accept": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            return json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        if e.code in (401, 403):
            _login()
            req = urllib.request.Request(
                f"{N9ROUTER_URL}{path}",
                headers={"Cookie": _cookie, "Accept": "application/json"},
            )
            with urllib.request.urlopen(req, timeout=20) as resp:
                return json.loads(resp.read().decode())
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


def render_metrics() -> str:
    lines: list[str] = [
        "# HELP n9router_scrape_success 1 if last scrape ok",
        "# TYPE n9router_scrape_success gauge",
        "# HELP n9router_scrape_timestamp_seconds Unix time of last successful scrape",
        "# TYPE n9router_scrape_timestamp_seconds gauge",
        "# HELP n9router_requests_total Cumulative LLM requests via 9Router",
        "# TYPE n9router_requests_total counter",
        "# HELP n9router_prompt_tokens_total Cumulative prompt tokens",
        "# TYPE n9router_prompt_tokens_total counter",
        "# HELP n9router_completion_tokens_total Cumulative completion tokens",
        "# TYPE n9router_completion_tokens_total counter",
        "# HELP n9router_cached_tokens_total Cumulative cached tokens",
        "# TYPE n9router_cached_tokens_total counter",
        "# HELP n9router_cost_usd_total Cumulative estimated cost USD",
        "# TYPE n9router_cost_usd_total counter",
        "# HELP n9router_provider_requests_total Requests by provider",
        "# TYPE n9router_provider_requests_total counter",
        "# HELP n9router_provider_cost_usd_total Cost by provider",
        "# TYPE n9router_provider_cost_usd_total counter",
        "# HELP n9router_model_requests_total Requests by model",
        "# TYPE n9router_model_requests_total counter",
        "# HELP n9router_model_cost_usd_total Cost by model",
        "# TYPE n9router_model_cost_usd_total counter",
        "# HELP n9router_provider_active Provider connection active (1/0)",
        "# TYPE n9router_provider_active gauge",
        "# HELP n9router_provider_expires_unix OAuth/token expiry unix seconds",
        "# TYPE n9router_provider_expires_unix gauge",
        "# HELP n9router_provider_has_error 1 if lastError set",
        "# TYPE n9router_provider_has_error gauge",
    ]
    try:
        usage = _get_json("/api/usage/stats")
        providers = _get_json("/api/providers")
        now = time.time()
        lines.append(_line("n9router_scrape_success", 1))
        lines.append(_line("n9router_scrape_timestamp_seconds", now))
        lines.append(_line("n9router_requests_total", float(usage.get("totalRequests") or 0)))
        lines.append(
            _line("n9router_prompt_tokens_total", float(usage.get("totalPromptTokens") or 0))
        )
        lines.append(
            _line(
                "n9router_completion_tokens_total",
                float(usage.get("totalCompletionTokens") or 0),
            )
        )
        lines.append(
            _line("n9router_cached_tokens_total", float(usage.get("totalCachedTokens") or 0))
        )
        lines.append(_line("n9router_cost_usd_total", float(usage.get("totalCost") or 0)))

        for provider, row in (usage.get("byProvider") or {}).items():
            labels = {"provider": str(provider)}
            lines.append(
                _line(
                    "n9router_provider_requests_total",
                    float(row.get("requests") or 0),
                    labels,
                )
            )
            lines.append(
                _line(
                    "n9router_provider_cost_usd_total",
                    float(row.get("cost") or 0),
                    labels,
                )
            )

        for model, row in (usage.get("byModel") or {}).items():
            labels = {
                "model": str(model),
                "provider": str(row.get("provider") or "unknown"),
                "raw_model": str(row.get("rawModel") or model),
            }
            lines.append(
                _line(
                    "n9router_model_requests_total",
                    float(row.get("requests") or 0),
                    labels,
                )
            )
            lines.append(
                _line(
                    "n9router_model_cost_usd_total",
                    float(row.get("cost") or 0),
                    labels,
                )
            )

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
                _line(
                    "n9router_provider_active",
                    1.0 if conn.get("isActive") else 0.0,
                    labels,
                )
            )
            exp = conn.get("expiresAt")
            exp_unix = 0.0
            if isinstance(exp, str) and exp:
                try:
                    # 2026-08-10T07:32:21.791Z
                    from datetime import datetime, timezone

                    exp_unix = datetime.fromisoformat(exp.replace("Z", "+00:00")).timestamp()
                except Exception:
                    exp_unix = 0.0
            lines.append(_line("n9router_provider_expires_unix", exp_unix, labels))
            lines.append(
                _line(
                    "n9router_provider_has_error",
                    1.0 if conn.get("lastError") else 0.0,
                    labels,
                )
            )
    except Exception as e:
        lines.append(_line("n9router_scrape_success", 0))
        lines.append(
            "# HELP n9router_scrape_error_info Last scrape error (always 1 with label)"
        )
        lines.append("# TYPE n9router_scrape_error_info gauge")
        lines.append(_line("n9router_scrape_error_info", 1, {"error": str(e)[:180]}))
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
    # warm first scrape
    time.sleep(0.2)
    httpd = ThreadingHTTPServer((host or "0.0.0.0", port), Handler)
    print(f"nine-exporter listening on {host}:{port} -> {N9ROUTER_URL}", flush=True)
    httpd.serve_forever()


if __name__ == "__main__":
    main()
