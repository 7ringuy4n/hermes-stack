# Case: security / policy (High)

- Policy evaluate default-deny (e.g. export) **and** an allow path.
- Antivirus: disabled short alert **and** an **infected** EICAR scan (INFECTED/BLOCKED + short alert).
- OpenVPN off → short alert.
- Public edge stays loopback when ACME is unavailable.
- Fallback paths must not bypass policy.
- **Secret Probe** is independent of `task_hint`. Statuses: `SAFE` / `BLOCKED` / `REVIEW`.
  Never classify `SECRET` as a task type. Blocked input must not reach LLM, schedule,
  tools, memory, or queues. Refuse copy from `ux.json` / gateway messages — no secret text
  in Notify or logs.
- Input probe before Model Router / Schedule Manager. Output probe before the user.
