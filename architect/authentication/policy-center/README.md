# authentication / policy-center

## Purpose

Stores and evaluates additional policies (tool allowlists, content rules) beyond basic workspace ACL when `ENABLE_POLICY=active`.

## Profile

Optional security-worker component.

## Main functions

| Function | Detail |
|---|---|
| Policy documents | Versioned rules operators can edit |
| Evaluate | Given context, return allow/deny + reason |
| Integrate | Called from authz or security-manager |

## Related

- [authz](../authz/README.md)
