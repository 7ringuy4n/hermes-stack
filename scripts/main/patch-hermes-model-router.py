#!/usr/bin/env python3
"""Point shared Hermes config at router-worker (OmniRouter default path).

Reads OMNIROUTER_API_KEY / OMNIROUTER_DEFAULT_COMBO from stack .env when present.
Safe to re-run (idempotent base_url / provider / default patch).
"""
from __future__ import annotations

import os
import re
import sys
from pathlib import Path

ROOT = Path(os.environ.get("STACK_ROOT", Path(__file__).resolve().parents[2]))
HERMES_DATA = Path(os.environ.get("HERMES_DATA_DIR", os.environ.get("ASSISTANT_DATA_DIR", "/data/assistant")))
MODEL_ROUTER_BASE = os.environ.get("HERMES_OPENAI_BASE_URL", "http://router-worker:8096/v1").strip()
# Combo alias (OMNIROUTER_DEFAULT_COMBO) — not a vendor model id.
DEFAULT_COMBO = os.environ.get("OMNIROUTER_DEFAULT_COMBO", "hermes").strip() or "hermes"

# Obsolete image pins cleared on shared .env sync (combo-based routing only).
_OBSOLETE_IMAGE_ENV = [
    "IMAGE_OMNI_MODEL",
    "OMNIROUTER_IMAGE_MODEL",
    "IMAGE_GEN_SIZE",
    "IMAGE_GEN_HEAD_MODEL",
    "IMAGE_LLM_MODEL",
    "IMAGE_LLM_SIZE",
    "IMAGE_LLM_PROVIDER",
    "IMAGE_LLM_API_KEY",
    "IMAGE_LLM_BASE_URL",
    "IMAGE_VENDOR_PROVIDER",
    "IMAGE_VENDOR_API_KEY",
    "IMAGE_VENDOR_URL",
    "IMAGE_VENDOR_MODEL",
    "IMAGE_BACKENDS",
]


def load_env(path: Path) -> dict[str, str]:
    out: dict[str, str] = {}
    if not path.is_file():
        return out
    raw = path.read_text(encoding="utf-8")
    if "\\n" in raw:
        raw = raw.replace("\\n", "\n")
    for line in raw.splitlines():
        s = line.strip()
        if not s or s.startswith("#") or "=" not in s:
            continue
        k, v = s.split("=", 1)
        out[k.strip()] = v.strip().strip('"').strip("'")
    return out


def patch_hermes_config(cfg: Path, key: str, model: str, base_url: str) -> bool:
    if not cfg.is_file():
        print(f"WARN: missing {cfg}", file=sys.stderr)
        return False
    text = cfg.read_text(encoding="utf-8")
    orig = text
    if re.search(r"(?m)^model:\s*$", text):
        text = re.sub(r"(?m)^(  default:\s*).*$", rf'\1"{model}"', text, count=1)
        text = re.sub(r"(?m)^(  provider:\s*).*$", r'\1"custom"', text, count=1)
        text = re.sub(r"(?m)^(  base_url:\s*).*$", rf'\1"{base_url}"', text, count=1)
    else:
        block = (
            "\nmodel:\n"
            f'  default: "{model}"\n'
            '  provider: "custom"\n'
            f'  base_url: "{base_url}"\n'
        )
        if "model:" not in text:
            text = text.rstrip() + block
        else:
            text = re.sub(r"(?m)^(  default:\s*).*$", rf'\1"{model}"', text, count=1)
            text = re.sub(r"(?m)^(  provider:\s*).*$", r'\1"custom"', text, count=1)
            text = re.sub(r"(?m)^(  base_url:\s*).*$", rf'\1"{base_url}"', text, count=1)
    if key and re.search(r"(?m)^  api_key:\s*", text):
        text = re.sub(r"(?m)^(  api_key:\s*).*$", rf'\1"{key}"', text, count=1)
    elif key:
        text = re.sub(
            rf'(?m)^(  base_url:\s*"{re.escape(base_url)}"\s*)$',
            rf'\1\n  api_key: "{key}"',
            text,
            count=1,
        )
    if text != orig:
        cfg.write_text(text, encoding="utf-8")
        print(f"OK: patched {cfg} → {base_url} model={model}")
        return True
    print(f"OK: {cfg} already points at model-router")
    return True


