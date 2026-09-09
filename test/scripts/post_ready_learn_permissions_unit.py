#!/usr/bin/env python3
"""Regression checks for restored knowledge-tree ownership and failure propagation."""
from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def main() -> int:
    run = (ROOT / "run.sh").read_text(encoding="utf-8")
    start = run.index("do_post_ready_learn()")
    end = run.index("\nenv_upsert()", start)
    block = run[start:end]
    checks = {
        "rejects a root data path": '"$data_root" == "/"' in block,
        "limits repair to the docs mirror": 'docs_root="${data_root}/docs"' in block
        and 'chown -R "$owner_uid:$owner_gid" "$docs_root"' in block,
        "supports an unprivileged deploy user without an interactive prompt": all(
            marker in block
            for marker in (
                'sudo -n mkdir -p "$docs_root"',
                'sudo -n chown -R "$owner_uid:$owner_gid" "$docs_root"',
                'hermes_container="$(compose ps -q hermes | head -n1)"',
                'docker exec -u 0 "$hermes_container"',
            )
        )
        and 'sudo mkdir -p "$docs_root"' not in block,
        "repairs inaccessible restored descendants":
        '|| ! chmod -R u+rwX "$docs_root" 2>/dev/null' in block,
        "root execution targets the runtime owner": 'owner_uid="${HERMES_UID:-1000}"' in block
        and 'owner_gid="${HERMES_GID:-1000}"' in block,
        "restores deploy-user write access": 'chmod -R u+rwX "$docs_root"' in block,
        "knowledge sync failure propagates": 'if ! python3 "${SCRIPTS_DIR}/post-ready-learn.py"' in block
        and "return 1" in block,
        "failure is not converted to warning success": "WARN: post-ready-learn failed" not in block,
    }
    for name, ok in checks.items():
        print(("PASS" if ok else "FAIL"), name)
    return 0 if all(checks.values()) else 1


if __name__ == "__main__":
    raise SystemExit(main())
