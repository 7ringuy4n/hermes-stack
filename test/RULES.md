# Deployment & Profile Test Rules

## 1. Test Runs

Run the complete test suite **2 times**, using different test cases/data each run.

For every run and every profile:

1. Clear previous test files/data.
2. Destroy the current profile/environment.
3. Recreate from source.
4. Deploy the profile.
5. Test both modes:
   - `local`
   - `public`
6. Record all results with timestamps.
7. Do not reuse artifacts from a previous profile unless the test explicitly requires persistence.

## 2. Zalo Installation

When Zalo is requested:

1. Install/configure the **bridge/proxy first**.
2. Complete all automated setup.
3. Stop before QR scanning.
4. Ask the user to manually scan the QR code.
5. Continue testing only after the user confirms the QR login is complete.

## 3. All Profiles — Basic Tests

For **every profile** verify:

- Installation completes without unhandled exceptions.
- All expected services start successfully.
- Configuration is valid.
- Health checks pass.
- Hermes starts without crash-looping.
- Edge ports are reachable where expected.
- Hermes can connect to the configured LLM router/model.
- Session creation, request handling, and response delivery work.
- Restart services and verify recovery.
- Verify logs contain no unexpected `ERROR`, exception, or repeated failure.
- Verify local/public exposure follows the profile's security rules.
- Verify disabled components are actually inaccessible/disabled.
- Verify enabled optional components work.
- Verify graceful failure when a dependency is unavailable.

## 4. Medium / High Profiles — Media

Verify image/media generation behavior.

**Required negative test:**

- Disable image-generation/media tools.
- Send a media-generation request.
- Verify Hermes does not crash, hang, or falsely claim media was generated.
- Verify it returns a short, user-friendly alert indicating media generation is unavailable.

Also test:

- Media service unavailable.
- Media service timeout.
- Invalid media request.
- Generated media delivery failure.
- Unsupported media type.

## 5. High Profile — Concurrent Request Test

Run concurrent requests containing:

1. Text message
2. PDF
3. TXT
4. Markdown
5. DOC/DOCX
6. XLS/XLSX
7. PPT/PPTX
8. Image
9. Music/audio
10. Video

Record:

- Number of concurrent requests.
- Request start/end timestamps.
- Success/failure.
- Response latency.
- Queue behavior.
- Memory/CPU impact.
- Any timeout.
- Any exception.
- Any dropped request.
- Any cross-request/session data leakage.

Repeat with different files/data on Run 2.

**Ramp until fail (required):** after the 10-type burst, increase concurrent load (text or mixed) in steps (for example 8 → 16 → 32 → 48) until the **first** failure, timeout, drop, or crash. Record:

- Last batch size that was **all success**
- First batch size that **failed**
- Failure mode (timeout, HTTP error, exception, dropped, Hermes/Zalo down)
- Whether the stack auto-recovered afterward

A concurrency test that never attempts a fail event is incomplete.

## 6. High Profile — Web Search

Test web-search capability with:

> Search for the current weather in Ho Chi Minh City.

Verify:

- Search tool is invoked.
- Current information is returned.
- Hermes does not fabricate results when search is unavailable.
- Search timeout/failure produces a controlled response.

## 7. High Profile — Security & Policy

Test:

- Policy enforcement.
- Permission/role restrictions.
- ACL/default-deny behavior where applicable.
- Secret-probe/security rules.
- Antivirus/file scanning.
- Malicious/blocked file handling.
- Unsupported/oversized file handling.
- Unauthorized tool access.
- Public endpoint restrictions.
- OpenVPN access.
- No policy bypass through fallback/error paths.

For blocked operations, verify the user receives a **short, safe alert**, not internal logs or security details.

**Fail events are required** (happy-path only is not enough):

- Antivirus: scan a **clean** file **and** an **infected** sample (use the EICAR test file). Expect CLEAN vs INFECTED/BLOCKED and a short user alert — never a stack trace.
- If AV is disabled, also record the disabled short alert, then enable AV for the infected case (or mark FAIL if High cannot scan infected files).
- Policy: allow path and deny path.
- Media: success path when backends exist **or** disabled/unavailable fail path with a short alert.

## 8. Optional Services

Create installation and functional test cases for every optional service, including where applicable:

- `9router`
- `Omnirouter`
- Other LLM routers/providers
- Memory services
- Vector/knowledge services
- OCR
- Browser/search services
- Media services
- Queue/worker services
- Storage/backup services
- Any other profile-specific optional component

For each service test:

1. Install.
2. Start.
3. Health-check.
4. Verify integration with Hermes.
5. Stop/disable.
6. Verify Hermes handles the missing service gracefully.
7. Re-enable/restart.
8. Verify recovery.

