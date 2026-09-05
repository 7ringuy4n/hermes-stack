"""Shared OpenBao KV key lists (seed, compose host fill, env scrub)."""
from __future__ import annotations

# Copied from .env → OpenBao on seed/update (non-empty, not CHANGE_ME).
SEED_KEYS = (
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
    "DEEPSEEK_OCR_API_KEY",
    "EMBED_API_KEY",
    "OCR_API_KEY",
    "LLM_JUDGE_KEY",
    "GOOGLE_API_KEY",
    "OPENAI_API_KEY",
    "ANTHROPIC_API_KEY",
    "XAI_API_KEY",
    "QWEN_API_KEY",
    "ALIBABA_API_KEY",
    "DASHSCOPE_API_KEY",
)

# Retired secrets — removed from OpenBao KV on each seed/update.
OBSOLETE_SECRET_KEYS = (
    "N9ROUTER_API_KEY",
    "N9ROUTER_INITIAL_PASSWORD",
    "FAL_KEY",
    "FLUXAI_API_KEY",
    "IMAGE_LLM_API_KEY",
    "IMAGE_VENDOR_API_KEY",
    "IMAGE_OMNI_MODEL",
    "IMAGE_GEN_SIZE",
    "IMAGE_ALLOW_PILLOW",
    "ADMIN_API_TOKEN",  # legacy alias; Zalo uses ZALO_API_TOKEN / OpenBao
    "MEM0_API_KEY",
)

# Retired host .env pins (secret or not) — delete entire KEY= lines on scrub/load.
# Keep ENABLE_*/WORKER_* install flags; those are still written by run.sh install.
OBSOLETE_ENV_KEYS = OBSOLETE_SECRET_KEYS + (
    "ENABLE_9ROUTER",
    "N9ROUTER_BASE_URL",
    "N9ROUTER_HOST_PORT",
    "N9ROUTER_IMAGE",
    "N9ROUTER_DEFAULT_COMBO",
    "N9ROUTER_COMBO_STRATEGY",
    "N9ROUTER_COMBO_STICKY_LIMIT",
    "N9ROUTER_IMAGE_COMBO",
    "N9ROUTER_VISION_COMBO",
    "N9ROUTER_EMBED_COMBO",
    "ROUTER_WORKER_URL",
    "WHISPER_ENABLED",
    "WHISPER_MODEL",
    "WHISPER_CACHE_DIR",
    "WEB_BACKENDS",  # Omni combo web-search only
    "WEB_SEARCH_COMBO_PATH",
    "WEB_EXTRACT_BACKENDS",
    "OMNIROUTER_SEARCH_PROVIDERS",
    "IMAGE_OMNI_MODEL",
    "OMNIROUTER_IMAGE_MODEL",
    "IMAGE_GEN_HEAD_MODEL",
    "IMAGE_LLM_MODEL",
    "IMAGE_LLM_SIZE",
    "IMAGE_LLM_PROVIDER",
    "IMAGE_LLM_BASE_URL",
    "IMAGE_VENDOR_PROVIDER",
    "IMAGE_VENDOR_URL",
    "IMAGE_VENDOR_MODEL",
    "OLLAMA_HOST",
    "QWEN_MODEL",
    "ENABLE_QWEN",
)

# Compose ${VAR:?} reads ROOT/.env at parse time — refill from KV when empty.
COMPOSE_HOST_KEYS = (
    "MEMORY_DB_PASSWORD",
    "HERMES_DASHBOARD_PASSWORD",
    "HERMES_DASHBOARD_SECRET",
    "API_SERVER_KEY",
    "OMNIROUTER_API_KEY",
    "OMNIROUTER_INITIAL_PASSWORD",
    "GATEWAY_API_KEYS",
)

# Strip plaintext values from ROOT/.env after OpenBao seed (bootstrap token stays).
ENV_SCRUB_KEYS = SEED_KEYS + (
    "FAL_KEY",
    "FLUXAI_API_KEY",
    "POLLINATIONS_API_KEY",
)

OPENBAO_SECRET_PATH = "secret/data/assistant/api-keys"


def is_secret_env_name(name: str) -> bool:
    """Recognize credential-bearing env names without maintaining a vendor list."""
    key = str(name or "").strip().upper()
    if not key or key == "OPENBAO_DEV_ROOT_TOKEN":
        return False
    return key.endswith(
        (
            "_API_KEY",
            "_API_KEYS",
            "_TOKEN",
            "_PASSWORD",
            "_SECRET",
            "_CREDENTIAL",
            "_CREDENTIALS",
        )
    ) or key in {"API_SERVER_KEY", "GATEWAY_API_KEYS"}
