#!/usr/bin/env python3
"""After Hermes + 9Router are ready: if hermes/main/skills is not empty, sync skill/docs → learn.

All profiles. Silent (no chat spam).
- Skills stay mounted for Hermes (compose bind).
- SKILL.md + markdown under each skill (+ hermes/main/docs, hermes/main/setup) are copied into
  $ASSISTANT_DATA_DIR/docs/ then ingest learn/scan (auto when LEARN_REQUIRE_APPROVE=0).

Usage:
  python3 scripts/main/post-ready-learn.py
  bash run.sh post-ready-learn
"""
from __future__ import annotations

import json
import os
import shutil
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(os.environ.get("STACK_ROOT") or Path(__file__).resolve().parents[2])
# Default product tree: hermes/main (override with HERMES_DIR)
_hermes = Path(os.environ.get("HERMES_DIR") or (ROOT / "hermes" / "main"))
if not _hermes.is_absolute():
    _hermes = ROOT / _hermes
SKILLS_DIR = _hermes / "skills"
HERMES_DOCS = _hermes / "docs"
HERMES_SETUP = _hermes / "setup"
DATA_DIR = Path(os.environ.get("ASSISTANT_DATA_DIR") or os.environ.get("HERMES_DATA_DIR") or "/data/assistant")
DOCS_ROOT = Path(os.environ.get("LEARN_DOCS_HOST") or (DATA_DIR / "docs"))

N9_PORT = int(os.environ.get("N9ROUTER_HOST_PORT", "20128"))
OMNI_PORT = int(os.environ.get("OMNIROUTER_HOST_PORT", "20129"))
ROUTER_PORT = int(os.environ.get("MODEL_ROUTER_HOST_PORT", "8096"))
ENABLE_9ROUTER = (os.environ.get("ENABLE_9ROUTER") or "0").strip().lower() in {"1", "true", "yes", "on"}
ENABLE_OMNI = (os.environ.get("ENABLE_OMNIROUTER") or "1").strip().lower() in {"1", "true", "yes", "on"}
HERMES_PORT = int(os.environ.get("HERMES_DASHBOARD_PORT", "29119"))
TRAEFIK_PORT = int(os.environ.get("TRAEFIK_HOST_PORT", "8080"))
GATEWAY_PORT = int(os.environ.get("GATEWAY_HOST_PORT", "8088"))
HERMES_REPLICAS = int(os.environ.get("HERMES_REPLICAS", "1") or "1")
INGEST_URL = (os.environ.get("INGEST_URL") or "http://127.0.0.1:8099").rstrip("/")

SKIP_SKILL_DIRS = {"_example", "__pycache__", ".git", "official", "vendor"}
CATEGORY_DIRS = {"core", "knowledge", "coding", "communication"}


def http_ok(url: str, timeout: float = 3.0) -> bool:
    try:
        with urllib.request.urlopen(url, timeout=timeout) as resp:
            return 200 <= resp.status < 500
    except Exception:
        return False


def wait_ready(name: str, url: str, tries: int = 45) -> bool:
    for i in range(tries):
        if http_ok(url):
            print(f"OK  {name}", flush=True)
            return True
        time.sleep(2)
        if (i + 1) % 5 == 0:
            print(f"waiting {name} ({i + 1}/{tries})…", flush=True)
    print(f"FAIL {name} not ready: {url}", file=sys.stderr)
    return False


def list_skill_dirs(skills: Path) -> list[Path]:
    if not skills.is_dir():
        return []
    out: list[Path] = []
    for p in sorted(skills.iterdir()):
        if not p.is_dir():
            continue
        if p.name in SKIP_SKILL_DIRS or p.name.startswith("."):
            continue
        if (p / "SKILL.md").is_file():
            out.append(p)
        if p.name in CATEGORY_DIRS:
            for sub in sorted(p.iterdir()):
                if sub.is_dir() and (sub / "SKILL.md").is_file():
                    out.append(sub)
    return out


def copy_md_tree(src: Path, dest: Path) -> int:
    """Copy .md / .txt / .pdf files under src → dest. Returns file count."""
    n = 0
    if not src.exists():
        return 0
    dest.mkdir(parents=True, exist_ok=True)
    if src.is_file():
        if src.suffix.lower() in {".md", ".txt", ".pdf", ".csv"}:
            shutil.copy2(src, dest / src.name)
            return 1
        return 0
    for path in src.rglob("*"):
        if not path.is_file():
            continue
        if path.suffix.lower() not in {".md", ".txt", ".pdf", ".csv"}:
            continue
        if any(part.startswith(".") or part == "__pycache__" for part in path.parts):
            continue
        rel = path.relative_to(src)
        target = dest / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, target)
        n += 1
    return n


