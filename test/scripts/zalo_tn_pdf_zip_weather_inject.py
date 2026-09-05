# -*- coding: utf-8 -*-
"""Inject PDF, zip, and weather-scene turns for Zalo user Tn (VPS lab).

Uses bridge /inject-event like image-analyze inject.
Env: ASSISTANT_SSH_* ; required ZALO_TEST_USER_ID; optional ZALO_TEST_WAIT_S (default 180)
Report: test/reports/run-zalo-tn-pdf-zip-weather/
"""
from __future__ import annotations

import io
import json
import os
import sys
import zipfile
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from deploy_stack import connect, sudo_bash  # noqa: E402
from sanitize import sanitize as _sanitize  # noqa: E402

if hasattr(sys.stdout, "buffer"):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

ROOT = Path(os.environ.get("ASSISTANT_REPO_ROOT", Path(__file__).resolve().parents[2]))
OUT = ROOT / "test" / "reports" / "run-zalo-tn-pdf-zip-weather"
TN_ID = (os.environ.get("ZALO_TEST_USER_ID") or "").strip()
WAIT_S = int(os.environ.get("ZALO_TEST_WAIT_S") or "180")


def ts() -> str:
    return datetime.now(timezone.utc).astimezone().strftime("%Y-%m-%d %H:%M:%S %z")


def _inject_text(c, text: str, *, label: str) -> dict:
    payload = {
        "type": "message",
        "threadId": TN_ID,
        "threadType": "user",
        "senderId": TN_ID,
        "senderName": "Tn",
        "text": text,
        "messageId": f"lab-{label}-{int(datetime.now().timestamp())}",
    }
    cmd = (
        "curl -sfS -X POST http://127.0.0.1:8787/inject-event "
        f"-H 'Content-Type: application/json' -d {_sanitize(json.dumps(payload))}"
    )
    raw = sudo_bash(c, cmd)
    return {"label": label, "inject": raw[:500]}


def _stage_and_inject_file(c, local_bytes: bytes, name: str, *, caption: str = "") -> dict:
    remote_dir = f"/opt/data/media/inbound/{TN_ID}"
    remote_path = f"{remote_dir}/{name}"
    sudo_bash(c, f"mkdir -p {remote_dir}")
    import base64

    b64 = base64.b64encode(local_bytes).decode("ascii")
    sudo_bash(
        c,
        f"echo {_sanitize(b64)} | base64 -d > {_sanitize(remote_path)} && chmod 664 {_sanitize(remote_path)}",
    )
    payload = {
        "type": "message",
        "threadId": TN_ID,
        "threadType": "user",
        "senderId": TN_ID,
        "senderName": "Tn",
        "text": caption or name,
        "messageId": f"lab-file-{name}-{int(datetime.now().timestamp())}",
        "media": {
            "url": f"file://{remote_path}",
            "fileName": name,
            "kind": "file",
            "mime": "application/octet-stream",
        },
    }
    cmd = (
        "curl -sfS -X POST http://127.0.0.1:8787/inject-event "
        f"-H 'Content-Type: application/json' -d {_sanitize(json.dumps(payload))}"
    )
    raw = sudo_bash(c, cmd)
    return {"file": name, "inject": raw[:500]}


def main() -> int:
    if not TN_ID:
        print("ERROR: ZALO_TEST_USER_ID is required", file=sys.stderr)
        return 2
    OUT.mkdir(parents=True, exist_ok=True)
    c = connect()
    report: dict = {"ts": ts(), "user": TN_ID, "steps": []}
    try:
        pdf_body = (
            b"%PDF-1.4\n1 0 obj<<>>endobj\n2 0 obj<</Length 44>>stream\n"
            b"BT /F1 12 Tf 72 720 Td (Java Developer HCM - lab) Tj ET\n"
            b"endstream\nendobj\ntrailer<</Root 1 0 R>>\n%%EOF\n"
        )
        report["steps"].append(_stage_and_inject_file(c, pdf_body, "lab-java-dev.pdf"))
        report["steps"].append(
            _inject_text(c, "đọc file pdf vừa gửi", label="pdf-read")
        )

        zbuf = io.BytesIO()
        with zipfile.ZipFile(zbuf, "w") as zf:
            zf.writestr(
                "pdf.pdf",
                b"%PDF-1.4\nBT /F1 12 Tf 72 720 Td (Zip inner PDF lab) Tj ET\n%%EOF\n",
            )
            zf.writestr("note.txt", "Zip inner text lab HCM weather ok\n")
        report["steps"].append(_stage_and_inject_file(c, zbuf.getvalue(), "lab-pack.zip"))
        report["steps"].append(
            _inject_text(c, "đọc 2 file vừa giải nén", label="zip-read")
        )

        report["steps"].append(
            _inject_text(
                c,
                "cập nhật thông tin thời tiết hồ chí minh lúc này, ghi lên hình ảnh tp hcm",
                label="weather-scene",
            )
        )

        import time

        time.sleep(WAIT_S)
        logs = sudo_bash(
            c,
            "docker logs --since 6m assistant-hermes-main 2>&1 | tail -n 120; "
            "journalctl --user -u com.hermes.zaloplugin -n 40 --no-pager 2>/dev/null || true",
        )
        report["logs_tail"] = logs[-12000:]
        out_path = OUT / f"report-{datetime.now().strftime('%Y%m%d-%H%M%S')}.json"
        out_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"REPORT {out_path}")
        bad = (
            "Chưa đọc được nội dung" in logs
            and "lab-java-dev.pdf" in logs
        )
        return 1 if bad else 0
    finally:
        c.close()


if __name__ == "__main__":
    raise SystemExit(main())
