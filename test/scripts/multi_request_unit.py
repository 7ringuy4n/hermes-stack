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
    hang_daily = (
        "yêu cầu:\n"
        "1. Gửi tin nhắn hằng ngày để nhắc thức dậy vào 06:00 GMT+7\n"
        "2. Vẽ hình Thành phố Hồ Chí Minh dựa trên thời tiết thực tế.\n"
        "3. Cập nhật ngắn gọn giá xăng E5 RON92 và E10 RON95 gần nhất, bằng tiếng Việt"
    )
    hang_kept = split_compound_requests(hang_daily)
    if hang_kept != [hang_daily]:
        print(f"FAIL hằng ngày schedule must stay whole, got {hang_kept!r}")
        return 1
    print("PASS hằng ngày + GMT+7 numbered list stays one job")
    thuchien = (
        "Thực hiện:\n"
        "1. Tìm giá USD hiện tại\n"
        "2. Vẽ hình Thành phố Hồ Chí Minh dựa trên thời tiết thực tế.\n"
        "3. Cập nhật ngắn gọn giá xăng E5 RON92 và E10 RON95 gần nhất, bằng tiếng Việt."
    )
    th_parts = split_compound_requests(thuchien)
    if len(th_parts) != 3 or "USD" not in th_parts[0] or "xăng" not in th_parts[2]:
        print(f"FAIL Thực hiện newline list: {th_parts!r}")
        return 1
    flat = (
        "Thực hiện: 1. Tìm giá USD hiện tại 2. Vẽ hình Thành phố Hồ Chí Minh "
        "dựa trên thời tiết thực tế. 3. Cập nhật ngắn gọn giá xăng E5 RON92 và E10 RON95 gần nhất."
    )
    flat_parts = split_compound_requests(flat)
    if len(flat_parts) != 3 or "USD" not in flat_parts[0] or "xăng" not in flat_parts[2]:
        print(f"FAIL Thực hiện one-line list: {flat_parts!r}")
        return 1
    from multi_request import wrap_compound_part
    wrapped = wrap_compound_part(1, 3, "Tìm giá USD hiện tại")
    if "1/3" not in wrapped or "USD" not in wrapped:
        print(f"FAIL wrap: {wrapped!r}")
        return 1
    print("PASS Thực hiện 3-part split (newline + one-line) + wrap")
    plenty = (
        "Thực hiện:\n"
        "1. Gửi tin chào buổi sáng\n"
        "2. Vẽ hình thời tiết HCMC\n"
        "3. Cập nhật giá xăng E5 RON92 và E10 RON95\n"
        "4. Báo tỷ giá USD/VND\n"
        "5. Tóm tắt lịch hôm nay\n"
        "6. Nhắc uống nước"
    )
    plenty_parts = split_compound_requests(plenty)
    if len(plenty_parts) != 6 or "USD" not in plenty_parts[3]:
        print(f"FAIL plenty immediate 6: {plenty_parts!r}")
        return 1
    plenty_cron = (
        "hằng ngày lúc 13:54 GMT+7:\n"
        "1. wakeup 6:00 AM GMT +7\n"
        "2. Vẽ hình HCMC\n"
        "3. Cập nhật giá xăng\n"
        "4. USD\n"
        "5. calendar\n"
        "6. water"
    )
    kept6 = split_compound_requests(plenty_cron)
    if kept6 != [plenty_cron]:
        print(f"FAIL plenty schedule must stay whole, got {kept6!r}")
        return 1
    print("PASS plenty 6-item immediate split + 13:54 schedule keep-whole")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
