# social-app / http

## Purpose

Generic HTTP / webhook channel so IDEs, custom UIs, or third-party chat can POST messages into Hermes and receive replies without Zalo/Telegram.

## Profile

Optional. Useful when chatting from an IDE or editor plugin.

## Typical API shape (target)

- `POST /v1/chat` — `{ "thread_id", "text", "user_id?" }` → assistant reply  
- Optional streaming later  

## Related

- [../README.md](../README.md)  
- [docs/01-workflow.md](../../../docs/01-workflow.md)
