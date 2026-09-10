# Case 59: Backup Corruption / Partial Backup

**Gap matrix id:** Case 55 (Production Failure Gap Test Cases v2)

**Zalo identity:** inject as allowlisted user **Tn** when the case touches inbound Zalo.

## Goal

Verify backup verification catches unusable backups.

## Procedure

Create known:

- Postgres data;
- Qdrant data;
- Valkey/session state;
- workflow state;
- knowledge files;
- configuration.

Then test:

- truncated backup;
- missing file;
- corrupted archive;
- wrong permissions;
- incomplete Qdrant snapshot;
- incomplete Postgres dump;
- backup created while writes are active.

## Pass criteria

`backup` or `verify` must fail rather than declaring success.

Never allow:

`backup exit code 0 → restore unusable data`

The current rules already explicitly require functional verification after restore; this case makes the failure side explicit.

---
