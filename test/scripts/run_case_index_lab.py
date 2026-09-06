# -*- coding: utf-8 -*-
"""Run the current test/RULES.md offline and VPS release gates in batch.

Env (VPS scripts): ASSISTANT_SSH_HOST, ASSISTANT_SSH_USER, ASSISTANT_SSH_PASSWORD
Optional: SKIP_VPS=1 (units only), CASE_FILTER=38,32 (comma ids)

Report: test/reports/run-case-index-lab/SUMMARY.md
"""
from __future__ import annotations

import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "test" / "reports" / "run-case-index-lab"
PY = sys.executable

UNITS: list[tuple[str, str]] = [
    (path.name, path.stem)
    for path in sorted((ROOT / "test" / "scripts").glob("*_unit.py"))
]
UNITS.append(("router_worker_chat_norm.py", "router_worker_chat_norm"))

VPS: list[tuple[str, str]] = [
    ("vps_health_check.py", "health"),
    ("omni_combo_preflight.py", "38"),
    ("zalo_tn_greeting_inject.py", "32"),
    ("zalo_tn_visual_weather_pdf_inject.py", "39"),
    ("zalo_latency_lab.py", "17"),
    ("zalo_special_four_lab.py", "25"),
    ("zalo_weather_fuel_lab.py", "26"),
    ("file_pipeline_security_lab.py", "19"),
    ("grafana_integration_lab.py", "20"),
    ("defaults_routers_lab.py", "21"),
    ("zalo_tn_history_regression.py", "history"),
    ("openbao_kv_lab.py", "43"),
    ("zalo_tn_youtube_refuse_inject.py", "yt-refuse"),
    ("embedding_compact_lab.py", "embed"),
    ("zalo_tn_remaining_suite_lab.py", "remaining"),
    ("env_obsolete_cleanup_lab.py", "env-clean"),
    ("zalo_tn_archive_extract_lab.py", "archive"),
    ("zalo_dm_group_concurrency_lab.py", "dm-group-concurrency"),
    ("zalo_queue_failover_lab.py", "queue-failover"),
    ("zalo_active_cancel_lab.py", "active-cancel"),
]


def ts() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat()


def run_script(name: str, case: str) -> tuple[str, int, str]:
    path = ROOT / "test" / "scripts" / name
    if not path.is_file():
        return case, 127, f"MISSING {name}"
    env = os.environ.copy()
    env.setdefault("ASSISTANT_REPO_ROOT", str(ROOT))
    try:
        p = subprocess.run(
            [PY, str(path)],
            cwd=str(ROOT),
            env=env,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=int(env.get("CASE_INDEX_TIMEOUT_S", "600")),
        )
        out = (p.stdout or "") + (p.stderr or "")
        tail = "\n".join(out.strip().splitlines()[-8:])
        return case, p.returncode, tail
    except subprocess.TimeoutExpired:
        return case, 124, "TIMEOUT"
    except Exception as e:
        return case, 1, str(e)


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    filt = {
        x.strip()
        for x in (os.environ.get("CASE_FILTER") or "").split(",")
        if x.strip()
    }
    skip_vps = os.environ.get("SKIP_VPS", "0").strip() in {"1", "true", "yes"}
    rows: list[str] = []
    fails = 0

    for name, case in UNITS:
        if filt and case not in filt and name not in filt:
            continue
        c, rc, tail = run_script(name, case)
        status = "PASS" if rc == 0 else f"FAIL({rc})"
        if rc != 0:
            fails += 1
        rows.append(f"| unit | {c} | {name} | {status} | `{tail[:120]}` |")
        print(f"[unit {c}] {status} {name}", flush=True)

    if not skip_vps:
        for name, case in VPS:
            if filt and case not in filt and name not in filt:
                continue
            c, rc, tail = run_script(name, case)
            status = "PASS" if rc == 0 else f"FAIL({rc})"
            if rc != 0:
                fails += 1
            rows.append(f"| vps | {c} | {name} | {status} | `{tail[:120]}` |")
            print(f"[vps {c}] {status} {name}", flush=True)

    md = (
        f"# Case index lab — {ts()}\n\n"
        "| kind | case | script | result | tail |\n"
        "|------|------|--------|--------|------|\n"
        + "\n".join(rows)
        + f"\n\n**Fails:** {fails}\n"
    )
    (OUT / "SUMMARY.md").write_text(md, encoding="utf-8")
    print(f"SUMMARY {OUT / 'SUMMARY.md'} fails={fails}", flush=True)
    return 1 if fails else 0


if __name__ == "__main__":
    raise SystemExit(main())
