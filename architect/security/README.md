# security

## System architecture

| | |
|--|--|
| **Sits between** | Uploads / risky text ↔ OCR / ingest / Hermes |
| **Owns** | AV gateway, security-manager, optional SIEM |
| **Does not own** | Document storage (ingest/Qdrant) |

<table style="width:100%;border-collapse:collapse;font-size:13px;">
  <tr>
    <td style="padding:12px;background:#f5f5f5;border:1px solid #ddd;text-align:center;width:28%;">File / text</td>
    <td style="padding:8px;background:#eee;text-align:center;width:4%;">→</td>
    <td style="padding:14px;background:#2563eb;color:#fff;text-align:center;border:3px solid #fbbf24;width:36%;"><b>AV → security-manager</b></td>
    <td style="padding:8px;background:#eee;text-align:center;width:4%;">→</td>
    <td style="padding:12px;background:#e8f4ea;border:1px solid #c5e0c8;text-align:center;width:28%;">OCR / ingest · or block</td>
  </tr>
</table>

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
