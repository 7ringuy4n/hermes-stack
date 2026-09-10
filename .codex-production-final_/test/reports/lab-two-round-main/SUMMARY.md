# Two-round main lab — 2026-08-22

Host: VPS lab (tn). Branch: `main` @ `c08529f`. Duration: ~18.5 min deploy + tests × 2.

## Deploy (both rounds)

| Step | Round 1 | Round 2 |
|------|---------|---------|
| Backup Zalo + postgres | OK | skipped |
| Wipe (fail2ban + preserve kept) | OK | OK |
| Clone main + secrets + all workers + Qwen local | OK | OK |
| Zalo restore (loggedIn, sseClients=1) | OK | OK |
| Post-lab restore | OK (`POST_LAB_RESTORE_OK`) | — |

Workers activated: Schedule, Media|File, Security (AV/sandbox/YARA/Judge), Notify, Message, Monitor, Qwen (Ollama qwen2.5:7b), Zalo.

## §15 Case index — consistent results (both rounds)

| Script | Result | Notes |
|--------|--------|-------|
| Units 15–16, 22–23, 29, 32, 34–37, soul, zalo-store, qwen-par | PASS | |
| `grafana_pairing_unit.py` | FAIL | Expected on Omni-only lab (9router not in HEALTH_TARGETS) |
| `defaults_profile_unit.py` | FAIL | Profile/classify.json assertion |
| `workflow_cadence_unit.py` | FAIL | Offline LLM classify dependency |
| `vps_health_check.py` | PASS | |
| `qwen_combo_preflight.py` (38) | PASS | Ollama combos filled |
| `zalo_tn_greeting_inject.py` (32) | FAIL | `NO_ADMIN_USER name=Tn` — preserve had corrupted admin files (credentials copied as allowlist); fix in post-lab-restore |
| `zalo_latency_lab.py` (17) | FAIL | p50 > 5s SLO on CPU Ollama |
| `zalo_special_four_lab.py` (25) | FAIL | HTTP error (needs Tn admin + LLM) |
| `zalo_weather_fuel_lab.py` (26) | FAIL | classify/plan |
| `file_pipeline_security_lab.py` (19) | PASS | |
| `grafana_integration_lab.py` (20) | SKIP/PASS | Grafana off |
| `defaults_routers_lab.py` (21) | FAIL | 9router unreachable (Omni-only default) |
| `zalo_tn_qwen_parallel_sizing.py` | PASS | |
| `zalo_tn_history_regression.py` | FAIL | `NO_ADMIN_USER` |

**Fails per round:** 9 (same set).

## Post-lab

- `POST_LAB_RESTORE_OK` — bridge, zalo-api, model-router, case 38 preflight.
- Admin allowlist re-seed from postgres added to `post-lab-restore.sh` for next run.

## Source fixes still open

1. Admin backup must not copy `credentials.json` into allowlist files (fixed in lab script + post-lab-restore).
2. `defaults_profile_unit` / `workflow_cadence_unit` — update or mock for Omni-only + offline.
3. Zalo real-case scripts need valid `uid|Tn` admin after fresh restore.
4. Latency SLO (17) — CPU Ollama may need longer SLO or GPU for lab host.
