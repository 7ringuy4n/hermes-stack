# security / av-gateway

## Purpose

HTTP gateway in front of ClamAV (and similar). Scans uploaded or inbound files and returns clean / infected before any extract or OCR.

## Profile

High (`ENABLE_ANTIVIRUS=1`).

## Main functions

| Function | Detail |
|---|---|
| Scan by path or upload | Returns status for pipeline |
| Fail closed | On scanner down, prefer block or skip ingest (config) |

## Related

- [../README.md](../README.md)  
- [security-manager](../security-manager/README.md)
