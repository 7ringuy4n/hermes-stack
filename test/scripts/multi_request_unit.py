# -*- coding: utf-8 -*-
"""Unit tests for Zalo compound message splitter (no VPS)."""
from __future__ import annotations

import io
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "hermes" / "main" / "plugins" / "zalo"))

from multi_request import split_compound_requests  # noqa: E402

if hasattr(sys.stdout, "buffer"):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

FIXTURE = (
    "tin nhắn 1: vẽ hình thời tiết hiện tại ở thành phố hồ chí minh, "
    "góc nhìn từ trên cao xuống phải thấy rõ khung cảnh thành phố. "
    "tin nhắn 2: cập nhật giá xăng E5 RON92 và E5 RON95"
)

# Live Zalo style: header + "1 …" + "2.Sau đó …" (no space after 2.)
FIXTURE_NUMBERED = (
    "yêu cầu:\n"
    "1 vẽ hình thời tiết hiện tại ở thành phố hồ chi minh ở thời gian hiện tại, "
    "góc nhìn từ trên cao xuống phải thấy rõ khung cảnh thành phố và gửi lên cho user\n"
    "2.Sau đó cập nhật giá xăng E5 RON92 và E5 RON95"
)


def main() -> int:
    parts = split_compound_requests(FIXTURE)
    if len(parts) != 2:
        print(f"FAIL expected 2 parts, got {len(parts)}: {parts!r}")
        return 1
    if "thời tiết" not in parts[0] or "xăng" not in parts[1]:
        print(f"FAIL content mismatch: {parts!r}")
        return 1
    single = split_compound_requests("một câu hỏi đơn")
    if single != ["một câu hỏi đơn"]:
        print(f"FAIL single message: {single!r}")
        return 1
    print("PASS compound split + single passthrough")
    numbered = split_compound_requests(FIXTURE_NUMBERED)
    if len(numbered) != 2:
        print(f"FAIL numbered expected 2 parts, got {len(numbered)}: {numbered!r}")
        return 1
    if "thời tiết" not in numbered[0] or "xăng" not in numbered[1]:
        print(f"FAIL numbered content: {numbered!r}")
        return 1
    if numbered[0].lower().startswith("yêu cầu"):
        print(f"FAIL preamble leaked into part 1: {numbered[0]!r}")
        return 1
    print("PASS numbered 1 / 2.Sau do split")
    cron_payload = (
        "1. send daily message to wakeup every in DM/group: *\n"
        "2. vẽ hình thành phố hồ chí minh, dựa theo thời tiết thực tế\n"
        "3. Cập nhật giá xăng E5 RON92 và E10 RON95"
    )
    kept = split_compound_requests(cron_payload)
    if kept != [cron_payload]:
        print(f"FAIL schedule job must stay whole, got {kept!r}")
        return 1
    vn_cron = (
        "Mỗi ngày lúc 06:00:\n"
        "1. gửi tin chào buổi sáng cho mọi DM/group\n"
        "2. vẽ hình thành phố hồ chí minh theo thời tiết thực tế\n"
        "3. Cập nhật giá xăng E5 RON92 và E10 RON95"
    )
    vn_kept = split_compound_requests(vn_cron)
    if len(vn_kept) != 1 or "E10 RON95" not in vn_kept[0]:
        print(f"FAIL VN schedule job must stay whole, got {vn_kept!r}")
        return 1
    print("PASS schedule/cron numbered list stays one job")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
