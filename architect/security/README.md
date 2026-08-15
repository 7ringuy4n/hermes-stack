# security

## Purpose

Protect the stack from risky files and confidential probes: antivirus, static/LLM security judgment, SIEM-style event collection, and editable secret-probe keyword lists.

## Profile

| Profile | State |
|---|---|
| Low / Medium | Off |
| High | AV + security-manager + optional SIEM / secret-probe |

## Sub-packages

| Package | Function |
|---|---|
| [av-gateway/](./av-gateway/README.md) | Scan files (ClamAV) before OCR/ingest |
| [security-manager/](./security-manager/README.md) | Type/size limits, YARA/rules, risk decision |
| [siem/](./siem/README.md) | Security event intake / forward (High) |

## How it works (High, inbound file)

```text
File from social-app or upload
    → av-gateway (malware)
    → security-manager (policy / YARA / optional LLM judge)
    → CLEAN → OCR / ingest / Hermes read
    → BLOCK → user-safe one-liner (from hermes/main/messages), no stack trace
```

**Secret-probe:** if the *message text* asks for secrets/confidential docs, refuse early (skill + editable lists preferred over huge hardcoded regex). Notify admin via notification layer when configured.

## Related

- [social-app](../social-app/README.md)  
- [tools/ingest](../tools/ingest/README.md)  
- [hermes/main/messages](../../hermes/main/messages/README.md)
