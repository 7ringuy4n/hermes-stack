#!/usr/bin/env bash
# Smoke-check High services (localhost). Run after: ASSISTANT_PROFILE=high bash run.sh up
set -euo pipefail

fail=0
check() {
  local name="$1" url="$2"
  if curl -fsS -m 8 "$url" >/dev/null 2>&1; then
    echo "OK  ${name}  ${url}"
  else
    echo "FAIL ${name}  ${url}"
    fail=1
  fi
}

echo "ASSISTANT_PROFILE=${ASSISTANT_PROFILE:-unset}"
check openbao   "http://127.0.0.1:${OPENBAO_PORT:-8200}/v1/sys/health"
check grafana   "http://127.0.0.1:${GRAFANA_HOST_PORT:-23000}/api/health"
check security  "http://127.0.0.1:${SECURITY_PORT:-8093}/health"
check authz     "http://127.0.0.1:${AUTHZ_PORT:-8097}/health"
if [[ "${ENABLE_ZALO:-0}" == "1" ]]; then
  check zalo-api "http://127.0.0.1:${ZALO_API_PORT:-${ADMIN_API_PORT:-8100}}/health"
else
  echo "INFO zalo-api skipped (ENABLE_ZALO=0)"
fi
check siem      "http://127.0.0.1:${SIEM_PORT:-8105}/health"
check policy    "http://127.0.0.1:${POLICY_PORT:-8106}/health"

if [[ "${ENABLE_ANTIVIRUS:-0}" == "1" ]]; then
  check av "http://127.0.0.1:${AV_GATEWAY_PORT:-8098}/health"
else
  echo "INFO antivirus disabled (ENABLE_ANTIVIRUS=0)"
fi
echo "INFO sandbox=${SECURITY_SANDBOX:-0} llm_judge=${SECURITY_LLM_JUDGE:-0} (defaults off; not a security boundary)"

if [[ "${ENABLE_NOTIFY:-0}" == "1" ]]; then
  check notify "http://127.0.0.1:${NOTIFY_PORT:-8092}/health"
else
  echo "INFO notify disabled (ENABLE_NOTIFY=0)"
fi

if [[ "$fail" -ne 0 ]]; then
  echo "High smoke failed — check: bash run.sh ps"
  exit 1
fi
echo "OK: High smoke passed"
