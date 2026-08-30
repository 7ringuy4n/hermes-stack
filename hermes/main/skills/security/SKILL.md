---
name: security
description: "Send untrusted files to the Security Worker (AV, YARA, sandbox, judge). Not a classifier task_hint."
---

# Security skill

Hermes does **not** implement AV, YARA, sandbox, or LLM-judge itself.

```text
Hermes → this skill → Security Worker
                      ├── AV (ClamAV via av-gateway)
                      ├── YARA
                      ├── Sandbox
                      └── Judge
```

Use this **before** Media/File / knowledge-learn when the inbound file is untrusted.

- Worker base: `http://security-manager:8093` (stack overlay)
- AV gateway: `http://av-gateway:8098` (`ENABLE_ANTIVIRUS=active`)
- Classifier must **not** return `task_hint=yara` (or av/sandbox/judge). Those are worker capabilities.

## Fail closed

- If `ENABLE_ANTIVIRUS=active` (or `AV_SCAN=1`) and the AV gateway is down → **refuse** the file (do not ask to learn it). Override with `AV_REQUIRED=0` only for explicit lab bypass.
- Do **not** reimplement virus signatures in the Zalo adapter. EICAR / malware detection belongs in Security Worker / ClamAV.
- Secret / protected-path probes use `config/agent/secret-probe.json` (never disclose `/opt/data`, `.env`, keys).

When Security Worker and antivirus are both off, skip scanning and say so — do not invent a local scanner.
