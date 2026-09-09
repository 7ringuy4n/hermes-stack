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

HOST_UNIT_SCRIPTS = {
    "router_worker_chat_norm.py",
    "router_worker_identity_unit.py",
}
GATEWAY_UNIT_SCRIPTS = {
    "workflow_gateway_unit.py",
    "workflow_schedule_concurrency_unit.py",
}

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
    ("zalo_user_latency.py", "17"),
    ("zalo_weather_fuel_lab.py", "26"),
    ("zalo_scheduled_composed_image_lab.py", "27-fire"),
    ("zalo_flexible_composed_layout_lab.py", "flexible-layout"),
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
    ("zalo_dm_group_capability_concurrency_lab.py", "76"),
    ("zalo_queue_failover_lab.py", "queue-failover"),
    ("zalo_active_cancel_lab.py", "active-cancel"),
    ("zalo_note_locale_lab.py", "44-note-locale"),
    ("zalo_continuous_messages_lab.py", "continuous-messages"),
    ("memory_scale_10m_lab.py", "memory-scale-10m"),
]


def ts() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat()


def report_cell(value: str, limit: int = 120) -> str:
    """Return one safe Markdown-table cell without terminal auth prompts."""
    lines: list[str] = []
    for raw in (value or "").splitlines():
        line = raw.strip()
        lowered = line.lower()
        if not line:
            continue
        if "password:" in lowered and ("sudo" in lowered or "authenticate" in lowered):
            continue
        lines.append(line)
    clean = " / ".join(lines).replace("|", "\\|").replace("`", "'")
    return clean[:limit]


def progress_line(index: int, total: int, kind: str, case: str, name: str) -> str:
    return f"running test case {index}/{total}: {kind} {case} {name}"


def enabled(name: str) -> bool:
    return (os.environ.get(name) or "").strip().casefold() in {"1", "true", "yes"}


def unit_command(name: str) -> list[str]:
    path = ROOT / "test" / "scripts" / name
    if not enabled("ASSISTANT_TEST_LOCAL") or name in HOST_UNIT_SCRIPTS:
        return [PY, str(path)]
    image = "assistant-api-gateway" if name in GATEWAY_UNIT_SCRIPTS else "assistant-dispatcher"
    return [
        "docker", "run", "--rm",
        "-e", "ASSISTANT_REPO_ROOT=/repo",
        "-e", "PYTHONUTF8=1",
        "-e", "PYTHONIOENCODING=utf-8",
        "-v", f"{ROOT}:/repo",
        "-w", "/repo",
        image, "python", f"test/scripts/{name}",
    ]


def run_script(name: str, case: str, *, unit: bool = False) -> tuple[str, int, str]:
    path = ROOT / "test" / "scripts" / name
    if not path.is_file():
        return case, 127, f"MISSING {name}"
    env = os.environ.copy()
    # A parent shell may point at another checkout. Test evidence must always
    # stay with the case index that launched the child process.
    env["ASSISTANT_REPO_ROOT"] = str(ROOT)
    # Keep child output deterministic when the host shell uses a legacy Windows
    # console code page; several tests intentionally exercise Unicode content.
    env.setdefault("PYTHONUTF8", "1")
    env.setdefault("PYTHONIOENCODING", "utf-8")
    try:
        p = subprocess.run(
            unit_command(name) if unit else [PY, str(path)],
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
    selected_units = [
        row for row in UNITS if not filt or row[1] in filt or row[0] in filt
    ]
    selected_vps = [] if skip_vps else [
        row for row in VPS if not filt or row[1] in filt or row[0] in filt
    ]
    total = len(selected_units) + len(selected_vps)
    progress = 0

    for name, case in selected_units:
        progress += 1
        print(progress_line(progress, total, "unit", case, name), flush=True)
        c, rc, tail = run_script(name, case, unit=True)
        status = "PASS" if rc == 0 else f"FAIL({rc})"
        if rc != 0:
            fails += 1
        rows.append(f"| unit | {c} | {name} | {status} | `{report_cell(tail)}` |")
        print(f"[unit {c}] {status} {name}", flush=True)

    for name, case in selected_vps:
        progress += 1
        print(progress_line(progress, total, "vps", case, name), flush=True)
        c, rc, tail = run_script(name, case)
        status = "PASS" if rc == 0 else f"FAIL({rc})"
        if rc != 0:
            fails += 1
        rows.append(f"| vps | {c} | {name} | {status} | `{report_cell(tail)}` |")
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
