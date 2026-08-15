#!/usr/bin/env python3
"""Scrape Redis / Qdrant / lab /health → Prometheus metrics (stdlib only)."""
from __future__ import annotations

import json
import os
import re
import socket
import threading
import time
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any
from urllib.parse import urlparse

LISTEN = os.environ.get("LISTEN", "0.0.0.0:9102")
SCRAPE_INTERVAL = float(os.environ.get("SCRAPE_INTERVAL", "30"))
REDIS_URL = os.environ.get("REDIS_URL", "redis://redis:6379/0")
QDRANT_URL = os.environ.get("QDRANT_URL", "http://qdrant:6333").rstrip("/")
COLL_KNOWLEDGE = os.environ.get("QDRANT_COLLECTION_KNOWLEDGE", "knowledge_chunks")
COLL_MEMORY = os.environ.get("QDRANT_COLLECTION_MEMORY", "conversational_memory")
# Must/High health targets — optional clamav/av-gateway/notify are added by compose
# when ENABLE_ANTIVIRUS=1 / ENABLE_NOTIFY=1 (do not hardcode them here).
HEALTH_TARGETS = os.environ.get(
    "HEALTH_TARGETS",
    "redis_via_tcp=redis:6379,"
    "qdrant=qdrant:6333/readyz,"
    "security-manager=security-manager:8093/health,"
    "ocr=ocr:8091/health,"
    "ingest=ingest:8099/health,"
    "mem0=mem0:8096/health,"
    "authz=authz:8097/health,"
    "embedding=embedding:8094/health,"
    "dispatcher=dispatcher:8090/health,"
    "memory=memory:8095/health,"
    "admin-api=admin-api:8100/health,"
    "openbao=openbao:8200/v1/sys/health",
)

_lock = threading.Lock()
_metrics_text = "# scrape pending\n"


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


def _parse_redis_url(url: str) -> tuple[str, int, int]:
    u = urlparse(url)
    host = u.hostname or "redis"
    port = int(u.port or 6379)
    db = 0
    if u.path and u.path.strip("/"):
        try:
            db = int(u.path.strip("/").split("/")[0])
        except ValueError:
            db = 0
    return host, port, db


def _redis_cmd(host: str, port: int, *parts: str, timeout: float = 5.0) -> bytes:
    buf = f"*{len(parts)}\r\n".encode()
    for p in parts:
        b = p.encode() if isinstance(p, str) else p
        buf += f"${len(b)}\r\n".encode() + b + b"\r\n"
    with socket.create_connection((host, port), timeout=timeout) as s:
        s.sendall(buf)
        data = b""
        while True:
            chunk = s.recv(65536)
            if not chunk:
                break
            data += chunk
            # enough for INFO / SCAN bulk; stop when no more immediate data
            s.settimeout(0.15)
            try:
                more = s.recv(65536)
                if not more:
                    break
                data += more
            except socket.timeout:
                break
    return data


def _redis_info(host: str, port: int) -> dict[str, str]:
    raw = _redis_cmd(host, port, "INFO")
    # bulk string: $<n>\r\n...\r\n
    text = raw.decode("utf-8", errors="replace")
    if text.startswith("$"):
        nl = text.find("\r\n")
        text = text[nl + 2 :] if nl >= 0 else text
    out: dict[str, str] = {}
    for line in text.splitlines():
        if not line or line.startswith("#") or ":" not in line:
            continue
        k, v = line.split(":", 1)
        out[k.strip()] = v.strip()
    return out


def _resp_bulk_strings(raw: bytes) -> list[str]:
    """Extract bulk-string payloads from a RESP reply (best-effort)."""
    text = raw.decode("utf-8", errors="replace")
    lines = text.split("\r\n")
    out: list[str] = []
    i = 0
    while i < len(lines):
        ln = lines[i]
        if ln.startswith("$") and ln[1:].lstrip("-").isdigit():
            n = int(ln[1:])
            if n >= 0 and i + 1 < len(lines):
                out.append(lines[i + 1])
                i += 2
                continue
        i += 1
    return out


