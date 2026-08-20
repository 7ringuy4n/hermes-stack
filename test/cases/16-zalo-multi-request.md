# Case: Zalo compound message (multiple requests in one bubble)

One inbound Zalo message contains **two or more** distinct user tasks.
Bot must process **all** tasks, not only the first.

LLM classify (`POST model-router /v1/classify`) returns `instructions[]`.
Application code does not split/join/regex the user text.

## Example fixture

```text
tin nhắn 1: vẽ hình thời tiết hiện tại ở thành phố hồ chí minh, góc nhìn từ trên cao xuống phải thấy rõ khung cảnh thành phố.
tin nhắn 2: cập nhật giá xăng E5 RON92 và E5 RON95
```

Also this live style (must classify to two instructions):

```text
yêu cầu:
1 vẽ hình thời tiết hiện tại ở thành phố hồ chi minh ở thời gian hiện tại, góc nhìn từ trên cao xuống phải thấy rõ khung cảnh thành phố và gửi lên cho user
2.Sau đó cập nhật giá xăng E5 RON92 và E5 RON95
```

Do **not** let `media-out` / “no recap after file” drop part 2.

## Preconditions

- `ENABLE_ZALO=1`, bridge healthy
- High preferred (image + web search backends)

## Steps (unit)

1. Run `python test/scripts/multi_request_unit.py` and `python test/scripts/llm_classify_unit.py`
2. Lab: `python test/scripts/zalo_multi_request_lab.py` — classify the live numbered fixture, then a Zalo-origin workflow to the admin DM (delivery through the logged-in bridge).

## Steps (lab)

1. Send the example fixture as **one** Zalo message
2. Record outbound: must reflect **both** image/weather **and** fuel-price intent
3. If only one topic answered → FAIL

## Pass criteria

- Classify unit PASS
- Lab: both intents addressed (image attempt + price/update answer or controlled "no data")
- No crash; SSE stays at 1
- Daily/cron numbered lists are `task_hint=schedule` (one lịch; explode at tick — case 22). Greeting + fuel summary + weather summary + later draw/send-image is **four** jobs, not one overlay poster.
- No extra `Đã xong.` / `Done.` ack after files (file/result only)

## Fail events

- Only first labeled block handled → FAIL
- Second message required from user to get part 2 → FAIL
