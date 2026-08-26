# -*- coding: utf-8 -*-
"""Run test/RULES.md §15 unit + VPS lab scripts in batch.

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
    ("schedule_timezone_unit.py", "15"),
    ("multi_request_unit.py", "16"),
    ("knowledge_cite_unit.py", "29"),
    ("llm_classify_unit.py", "24"),
    ("gateway_noise_unit.py", "22"),
    ("inbound_queue_unit.py", "23"),
    ("web_search_backends_unit.py", "18"),
    ("grafana_pairing_unit.py", "20"),
    ("defaults_profile_unit.py", "21"),
    ("ux_copy_unit.py", "ux"),
    ("zalo_attachment_unit.py", "34"),
    ("schedule_crud_unit.py", "34"),
    ("secret_probe_path_unit.py", "32"),
    ("ocr_refuse_unit.py", "35"),
    ("paddle_ocr_unit.py", "36"),
    ("omni_rotate_noreply_unit.py", "37"),
    ("zalo_workflow_parallel_unit.py", "wf-par"),
    ("soul_deception_unit.py", "soul"),
    ("workflow_cadence_unit.py", "wf"),
    ("zalo_store_unit.py", "zalo-store"),
]

VPS: list[tuple[str, str]] = [
    ("vps_health_check.py", "health"),
    ("omni_combo_preflight.py", "38"),
    ("zalo_tn_greeting_inject.py", "32"),
    ("zalo_latency_lab.py", "17"),
    ("zalo_special_four_lab.py", "25"),
    ("zalo_weather_fuel_lab.py", "26"),
    ("file_pipeline_security_lab.py", "19"),
    ("grafana_integration_lab.py", "20"),
    ("defaults_routers_lab.py", "21"),
    ("zalo_tn_history_regression.py", "history"),
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
