# Case: Dual Hermes isolation (admin concurrent mix)

Scale Hermes to **2** replicas. Fire concurrent admin-originated requests through the **Zalo bridge** (inject / real inbound path — not a second SSE login). Watch session isolation and shared `media/*` permissions.

## Goal

- Two Hermes containers healthy; exactly **one** Zalo SSE owner (`sseClients=1`)
- Concurrent mix does not cross-contaminate replies / `media/out` claims
- No `Permission denied` on `/opt/data/media/inbound` or `media/out`
- After the run, restore `HERMES_REPLICAS` to the pre-test value (rule 41)

## Request mix (admin thread)

| Kind | Example (Vietnamese/English OK) |
|------|----------------------------------|
| Hello | `xin chào` / `hello` |
| Web search | `tìm trên web thời tiết Hồ Chí Minh hôm nay` |
| Text create | `tạo file txt ghi nội dung: isolation probe <tag>` |
| Vision / docs | Attach or stage sample image/pdf/xlsx/docx/pptx under inbound and ask to read/summarize |

## Preconditions

- `ENABLE_ZALO=1`, bridge `loggedIn=true`
- Media worker on if vision/file kinds are included (`ENABLE_MEDIA_FILE` / `WORKER_MEDIA_FILE`)
- Sole admin uid present in `zalo_admin_users.txt`

## Lab script

```bash
python test/scripts/hermes_dual_isolation_lab.py
```

Env: `ASSISTANT_SSH_*`. Optional: `HERMES_DUAL_RESTORE=1` (default) restores replica count after the run.

Reports: `test/reports/run-hermes-dual-isolation/` (no host/account secrets).

## Pass criteria

- `hermes_count=2` during the burst
- `sseClients=1` before and after
- Each kind records success or a short user-facing error (no stack traces)
- Log scan: no `Permission denied: /opt/data/media`
- No evidence of reply text from one kind appearing as the answer for another tag
- Defaults restored (`HERMES_REPLICAS` back)

## Fail events

- Second SSE attach / double Zalo owner
- Hermes crash-loop during scale or burst
- Media permission errors on inbound/out
- Cross-talk between concurrent admin tags
