# Case 63: Public / Local Security Regression

**Gap matrix id:** Case 59 (Production Failure Gap Test Cases v2)

**Zalo identity:** inject as allowlisted user **Tn** when the case touches inbound Zalo.

## Goal

Verify exposure cannot accidentally change during restart or worker changes.

## Matrix

Test:

- Traefik local;
- Traefik public;
- worker add;
- worker remove;
- Hermes ×2;
- restart;
- destroy/recreate;
- config update.

Probe:

- Hermes;
- OmniRouter;
- 9Router;
- Postgres;
- Qdrant;
- Valkey;
- OpenBao;
- workflow;
- dispatcher;
- OCR.

## Pass criteria

Only intended public endpoints are reachable.

Internal services must never become exposed because:

- Compose overlay changes;
- worker activation;
- restart;
- replica scaling;
- health check;
- temporary failure.

---
