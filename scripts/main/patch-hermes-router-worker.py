#!/usr/bin/env python3
"""Point shared Hermes config at router-worker (OmniRoute path).

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
ROUTER_WORKER_BASE = os.environ.get("HERMES_OPENAI_BASE_URL", "http://router-worker:8096/v1").strip()
# Combo alias (OMNIROUTER_DEFAULT_COMBO) — not a vendor model id.
DEFAULT_COMBO = os.environ.get("OMNIROUTER_DEFAULT_COMBO", "hermes").strip() or "hermes"

# Obsolete image pins cleared on shared .env sync (combo-based routing only).
_OBSOLETE_IMAGE_ENV = [
    "IMAGE_OMNI_MODEL",
    "OMNIROUTER_IMAGE_MODEL",
    "IMAGE_GEN_SIZE",
    "IMAGE_GEN_HEAD_MEMBER",
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
    text = _patch_vision_routing(text, key=key, base_url=base_url)
    text = _patch_web_routing(text)
    if text != orig:
        cfg.write_text(text, encoding="utf-8")
        print(f"OK: patched {cfg} → {base_url} model={model}")
        return True
    print(f"OK: {cfg} already points at router-worker")
    return True


def _patch_web_routing(text: str) -> str:
    """Route both native search and extraction through the stack-owned provider."""
    out = text
    if not re.search(r"(?m)^web:[ \t]*$", out):
        out = out.rstrip() + (
            "\nweb:\n"
            "  search_backend: router-worker\n"
            "  extract_backend: router-worker\n"
        )
    else:
        for field in ("search_backend", "extract_backend"):
            pattern = rf"(?m)^(  {field}:\s*).*$"
            if re.search(pattern, out):
                out = re.sub(pattern, rf"\1router-worker", out, count=1)
            else:
                out = re.sub(
                    r"(?m)^(web:[ \t]*)$",
                    rf"\1\n  {field}: router-worker",
                    out,
                    count=1,
                )
    return _patch_enabled_plugin(out, "web/router_worker")


def _patch_enabled_plugin(text: str, plugin_key: str) -> str:
    """Add one Hermes user plugin without replacing operator-managed entries."""
    lines = text.splitlines()
    if any(line.strip() == f"- {plugin_key}" for line in lines):
        return text

    plugins_idx = next(
        (i for i, line in enumerate(lines) if line == "plugins:"),
        None,
    )
    if plugins_idx is None:
        lines.extend(["", "plugins:", "  enabled:", f"    - {plugin_key}"])
        return "\n".join(lines).rstrip() + "\n"

    section_end = next(
        (
            i
            for i in range(plugins_idx + 1, len(lines))
            if lines[i] and not lines[i].startswith((" ", "#"))
        ),
        len(lines),
    )
    enabled_idx = next(
        (
            i
            for i in range(plugins_idx + 1, section_end)
            if lines[i].startswith("  enabled:")
        ),
        None,
    )
    if enabled_idx is None:
        lines[plugins_idx + 1:plugins_idx + 1] = [
            "  enabled:",
            f"    - {plugin_key}",
        ]
    elif lines[enabled_idx].strip() == "enabled: []":
        lines[enabled_idx] = "  enabled:"
        lines.insert(enabled_idx + 1, f"    - {plugin_key}")
    elif "[" in lines[enabled_idx] and "]" in lines[enabled_idx]:
        raw = lines[enabled_idx].split("[", 1)[1].rsplit("]", 1)[0]
        existing = [item.strip().strip("'\"") for item in raw.split(",") if item.strip()]
        lines[enabled_idx:enabled_idx + 1] = [
            "  enabled:",
            *(f"    - {item}" for item in existing),
            f"    - {plugin_key}",
        ]
    else:
        insert_at = enabled_idx + 1
        while insert_at < section_end and (
            not lines[insert_at].strip()
            or lines[insert_at].startswith("    - ")
            or lines[insert_at].lstrip().startswith("#")
        ):
            insert_at += 1
        lines.insert(insert_at, f"    - {plugin_key}")
    return "\n".join(lines).rstrip() + "\n"


def _patch_vision_routing(text: str, *, key: str, base_url: str) -> str:
    """Native image attach + vision-ocr aux so Zalo describe skips blind text-only path."""
    out = text
    if not re.search(r"(?m)^agent:\s*$", out):
        out = out.rstrip() + "\nagent:\n  image_input_mode: native\n"
    elif not re.search(r"(?m)^  image_input_mode:\s*", out):
        out = re.sub(r"(?m)^(agent:\s*)$", r"\1\n  image_input_mode: native", out, count=1)
    else:
        out = re.sub(r"(?m)^(  image_input_mode:\s*).*$", r"\1native", out, count=1)
    if re.search(r"(?m)^  supports_vision:\s*", out):
        out = re.sub(r"(?m)^(  supports_vision:\s*).*$", r"\1true", out, count=1)
    elif re.search(r"(?m)^model:\s*$", out):
        out = re.sub(r"(?m)^(model:\s*)$", r"\1\n  supports_vision: true", out, count=1)
    vision_block = (
        "auxiliary:\n"
        "  vision:\n"
        '    provider: "custom"\n'
        '    model: "vision-ocr"\n'
        f'    base_url: "{base_url}"\n'
        f'    api_key: "{key}"\n'
        "    timeout: 120\n"
    )
    if not re.search(r"(?m)^auxiliary:\s*$", out):
        out = out.rstrip() + "\n" + vision_block
    elif not re.search(r"(?m)^  vision:\s*$", out):
        out = re.sub(r"(?m)^(auxiliary:\s*)$", r"\1\n  vision:\n    provider: \"custom\"\n    model: \"vision-ocr\"\n    base_url: \"" + base_url + "\"\n    api_key: \"" + key + "\"\n    timeout: 120", out, count=1)
    else:
        out = re.sub(r'(?m)^(    model:\s*).*$', r'\1"vision-ocr"', out, count=1)
        out = re.sub(r'(?m)^(    base_url:\s*).*$', rf'\1"{base_url}"', out, count=1)
        if key:
            if re.search(r"(?m)^    api_key:\s*", out):
                out = re.sub(r'(?m)^(    api_key:\s*).*$', rf'\1"{key}"', out, count=1)
    return out


def patch_shared_env(
    envp: Path,
    key: str,
    base_url: str,
    *,
    omni_base: str = "",
    image_combo: str = "",
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
        or ""
    ).strip()
    model = stack_env.get("OMNIROUTER_DEFAULT_COMBO", DEFAULT_COMBO).strip() or DEFAULT_COMBO
    base_url = stack_env.get("HERMES_OPENAI_BASE_URL", ROUTER_WORKER_BASE).strip() or ROUTER_WORKER_BASE
    omni_base = stack_env.get("OMNIROUTER_BASE_URL", "http://omni-router:20129/v1").strip()
    image_combo = stack_env.get("IMAGE_GEN_COMBO", "image-gen").strip() or "image-gen"
    cfg = HERMES_DATA / "config.yaml"
    if not patch_hermes_config(cfg, key, model, base_url):
        return 1
    patch_shared_env(
        HERMES_DATA / ".env",
        key,
        base_url,
        omni_base=omni_base,
        image_combo=image_combo,
    )
    sync_replica_env(HERMES_DATA / ".env")
    sync_replica_configs(cfg)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
