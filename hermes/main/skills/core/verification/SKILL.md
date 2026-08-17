---
name: verification
description: "Before claiming complete, fixed, or passing — run verification and cite evidence. Use before commits, PRs, deploy claims, or 'Đã xong' on technical work."
---

# Verification

**Evidence before claims.**

## Gate (every completion claim)

1. **Identify** — what command or check proves the claim?
2. **Run** — execute it fresh in this session.
3. **Read** — full output + exit code.
4. **State** — claim only with that evidence attached.

## Must follow

- Load full upstream workflow: `vendor/superpowers/verification-before-completion/SKILL.md`.
- Never claim tests pass, build ok, or bug fixed without running the relevant check.
- Media/file tasks: confirm `ok:true` or file exists at the expected path.

## Sources

obra/superpowers `verification-before-completion` (MIT). See `vendor/superpowers/ATTRIBUTION.md`.
