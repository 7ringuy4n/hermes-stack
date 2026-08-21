---
name: security
description: "Send untrusted files to the Security Worker (AV, YARA, sandbox, judge). Not a classifier task_hint."
---

# Security skill

Hermes does not implement AV, YARA, sandbox, or LLM-judge itself (except a deterministic EICAR test-signature check).

```text
Hermes → this skill → Security Worker
                      ├── AV
                      ├── YARA
                      ├── Sandbox
                      └── Judge
```

Use this **before** Media/File / knowledge-learn when the inbound file is untrusted.

- Worker base: `http://security-manager:8093` (stack overlay)
- Classifier must **not** return `task_hint=yara` (or av/sandbox/judge). Those are worker capabilities.

## Fail closed

- If `ENABLE_ANTIVIRUS=1` (or `AV_SCAN=1`) and the AV gateway is down → **refuse** the file (do not ask to learn it). Override with `AV_REQUIRED=0` only for explicit lab bypass.
- EICAR / known test-virus markers are blocked locally even when Security Worker is inactive.
- Secret / protected-path probes use `config/agent/secret-probe.json` (never disclose `/opt/data`, `.env`, keys).

When Security Worker is inactive and antivirus is off, do not invent a full scanner — but still apply secret-probe + EICAR.
