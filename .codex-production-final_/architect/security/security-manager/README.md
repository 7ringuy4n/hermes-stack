# security / security-manager

## Purpose

Decides whether files are safe enough to process. **Isolation layers** (size, archive limits, static, YARA, optional AV/sandbox) can allow or block. The optional **LLM judge is a heuristic**: it may add RISK only. `CLEAN` never allows a file.

Emits a user-safe refusal string on block.

## Profile

Security worker (`ENABLE_SECURITY=active`). Defaults: YARA on; AV, sandbox, and LLM judge **off**.

## Main functions

| Function | Detail |
|---|---|
| Static checks | Extension, archive bombs, path tricks |
| Rules | `rules/` YARA or custom |
| Optional AV | ClamAV via av-gateway when `ENABLE_ANTIVIRUS=active` |
| Optional LLM | `SECURITY_LLM_JUDGE=active` — RISK-only, not a security boundary |
| Verdict | isolation must pass; heuristic may only add RISK |

## Related

- [av-gateway](../av-gateway/README.md)
- [docs/SECURITY.md](../../../docs/SECURITY.md)
