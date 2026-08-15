# security / security-manager

## Purpose

Decides whether code/files are safe enough to process: extension/size limits, rule packs under `rules/`, optional semantic checks. Emits a user-safe refusal string on block.

## Profile

High (`ENABLE_SECURITY=1`).

## Main functions

| Function | Detail |
|---|---|
| Static checks | Extension, archive bombs, path tricks |
| Rules | `rules/` YARA or custom |
| Verdict | clean / risk → pipeline continue or stop |

## Related

- [av-gateway](../av-gateway/README.md)
