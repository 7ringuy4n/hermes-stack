#!/usr/bin/env python3
# Qdrant vendor snapshots (stdlib only). UTF-8 paths.
from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.stderr.reconfigure(encoding="utf-8", errors="replace")


def _req(url: str, method: str = "GET", data: bytes | None = None, timeout: int = 120) -> Any:
    headers = {"Accept": "application/json"}
    if data is not None:
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=data, method=method, headers=headers)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        raw = resp.read()
        if not raw:
            return None
        try:
            return json.loads(raw.decode("utf-8"))
        except json.JSONDecodeError:
            return raw


def _get(url: str, dest: str) -> None:
    os.makedirs(os.path.dirname(dest) or ".", exist_ok=True)
    req = urllib.request.Request(url, method="GET")
    with urllib.request.urlopen(req, timeout=600) as resp, open(dest, "wb") as out:
        while True:
            chunk = resp.read(1024 * 1024)
            if not chunk:
                break
            out.write(chunk)


def collections(base: str) -> list[str]:
    body = _req(f"{base}/collections")
    cols = (body or {}).get("result", {}).get("collections") or []
    return [c["name"] for c in cols if isinstance(c, dict) and c.get("name")]


def backup(base: str, out_dir: str) -> dict[str, Any]:
    os.makedirs(out_dir, exist_ok=True)
    names = collections(base)
    meta: dict[str, Any] = {"collections": names, "snapshots": []}
    # Storage-level snapshot (all collections)
    created = _req(f"{base}/snapshots", method="POST", data=b"{}")
    snap = (created or {}).get("result") or {}
    snap_name = snap.get("name")
    if not snap_name:
        raise SystemExit(f"qdrant storage snapshot failed: {created}")
    dest = os.path.join(out_dir, "storage.snapshot")
    _get(f"{base}/snapshots/{snap_name}", dest)
    if not os.path.isfile(dest) or os.path.getsize(dest) < 1:
        raise SystemExit("qdrant storage snapshot empty")
    meta["storage_snapshot"] = snap_name
    meta["storage_bytes"] = os.path.getsize(dest)
    # Per-collection (restore fallback)
    for name in names:
        qn = urllib.parse.quote(name, safe="")
        created = _req(f"{base}/collections/{qn}/snapshots", method="POST", data=b"{}")
        csnap = (created or {}).get("result") or {}
        cname = csnap.get("name")
        if not cname:
            raise SystemExit(f"qdrant snapshot failed for collection {name}: {created}")
        cdest = os.path.join(out_dir, f"col_{name}.snapshot")
        _get(
            f"{base}/collections/{qn}/snapshots/{urllib.parse.quote(cname, safe='')}",
            cdest,
        )
        meta["snapshots"].append(
            {"collection": name, "name": cname, "bytes": os.path.getsize(cdest)}
        )
    with open(os.path.join(out_dir, "manifest.json"), "w", encoding="utf-8") as fh:
        json.dump(meta, fh, ensure_ascii=False, indent=2)
    return meta


def recover_file(base: str, location: str) -> None:
    payload = json.dumps({"location": location}).encode("utf-8")
    body = _req(f"{base}/snapshots/recover", method="PUT", data=payload, timeout=600)
    if body is None:
        raise SystemExit("qdrant recover returned empty")
    for _ in range(60):
        try:
            _req(f"{base}/readyz")
            break
        except urllib.error.URLError:
            time.sleep(2)
    print(json.dumps(body, ensure_ascii=False))


def recover_collection(base: str, collection: str, location: str) -> None:
    payload = json.dumps({"location": location}).encode("utf-8")
    url = f"{base}/collections/{urllib.parse.quote(collection, safe='')}/snapshots/recover"
    body = _req(url, method="PUT", data=payload, timeout=600)
    print(json.dumps(body, ensure_ascii=False))


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("cmd", choices=["backup", "recover-storage", "recover-collection", "list"])
    p.add_argument("--base", default="http://127.0.0.1:6333")
    p.add_argument("--dir", default="")
    p.add_argument("--location", default="")
    p.add_argument("--collection", default="")
    args = p.parse_args()
    base = args.base.rstrip("/")
    if args.cmd == "list":
        print(json.dumps({"collections": collections(base)}, ensure_ascii=False))
        return
    if args.cmd == "backup":
        if not args.dir:
            raise SystemExit("--dir required")
        meta = backup(base, args.dir)
        print(json.dumps(meta, ensure_ascii=False))
        return
    if args.cmd == "recover-storage":
        if not args.location:
            raise SystemExit("--location file:///... required")
        recover_file(base, args.location)
        return
    if args.cmd == "recover-collection":
        if not args.location or not args.collection:
            raise SystemExit("--collection and --location required")
        recover_collection(base, args.collection, args.location)
        return


if __name__ == "__main__":
    main()
