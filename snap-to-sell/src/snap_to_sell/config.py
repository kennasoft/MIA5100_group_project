"""Central config. All knobs read from environment variables so you never edit code
to switch providers or thresholds. See .env.example.

Values are read at import; call ``refresh()`` after changing ``os.environ`` at runtime
(e.g. from a notebook Configuration cell) to re-read them."""
import os

# Open Food Facts asks for a descriptive User-Agent (app name + contact). Override with SNAP_USER_AGENT.
USER_AGENT = os.getenv("SNAP_USER_AGENT", "snap-to-sell/0.1 (MIA5100 project)")

# ---- open data endpoints (free, static) ----
# Open Food Facts (food) + Open Products Facts (non-food: household, electronics, etc.).
# NOTE: the legacy cgi/search.pl Perl search is deprecated (HTTP 503); OFF search now uses the
# Search-a-licious service. Barcode product lookups (/api/v2/product) are unaffected.
OFF_SEARCH_SALICIOUS = "https://search.openfoodfacts.org/search"   # current OFF search API
OFF_PRODUCT_URL = "https://world.openfoodfacts.org/api/v2/product/{code}.json"
OPF_SEARCH_URL = "https://world.openproductsfacts.org/cgi/search.pl"  # legacy (best-effort)
OPF_PRODUCT_URL = "https://world.openproductsfacts.org/api/v2/product/{code}.json"
OPEN_PRICES_URL = "https://prices.openfoodfacts.org/api/v1/prices"


def _f(name, default):
    try:
        return float(os.getenv(name, default))
    except ValueError:
        return float(default)


def _truthy(name):
    return os.getenv(name, "").strip().lower() in {"1", "true", "yes"}


def refresh():
    """Re-read all env-derived settings into module globals. Call after editing os.environ."""
    global CONFIDENCE_THRESHOLD, IMAGE_MATCH_THRESHOLD, STRICT_PROVIDER, ALWAYS_SWAP
    global CURRENCY, HTTP_TIMEOUT, LLM_PROVIDER
    global ANTHROPIC_API_KEY, GEMINI_API_KEY, OPENAI_API_KEY
    global ANTHROPIC_MODEL, GEMINI_MODEL, OPENAI_MODEL

    CONFIDENCE_THRESHOLD = _f("SNAP_CONFIDENCE_THRESHOLD", "0.5")     # below -> route to review
    IMAGE_MATCH_THRESHOLD = _f("SNAP_IMAGE_MATCH_THRESHOLD", "0.80")  # adopt catalogue image if >=
    # Provider-only mode: recognition never uses the offline sidecar, so a wrong result proves
    # the hosted model failed (confirms real inference is running).
    STRICT_PROVIDER = _truthy("SNAP_STRICT_PROVIDER")
    # Demo override: adopt the retrieved catalogue image without requiring the same-SKU match.
    ALWAYS_SWAP = _truthy("SNAP_ALWAYS_SWAP")
    CURRENCY = os.getenv("SNAP_CURRENCY", "CAD")
    HTTP_TIMEOUT = _f("SNAP_HTTP_TIMEOUT", "10")

    # hosted multimodal provider (recognition + generation)
    # SNAP_LLM_PROVIDER = "openai" | "anthropic" | "gemini" | "" (empty -> auto-detect, else offline)
    LLM_PROVIDER = os.getenv("SNAP_LLM_PROVIDER", "").lower().strip()
    ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
    GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
    ANTHROPIC_MODEL = os.getenv("SNAP_ANTHROPIC_MODEL", "claude-haiku-4-5-20251001")
    GEMINI_MODEL = os.getenv("SNAP_GEMINI_MODEL", "gemini-2.5-flash")
    OPENAI_MODEL = os.getenv("SNAP_OPENAI_MODEL", "gpt-4o-mini")


refresh()  # initial load at import


def active_provider() -> str:
    """Which hosted provider to use, or '' for offline. Honours SNAP_LLM_PROVIDER,
    else auto-detects whichever API key is present (OpenAI preferred)."""
    if LLM_PROVIDER == "openai" and OPENAI_API_KEY:
        return "openai"
    if LLM_PROVIDER == "anthropic" and ANTHROPIC_API_KEY:
        return "anthropic"
    if LLM_PROVIDER == "gemini" and GEMINI_API_KEY:
        return "gemini"
    if not LLM_PROVIDER:
        if OPENAI_API_KEY:
            return "openai"
        if ANTHROPIC_API_KEY:
            return "anthropic"
        if GEMINI_API_KEY:
            return "gemini"
    return ""
