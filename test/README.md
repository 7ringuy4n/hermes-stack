# Lab tests (v0.5.0)

Follow `RULES.md`. Reports must **not** include hostnames, IPs, or account names.

```text
test/
├── RULES.md
├── cases/
├── fixtures/
│   ├── run-01/
│   └── run-02/
├── scripts/
└── reports/
    ├── run-01/
    └── run-02/
```

Each run covers Low / Medium / High × Traefik `local` and `public`. High stays running after the last cycle.

Summary grids in `reports/*/SUMMARY.md` use **HTML tables**. Every capability must include a **fail event** (see `RULES.md` §13 and `cases/07-fail-events.md`).

Zalo concurrent: [cases/08-zalo-concurrent.md](./cases/08-zalo-concurrent.md) ·
[scripts/zalo_concurrent.py](./scripts/zalo_concurrent.py).

Zalo: install bridge/proxy first. If the session is dead, stop and ask an operator to run `bash scripts/main/login-zalo.sh` (QR) before Zalo↔Hermes checks.

- Zalo concurrent: [cases/08-zalo-concurrent.md](./cases/08-zalo-concurrent.md) / [scripts/zalo_concurrent.py](./scripts/zalo_concurrent.py)

