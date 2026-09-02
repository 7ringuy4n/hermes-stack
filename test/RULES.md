# Deployment & Worker Test Rules

**Source of truth for agent/operator policy:** [`../AGENT_RULES.md`](../AGENT_RULES.md) (sections **1–31**).\
**This file** is the lab methodology companion named in AGENT_RULES §28 / §30: how to run deployments, worker sets, and cases under [`cases/`](./cases/).

Hard gates that always apply to lab work (see AGENT_RULES):

| Topic | AGENT_RULES |
|-------|-------------|
| Test integrity / no cheat passes | §3 Hard Gates, §5 Test Integrity |
| Real Zalo path when available | §7 Real Integration Testing |
| No lab identity in committed source | §16 Lab Isolation |
| No deploy / push / MR without permission | §17 Deployment Safety |
| Remote SSH / script send needs permission | §18 Remote Operations |
| Restore defaults after testing | §19 Test Configuration Cleanup |
| Post-test / post-patch crash-loop log watch | §18.1 / §19 (HISTORY 2026-08-21 11:20) |
| Source-first fixes (no lab hotpatch) | §15 Source-First Fixes |

## Cases not to run (AGENT_RULES §28)

Existing cases: [`cases/`](./cases/). Skip only:

| Case | File |
|------|------|
| Skills mount + auto-learn (Medium+) | `cases/12-skills-auto-learn.md` |
| Exact text poster (text-poster backend) | `cases/13-image-text-poster.md` |
| Internal docs knowledge-first | `cases/14-knowledge-internal-rag.md` |

## 1. Test Runs

Run the complete test suite **2 times**, using different test cases/data each run.

For every run and every target worker set:

1. **Backup first:** `bash run.sh backup` then `bash run.sh verify <stamp>` must succeed.
2. Clear previous test files/data.
3. Destroy the current environment (`bash run.sh destroy` also backup+verifies).
4. Recreate from source.
5. Deploy the chosen worker set.
6. Test both modes:
   - `local`
   - `public`
7. Record all results with timestamps.
8. Do not reuse artifacts from a previous profile unless the test explicitly requires persistence.
9. **Restore defaults (AGENT_RULES §19):** when the run is finished, revert test-only source and config to product defaults. Do not leave lab timeouts, cache-bust keys, host identities, or worker/component flags that were only for that run.
10. **Monitor abnormal logs after the run (and while patching):** test cases / heal / bridge patches may leave a crash-loop on the Zalo bridge or other services. Before calling the run done, watch at least:
    - `docker logs -f assistant-hermes-1 2>&1` (live Hermes container name if different)
    - `journalctl --user -u com.hermes.zaloplugin -f`
    Fail the run if you see `EADDRINUSE` restart storms, repeated unit `auto-restart`, media-proxy `/media/fetch` 404 spam, or unrelated worker flap. Reference: [`../scripts/HISTORY.md`](../scripts/HISTORY.md) **2026-08-21 11:20 +07 — Bridge crash-loop on :8787**. Same watch applies whenever patching the bridge or Hermes Zalo path (AGENT_RULES §18.1).

Destroy and config changes (`destroy`, `add-components`, `update`) **abort** if backup or verify fails. `switch-profile` is legacy and must fail fast.

## 2. Zalo Installation

When Zalo is requested:

1. Install/configure the **bridge/proxy first**.
2. Complete all automated setup.
3. Stop before QR scanning.
4. Ask the user to manually scan the QR code.
5. Continue testing only after the user confirms the QR login is complete.
6. After setup, patch, or heal: keep `journalctl --user -u com.hermes.zaloplugin -f` and Hermes `docker logs` open long enough to catch an `EADDRINUSE` crash-loop or media-proxy 404 (AGENT_RULES §18.1; HISTORY **2026-08-21 11:20 +07**).

## 3. All Worker Sets — Basic Tests

For **every tested worker set** verify:

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
- Verify local/public exposure follows the active edge/security rules.
- Verify disabled components are actually inaccessible/disabled.
- Verify enabled optional components work.
- Verify graceful failure when a dependency is unavailable.

## 4. Media|File Worker — Media

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

## 5. Security / full worker set — Concurrent Request Test

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

**Zalo concurrent (High, required when Zalo is on):**

