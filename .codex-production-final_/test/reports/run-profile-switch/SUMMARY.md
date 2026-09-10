# Profile switch (upgrade/downgrade + options)

- Timestamp: `2026-08-17 15:02:20 +0700`

- **dry_switch**: pass — ok
- **fail_bogus_profile**: pass — ok
- **fail_bogus_flag**: pass — ok
- **archive_options**: pass — ok
- **add_notify**: pass — ok
- **remove_notify**: fail — missing marker
- **remove_notify (retest after source fix)**: pass — NOTIFY_GONE / ALERT_GONE; `run.sh` now drops disabled-profile containers
- **existing_zalo**: pass — ok
- **downgrade_openbao_gone**: pass — ok
- **downgrade_ocr**: pass — ok
- **downgrade_zalo**: pass — ok
- **upgrade_openbao**: pass — ok
- **upgrade_authz**: pass — ok
- **upgrade_security**: pass — ok
- **upgrade_hermes_x2**: pass — HERMES_N=2

Final: **PASS** (0 fail after retest; first pass had 1 fail on notify leftover, fixed in `run.sh`)
