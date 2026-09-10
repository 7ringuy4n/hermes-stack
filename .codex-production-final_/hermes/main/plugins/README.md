# hermes / plugins

## Purpose

Channel **adapters** Hermes loads (Python/JS plugins). Keep platform HTTP under `architect/social-app/`; keep Hermes-side glue here.

## Profile

Only when a social-app is attached (e.g. [`zalo/`](./zalo/README.md) — includes mention-before-gates fix).

## Rules

- UX strings → `hermes/main/messages/`
- Triggers → skills when possible
- Prefer assistant naming; keep UX strings in `messages/`

## Related

- [architect/social-app](../../architect/social-app/README.md)  
- [messages](../messages/README.md)