- Text-only ramp: `cases/08-zalo-concurrent.md` (do not open a second SSE client).
- **Mixed text + media generation** in the same burst: `cases/09-zalo-concurrent-media.md`.
  Half the workers send short chat text (**Traefik `:8080/v1/chat/completions`** + `API_SERVER_KEY`); half call dispatcher `POST /v1/image` (`refine=false`).
  Record **delay** per kind (min / p50 / p95 / max ms), last all-success N, first-fail N, SSE still `1`, Hermes replicas still up.
  Lab run-05: last all-success **N=4**, first-fail **N=8** (text HTTP 503 / one image 502); image ~0.3–6s; text ~4–16s when 200.

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
- Public endpoint restrictions (VPN/localhost only — `TRAEFIK_MODE=local`; ACME off unless explicitly testing public).
- OpenVPN access.
- No policy bypass through fallback/error paths.
- **Isolation vs LLM judge** (`cases/10-security-isolation-risks.md`): judge default off; `CLEAN` must not allow; prompt-injection excerpt must not become the security boundary.
- **Container socket:** `docker.sock` must not be mounted on security-manager or zalo-api; `docker-socket-proxy` must not run unless `SECURITY_SANDBOX=1`.
- OpenBao / 9router / Postgres host publishes stay on loopback (not Traefik).

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

### Omni combos (`hermes` / `classifier`)

Before Zalo reply tests (case 32) or manual Zalo chat on the lab:

1. Run case **38** — `python test/scripts/omni_combo_preflight.py`
2. If empty combos: `bash run.sh first-setup-omnirouter`
3. Re-run case 38 until `PASS_OMNI_COMBO_PREFLIGHT`

Empty `hermes`/`classifier` combos: inbound Zalo messages succeed but **Hermes sends no reply** (router 400).

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
4. Destroy/reset the relevant data/environment (`destroy` also backup+verifies first).
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
| Zalo mixed media+text | Ramp interleaved chat + `/v1/image` until first fail | Last-all-success N, first-fail N, **delay p50/p95/max per kind**, SSE=1; text auth via Traefik+`API_SERVER_KEY` |
| Zalo compound message | One bubble with `tin nhắn 1` + `tin nhắn 2` | Both intents addressed (case 16) |
| Zalo busy + cron multi-task | Interrupt `/busy` tip; 3-item daily job | Tip dropped; all cron items run (case 22) |
| Zalo inbound FIFO | 3 requests in one bubble; rate-limit burst | All queued intents run; extras not dropped (case 23) |
| Zalo special four (hello/image/fuel/video) | 4-item English lịch, 2 minutes | Four jobs, **new** image+video `send-attachment` in the fire window; leftover mp4 does not count (case 25) |
| Zalo weather+fuel infographic | One Vietnamese sentence | `PLAN_N 1`, file sent to admin DM, overlay facts on the image (case 26) |
| Zalo media + lịch delivery | Video invalid-param / leftover job | Remuxed mp4 sent; completed job must not claim a later file; media turns result-only (case 28) |
| Zalo latency SLO | 5 short text pings | FAIL if any sample **> 5s** on localhost (case 17) |
| Grafana integration | Grafana on → each deployed scrape target | `assistant_service_up` + exporter scrape success (case 20) |
| Default routers | 9Router always; OmniRouter default 0 | Hermes connected; flag matches container (case 21) |
| Schedule TZ | 05:58 local → daily 06:00 | Must be **today**, not tomorrow (case 15) |
| Web search backends | `/v1/search` + `/health` | Record `backend` field (case 18) |
| File pipeline security | EICAR + matrix | AV inbound vs YARA paths (case 19) |
| Isolation / LLM judge | Judge off; EICAR via YARA; injection file cannot LLM-allow | Sock absent on AI services; sandbox/proxy off; VPN-only edge |
| Profile switch | Unknown tier / unknown `ENABLE_*`; notify add then remove | Usage error; High↔Medium overlays; existing Zalo flag kept; backup+verify before apply |
| Skills auto-learn | Ingest down or empty skills dir | post-ready-learn skip/fail without Hermes crash-loop; rebuild dispatcher for text-poster |
| Text poster | Empty prompt | HTTP 400; no PNG written |
| Internal knowledge | learn/list empty after successful learn | FAIL — pipeline broken |
| Media / search / VPN / policy | Disabled or deny | Short user-facing alert; no stack dump |

**Auto-heal:** if Hermes or Zalo dies from an error/exception/lost connection, health must return without a manual QR (unless the Zalo session is actually dead). Record timestamps: fault injected → watch tick → healthy.

