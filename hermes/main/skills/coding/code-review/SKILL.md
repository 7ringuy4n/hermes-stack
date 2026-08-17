---
name: code-review
description: "Review code for bugs, design, security, maintainability. Use for PR review, diff review, audit prep, or 'check this code'."
---

# Code review

## Load by scope

| Scope | Vendor skill |
|---|---|
| Understand codebase first | `vendor/trailofbits/audit-context-building` |
| Git diff / PR | `vendor/trailofbits/differential-review` |
| General quality | `vendor/mattpocock/code-review` |

## Must follow

1. **Context before verdicts** on unfamiliar code (audit-context-building).
2. Report: severity, location, exploitability, suggested fix — no drive-by rewrites unless asked.
3. Security regressions → `coding/security-review`.

## Sources

Trail of Bits (CC BY-SA 4.0), mattpocock/skills (MIT). See vendor `ATTRIBUTION.md` files.
