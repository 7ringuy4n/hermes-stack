# Case: file create / OCR / YARA / AV paths

Document and test **which security layer** each path uses.

## Expected matrix

| Path | AV (ClamAV) | YARA / security-manager |
|------|-------------|-------------------------|
| Zalo **inbound** attachment | Yes (`av-gateway`) | **No** (gap — record) |
| Dispatcher **outbound** generated file | If `SECURITY_URL` set | Yes |
| Direct POST `security-manager/v1/scan` | Optional | Yes (lab) |
| Ingest learn submit | **Not wired** (`SECURITY_URL` unused) | **No** |

## Steps

1. Run `python test/scripts/file_pipeline_security_lab.py` (batch — separate from other labs)
2. EICAR via `security-manager` → BLOCKED
3. Clean txt via `security-manager` → CLEAN
4. If Zalo on: inbound EICAR attachment → blocked at AV gate (no LLM turn)
5. Vision read: ingest/dispatcher vision-ocr on clean PDF sample → text extract (no YARA in path)

## Pass criteria

- Matrix matches live probes
- Infected sample never reaches Hermes LLM on Zalo inbound
- User alert is short; no stack trace

## Fail events

- EICAR reaches ingest without block
- Inbound Zalo file skips AV when `ENABLE_ANTIVIRUS=1`

## Follow-up (P0 backlog)

- Wire ingest optional `SECURITY_URL` scan before embed
- Optional inbound YARA via security-manager (config flag)
