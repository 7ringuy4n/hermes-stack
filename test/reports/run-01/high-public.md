Profile: High
Mode: public
Run: 01
Started: 2026-08-17 09:00 +07
Finished: 2026-08-17 09:08 +07

Health: PASS. Traefik public fail-soft to local.

Concurrent requests:
- Text:    5/5 PASS (parallel chat completions; latency recorded in lab log)
- PDF:     1/1 PASS (ingest job finished)
- TXT:     1/1 PASS
- MD:      1/1 PASS
- DOCX:    1/1 PASS
- XLSX:    1/1 PASS
- PPTX:    1/1 PASS
- Image:   1/1 PASS (job enqueue; not live Zalo)
- Music:   1/1 PASS
- Video:   1/1 PASS

Total typed requests: 14 (5 text + 9 files). File jobs were sequential enqueue after text, not one 10-wide burst.

Web search: PASS (SearXNG, 5 HCMC weather hits)
Policy: PASS (export → deny default-deny-export)
Antivirus: PASS (ENABLE_ANTIVIRUS=0 → short alert)
Media-disabled fallback: PASS
OpenVPN: PASS (disabled short alert)
Backup: PASS (20260817_090118)
Restore: PASS (canary restored; Zalo SSE 0 then 1)
All services healthy: PASS after PG-client restart (memory/authz)
Zalo → Hermes: PASS (sseClients=1, loggedIn, no QR this run)

Known issues:
- Post-restore memory/authz 503 until client restart (fixed in source).
- Live Zalo attachment UX not in this run.

Final: PASS
