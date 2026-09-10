# memory / session

## Purpose

Fast **short-term** conversation state in Valkey: active messages per thread, destination metadata, optional timing/file-claim helpers. Data expires with TTL so RAM stays bounded.

## Profile

Must — container `session`.

## Main functions

| Function | Detail |
|----------|--------|
| Session CRUD | Create/read active conversation for `thread_id` |
| TTL | Keys expire (e.g. 1 day) — “new session after clear” is this store |
| Dest / helpers | Where to send replies when a social-app is attached |

## Keys

Prefix default: `conversation_active:{session_id}` (`SESSION_KEY_PREFIX`).

## How it differs from long-term memory

| | session (Valkey) | Memory Manager (Postgres) |
|--|------------------|---------------------------|
| Lifetime | Hours–days (TTL) | Long-term |
| Content | Recent chat turns | Extracted / typed facts |
| Failure mode | Empty history | Still may recall preferences |

## Related

- [../README.md](../README.md)  
- [memory-manager](../memory-manager/README.md)