def patch_shared_env(
    envp: Path,
    key: str,
    base_url: str,
    *,
    omni_base: str = "",
    image_combo: str = "",
    image_head_member: str = "",
) -> None:
    lines: dict[str, str] = {}
    if envp.is_file():
        raw = envp.read_text(encoding="utf-8")
        if "\\n" in raw:
            raw = raw.replace("\\n", "\n")
        for line in raw.splitlines():
            if "=" in line and not line.strip().startswith("#"):
                k, v = line.split("=", 1)
                lines[k.strip()] = v
    for obsolete in _OBSOLETE_IMAGE_ENV:
        lines.pop(obsolete, None)
    if key:
        lines["OPENAI_API_KEY"] = key
        lines["OMNIROUTER_API_KEY"] = key
    if omni_base:
        lines["OMNIROUTER_BASE_URL"] = omni_base
    if image_combo:
        lines["IMAGE_GEN_COMBO"] = image_combo
    if image_head_member:
        lines["IMAGE_GEN_HEAD_MEMBER"] = image_head_member
    else:
        lines.pop("IMAGE_GEN_HEAD_MEMBER", None)
    lines["OPENAI_BASE_URL"] = base_url
    envp.parent.mkdir(parents=True, exist_ok=True)
    envp.write_text("\n".join(f"{k}={v}" for k, v in lines.items()) + "\n", encoding="utf-8")
    try:
        envp.chmod(0o600)
    except OSError:
        pass


def sync_replica_env(shared_env: Path) -> None:
    replicas = shared_env.parent / "replicas"
    if not shared_env.is_file() or not replicas.is_dir():
        return
    text = shared_env.read_text(encoding="utf-8")
    for rep in replicas.iterdir():
        if not rep.is_dir():
            continue
        dst = rep / ".env"
        try:
            if dst.is_symlink():
                continue
            dst.write_text(text, encoding="utf-8")
            dst.chmod(0o600)
        except OSError:
            continue


def sync_replica_configs(shared_cfg: Path) -> None:
    replicas = shared_cfg.parent / "replicas"
    if not replicas.is_dir():
        return
    for rep in replicas.glob("*/config.yaml"):
        try:
            rep.write_text(shared_cfg.read_text(encoding="utf-8"), encoding="utf-8")
        except OSError:
            continue


def main() -> int:
    stack_env = load_env(ROOT / ".env")
    key = (
        stack_env.get("OMNIROUTER_API_KEY")
        or stack_env.get("OPENAI_API_KEY")
        or stack_env.get("N9ROUTER_API_KEY")
        or ""
    ).strip()
    model = stack_env.get("OMNIROUTER_DEFAULT_COMBO", DEFAULT_COMBO).strip() or DEFAULT_COMBO
    base_url = stack_env.get("HERMES_OPENAI_BASE_URL", MODEL_ROUTER_BASE).strip() or MODEL_ROUTER_BASE
    omni_base = stack_env.get("OMNIROUTER_BASE_URL", "http://omni-router:20129/v1").strip()
    image_combo = stack_env.get("IMAGE_GEN_COMBO", "image-gen").strip() or "image-gen"
    image_head_member = (stack_env.get("IMAGE_GEN_HEAD_MEMBER") or "").strip()
    cfg = HERMES_DATA / "config.yaml"
    if not patch_hermes_config(cfg, key, model, base_url):
        return 1
    patch_shared_env(
        HERMES_DATA / ".env",
        key,
        base_url,
        omni_base=omni_base,
        image_combo=image_combo,
        image_head_member=image_head_member,
    )
    sync_replica_env(HERMES_DATA / ".env")
    sync_replica_configs(cfg)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