## 14. Two-pass lab (source then Quick start)

When re-testing a live High/Zalo lab:

1. **Pass 1 — source allowed.** Sync tree, destroy leftovers, `bash run.sh up` (High + Zalo + edge). If deploy hits a **source** defect, fix the repo, changelog, rebuild, rerun the failed step. Then run cases 08–11 and fail-events.
2. **Pass 2 — script only.** No source edits. Follow README **Quick start** on the already-synced tree: `bash run.sh down` then `bash run.sh up`, `bash run.sh first-setup-llm`, `bash run.sh ps`. Re-probe health (Traefik **`/health`**, not `/`), Zalo SSE, isolation risks (`security_risks.py`), a **smaller** mixed media burst (e.g. N≤4 via `ZALO_MEDIA_MAX=4`), and worker **dry-run** (`add-components WORKER_NOTIFY=active --dry-run` / `workers`).
3. Leave High running. Do not put hostnames, IPs, or account names in reports.
4. After the run, add any new cases to this file (this section and the case index under `test/cases/`).
5. Record summary in `test/reports/run-NN-two-pass/SUMMARY.md` with an **HTML** profile×mode table (see §11).

**Latest lab (run-skills-lab):** Medium + skills copy + post-ready-learn PASS; 52 docs indexed (approve 52/52); cases 12–14 PASS (mount, learn/list, text-poster HTTP 400 fail-event, knowledge mount). Local ONNX embedding fallback. See `reports/run-skills-lab/SUMMARY.md`.

**Latest two-pass lab (run-05):** pass 1 sync+deploy PASS; case 11 High↔Medium + add/remove notify (source fix: drop disabled-profile containers); text concurrent N≤24 PASS; mixed media last-ok **N=4** first-fail **N=8** (text 503); isolation PASS; pass 2 Quick start PASS; see `reports/run-05-two-pass/SUMMARY.md`.

## 15. Case index

| Case | File |
|------|------|
| Basic health (all profiles) | `cases/01-basic-health.md` |
| Media disabled | `cases/02-media-disabled.md` |
| High 10-type concurrency | `cases/03-high-concurrency.md` |
| Web search | `cases/04-web-search.md` |
| Security / policy | `cases/05-security-policy.md` |
| Backup / restore | `cases/06-backup-restore.md` |
| Fail events + auto-heal | `cases/07-fail-events.md` |
| Zalo concurrent text | `cases/08-zalo-concurrent.md` |
| Zalo concurrent text + media gen + delay | `cases/09-zalo-concurrent-media.md` |
| Isolation risks (sock, judge, VPN-only) | `cases/10-security-isolation-risks.md` |
| Worker add/remove | `cases/11-worker-switch.md` |
| Skills mount + auto-learn (Medium+) | `cases/12-skills-auto-learn.md` |
| Exact text poster (text-poster backend) | `cases/13-image-text-poster.md` |
| Internal docs knowledge-first | `cases/14-knowledge-internal-rag.md` |
| Schedule TZ (today vs tomorrow) | `cases/15-schedule-timezone.md` |
| Zalo compound multi-request | `cases/16-zalo-multi-request.md` |
| Zalo latency SLO | `cases/17-zalo-latency-slo.md` |
| Web search backend chain | `cases/18-web-search-backends.md` |
| File/OCR/YARA/AV matrix | `cases/19-file-pipeline-security.md` |
| Grafana component integration | `cases/20-grafana-component-integration.md` |
| Default 9Router / OmniRouter connected | `cases/21-defaults-routers-connected.md` |
| Zalo busy interrupt + multi-task cron | `cases/22-zalo-busy-cron-multi.md` |
| Zalo inbound FIFO (plenty of requests) | `cases/23-zalo-inbound-queue.md` |
| Plenty-in-one + same/different-time cron | `cases/24-workflow-multi-cron-channels.md` |
| Zalo special four (hello + image + fuel + video) | `cases/25-zalo-special-four.md` |
| Zalo weather+fuel infographic (one picture) | `cases/26-zalo-weather-fuel-poster.md` |
| Daily lịch of one weather+fuel infographic | `cases/27-zalo-weather-fuel-daily.md` |
| Zalo media gen + lịch delivery | `cases/28-zalo-media-cron-delivery.md` |
| Zalo once-lịch numbered tasks (no cite) | `cases/29-zalo-once-numbered-nocite.md` |
| Hermes dual-replica isolation | `cases/30-hermes-dual-isolation.md` |
| Schedule fire into a group | `cases/31-schedule-group-fire.md` |
| Secret-probe paths + AV via Security Worker | `cases/32-secret-probe-path-eicar.md` |
| Zalo Tn greeting reply (LLM configured) | `cases/32-zalo-tn-greeting-reply.md` |
| Zalo image / PDF / txt send / queue | `cases/33-zalo-image-pdf-txt-queue.md` |
| Attachment workers, mixed pack, compound split, schedule remove | `cases/34-zalo-attachment-workers-schedule-remove.md` |
| Image / video text really read (OCR fallback, ASR) | `cases/35-image-video-text-really-read.md` |
| Vision-ocr combo for images/PDF | `cases/36-vision-ocr-combo.md` |
| Omni rotate + OCR never silent | `cases/37-omni-rotate-ocr-noreply.md` |
| Omni combo preflight (hermes + classifier filled) | `cases/38-omni-combo-preflight.md` |