## 9. Infrastructure Tests

Test all enabled infrastructure components, including where applicable:

- OpenVPN
- API gateway/edge
- Hermes
- Memory manager
- Valkey/cache/session
- PostgreSQL
- Vector database
- Workers/queue
- Storage
- LLM router
- MCP/tools
- Knowledge/RAG
- Backup/restore
- Monitoring/health checks

Check for:

- Startup failure.
- Runtime exception.
- Connection failure.
- Timeout.
- Retry failure.
- Resource exhaustion.
- Service restart/recovery.
- Dependency unavailable.
- Incorrect configuration.
- Cross-profile contamination.

## 10. Backup / Restore — Final Round

At the final test round:

1. Create known test data.
2. Run backup.
3. Verify backup completed successfully.
4. Destroy/reset the relevant data/environment.
5. Restore the backup.
6. Verify the restored data.
7. Verify memory/knowledge/session data where applicable.
8. Verify configuration required for restoration.
9. Restart services.
10. Verify all services are healthy.
11. Verify Hermes works after restore.
12. Verify Zalo can connect to Hermes after restore.

Do not consider backup/restore successful merely because the backup command returned exit code `0`; verify actual restored data/functionality.

## 11. Test Directory & Reports

Create:

```text
test/
├── cases/
├── fixtures/
├── scripts/
└── reports/
    ├── run-01/
    └── run-02/
```

Create a detailed report for **every profile and every run**.

Each report must include:

- Profile.
- Mode (`local` / `public`).
- Test-run ID.
- Start/end timestamp.
- Source commit/version.
- Installed services.
- Optional services tested.
- Number of test cases.
- Passed/failed/skipped count.
- Concurrent request count.
- Per-request type and result.
- Response/error details.
- Service health results.
- Security/policy results.
- Media results.
- Web-search result.
- Backup/restore verification.
- Zalo connectivity result.
- Resource/concurrency observations.
- Known issues.
- Final pass/fail status.

Profile×mode **summary tables must be HTML** (`<table>`, `<thead>`, `<th>`, `<td>`), not Markdown pipes. Example:

```html
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
```

Do not put hostnames, IPs, or account names in reports.

Example detail block:

```text
Profile: High
Mode: public
Run: 01
Started: 2026-08-17 09:00
Finished: 2026-08-17 10:42

Concurrent requests:
- Text:    1/1 PASS
- PDF:     1/1 PASS
- TXT:     1/1 PASS
- MD:      1/1 PASS
- DOCX:    1/1 PASS
- XLSX:    1/1 PASS
- PPTX:    1/1 PASS
- Image:   1/1 PASS
- Music:   1/1 PASS
- Video:   1/1 PASS

Total concurrent requests: 10
Successful: 10
Failed: 0

Web search: PASS
Policy: PASS
Antivirus: PASS
Media-disabled fallback: PASS
Backup: PASS
Restore: PASS
All services healthy: PASS
Zalo → Hermes: PASS

Final: PASS
```

## 12. Completion Criteria

A profile is **PASS** only when:

- Installation succeeds.
- All required services are healthy.
- Required integrations work.
- Local and public modes pass.
- Concurrent tests pass for the required profile.
- Failure/timeout paths are controlled.
- Security/policy tests pass.
- Media-disabled behavior is correct.
- Backup/restore is verified where required.
- Zalo connectivity is verified where applicable.
- No unexplained runtime exceptions remain.
- Test report is complete.

If a source-code defect is discovered during testing, **fix the source, update `docs/CHANGELOG.md` with timestamp, rebuild/redeploy, and rerun the affected tests**. Do not hide or work around the defect only in the test environment.

## 13. Fail events and auto-heal (required)

Every capability must include at least one **fail event**, not only success.

| Area | Required fail event | Pass criteria |
|------|---------------------|---------------|
| Antivirus | EICAR (or equivalent) infected file | Verdict INFECTED/BLOCKED + short alert; clean file still CLEAN |
| Concurrency | Ramp until first fail | Record last-all-success N and first-fail N |
| Hermes crash | Stop/kill a Hermes replica | `stack-watch` (or equivalent) restores the replica without a crash loop |
| Zalo lost connection | Stop proxy or SSE=0 | `zalo-watch` restores proxy/SSE; QR only if `sessionDead` |
| Media / search / VPN / policy | Disabled or deny | Short user-facing alert; no stack dump |

**Auto-heal:** if Hermes or Zalo dies from an error/exception/lost connection, health must return without a manual QR (unless the Zalo session is actually dead). Record timestamps: fault injected → watch tick → healthy.