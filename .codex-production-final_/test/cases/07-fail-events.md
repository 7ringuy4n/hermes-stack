# Case: fail events (High)

Happy-path only is incomplete.

1. **Antivirus infected** — EICAR test file must return INFECTED/BLOCKED + short alert. Also scan a clean file (CLEAN). If AV is off, record the disabled alert, then enable AV for the infected case.
2. **Concurrency until fail** — ramp concurrent text (8 → 16 → 32 → 48…) until the first timeout/error/drop. Record last all-success N and first-fail N.
3. **Hermes crash auto-heal** — stop one Hermes replica; `stack-watch` must bring it back; no crash loop; Zalo SSE stays a single owner.
4. **Zalo lost connection auto-heal** — stop `zalo-proxy`; `zalo-watch` must restart it. QR only if `sessionDead=true`.
