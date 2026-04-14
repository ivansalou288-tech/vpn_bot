import os


def _env(name: str, default: str) -> str:
    v = os.getenv(name)
    if v is None:
        return default
    v = str(v).strip()
    return v if v else default


# Domain where 3x-ui panel is reachable (used by public API server too)
PANEL_DOMAIN ="www.ezh-dev.ru"
PUBLIC_DOMAIN = "panel.ezh-dev.ru"
# Optional "location" / prefix path in 3x-ui panel URL (e.g. fHvt2YpAP8)
PANEL_PATH = "CJ7iS9lelb"
SUB_PAGE_PATH = "DmJx9ZO1Or"
# Scheme and ports for your FastAPI subscription service (not the 3x-ui panel)
SUBSCRIPTION_API_SCHEME = "https"
SUBSCRIPTION_API_HOST = PUBLIC_DOMAIN
SUBSCRIPTION_API_HTTPS_PORT = 2500
SUBSCRIPTION_API_HTTP_PORT = 2501

# Base URL to talk to 3x-ui panel API
PANEL_SCHEME = "https"
PANEL_BASE_URL = f"{PANEL_SCHEME}://{PANEL_DOMAIN}/{PANEL_PATH}"

# Public base URL used in user-facing links (subscriptions, landing pages, etc.)
PUBLIC_DOMAIN = "panel.ezh-dev.ru"
PUBLIC_SCHEME = "https"
PUBLIC_BASE_URL = f"{PUBLIC_SCHEME}://{PUBLIC_DOMAIN}"


def subscription_api_base_url() -> str:
    port = SUBSCRIPTION_API_HTTPS_PORT
    default_port = 443 if SUBSCRIPTION_API_SCHEME == "https" else 80
    if port == default_port:
        return f"{SUBSCRIPTION_API_SCHEME}://{SUBSCRIPTION_API_HOST}"
    return f"{SUBSCRIPTION_API_SCHEME}://{SUBSCRIPTION_API_HOST}:{port}"


def webhook_url() -> str:
    return f"{subscription_api_base_url()}/payment/webhook"