def sync_skills_and_docs(skill_dirs: list[Path]) -> int:
    total = 0
    skills_out = DOCS_ROOT / "skills"
    if skills_out.exists():
        # Refresh mirror of current skill set
        shutil.rmtree(skills_out, ignore_errors=True)
    for d in skill_dirs:
        try:
            dest_name = d.relative_to(SKILLS_DIR).as_posix()
        except ValueError:
            dest_name = d.name
        total += copy_md_tree(d, skills_out / dest_name)
    if HERMES_DOCS.is_dir():
        total += copy_md_tree(HERMES_DOCS, DOCS_ROOT / "hermes-docs")
    if HERMES_SETUP.is_dir():
        # inbox packs (optional)
        for child in sorted(HERMES_SETUP.iterdir()):
            if child.name.startswith("."):
                continue
            if child.name.lower() == "readme.md":
                continue
            if child.is_dir():
                total += copy_md_tree(child, DOCS_ROOT / "setup" / child.name)
            elif child.is_file() and child.suffix.lower() in {".md", ".txt", ".pdf"}:
                (DOCS_ROOT / "setup").mkdir(parents=True, exist_ok=True)
                shutil.copy2(child, DOCS_ROOT / "setup" / child.name)
                total += 1
    return total


def learn_scan() -> dict:
    req = urllib.request.Request(
        f"{INGEST_URL}/v1/learn/scan",
        data=json.dumps({"root": "docs"}).encode("utf-8"),
        method="POST",
        headers={"content-type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=180) as resp:
        return json.loads(resp.read().decode("utf-8") or "{}")


def main() -> int:
    print("==> post-ready learn (skills|docs)", flush=True)
    skill_dirs = list_skill_dirs(SKILLS_DIR)
    if not skill_dirs:
        print(f"skip: no skills in {SKILLS_DIR} (empty or only _example)", flush=True)
        return 0

    print(f"skills found: {len(skill_dirs)} under {SKILLS_DIR}", flush=True)

    # Prefer Router Worker / OmniRouter; 9Router only when ENABLE_9ROUTER=1
    llm_ok = False
    if wait_ready("model-router", f"http://127.0.0.1:{ROUTER_PORT}/health", tries=20):
        llm_ok = True
    elif ENABLE_OMNI and wait_ready("omni-router", f"http://127.0.0.1:{OMNI_PORT}/", tries=15):
        llm_ok = True
    elif ENABLE_9ROUTER and wait_ready("9router", f"http://127.0.0.1:{N9_PORT}/", tries=15):
        llm_ok = True
    if not llm_ok:
        print("FAIL no LLM router ready (model-router / omni / 9router)", file=sys.stderr)
        return 1
    # Hermes×1 publishes dashboard; replicas>1 use gateway/traefik health
    hermes_urls = []
    if HERMES_REPLICAS <= 1:
        hermes_urls.append(f"http://127.0.0.1:{HERMES_PORT}/")
    hermes_urls.extend(
        [
            f"http://127.0.0.1:{GATEWAY_PORT}/health",
            f"http://127.0.0.1:{TRAEFIK_PORT}/health",
        ]
    )
    hermes_ok = False
    for url in hermes_urls:
        if wait_ready("hermes", url, tries=15):
            hermes_ok = True
            break
    if not hermes_ok:
        print(
            "FAIL hermes edge not ready "
            f"(tried dashboard/Traefik/gateway; replicas={HERMES_REPLICAS})",
            file=sys.stderr,
        )
        return 1
    if not wait_ready("ingest", f"{INGEST_URL}/health"):
        return 1

    DOCS_ROOT.mkdir(parents=True, exist_ok=True)
    n_files = sync_skills_and_docs(skill_dirs)
    print(f"synced {n_files} doc file(s) → {DOCS_ROOT}", flush=True)
    if n_files <= 0:
        print("skip: nothing to learn after sync", flush=True)
        return 0

    try:
        result = learn_scan()
    except urllib.error.HTTPError as e:
        print(f"WARN: learn/scan HTTP {e.code}: {e.read()[:300]!r}", file=sys.stderr)
        return 1
    except Exception as e:
        print(f"WARN: learn/scan failed: {e}", file=sys.stderr)
        return 1

    print(
        f"OK: learn scan scanned={result.get('scanned')} new={result.get('count')} "
        f"auto={result.get('auto_ingest')} (Hermes skills already mounted)",
        flush=True,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
