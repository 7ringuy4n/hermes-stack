#!/usr/bin/env python3
"""Ops alert-watch → NotificationManager (admin Zalo DM).

Watches:
  - Lab service health (same targets as stack-exporter) → DOWN / recovered
  - Host CPU / RAM / disk via node-exporter → over threshold
  - 9Router provider errors / 429 / quota signals

Stdlib only. Cooldown per alert key to avoid spam.
"""
from __future__ import annotations

import json
import os
import re
import socket
import time
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any, Optional

LISTEN = os.environ.get("LISTEN", "0.0.0.0:9103")
CHECK_INTERVAL = float(os.environ.get("CHECK_INTERVAL", "60"))
COOLDOWN = float(os.environ.get("ALERT_COOLDOWN_SECONDS", "1800"))
NOTIFY_URL = os.environ.get("NOTIFY_URL", "http://notify:8092").rstrip("/")
NODE_EXPORTER = os.environ.get("NODE_EXPORTER_URL", "http://node-exporter:9100").rstrip("/")
N9ROUTER_URL = os.environ.get("N9ROUTER_URL", "http://9router:20128").rstrip("/")
N9ROUTER_PASSWORD = os.environ.get("N9ROUTER_PASSWORD", "")
N9ROUTER_API_KEY = os.environ.get("N9ROUTER_API_KEY", os.environ.get("OPENAI_API_KEY", ""))

CPU_PCT = float(os.environ.get("ALERT_CPU_PCT", "90"))
MEM_PCT = float(os.environ.get("ALERT_MEM_PCT", "90"))
DISK_PCT = float(os.environ.get("ALERT_DISK_PCT", "90"))
DISK_MOUNT_RE = os.environ.get("ALERT_DISK_MOUNT_RE", "^/$|^/data")

HEALTH_TARGETS = os.environ.get(
    "HEALTH_TARGETS",
    "redis_via_tcp=redis:6379,"
    "qdrant=qdrant:6333/readyz,"
    "av-gateway=av-gateway:8098/health,"
    "security-manager=security-manager:8093/health,"
    "ocr=ocr:8091/health,"
    "ingest=ingest:8099/health,"
    "mem0=mem0:8096/health,"
    "authz=authz:8097/health,"
    "embedding=embedding:8094/health,"
    "dispatcher=dispatcher:8090/health,"
    "notify=notify:8092/health,"
    "memory-manager=memory-manager:8095/health,"
    "admin-api=admin-api:8100/health,"
    "clamav=clamav:3310,"
    "9router_via_tcp=9router:20128,"
    # Hermes gateway often binds 8642 on loopback only; dashboard 9119 is on the docker network.
    "hermes=hermes:9119/,"
    "postgres_via_tcp=postgres:5432",
)

_QUOTA_RE = re.compile(
    r"429|quota|rate.?limit|insufficient.?quota|resource.?exhausted|too many requests|billing|credit",
    re.I,
)

_last_fire: dict[str, float] = {}
_prev_up: dict[str, bool] = {}
_cookie = ""
_cookie_at = 0.0
_status: dict[str, Any] = {"ok": True, "last_check": 0, "alerts": []}


