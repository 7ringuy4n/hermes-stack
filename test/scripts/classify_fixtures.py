# -*- coding: utf-8 -*-
"""Mock LLM classify output for unit tests. Not used in production."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

PLENTY_NOW = (
    "Thực hiện:\n"
    "1. Gửi tin chào buổi sáng\n"
    "2. Vẽ hình thời tiết HCMC\n"
    "3. Cập nhật giá xăng E5 RON92 và E10 RON95\n"
    "4. Báo tỷ giá USD/VND\n"
    "5. Tóm tắt lịch hôm nay\n"
    "6. Nhắc uống nước"
)
PLENTY_CRON_1354 = (
    "hằng ngày lúc 13:54 GMT+7:\n"
    "1. Send daily wakeup in DM/group: * a 6:00 AM GMT +7\n"
    "2. Vẽ hình thành phố hồ chí minh, dựa theo thời tiết thực tế\n"
    "3. Cập nhật giá xăng E5 RON92 và E10 RON95\n"
    "4. Báo tỷ giá USD/VND\n"
    "5. Tóm tắt lịch hôm nay\n"
    "6. Nhắc uống nước"
)
PLENTY_CRON_0600 = (
    "hằng ngày lúc 06:00 GMT+7:\n"
    "1. wakeup\n"
    "2. HCMC weather image\n"
    "3. fuel prices\n"
    "4. USD rate\n"
    "5. calendar brief\n"
    "6. water reminder"
)
PLENTY_CRON_1200 = (
    "hằng ngày lúc 12:00 GMT+7:\n"
    "1. noon ping\n"
    "2. HCMC weather image\n"
    "3. fuel prices\n"
    "4. USD rate\n"
    "5. calendar brief\n"
    "6. water reminder"
)

_SIX = [
    "Gửi tin chào buổi sáng",
    "Vẽ hình thời tiết HCMC",
    "Cập nhật giá xăng E5 RON92 và E10 RON95",
    "Báo tỷ giá USD/VND",
    "Tóm tắt lịch hôm nay",
    "Nhắc uống nước",
]
_SIX_EN_1354 = [
    "Send daily wakeup in DM/group: * a 6:00 AM GMT +7",
    "Vẽ hình thành phố hồ chí minh, dựa theo thời tiết thực tế",
    "Cập nhật giá xăng E5 RON92 và E10 RON95",
    "Báo tỷ giá USD/VND",
    "Tóm tắt lịch hôm nay",
    "Nhắc uống nước",
]
_SIX_0600 = [
    "wakeup",
    "HCMC weather image",
    "fuel prices",
    "USD rate",
    "calendar brief",
    "water reminder",
]
_SIX_1200 = [
    "noon ping",
    "HCMC weather image",
    "fuel prices",
    "USD rate",
    "calendar brief",
    "water reminder",
]
_EN4 = [
    "Send a hello greeting message.",
    "Draw an image of Ho Chi Minh City based on the actual current weather.",
    "Give a brief update of the latest E5 RON92 and E10 RON95 gasoline prices, in Vietnamese.",
    "Draw a video of Ho Chi Minh City based on the actual current weather.",
]

FIXTURE_EN4 = (
    "1. Send a hello greeting message.\n"
    "2. Draw an image of Ho Chi Minh City based on the actual current weather.\n"
    "3. Give a brief update of the latest E5 RON92 and E10 RON95 gasoline prices, in Vietnamese.\n"
    "4. Draw a video of Ho Chi Minh City based on the actual current weather."
)
FIXTURE_INFOGRAPHIC_VI = (
    "Vẽ hình Thành phố Hồ Chí Minh dựa trên tình hình thời tiết thực tế hiện tại, "
    "trên hình thể hiện ngắn gọn giá xăng E5 RON92 và E10 RON95 mới nhất và thông tin "
    "tình hình thời tiết hiện tại, bằng tiếng Việt."
)
FIXTURE_INFOGRAPHIC_EN = (
    "Draw an image of Ho Chi Minh City based on the actual current weather. "
    "On the image, briefly show the latest E5 RON92 and E10 RON95 gasoline prices "
    "and the current weather, in Vietnamese."
)
FIXTURE_INFOGRAPHIC_DAILY = (
    "hằng ngày lúc 07:00 GMT+7:\n" + FIXTURE_INFOGRAPHIC_VI
)
FIXTURE_ONCE_NOCITE = (
    "đặt lịch chạy một lần lúc 11:24\n"
    "1. Gửi một tin nhắn chào buổi sáng đến mọi người.\n"
    "2. Tóm tắt ngắn gọn giá xăng E5 RON92 và E10 RON95 mới nhất không trích dẫn nguồn\n"
    "3. Tóm tắt ngắn gọn thông tin tình hình thời tiết Hồ Chí Minh hiện tại"
)
_ONCE_NOCITE = [
    "Gửi một tin nhắn chào buổi sáng đến mọi người.",
    "Tóm tắt ngắn gọn giá xăng E5 RON92 và E10 RON95 mới nhất không trích dẫn nguồn",
    "Tóm tắt ngắn gọn thông tin tình hình thời tiết Hồ Chí Minh hiện tại",
]
FIXTURE_ONCE_FOUR = (
    "đặt lịch chạy một lần lúc 20:35\n"
    "1. Gửi tin nhắn chào\n"
    "2. Tìm và tóm tắt giá xăng E5 RON92 và E10 RON95 mới nhất\n"
    "3. Tìm và tóm tắt thời tiết TP.HCM hiện tại\n"
    "4. Vẽ tranh TP.HCM phản ánh đúng thời tiết lúc đó và gửi ảnh"
)
_ONCE_FOUR = [
    "Gửi tin nhắn chào",
    "Tìm và tóm tắt giá xăng E5 RON92 và E10 RON95 mới nhất",
    "Tìm và tóm tắt thời tiết TP.HCM hiện tại",
    "Vẽ tranh TP.HCM phản ánh đúng thời tiết lúc đó và gửi ảnh",
]
FIXTURE_ONCE_2113 = (
    "đặt lịch chạy một lần lúc 21:13\n"
    "1. Gửi một tin nhắn chào đến mọi người.\n"
    "2. Tóm tắt ngắn gọn giá xăng E5 RON92 và E10 RON95 mới nhất\n"
    "3. Tóm tắt ngắn gọn thông tin tình hình thời tiết hiện tại\n"
    "4. Vẽ hình Thành phố Hồ Chí Minh dựa trên tình hình thời tiết thực tế hiện tại"
)
_ONCE_2113 = [
    "Gửi một tin nhắn chào đến mọi người.",
    "Tóm tắt ngắn gọn giá xăng E5 RON92 và E10 RON95 mới nhất",
    "Tóm tắt ngắn gọn thông tin tình hình thời tiết hiện tại",
    "Vẽ hình Thành phố Hồ Chí Minh dựa trên tình hình thời tiết thực tế hiện tại",
]

FIXTURE_QUEUE_NOW = (
    "1. Chào buổi sáng trong DM\n"
    "2. Vẽ hình thành phố hồ chí minh, dựa theo thời tiết thực tế\n"
    "3. Cập nhật ngắn gọn nội dung giá xăng E5 RON92 và E10 RON95 gần nhất"
)
FIXTURE_QUEUE_SCHEDULE = (
    "1. Send daily message to wakeup every in DM/group: * a 6:00 AM GMT +7\n"
    "2. Vẽ hình thành phố hồ chí minh, dựa theo thời tiết thực tế\n"
    "3. Cập nhật ngắn gọn nội dung giá xăng E5 RON92 và E10 RON95 gần nhất"
)
_QUEUE_NOW = [
    "Chào buổi sáng trong DM",
    "Vẽ hình thành phố hồ chí minh, dựa theo thời tiết thực tế",
    "Cập nhật ngắn gọn nội dung giá xăng E5 RON92 và E10 RON95 gần nhất",
]

# No numbering, no clock: three deliverables joined by "và" / "kèm theo".
FIXTURE_CONJ_THREE = (
    "gửi tin chào buổi sáng và tóm tắt giá xăng E5 RON92 và E10 RON95 mới nhất "
    "kèm theo thông tin thời tiết Hồ Chí Minh hiện tại"
)
_CONJ_THREE = [
    "Gửi tin chào buổi sáng",
    "Tóm tắt giá xăng E5 RON92 và E10 RON95 mới nhất",
    "Tóm tắt thông tin thời tiết Hồ Chí Minh hiện tại",
]

_PLANS = {
    FIXTURE_QUEUE_NOW: {"task_hint": "tool", "instructions": _QUEUE_NOW},
    FIXTURE_QUEUE_SCHEDULE: {
        "task_hint": "schedule",
        "instructions": _QUEUE_NOW,
        "cadence": "daily",
        "cron_expr": "0 6 * * *",
    },
    FIXTURE_CONJ_THREE: {
        "task_hint": "tool",
        "execution_class": "async",
        "response_mode": "ack_then_deliver",
        "instructions": _CONJ_THREE,
        "task_details": [
            {"execution_class": "interactive", "task_type": "chat", "depends_on": []},
            {"execution_class": "async", "task_type": "search", "depends_on": []},
            {"execution_class": "async", "task_type": "search", "depends_on": []},
        ],
    },
    "Thực hiện: 1. Tìm giá USD hiện tại 2. Vẽ hình HCM 3. Cập nhật giá xăng": {
        "task_hint": "tool",
        "instructions": ["Tìm giá USD hiện tại", "Vẽ hình HCM", "Cập nhật giá xăng"],
    },
    "Thực hiện: 1. Tìm giá USD hiện tại 2. Vẽ hình HCMC 3. Cập nhật giá xăng": {
        "task_hint": "tool",
        "instructions": ["Tìm giá USD hiện tại", "Vẽ hình HCMC", "Cập nhật giá xăng"],
    },
    FIXTURE_EN4: {"task_hint": "tool", "instructions": _EN4},
    FIXTURE_INFOGRAPHIC_VI: {
        "task_hint": "tool",
        "execution_class": "async",
        "task_type": "media_generation",
        "response_mode": "ack_then_deliver",
        "instructions": [FIXTURE_INFOGRAPHIC_VI],
    },
    FIXTURE_INFOGRAPHIC_EN: {
        "task_hint": "tool",
        "instructions": [FIXTURE_INFOGRAPHIC_EN],
    },
    FIXTURE_INFOGRAPHIC_DAILY: {
        "task_hint": "schedule",
        "instructions": [FIXTURE_INFOGRAPHIC_VI],
        "cadence": "daily",
        "cron_expr": "0 7 * * *",
    },
    FIXTURE_ONCE_NOCITE: {
        "task_hint": "schedule",
        "instructions": _ONCE_NOCITE,
        "cadence": "once",
        "cron_expr": "24 11 * * *",
    },
    FIXTURE_ONCE_FOUR: {
        "task_hint": "schedule",
        "instructions": _ONCE_FOUR,
        "cadence": "once",
        "cron_expr": "35 20 * * *",
    },
    FIXTURE_ONCE_2113: {
        "task_hint": "schedule",
        "instructions": _ONCE_2113,
        "cadence": "once",
        "cron_expr": "13 21 * * *",
        "task_details": [
            {"execution_class": "interactive", "task_type": "chat", "depends_on": []},
            {"execution_class": "async", "task_type": "search", "depends_on": []},
            {"execution_class": "async", "task_type": "search", "depends_on": []},
            {"execution_class": "async", "task_type": "media_generation", "depends_on": [2]},
        ],
    },
    "Hello": {
        "task_hint": "normal",
        "execution_class": "interactive",
        "task_type": "chat",
        "response_mode": "direct",
        "instructions": ["Hello"],
    },
    "cite labsolution": {
        "task_hint": "knowledge",
        "instructions": ["labsolution"],
    },
    "kiến thức đã học": {
        "task_hint": "knowledge",
        "instructions": [],
    },
    "1. wakeup 2. image 3. fuel": {
        "task_hint": "tool",
        "instructions": ["wakeup", "image", "fuel"],
    },
    "hằng ngày lúc 06:00 GMT+7": {
        "task_hint": "schedule",
        "instructions": ["hằng ngày lúc 06:00 GMT+7"],
        "cadence": "daily",
        "cron_expr": "0 6 * * *",
    },
    "13:54 GMT+7": {
        "task_hint": "schedule",
        "instructions": ["13:54 GMT+7"],
        "cadence": "daily",
        "cron_expr": "54 13 * * *",
    },
    PLENTY_NOW: {"task_hint": "tool", "instructions": _SIX},
    PLENTY_CRON_1354: {
        "task_hint": "schedule",
        "instructions": _SIX_EN_1354,
        "cadence": "daily",
        "cron_expr": "54 13 * * *",
    },
    PLENTY_CRON_0600: {
        "task_hint": "schedule",
        "instructions": _SIX_0600,
        "cadence": "daily",
        "cron_expr": "0 6 * * *",
    },
    PLENTY_CRON_1200: {
        "task_hint": "schedule",
        "instructions": _SIX_1200,
        "cadence": "daily",
        "cron_expr": "0 12 * * *",
    },
    (
        "tin nhắn 1: vẽ hình thời tiết hiện tại ở thành phố hồ chí minh, "
        "góc nhìn từ trên cao xuống phải thấy rõ khung cảnh thành phố. "
        "tin nhắn 2: cập nhật giá xăng E5 RON92 và E5 RON95"
    ): {
        "task_hint": "tool",
        "instructions": [
            "vẽ hình thời tiết hiện tại ở thành phố hồ chí minh, góc nhìn từ trên cao xuống phải thấy rõ khung cảnh thành phố.",
            "cập nhật giá xăng E5 RON92 và E5 RON95",
        ],
    },
    (
        "yêu cầu:\n"
        "1 vẽ hình thời tiết hiện tại ở thành phố hồ chi minh ở thời gian hiện tại, "
        "góc nhìn từ trên cao xuống phải thấy rõ khung cảnh thành phố và gửi lên cho user\n"
        "2.Sau đó cập nhật giá xăng E5 RON92 và E5 RON95"
    ): {
        "task_hint": "tool",
        "instructions": [
            "vẽ hình thời tiết hiện tại ở thành phố hồ chi minh ở thời gian hiện tại, góc nhìn từ trên cao xuống phải thấy rõ khung cảnh thành phố và gửi lên cho user",
            "Sau đó cập nhật giá xăng E5 RON92 và E5 RON95",
        ],
    },
    (
        "1. send daily message to wakeup every in DM/group: *\n"
        "2. vẽ hình thành phố hồ chí minh, dựa theo thời tiết thực tế\n"
        "3. Cập nhật giá xăng E5 RON92 và E10 RON95"
    ): {
        "task_hint": "schedule",
        "instructions": [
            "send daily message to wakeup every in DM/group: *",
            "vẽ hình thành phố hồ chí minh, dựa theo thời tiết thực tế",
            "Cập nhật giá xăng E5 RON92 và E10 RON95",
        ],
        "cadence": "daily",
        "cron_expr": "0 6 * * *",
    },
    (
        "Mỗi ngày lúc 06:00:\n"
        "1. gửi tin chào buổi sáng cho mọi DM/group\n"
        "2. vẽ hình thành phố hồ chí minh theo thời tiết thực tế\n"
        "3. Cập nhật giá xăng E5 RON92 và E10 RON95"
    ): {
        "task_hint": "schedule",
        "instructions": [
            "gửi tin chào buổi sáng cho mọi DM/group",
            "vẽ hình thành phố hồ chí minh theo thời tiết thực tế",
            "Cập nhật giá xăng E5 RON92 và E10 RON95",
        ],
        "cadence": "daily",
        "cron_expr": "0 6 * * *",
    },
    (
        "yêu cầu:\n"
        "1. Gửi tin nhắn hằng ngày để nhắc thức dậy vào 06:00 GMT+7\n"
        "2. Vẽ hình Thành phố Hồ Chí Minh dựa trên thời tiết thực tế.\n"
        "3. Cập nhật ngắn gọn giá xăng E5 RON92 và E10 RON95 gần nhất, bằng tiếng Việt"
    ): {
        "task_hint": "schedule",
        "instructions": [
            "Gửi tin nhắn hằng ngày để nhắc thức dậy vào 06:00 GMT+7",
            "Vẽ hình Thành phố Hồ Chí Minh dựa trên thời tiết thực tế.",
            "Cập nhật ngắn gọn giá xăng E5 RON92 và E10 RON95 gần nhất, bằng tiếng Việt",
        ],
        "cadence": "daily",
        "cron_expr": "0 6 * * *",
    },
    (
        "Thực hiện:\n"
        "1. Tìm giá USD hiện tại\n"
        "2. Vẽ hình Thành phố Hồ Chí Minh dựa trên thời tiết thực tế.\n"
        "3. Cập nhật ngắn gọn giá xăng E5 RON92 và E10 RON95 gần nhất, bằng tiếng Việt."
    ): {
        "task_hint": "tool",
        "instructions": [
            "Tìm giá USD hiện tại",
            "Vẽ hình Thành phố Hồ Chí Minh dựa trên thời tiết thực tế.",
            "Cập nhật ngắn gọn giá xăng E5 RON92 và E10 RON95 gần nhất, bằng tiếng Việt.",
        ],
    },
    (
        "Thực hiện: 1. Tìm giá USD hiện tại 2. Vẽ hình Thành phố Hồ Chí Minh "
        "dựa trên thời tiết thực tế. 3. Cập nhật ngắn gọn giá xăng E5 RON92 và E10 RON95 gần nhất."
    ): {
        "task_hint": "tool",
        "instructions": [
            "Tìm giá USD hiện tại",
            "Vẽ hình Thành phố Hồ Chí Minh dựa trên thời tiết thực tế.",
            "Cập nhật ngắn gọn giá xăng E5 RON92 và E10 RON95 gần nhất.",
        ],
    },
    (
        "every day at 16:40 GMT+7:\n"
        "1. Send a hello greeting message.\n"
        "2. Draw an image of Ho Chi Minh City based on the actual current weather.\n"
        "3. Give a brief update of the latest E5 RON92 and E10 RON95 gasoline prices, in Vietnamese.\n"
        "4. Draw a video of Ho Chi Minh City based on the actual current weather."
    ): {
        "task_hint": "schedule",
        "instructions": _EN4,
        "cadence": "daily",
        "cron_expr": "40 16 * * *",
    },
    (
        "Tạo lịch hằng ngày lúc 06:00 GMT+7\n"
        "1. Nhắc thức dậy\n"
        "2. Vẽ hình thời tiết HCMC\n"
        "3. Báo giá xăng"
    ): {
        "task_hint": "schedule",
        "instructions": ["Nhắc thức dậy", "Vẽ hình thời tiết HCMC", "Báo giá xăng"],
        "cadence": "daily",
        "cron_expr": "0 6 * * *",
    },
    (
        "hằng ngày lúc 13:54 GMT+7\n"
        "1. wakeup 6:00 AM GMT +7\n"
        "2. HCMC image\n"
        "3. fuel\n"
        "4. USD\n"
        "5. calendar\n"
        "6. water"
    ): {
        "task_hint": "schedule",
        "instructions": ["wakeup 6:00 AM GMT +7", "HCMC image", "fuel", "USD", "calendar", "water"],
        "cadence": "daily",
        "cron_expr": "54 13 * * *",
    },
    (
        "hằng ngày lúc 12:00 GMT+7\n"
        "1. noon ping\n"
        "2. HCMC image\n"
        "3. fuel"
    ): {
        "task_hint": "schedule",
        "instructions": ["noon ping", "HCMC image", "fuel"],
        "cadence": "daily",
        "cron_expr": "0 12 * * *",
    },
}


def _planner(text: str, timezone: str = "Asia/Ho_Chi_Minh") -> dict:
    raw = (text or "").strip()
    hit = _PLANS.get(raw) or _PLANS.get(text or "")
    if hit:
        return dict(hit)
    if raw == "một câu hỏi đơn":
        return {"task_hint": "normal", "instructions": ["một câu hỏi đơn"]}
    return {"task_hint": "unknown", "instructions": [raw] if raw else []}


def install_unit_planner() -> None:
    for mod in list(sys.modules.values()):
        fn = getattr(mod, "set_planner", None)
        path = str(getattr(mod, "__file__", "") or "")
        if callable(fn) and path.replace("\\", "/").endswith("classify_client.py"):
            fn(_planner)