**Unit scripts (no VPS, run in small batches):**

| Script | Case |
|--------|------|
| `test/scripts/schedule_timezone_unit.py` | 15 |
| `test/scripts/multi_request_unit.py` | 16 + 22 (schedule keep-whole) + 26/27 infographic + 29 once-lịch |
| `test/scripts/knowledge_cite_unit.py` | 29 |
| `test/scripts/llm_classify_unit.py` | 24/25/26/27/29 classify JSON |
| `test/scripts/gateway_noise_unit.py` | 22 |
| `test/scripts/inbound_queue_unit.py` | 23 |
| `test/scripts/web_search_backends_unit.py` | 18 |
| `test/scripts/grafana_pairing_unit.py` | 20 |
| `test/scripts/defaults_profile_unit.py` | 21 |
| `test/scripts/ux_copy_unit.py` | schedule-saved locale map |
| `test/scripts/zalo_attachment_unit.py` | 34 (worker routing, blank caption, mixed-pack recall) |
| `test/scripts/schedule_crud_unit.py` | 34 (remove list / range / group / all) |
| `test/scripts/secret_probe_path_unit.py` | 32 |
| `test/scripts/ocr_refuse_unit.py` | 35 (blind model reply must not pass as OCR text) |
| `test/scripts/vision_ocr_policy_unit.py` | 36 (vision-ocr combo; no OCR container) |
| `test/scripts/omni_rotate_noreply_unit.py` | 37 (Omni rotate free models; OCR image always acks) |
| `test/scripts/zalo_workflow_parallel_unit.py` | Zalo workflow parallel default |
| `test/scripts/soul_deception_unit.py` | SOUL must not trip deception_hide |

**Lab scripts (SSH, one case per invocation — AGENT_RULES §17 / §18: explicit permission required):**

| Script | Case |
|--------|------|
| `test/scripts/zalo_tn_greeting_inject.py` | 32 (Tn greeting reply) |
| `test/scripts/omni_combo_preflight.py` | 38 (hermes + classifier combos filled) |
| `test/scripts/zalo_latency_lab.py` | 17 |
| `test/scripts/zalo_special_four_lab.py` | 25 |
| `test/scripts/zalo_weather_fuel_lab.py` | 26 |
| `test/scripts/file_pipeline_security_lab.py` | 19 |
| `test/scripts/grafana_integration_lab.py` | 20 (skip if Grafana off) |
| `test/scripts/defaults_routers_lab.py` | 21 |
| `test/scripts/zalo_tn_history_regression.py` | HISTORY no-reply / PDF / schedule gaps |
| `test/scripts/run_case_index_lab.py` | Full §15 batch (units + VPS scripts) |

## Production failure gap cases (40–74)

See [cases/README-gap-cases.md](./cases/README-gap-cases.md). Zalo cases inject as **Tn**. On failure, fix source and retry only the failed case (`ZALO_HISTORY_CASE=...`).

## Post-lab restore (required)

After the final lab round, before stopping the VPS:

1. `bash scripts/main/post-lab-restore.sh` — Omni OpenCode combos, Zalo session, health + router chat smoke.
2. Confirm case 38 `PASS` and case 32 greeting inject `PASS` (or document timeout with `ZALO_GREETING_WAIT_S`).
3. Do not leave empty `hermes`/`classifier` combos — that breaks manual Zalo chat (configuration gap, not bridge bug).

