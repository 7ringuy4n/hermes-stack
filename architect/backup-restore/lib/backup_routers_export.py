#!/usr/bin/env python3
"""Best-effort export of OmniRoute combos and settings into a backup stamp.

The source of truth for restore remains the ``omni_router_data`` Docker volume.
This JSON is for audit/verify and operator visibility after restore.
"""
from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request
from http.cookiejar import CookieJar
from pathlib import Path
from typing import Any


def env_active(value: str | None, default: str = "0") -> bool:
    return str(value or default).strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
        "active",
        "enabled",
    }


def load_dotenv(path: Path) -> dict[str, str]:
    out: dict[str, str] = {}
    if not path.is_file():
        return out
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        s = line.strip()
        if not s or s.startswith("#") or "=" not in s:
            continue
        k, _, v = s.partition("=")
        k = k.strip()
        v = v.strip().strip("'").strip('"')
        if k:
            out[k] = v
    return out


def http_json(
    opener: urllib.request.OpenerDirector,
    method: str,
    url: str,
    body: dict | None = None,
) -> tuple[int, Any]:
    data = None if body is None else json.dumps(body).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        method=method,
        headers={"Content-Type": "application/json", "Accept": "application/json"},
    )
    try:
        with opener.open(req, timeout=20) as resp:
            raw = resp.read().decode("utf-8") or "{}"
            try:
                parsed: Any = json.loads(raw) if raw.strip() else {}
            except json.JSONDecodeError:
                parsed = {"raw": raw[:500]}
            return int(resp.status), parsed
    except urllib.error.HTTPError as e:
        raw = e.read().decode("utf-8", errors="replace") if e.fp else ""
        try:
            parsed = json.loads(raw) if raw.strip() else {"error": str(e)}
        except json.JSONDecodeError:
            parsed = {"error": str(e), "raw": raw[:300]}
        return int(e.code), parsed
    except Exception as e:
        return 0, {"error": str(e)}


def export_one(
    name: str,
    base: str,
    password: str,
    out_dir: Path,
) -> dict[str, Any]:
    meta: dict[str, Any] = {"name": name, "base": base, "status": "skipped", "note": ""}
    if not password or password.startswith("CHANGE_ME"):
        meta["note"] = "password missing"
        return meta
    jar = CookieJar()
    opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))
    status, body = http_json(opener, "POST", f"{base}/api/auth/login", {"password": password})
    if status not in (200, 201):
        meta["status"] = "failed"
        meta["note"] = f"login HTTP {status}"
        return meta
    combos_status, combos = http_json(opener, "GET", f"{base}/api/combos")
    settings_status, settings = http_json(opener, "GET", f"{base}/api/settings")
    providers_status, providers = http_json(opener, "GET", f"{base}/api/providers")
    doc = {
        "schema": "assistant-router-export-v1",
        "router": name,
        "base": base,
        "combos": combos if combos_status == 200 else {"error": combos, "http": combos_status},
        "settings": settings if settings_status == 200 else {"error": settings, "http": settings_status},
        "providers": providers if providers_status == 200 else {"error": providers, "http": providers_status},
    }
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"{name}-export.json"
    path.write_text(json.dumps(doc, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    try:
        os.chmod(path, 0o600)
    except OSError:
        pass
    meta["status"] = "ok"
    meta["file"] = str(path.name)
    n_combos = 0
    if isinstance(combos, dict):
        lst = combos.get("combos")
        if isinstance(lst, list):
            n_combos = len(lst)
    meta["combo_count"] = n_combos
    meta["note"] = f"combos={n_combos}"
    return meta


def main() -> int:
    if len(sys.argv) < 2:
        print("usage: backup_routers_export.py <stamp-routers-dir>", file=sys.stderr)
        return 2
    out_dir = Path(sys.argv[1])
    root = Path(os.environ.get("ROOT") or "/opt/assistant")
    env = load_dotenv(root / ".env")
    env.update({k: v for k, v in os.environ.items() if k.startswith(("OMNI", "N9", "ENABLE_"))})

    results: list[dict[str, Any]] = []
    if env_active(env.get("ENABLE_OMNIROUTER"), "1"):
        port = env.get("OMNIROUTER_HOST_PORT") or "20129"
        pw = (env.get("OMNIROUTER_INITIAL_PASSWORD") or "").strip()
        results.append(
            export_one("omni-router", f"http://127.0.0.1:{port}", pw, out_dir)
        )
    else:
        results.append({"name": "omni-router", "status": "skipped", "note": "ENABLE_OMNIROUTER off"})

    summary = {"schema": "assistant-router-export-summary-v1", "results": results}
    (out_dir / "export-summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(summary, ensure_ascii=False))
    # Best-effort: never fail the whole backup for API export issues (volumes are SoT).
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
