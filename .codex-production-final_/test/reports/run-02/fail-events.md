# Run 02 — Fail events (High, public fail-soft)

Started: 2026-08-17 09:39:39 +0700  
Finished: 2026-08-17 09:42:39 +0700  

<table>
  <thead>
    <tr>
      <th>Area</th>
      <th>Fail event</th>
      <th>Result</th>
      <th>Detail</th>
    </tr>
  </thead>
  <tbody>
    <tr><td>Antivirus</td><td>EICAR infected file</td><td>PASS</td><td>session BLOCKED, infected=1; security-manager verdict RISK + short alert</td></tr>
    <tr><td>Antivirus</td><td>Clean file</td><td>PASS</td><td>READY_FOR_PROCESSING, clean=1, blocked=false</td></tr>
    <tr><td>Concurrency</td><td>Ramp until first fail</td><td>PASS</td><td>last all-success <strong>24</strong>; first fail <strong>32</strong> (HTTP 503); 8/8, 16/16, 24/24 then 31/32</td></tr>
    <tr><td>Hermes crash</td><td>Stop one replica</td><td>PASS</td><td>stack-watch restarted exited replica (~2s); both Up; no crash loop</td></tr>
    <tr><td>Zalo lost connection</td><td>Stop zalo-proxy</td><td>PASS</td><td>First tick missed stopped proxy (host bridge still up). Source fix: zalo-watch starts exited proxy. Retest 09:42:36 — proxy started, sseClients=1, no QR</td></tr>
  </tbody>
</table>

**Fail-event suite: PASS** (Zalo heal after source fix + retest)

Notes:

- Infected sample is the standard EICAR test string (not a real malware payload).
- Concurrency fail mode at 32: `HTTP 503 Service Unavailable` on Model Router / upstream — stack stayed up.
- Hermes/Zalo auto-heal does **not** replace QR when `sessionDead=true`.
