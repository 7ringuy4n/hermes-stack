---
name: security
description: "Send untrusted files to the Security Worker (AV, YARA, sandbox, judge). Not a classifier task_hint."
---

# Security skill

Hermes does not implement AV, YARA, sandbox, or LLM-judge itself.

```text
Hermes → this skill → Security Worker
                      ├── AV
                      ├── YARA
                      ├── Sandbox
                      └── Judge
```

Use this **before** Media/File processing when the inbound file is untrusted.

- Worker base: `http://security-manager:8093` (stack overlay)
- Classifier must **not** return `task_hint=yara` (or av/sandbox/judge). Those are worker capabilities.

If the worker is disabled on this profile, skip and say the file was not scanned — do not invent a local scanner.
