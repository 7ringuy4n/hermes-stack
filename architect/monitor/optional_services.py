# Shared enable-flags for optional compose services (alert-watch + stack-exporter).
# Must services have no mapping and are always expected.
from __future__ import annotations

import os
import socket
import urllib.error

_TRUE = {"1", "true", "yes", "on"}


def env_on(name: str, default: str = "0") -> bool:
    v = (os.environ.get(name, default) or "").strip().lower()
    return v in _TRUE


def monitor_metrics_on() -> bool:
    return env_on("ENABLE_GRAFANA") or env_on("ENABLE_PROMETHEUS")


def logs_on() -> bool:
    return env_on("ENABLE_LOKI") or env_on("ENABLE_ALLOY")


# hostname on the compose network → ENABLE_* that must be on to scrape/alert
HOST_FLAGS: dict[str, tuple[str, ...]] = {
    "node-exporter": ("ENABLE_GRAFANA", "ENABLE_PROMETHEUS"),
    "prometheus": ("ENABLE_GRAFANA", "ENABLE_PROMETHEUS"),
    "grafana": ("ENABLE_GRAFANA",),
    "stack-exporter": ("ENABLE_GRAFANA", "ENABLE_PROMETHEUS"),
    "loki": ("ENABLE_LOKI", "ENABLE_ALLOY"),
    "alloy": ("ENABLE_LOKI", "ENABLE_ALLOY"),
    "omni-exporter": ("ENABLE_OMNIROUTER",),
    "omni-router": ("ENABLE_OMNIROUTER",),
    "omni-attribution": ("ENABLE_OMNIROUTER",),
    "openbao": ("ENABLE_OPENBAO",),
    "av-gateway": ("ENABLE_ANTIVIRUS",),
    "clamav": ("ENABLE_ANTIVIRUS",),
    "zalo-api": ("ENABLE_ZALO",),
    "notify": ("ENABLE_NOTIFY",),
    "alert-watch": ("ENABLE_NOTIFY",),
    "docker-socket-proxy": ("SECURITY_SANDBOX",),
    "authz": ("ENABLE_AUTHZ",),
    "security-manager": ("ENABLE_SECURITY",),
    "jobs": ("ENABLE_JOBS",),
    "jobs-worker": ("ENABLE_JOBS",),
    "workflow": ("ENABLE_JOBS",),
}


def host_expected(host: str) -> bool:
    flags = HOST_FLAGS.get(host)
    if not flags:
        return True
    if host == "omni-exporter":
        return env_on("ENABLE_OMNIROUTER") and monitor_metrics_on()
    return any(env_on(f) for f in flags)


def name_unresolved(exc: BaseException) -> bool:
    if isinstance(exc, socket.gaierror):
        return True
    if isinstance(exc, urllib.error.URLError):
        reason = exc.reason
        if isinstance(reason, socket.gaierror):
            return True
        text = str(reason or exc)
    else:
        text = str(exc)
    low = text.lower()
    return "name resolution" in low or "name or service not known" in low or "temporary failure" in low
