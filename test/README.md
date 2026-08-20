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

Worker add/remove (existing options): [cases/11-worker-switch.md](./cases/11-worker-switch.md) ·
[scripts/worker_switch.py](./scripts/worker_switch.py).

Skills lab (Medium destroy/redeploy + auto-learn + text-poster): [cases/12-skills-auto-learn.md](./cases/12-skills-auto-learn.md) ·
[cases/13-image-text-poster.md](./cases/13-image-text-poster.md) ·
[cases/14-knowledge-internal-rag.md](./cases/14-knowledge-internal-rag.md) ·
[scripts/skills_lab.py](./scripts/skills_lab.py) ·
[reports/run-skills-lab/SUMMARY.md](./reports/run-skills-lab/SUMMARY.md).

Zalo: install bridge/proxy first. If the session is dead, stop and ask an operator to run `bash scripts/main/login-zalo.sh` (QR) before Zalo↔Hermes checks.

Plenty-in-one-message + same-time vs different-time cron (Zalo and Hermes API):
[cases/24-workflow-multi-cron-channels.md](./cases/24-workflow-multi-cron-channels.md) ·
[scripts/workflow_schedule_concurrency_unit.py](./scripts/workflow_schedule_concurrency_unit.py).


