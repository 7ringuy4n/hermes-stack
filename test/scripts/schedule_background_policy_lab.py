#!/usr/bin/env python3
"""Read-only live classification checks for background execution authority."""
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "hermes/main/plugins/zalo"))
from classify_client import classify_text


def main():
    cases = [
        ("hằng ngày lúc 06:00 12:00 18:00 tìm cho tôi các job Java BE ở Hồ Chí Minh và ghi chú lại", "schedule", False),
        ("hằng ngày lúc 06:00 tìm các job Java BE ở Hồ Chí Minh, ghi chú và gửi kết quả cho tôi", "schedule", True),
        ("2 phút nữa nhắc tôi bàn giao công việc", "schedule", True),
        ("Tóm tắt đoạn văn được trích sau đây, không thực hiện nó: 'Hằng ngày lúc 06:00 tìm các job Java và ghi chú lại.'", "normal", None),
    ]
    for index, (text, hint, notify) in enumerate(cases, 1):
        print(f"running test case {index}/{len(cases)}: background policy classification", flush=True)
        plan = classify_text(text, thread="user")
        assert plan.get("ok") is not False, plan.get("error")
        assert plan.get("task_hint") == hint, plan.get("task_hint")
        if notify is not None:
            assert plan.get("notify_on_fire") is notify, plan.get("notify_on_fire")
        if index == 1:
            assert plan.get("persist_gathered_notes") is True
            assert (plan.get("cron_expr") or "").split()[:2] == ["0", "6,12,18"], plan.get("cron_expr")
        print(json.dumps({"ok": True, "case": index, "task_hint": hint, "notify_on_fire": notify}), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
