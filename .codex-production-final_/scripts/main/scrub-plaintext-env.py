#!/usr/bin/env python3
"""Remove plaintext secret exports after OpenBao seed / update.

SoT for API keys is OpenBao KV. Deletes host-side .env.openbao copies after compose
has started; strips seeded key values from ROOT/.env (keys kept, values empty).

run.sh must call load-openbao-env immediately after this scrub so COMPOSE_HOST_KEYS
(and hermes env_file .env.openbao) are refilled for the next compose recreate.
Also removes retired KEY= lines (ADMIN_API_TOKEN, WEB_BACKENDS, …).
"""
from __future__ import annotations

import importlib.util
import os
import sys
from pathlib import Path

from openbao_common import ENV_SCRUB_KEYS, OBSOLETE_ENV_KEYS, is_secret_env_name

ROOT = Path(os.environ.get("STACK_ROOT") or Path(__file__).resolve().parents[2])
ENV_PATH = ROOT / ".env"
DATA_DIR = Path(
    os.environ.get("ASSISTANT_DATA_DIR")
    or os.environ.get("HERMES_DATA_DIR")
    or "/data/assistant"
)


def _scrub_env_file(path: Path) -> int:
    if not path.is_file():
        return 0
    lines_out: list[str] = []
    changed = 0
    want = {k.casefold() for k in ENV_SCRUB_KEYS}
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        raw = line.strip()
        if not raw or raw.startswith("#") or "=" not in line:
            lines_out.append(line)
            continue
        key, _, val = line.partition("=")
        k = key.strip()
        if (
            k.casefold() in want or is_secret_env_name(k)
        ) and str(val).strip() and not str(val).strip().startswith("CHANGE_ME"):
            lines_out.append(f"{k}=")
            changed += 1
        else:
            lines_out.append(line)
    if changed:
        path.write_text("\n".join(lines_out) + "\n", encoding="utf-8")
        try:
            os.chmod(path, 0o600)
        except OSError:
            pass
    return changed


def _unlink(path: Path) -> bool:
    try:
        if path.is_file():
            path.unlink()
            return True
    except OSError as e:
        print(f"WARN: could not remove {path}: {e}", file=sys.stderr)
    return False


def _cleanup_obsolete() -> None:
    spec = importlib.util.spec_from_file_location(
        "cleanup_obsolete_env",
        Path(__file__).resolve().parent / "cleanup-obsolete-env.py",
    )
    if not spec or not spec.loader:
        return
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    for p in (ENV_PATH, DATA_DIR / ".env"):
        gone = mod.remove_obsolete_keys(p, OBSOLETE_ENV_KEYS)
        if gone:
            print(
                f"OK: removed {len(gone)} obsolete key(s) from {p}: "
                f"{', '.join(sorted(set(gone)))}"
            )


def main() -> int:
    removed = []
    for p in (
        DATA_DIR / ".env.openbao",
        DATA_DIR / ".env",
        DATA_DIR / "profile-options.env",
        ROOT / "profile-options.env",
    ):
        if _unlink(p):
            removed.append(str(p))
    n = _scrub_env_file(ENV_PATH)
    print(f"OK: removed {len(removed)} plaintext export(s); scrubbed {n} key value(s) in {ENV_PATH}")
    for p in removed:
        print(f"  - {p}")
    try:
        _cleanup_obsolete()
    except Exception as e:  # noqa: BLE001
        print(f"WARN: obsolete env cleanup skipped: {e}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
