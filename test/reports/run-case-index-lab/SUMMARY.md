# Case index lab — 2026-09-06T20:55:11.722322+07:00

| kind | case | script | result | tail |
|------|------|--------|--------|------|
| vps | 39 | zalo_tn_visual_weather_pdf_inject.py | PASS | `2026-09-06 20:32:29,532 WARNING tools.registry: check_fn _check_kanban_mode returned False; dependent tools will be unav` |
| vps | 17 | zalo_latency_lab.py | PASS | `[sudo: authenticate] Password:

RESULT:{"status":"SKIP","reason":"no_api_server_key"}


[2026-09-06 20:36:13 +0700] lat` |
| vps | 25 | zalo_special_four_lab.py | FAIL(1) | `PLAN_HINT normal PLAN_N 5 CADENCE once


CREATE_DONE



FAIL classify did not persist 4 instructions` |
| vps | 26 | zalo_weather_fuel_lab.py | FAIL(1) | `
CLASSIFY_NOW HINT normal PLAN_N 3 OK True


CLASSIFY_DAILY HINT unknown PLAN_N 0 CRON None CADENCE None


BAD_NOW_PLAN` |
| vps | 19 | file_pipeline_security_lab.py | PASS | `
VISION_ROUTE_HEALTH=up


[2026-09-06 20:38:14 +0700] probe | RECORD | PROBE sm-clean code=200 body={"verdict":"CLEAN","` |
| vps | 20 | grafana_integration_lab.py | PASS | `
ZALO=1


SKIP_GRAFANA_OFF


[2026-09-06 20:38:16 +0700] grafana | SKIP | ENABLE_GRAFANA/PROMETHEUS off` |
| vps | 21 | defaults_routers_lab.py | PASS | `DEFAULTS_LAB_DONE


[2026-09-06 20:38:18 +0700] router_worker | PASS | connected
[2026-09-06 20:38:18 +0700] omni_match ` |
| vps | history | zalo_tn_history_regression.py | PASS | `INJECT 200 multilang hist-multilang-1788702154


PASS_HIST multilang



PASS_HIST_ALL` |
| vps | yt-refuse | zalo_tn_youtube_refuse_inject.py | FAIL(1) | `
INJECT_OK


REFUSE=0 NEWIMG=0


VERDICT FAIL no_refuse_evidence` |
| vps | remaining | zalo_tn_remaining_suite_lab.py | FAIL(1) | `
VERDICT FAIL


{"checks": [{"name": "image_gen_file", "ok": true, "detail": "size=1697027 delivered=True vision=A tabby` |
| vps | env-clean | env_obsolete_cleanup_lab.py | PASS | `VERDICT PASS


OK: removed 2 obsolete key(s) from /opt/assistant/.env: ADMIN_API_TOKEN, WEB_BACKENDS
ROOT_HAS_ADMIN Fals` |
| vps | archive | zalo_tn_archive_extract_lab.py | PASS | `## blank.docx
(empty)
PASS extract_3.zip media=2 chars=244 head=## img.png
A minimalist white image with two centered li` |

**Fails:** 4