def _http_json(url: str, *, data: Optional[bytes] = None, headers: Optional[dict] = None, timeout: float = 15) -> Any:
    req = urllib.request.Request(
        url,
        data=data,
        headers=headers or {"Accept": "application/json"},
        method="POST" if data is not None else "GET",
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        raw = resp.read().decode()
        return json.loads(raw) if raw else {}


def _http_text(url: str, timeout: float = 10) -> str:
    req = urllib.request.Request(url, headers={"Accept": "text/plain"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read().decode("utf-8", errors="replace")


def _http_ok(url: str, timeout: float = 4.0) -> bool:
    try:
        req = urllib.request.Request(url, method="GET")
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return 200 <= resp.status < 500  # 404 on / still means process up for some
    except Exception:
        return False


def _http_reachable(url: str, timeout: float = 4.0) -> bool:
    """True if TCP+HTTP answered (2xx/3xx/4xx). Connection refused → False."""
    try:
        req = urllib.request.Request(url, method="GET")
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return True
    except urllib.error.HTTPError:
        return True
    except Exception:
        return False


def _tcp_ok(host: str, port: int, timeout: float = 3.0) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


def _notify(title: str, body: str, severity: str = "warning") -> bool:
    if not NOTIFY_URL:
        return False
    try:
        payload = json.dumps(
            {
                "title": title,
                "body": body,
                "severity": severity,
                "channels": ["zalo", "log"],
                "kind": "alert",
            }
        ).encode()
        _http_json(
            f"{NOTIFY_URL}/v1/alert",
            data=payload,
            headers={"content-type": "application/json"},
            timeout=20,
        )
        return True
    except Exception as e:
        print(f"[alert-watch] notify failed: {e}", flush=True)
        return False


def _fire(key: str, title: str, body: str, severity: str = "warning") -> None:
    now = time.time()
    last = _last_fire.get(key, 0.0)
    if now - last < COOLDOWN:
        return
    ok = _notify(title, body, severity)
    if ok:
        _last_fire[key] = now
        _status.setdefault("alerts", []).append({"ts": now, "key": key, "title": title})
        _status["alerts"] = _status["alerts"][-50:]
        print(f"[alert-watch] FIRED {key}: {title}", flush=True)


def _parse_health_targets(raw: str) -> list[tuple[str, str, str, int, str]]:
    out: list[tuple[str, str, str, int, str]] = []
    for part in raw.split(","):
        part = part.strip()
        if not part or "=" not in part:
            continue
        name, rest = part.split("=", 1)
        name = name.strip()
        rest = rest.strip()
        path = "/health"
        hostport = rest
        if "/" in rest:
            hostport, path = rest.split("/", 1)
            path = "/" + path
        if ":" not in hostport:
            continue
        host, port_s = hostport.rsplit(":", 1)
        try:
            port = int(port_s)
        except ValueError:
            continue
        kind = "tcp" if name.endswith("_via_tcp") or name == "clamav" or path == "" else "http"
        if name in ("clamav", "redis_via_tcp", "postgres_via_tcp", "9router_via_tcp"):
            kind = "tcp"
        out.append((name, kind, host, port, path or "/"))
    return out


def check_services() -> None:
    for name, kind, host, port, path in _parse_health_targets(HEALTH_TARGETS):
        if kind == "tcp":
            ok = _tcp_ok(host, port)
        else:
            # Any HTTP response (incl. 401/404) means the process is up
            ok = _http_reachable(f"http://{host}:{port}{path or '/'}")
        prev = _prev_up.get(name)
        _prev_up[name] = ok
        if prev is None:
            continue  # warm-up: no alert on first sample
        if prev and not ok:
            _fire(
                f"service_down:{name}",
                f"Service DOWN: {name}",
                f"{name} failed health ({kind} {host}:{port}{path}). Check Grafana Stack health.",
                "critical",
            )
        elif (not prev) and ok:
            _fire(
                f"service_up:{name}",
                f"Service recovered: {name}",
                f"{name} is UP again.",
                "info",
            )


def _parse_prom(text: str) -> list[tuple[str, dict[str, str], float]]:
    rows: list[tuple[str, dict[str, str], float]] = []
    for line in text.splitlines():
        if not line or line.startswith("#"):
            continue
        m = re.match(r"^([a-zA-Z_:][a-zA-Z0-9_:]*)(\{[^}]*\})?\s+([0-9.eE+-]+)", line)
        if not m:
            continue
        name, lab_s, val_s = m.group(1), m.group(2) or "", m.group(3)
        labels: dict[str, str] = {}
        if lab_s:
            for km in re.finditer(r'([a-zA-Z_][a-zA-Z0-9_]*)="([^"]*)"', lab_s):
                labels[km.group(1)] = km.group(2)
        try:
            rows.append((name, labels, float(val_s)))
        except ValueError:
            continue
    return rows


def check_resources() -> None:
    try:
        text = _http_text(f"{NODE_EXPORTER}/metrics", timeout=8)
    except Exception as e:
        # Don't spam if node-exporter profile off — one cooldown key
        _fire(
            "node_exporter_unreachable",
            "node-exporter unreachable",
            f"Cannot scrape {NODE_EXPORTER}/metrics: {e}. CPU/RAM/disk alerts paused.",
            "warning",
        )
        return

    rows = _parse_prom(text)
    # --- memory ---
    mem_total = next((v for n, _, v in rows if n == "node_memory_MemTotal_bytes"), 0.0)
    mem_avail = next((v for n, _, v in rows if n == "node_memory_MemAvailable_bytes"), 0.0)
    if mem_total > 0:
        used_pct = (1.0 - (mem_avail / mem_total)) * 100.0
        if used_pct >= MEM_PCT:
            _fire(
                "host_mem_high",
                f"High RAM: {used_pct:.0f}%",
                f"Memory used {used_pct:.1f}% (threshold {MEM_PCT:.0f}%). "
                f"Avail={mem_avail/1e9:.2f}GiB / Total={mem_total/1e9:.2f}GiB",
                "warning",
            )

    # --- disk ---
    mount_re = re.compile(DISK_MOUNT_RE)
    sizes: dict[str, float] = {}
    avails: dict[str, float] = {}
    for n, lab, v in rows:
        mp = lab.get("mountpoint") or ""
        if not mount_re.search(mp):
            continue
        if n == "node_filesystem_size_bytes" and lab.get("fstype") not in ("tmpfs", "overlay", "squashfs"):
            sizes[mp] = v
        if n == "node_filesystem_avail_bytes" and lab.get("fstype") not in ("tmpfs", "overlay", "squashfs"):
            avails[mp] = v
    for mp, size in sizes.items():
        avail = avails.get(mp, 0.0)
        if size <= 0:
            continue
        used_pct = (1.0 - avail / size) * 100.0
        if used_pct >= DISK_PCT:
            _fire(
                f"host_disk_high:{mp}",
                f"High disk {mp}: {used_pct:.0f}%",
                f"Filesystem {mp} used {used_pct:.1f}% (threshold {DISK_PCT:.0f}%). "
                f"Avail={avail/1e9:.2f}GiB / Size={size/1e9:.2f}GiB",
                "critical" if used_pct >= 95 else "warning",
            )

    # --- CPU: 1 - idle rate over ~interval using counter delta ---
    # Use node_load1 vs CPU count as simple signal (no two-sample needed)
    load1 = next((v for n, _, v in rows if n == "node_load1"), None)
    cpus = sum(1 for n, lab, _ in rows if n == "node_cpu_seconds_total" and lab.get("mode") == "idle")
    # fallback: count unique cpu labels
    if cpus <= 0:
        cpus = len({lab.get("cpu") for n, lab, _ in rows if n == "node_cpu_seconds_total" and lab.get("cpu")})
    if load1 is not None and cpus > 0:
        load_pct = (load1 / cpus) * 100.0
        if load_pct >= CPU_PCT:
            _fire(
                "host_cpu_high",
                f"High CPU load: {load_pct:.0f}%",
                f"load1={load1:.2f} on {cpus} CPUs ≈ {load_pct:.0f}% (threshold {CPU_PCT:.0f}%).",
                "warning",
            )


def _n9_login() -> str:
    global _cookie, _cookie_at
    if not N9ROUTER_PASSWORD:
        raise RuntimeError("N9ROUTER_PASSWORD empty")
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
            raise RuntimeError(f"login missing cookie: {raw!r}")
        _cookie = token
        _cookie_at = time.time()
        return _cookie


def _n9_get(path: str) -> Any:
    global _cookie
    if not _cookie or (time.time() - _cookie_at) > 20 * 3600:
        _n9_login()
    req = urllib.request.Request(
        f"{N9ROUTER_URL}{path}",
        headers={"Cookie": _cookie, "Accept": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            return json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        if e.code in (401, 403):
            _n9_login()
            req = urllib.request.Request(
                f"{N9ROUTER_URL}{path}",
                headers={"Cookie": _cookie, "Accept": "application/json"},
            )
            with urllib.request.urlopen(req, timeout=20) as resp:
                return json.loads(resp.read().decode())
        raise


def check_llm_quota() -> None:
    # 1) Provider dashboard errors (quota / 429 often land in lastError)
    if N9ROUTER_PASSWORD:
        try:
            providers = _n9_get("/api/providers")
            for conn in providers.get("connections") or []:
                err = str(conn.get("lastError") or "")
                name = str(conn.get("name") or conn.get("provider") or conn.get("id") or "?")
                provider = str(conn.get("provider") or "?")
                if err and _QUOTA_RE.search(err):
                    _fire(
                        f"llm_quota:{provider}:{name}",
                        f"LLM quota/429: {provider}",
                        f"Provider {provider} ({name}) lastError:\n{err[:800]}",
                        "critical",
                    )
                elif err:
                    print(
                        f"[alert-watch] llm skip notify ({provider}/{name}): {err[:240]}",
                        flush=True,
                    )
        except Exception as e:
            _fire(
                "n9router_api_unreachable",
                "9Router API unreachable",
                f"Cannot read /api/providers: {e}",
                "warning",
            )

    # 2) Lightweight probe: models list — 429 here means gateway throttling
    headers = {"Accept": "application/json"}
    if N9ROUTER_API_KEY:
        headers["Authorization"] = f"Bearer {N9ROUTER_API_KEY}"
    try:
        req = urllib.request.Request(f"{N9ROUTER_URL}/v1/models", headers=headers)
        with urllib.request.urlopen(req, timeout=15) as resp:
            _ = resp.read()
    except urllib.error.HTTPError as e:
        body = ""
        try:
            body = e.read().decode("utf-8", errors="replace")[:500]
        except Exception:
            pass
        if e.code == 429 or _QUOTA_RE.search(body):
            _fire(
                "llm_http_429",
                "LLM HTTP 429 / quota",
                f"GET {N9ROUTER_URL}/v1/models → {e.code}\n{body}",
                "critical",
            )
        else:
            print(f"[alert-watch] llm http {e.code} (no notify): {body[:200]}", flush=True)
    except Exception:
        pass


def run_once() -> None:
    check_services()
    check_resources()
    check_llm_quota()
    _status["last_check"] = time.time()
    _status["ok"] = True
    down = [n for n, up in _prev_up.items() if up is False]
    _status["services_down"] = down


def loop() -> None:
    # warm-up sample (establish baselines, no DOWN spam on boot)
    try:
        check_services()
    except Exception as e:
        print(f"[alert-watch] warm-up: {e}", flush=True)
    time.sleep(2)
    while True:
        try:
            run_once()
        except Exception as e:
            print(f"[alert-watch] loop error: {e}", flush=True)
            _status["ok"] = False
            _status["error"] = str(e)[:200]
        time.sleep(CHECK_INTERVAL)


class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt: str, *args: Any) -> None:
        return

    def do_GET(self) -> None:  # noqa: N802
        if self.path in ("/health", "/"):
            body = json.dumps(
                {
                    "ok": _status.get("ok", True),
                    "last_check": _status.get("last_check"),
                    "services_down": _status.get("services_down", []),
                    "cooldown": COOLDOWN,
                    "thresholds": {"cpu": CPU_PCT, "mem": MEM_PCT, "disk": DISK_PCT},
                }
            ).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        if self.path == "/v1/recent":
            body = json.dumps({"items": _status.get("alerts", [])}).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        self.send_response(404)
        self.end_headers()


def main() -> None:
    import threading

    threading.Thread(target=loop, daemon=True).start()
    host, _, port_s = LISTEN.partition(":")
    port = int(port_s or "9103")
    httpd = ThreadingHTTPServer((host or "0.0.0.0", port), Handler)
    print(
        f"alert-watch on {host}:{port} notify={NOTIFY_URL} "
        f"cpu>={CPU_PCT} mem>={MEM_PCT} disk>={DISK_PCT} cooldown={COOLDOWN}s",
        flush=True,
    )
    httpd.serve_forever()


if __name__ == "__main__":
    main()
