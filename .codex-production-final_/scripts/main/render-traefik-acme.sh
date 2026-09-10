#!/usr/bin/env bash
# Render Traefik ACME dynamic config from template (UTF-8 domain safe).
# Called by run.sh when TRAEFIK_ACME_ENABLED=active.
set -euo pipefail
export LC_ALL="${LC_ALL:-C.UTF-8}"
export LANG="${LANG:-C.UTF-8}"

ROOT="${STACK_ROOT:-$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)}"
TEMPLATE="${ROOT}/architect/edge/traefik/dynamic/hermes.tls.yml.template"
OUT_DIR="${ROOT}/architect/edge/traefik/dynamic-acme"
OUT="${OUT_DIR}/hermes.yml"
DOMAIN="${TRAEFIK_ACME_DOMAIN:-}"

if [[ -z "$DOMAIN" || "$DOMAIN" == "CHANGE_ME_DOMAIN" ]]; then
  echo "ERROR: set TRAEFIK_ACME_DOMAIN in .env for Let's Encrypt" >&2
  exit 1
fi
if [[ -z "${TRAEFIK_ACME_EMAIL:-}" || "${TRAEFIK_ACME_EMAIL}" == change-me@* ]]; then
  echo "ERROR: set TRAEFIK_ACME_EMAIL in .env for Let's Encrypt" >&2
  exit 1
fi

mkdir -p "$OUT_DIR"
# Replace placeholder only (domain may contain UTF-8 IDN — keep as given)
# Prefer python for safe replace across CRLF/LF
python3 - <<PY
from pathlib import Path
tpl = Path(r"""${TEMPLATE}""").read_text(encoding="utf-8")
domain = """${DOMAIN}"""
out = tpl.replace("CHANGE_ME_DOMAIN", domain)
Path(r"""${OUT}""").write_text(out, encoding="utf-8", newline="\n")
print(f"OK: wrote {Path(r'''${OUT}''')} for Host({domain})")
PY
