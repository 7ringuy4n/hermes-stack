# 2026-09-04 — §15 units + greeting + visual weather

## Core / labs
- Case-index units aligned to `active`/`inactive`, classify-owned secret probe, multi-clock `tasks[]`
- Visual weather PDF inject fixed (no sanitize on loopback URLs)
- `run_case_index_lab.py` includes newer §15 scripts

## VPS gate (PASS)
- Omni combo preflight (hermes/classifier filled)
- Tn greeting reply (~31s send)
- Visual weather HCMC PDF (new PDF, no SERP chrome)
- Prior: archive extract, remaining suite, Playwright failover

## Merge
MR develop → main; VPS update from `main` only.