def _redis_scan_count(host: str, port: int, pattern: str, db: int = 0) -> int:
    try:
        _redis_cmd(host, port, "SELECT", str(db))
    except OSError:
        return 0
    cursor = "0"
    total = 0
    for _ in range(500):
        raw = _redis_cmd(host, port, "SCAN", cursor, "MATCH", pattern, "COUNT", "200")
        bulks = _resp_bulk_strings(raw)
        if not bulks:
            break
        cursor = bulks[0]
        total += max(0, len(bulks) - 1)
        if cursor == "0":
            break
    return total


def _http_json(url: str, timeout: float = 5.0) -> Any:
    req = urllib.request.Request(url, headers={"Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode())


def _http_ok(url: str, timeout: float = 4.0) -> bool:
    try:
        req = urllib.request.Request(url, method="GET")
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return 200 <= resp.status < 300
    except Exception:
        return False


def _tcp_ok(host: str, port: int, timeout: float = 3.0) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


def _qdrant_collection(name: str) -> dict[str, float]:
    try:
        data = _http_json(f"{QDRANT_URL}/collections/{name}")
        result = data.get("result") or {}
        points = result.get("points_count")
        if points is None:
            points = (result.get("indexed_vectors_count") or 0)
        segments = result.get("segments_count") or 0
        status = 1.0 if (result.get("status") == "green" or data.get("status") == "ok") else 0.5
        # status field often "ok" at top level when collection exists
        if data.get("status") == "ok":
            status = 1.0
        return {
            "points": float(points or 0),
            "segments": float(segments or 0),
            "up": status,
        }
    except Exception:
        return {"points": 0.0, "segments": 0.0, "up": 0.0}


def _parse_health_targets(raw: str) -> list[tuple[str, str, str, int, str]]:
    """Return list of (name, kind, host, port, path) kind=http|tcp."""
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
        kind = "tcp" if name in ("clamav", "redis_via_tcp") or path == "" else "http"
        if name == "redis_via_tcp":
            kind = "tcp"
        if name == "clamav":
            kind = "tcp"
        if name == "qdrant" and path == "/readyz":
            kind = "http"
        out.append((name, kind, host, port, path))
    return out


def render_metrics() -> str:
    lines: list[str] = [
        "# HELP assistant_stack_scrape_success 1 if exporter scrape loop ok",
        "# TYPE assistant_stack_scrape_success gauge",
        "# HELP assistant_stack_scrape_timestamp_seconds Unix time of last scrape",
        "# TYPE assistant_stack_scrape_timestamp_seconds gauge",
        "# HELP assistant_service_up 1 if service health check passed",
        "# TYPE assistant_service_up gauge",
        "# HELP assistant_redis_up 1 if Redis PING/INFO ok",
        "# TYPE assistant_redis_up gauge",
        "# HELP assistant_redis_connected_clients Redis connected_clients",
        "# TYPE assistant_redis_connected_clients gauge",
        "# HELP assistant_redis_used_memory_bytes Redis used_memory",
        "# TYPE assistant_redis_used_memory_bytes gauge",
        "# HELP assistant_redis_keys Redis dbsize / keyspace keys",
        "# TYPE assistant_redis_keys gauge",
        "# HELP assistant_redis_session_keys Conversation session keys (mem0:conv:*)",
        "# TYPE assistant_redis_session_keys gauge",
        "# HELP assistant_redis_memory_index_keys mem0 memory index keys (mem0:idx:*)",
        "# TYPE assistant_redis_memory_index_keys gauge",
        "# HELP assistant_redis_ingest_queue_len Length of ingest:jobs list",
        "# TYPE assistant_redis_ingest_queue_len gauge",
        "# HELP assistant_qdrant_up 1 if collection reachable",
        "# TYPE assistant_qdrant_up gauge",
        "# HELP assistant_qdrant_points Points in Qdrant collection",
        "# TYPE assistant_qdrant_points gauge",
        "# HELP assistant_qdrant_segments Segments in Qdrant collection",
        "# TYPE assistant_qdrant_segments gauge",
    ]
    now = time.time()
    try:
        host, port, db = _parse_redis_url(REDIS_URL)
        info = _redis_info(host, port)
        lines.append(_line("assistant_redis_up", 1))
        lines.append(
            _line("assistant_redis_connected_clients", float(info.get("connected_clients") or 0))
        )
        lines.append(
            _line("assistant_redis_used_memory_bytes", float(info.get("used_memory") or 0))
        )
        # keyspace db0:keys=N
        keys = 0.0
        ks = info.get(f"db{db}") or info.get("db0") or ""
        m = re.search(r"keys=(\d+)", ks)
        if m:
            keys = float(m.group(1))
        lines.append(_line("assistant_redis_keys", keys))
        try:
            sess = float(_redis_scan_count(host, port, "mem0:conv:*", db))
        except Exception:
            sess = 0.0
        try:
            idx = float(_redis_scan_count(host, port, "mem0:idx:*", db))
        except Exception:
            idx = 0.0
        lines.append(_line("assistant_redis_session_keys", sess))
        lines.append(_line("assistant_redis_memory_index_keys", idx))
        # LLEN ingest:jobs
        try:
            raw = _redis_cmd(host, port, "LLEN", "ingest:jobs")
            text = raw.decode("utf-8", errors="replace").strip()
            qlen = 0.0
            if text.startswith(":"):
                qlen = float(text[1:].split("\r")[0])
            lines.append(_line("assistant_redis_ingest_queue_len", qlen))
        except Exception:
            lines.append(_line("assistant_redis_ingest_queue_len", 0))
    except Exception as e:
        lines.append(_line("assistant_redis_up", 0))
        lines.append(
            _line("assistant_service_up", 0, {"service": "redis", "error": str(e)[:80]})
        )

    for coll in (COLL_KNOWLEDGE, COLL_MEMORY):
        st = _qdrant_collection(coll)
        labels = {"collection": coll}
        lines.append(_line("assistant_qdrant_up", st["up"], labels))
        lines.append(_line("assistant_qdrant_points", st["points"], labels))
        lines.append(_line("assistant_qdrant_segments", st["segments"], labels))

    for name, kind, host, port, path in _parse_health_targets(HEALTH_TARGETS):
        ok = False
        if name == "redis_via_tcp":
            ok = _tcp_ok(host, port)
        elif kind == "tcp":
            ok = _tcp_ok(host, port)
        else:
            ok = _http_ok(f"http://{host}:{port}{path}")
        lines.append(_line("assistant_service_up", 1.0 if ok else 0.0, {"service": name}))

    lines.append(_line("assistant_stack_scrape_success", 1))
    lines.append(_line("assistant_stack_scrape_timestamp_seconds", now))
    lines.append("")
    return "\n".join(lines)


def scraper_loop() -> None:
    global _metrics_text
    while True:
        try:
            text = render_metrics()
        except Exception as e:
            text = (
                "# HELP assistant_stack_scrape_success 1 if exporter scrape loop ok\n"
                "# TYPE assistant_stack_scrape_success gauge\n"
                f"assistant_stack_scrape_success 0\n"
                f'assistant_stack_scrape_error_info{{error="{_esc(str(e)[:160])}"}} 1\n'
            )
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
    port = int(port_s or "9102")
    threading.Thread(target=scraper_loop, daemon=True).start()
    time.sleep(0.3)
    httpd = ThreadingHTTPServer((host or "0.0.0.0", port), Handler)
    print(
        f"stack-exporter listening on {host}:{port} redis={REDIS_URL} qdrant={QDRANT_URL}",
        flush=True,
    )
    httpd.serve_forever()


if __name__ == "__main__":
    main()
