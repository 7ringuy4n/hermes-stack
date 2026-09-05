# Case: basic health (all profiles)

- Install completes; expected services start; config valid.
- Health checks pass; Hermes not crash-looping.
- Edge ports follow profile rules (public fail-soft to local without ACME).
- Hermes reaches Model Router / omni-router.
- Session lock acquire/release (when session is up).
- Restart a dependency (dispatcher) and confirm recovery.
- Logs: no unexplained ERROR/Traceback burst.
- Disabled optionals stay off; enabled optionals respond.
