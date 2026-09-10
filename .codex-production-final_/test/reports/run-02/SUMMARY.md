# Run 02 — Summary

Version target: **v0.5.0**  
Branch: `feature/arch/v0.5.0-router-layer`  
Started: 2026-08-17 09:17:50 +0700  
Finished: 2026-08-17 09:34:59 +0700  
Final stack left running: **High** (Traefik public → fail-soft local when ACME absent)

<table>
  <thead>
    <tr>
      <th>Profile</th>
      <th>Mode</th>
      <th>Health</th>
      <th>Media-disabled</th>
      <th>Final</th>
    </tr>
  </thead>
  <tbody>
    <tr><td>Low</td><td>local</td><td>PASS</td><td>n/a</td><td>PASS</td></tr>
    <tr><td>Medium</td><td>local</td><td>PASS</td><td>PASS</td><td>PASS</td></tr>
    <tr><td>High</td><td>local</td><td>PASS</td><td>PASS</td><td>PASS</td></tr>
    <tr><td>Low</td><td>public</td><td>PASS</td><td>n/a</td><td>PASS</td></tr>
    <tr><td>Medium</td><td>public</td><td>PASS</td><td>PASS</td><td>PASS</td></tr>
    <tr><td>High</td><td>public</td><td>PASS</td><td>PASS</td><td>PASS</td></tr>
  </tbody>
</table>

Concurrent burst: 10/10 in 4782 ms  
Web search: PASS  
Policy: PASS  
Antivirus (disabled alert): PASS — infected EICAR in `fail-events.md`  
OpenVPN (disabled alert): PASS  
Media-disabled: PASS on Medium/High (503 + empty-prompt 400)  
Backup/restore: PASS (stamp `20260817_093248`, canary restored)  
Zalo: PASS (sseClients=1 after election wait; session already logged in — QR not required)

Reports omit hostnames, IPs, and account names.

Fail-event extras (same High stack, 09:39–09:42 +07): see `fail-events.md`.

- EICAR infected: PASS (BLOCKED)
- Concurrency until fail: last all-success **24**, first fail **32** (503)
- Hermes crash auto-heal: PASS
- Zalo proxy crash auto-heal: PASS after zalo-watch start-exited-proxy fix

**Run 02 overall: PASS**

Note: a mid-restore health sample saw sseClients=0 while Hermes was electing; confirmed sseClients=1 at 09:35:40 +07 without a new QR login.
