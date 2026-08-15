# memory / session

## Purpose

Fast **short-term** conversation state in Valkey: active messages per thread, destination metadata, optional timing/file-claim helpers. Data expires with TTL so RAM stays bounded.

## Profile

Must — container `session`.

## Main functions

| Function | Detail |
|---|---|
| Session CRUD | Create/read active conversation for `thread_id` |
| TTL | Keys expire (e.g. 1 day) — “new session after clear” is this store |
| Dest / helpers | Where to send replies when a social-app is attached |

## How it differs from Mem0

| | session (Valkey) | Mem0 |
|---|---|---|
| Lifetime | Hours–days | Long-term |
| Content | Recent chat turns | Extracted facts |
| Failure mode | Empty history | Still may recall preferences |

## Related

- [../README.md](../README.md)  
- [memory-manager](../memory-manager/README.md)
