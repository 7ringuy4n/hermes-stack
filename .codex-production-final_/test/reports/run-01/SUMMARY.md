# Run 01 — Summary

Version target: **v0.5.0**  
Branch: `feature/arch/v0.5.0-router-layer`  
Started: 2026-08-17 08:46 +07  
Finished: 2026-08-17 09:08 +07  
Final stack left running: **High** (Traefik public → fail-soft local)

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
    <tr><td>Medium</td><td>local</td><td>PASS</td><td>PASS (503)</td><td>PASS</td></tr>
    <tr><td>High</td><td>local</td><td>PASS</td><td>PASS (503)</td><td>PASS</td></tr>
    <tr><td>Low</td><td>public</td><td>PASS</td><td>n/a</td><td>PASS</td></tr>
    <tr><td>Medium</td><td>public</td><td>PASS</td><td>PASS (503)</td><td>PASS</td></tr>
    <tr><td>High</td><td>public</td><td>PASS</td><td>PASS (503)</td><td>PASS</td></tr>
  </tbody>
</table>

High extras (public, last cycle):

- Concurrent text: 5/5 PASS (not the full 10-type burst; files were queued after)
- File ingest jobs: 9/9 finished (txt/md/pdf/docx/xlsx/pptx/png/mp3/mp4)
- Web search HCMC: PASS (SearXNG, 5 hits)
- Policy: PASS (export deny)
- Antivirus: PASS (disabled short alert; scanner not enabled — **infected case not in this run**)
- OpenVPN: PASS (disabled short alert)
- Backup/restore: PASS (stamp `20260817_090118`, canary restored)
- Zalo SSE: PASS (`sseClients=1` after heal; Hermes ×2)
- Memory/authz after restore: recovered after PG-client restart (source fix applied)

Fail-event gaps vs RULES.md §13 (covered after run 02 on the same High stack): EICAR infected scan, concurrency ramp until first fail, Hermes/Zalo auto-heal.

**Run 01 overall: PASS** for install/health/media-disabled. Fail-event suite is in `reports/run-02/fail-events.md`.
