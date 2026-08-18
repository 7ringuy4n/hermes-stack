# Case: Zalo compound message (multiple requests in one bubble)

One inbound Zalo message contains **two or more** distinct user tasks.
Bot must process **all** tasks, not only the first.

## Example fixture

```text
tin nhắn 1: vẽ hình thời tiết hiện tại ở thành phố hồ chí minh, góc nhìn từ trên cao xuống phải thấy rõ khung cảnh thành phố.
tin nhắn 2: cập nhật giá xăng E5 RON92 và E5 RON95
```

Also this live style (must split the same way):

```text
yêu cầu:
1 vẽ hình thời tiết hiện tại ở thành phố hồ chi minh ở thời gian hiện tại, góc nhìn từ trên cao xuống phải thấy rõ khung cảnh thành phố và gửi lên cho user
2.Sau đó cập nhật giá xăng E5 RON92 và E5 RON95
```

Do **not** let `media-out` / “no recap after file” drop part 2. Splitter must emit two turns.

## Preconditions

- `ENABLE_ZALO=1`, bridge healthy
- High preferred (image + web search backends)

## Steps (unit)

1. Run `python test/scripts/multi_request_unit.py`
2. Assert splitter returns 2 parts for the example fixture

## Steps (lab)

1. Send the example fixture as **one** Zalo message
2. Record outbound: must reflect **both** image/weather **and** fuel-price intent
3. If only one topic answered → FAIL

## Pass criteria

- Splitter unit PASS
- Lab: both intents addressed (image attempt + price/update answer or controlled "no data")
- No crash; SSE stays at 1
- Daily/cron numbered lists are **not** split (case 22)
- `Đã xong.` / `Done.` must be the **last** outbound bubble on compound runs (image → prices → ack)

## Fail events

- Only first labeled block handled → FAIL
- Second message required from user to get part 2 → FAIL
