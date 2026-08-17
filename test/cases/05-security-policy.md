# Case: security / policy (High)

- Policy evaluate default-deny (e.g. export) **and** an allow path.
- Antivirus: disabled short alert **and** an **infected** EICAR scan (INFECTED/BLOCKED + short alert).
- OpenVPN off → short alert.
- Public edge stays loopback when ACME is unavailable.
- Fallback paths must not bypass policy.
