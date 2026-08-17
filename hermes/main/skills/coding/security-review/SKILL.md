---
name: security-review
description: "Secure coding and vulnerability review. Use for auth, injection, secrets, dependencies, threat modeling, or audit-style analysis."
---

# Security review

## Workflows

1. **Map context** — `vendor/trailofbits/audit-context-building`
2. **Review changes** — `vendor/trailofbits/differential-review`
3. **Insecure defaults** — `vendor/trailofbits/insecure-defaults/references/*.md`

## Must follow

- Apply **`core/safety`** (fail closed, no secret echo).
- Evidence-based findings; CWE/OWASP labels when helpful.
- Hermes stack: respect isolation docs (`docs/SECURITY.md`) — do not re-enable sandbox/judge without operator intent.

## Sources

Trail of Bits skills (CC BY-SA 4.0). See `vendor/trailofbits/ATTRIBUTION.md`.
