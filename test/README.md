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

Zalo concurrent **text + media generation** (delay): [cases/09-zalo-concurrent-media.md](./cases/09-zalo-concurrent-media.md) ·
[scripts/zalo_concurrent_media.py](./scripts/zalo_concurrent_media.py).

Isolation risks: [cases/10-security-isolation-risks.md](./cases/10-security-isolation-risks.md) ·
[scripts/security_risks.py](./scripts/security_risks.py).

Two-pass lab summary (latest): [reports/run-05-two-pass/SUMMARY.md](./reports/run-05-two-pass/SUMMARY.md).

Profile upgrade/downgrade (existing / add / remove options): [cases/11-profile-switch.md](./cases/11-profile-switch.md) ·
[scripts/profile_switch.py](./scripts/profile_switch.py).

Zalo: install bridge/proxy first. If the session is dead, stop and ask an operator to run `bash scripts/main/login-zalo.sh` (QR) before Zalo↔Hermes checks.

