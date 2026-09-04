"""Shared OpenBao KV key lists (seed, compose host fill, env scrub)."""
from __future__ import annotations

# Copied from .env → OpenBao on seed/update (non-empty, not CHANGE_ME).
SEED_KEYS = (
    "N9ROUTER_API_KEY",
    "N9ROUTER_INITIAL_PASSWORD",
    "OMNIROUTER_API_KEY",
    "OMNIROUTER_INITIAL_PASSWORD",
    "API_SERVER_KEY",
    "GATEWAY_API_KEYS",
    "TAVILY_API_KEY",
    "FIRECRAWL_API_KEY",
    "POLLINATIONS_API_KEY",
    "HERMES_DASHBOARD_PASSWORD",
    "HERMES_DASHBOARD_SECRET",
    "MEMORY_DB_PASSWORD",
    "ZALO_API_TOKEN",
    "ZALO_PLUGIN_TOKEN",
    "GRAFANA_ADMIN_PASSWORD",
    "TELEGRAM_BOT_TOKEN",
    "GEMINI_API_KEY",
    "DEEPSEEK_API_KEY",
)

# Retired keys — removed from KV on each seed/update.
OBSOLETE_SECRET_KEYS = (
    "FAL_KEY",
    "FLUXAI_API_KEY",
    "IMAGE_LLM_API_KEY",
    "IMAGE_VENDOR_API_KEY",
    "IMAGE_OMNI_MODEL",
    "IMAGE_GEN_SIZE",
    "IMAGE_ALLOW_PILLOW",
)

# Compose ${VAR:?} reads ROOT/.env at parse time — refill from KV when empty.
COMPOSE_HOST_KEYS = (
    "MEMORY_DB_PASSWORD",
    "HERMES_DASHBOARD_PASSWORD",
    "HERMES_DASHBOARD_SECRET",
    "API_SERVER_KEY",
    "OMNIROUTER_API_KEY",
    "OMNIROUTER_INITIAL_PASSWORD",
    "N9ROUTER_API_KEY",
    "N9ROUTER_INITIAL_PASSWORD",
    "GATEWAY_API_KEYS",
)

# Strip plaintext values from ROOT/.env after OpenBao seed (bootstrap token stays).
ENV_SCRUB_KEYS = SEED_KEYS + (
    "FAL_KEY",
    "FLUXAI_API_KEY",
    "POLLINATIONS_API_KEY",
)

OPENBAO_SECRET_PATH = "secret/data/assistant/api-keys"
