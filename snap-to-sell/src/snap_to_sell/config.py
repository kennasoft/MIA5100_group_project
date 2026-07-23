"""Central config. All knobs read from environment variables so you never edit code
to switch providers or thresholds. See .env.example.

Values are read at import; call ``refresh()`` after changing ``os.environ`` at runtime
(e.g. from a notebook Configuration cell) to re-read them.

The nearest ``.env`` is loaded automatically so running a notebook, the app, or the eval
harness from inside the repo picks up your keys with no manual paste. It uses python-dotenv
when available and otherwise falls back to a tiny built-in parser, so ``.env`` is read even
if python-dotenv is not installed. Variables already exported in the real shell always win —
``.env`` never clobbers them."""
import os
from pathlib import Path


def _parse_env_file(path):
    """Minimal .env parser used when python-dotenv is not installed. Handles KEY=VALUE lines,
    comments, blank lines, an optional leading ``export``, and single/double quoted values."""
    data = {}
    for raw in path.read_text().splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[len("export "):]
        if "=" not in line:
            continue
        key, _, val = line.partition("=")
        key, val = key.strip(), val.strip()
        if not key:
            continue
        if val[:1] in ("'", '"'):                       # quoted: take up to the closing quote
            end = val.find(val[0], 1)
            val = val[1:end] if end != -1 else val[1:]
        else:                                            # unquoted: strip a trailing inline comment
            val = val.split(" #", 1)[0].strip()
        data[key] = val
    return data


def _load_dotenv():
    """Load the nearest .env into os.environ without overriding vars already set in the shell.
    Anchored to the repo root (this file is snap-to-sell/src/snap_to_sell/config.py, so the root
    is parents[2]) so it works regardless of the current working directory. No-op if no .env
    exists. Works with or without python-dotenv installed."""
    for _base in (Path(__file__).resolve().parents[2], Path.cwd()):
        _env = _base / ".env"
        if not _env.is_file():
            continue
        try:
            from dotenv import load_dotenv
            load_dotenv(_env, override=False)   # don't clobber real shell env
        except Exception:
            # python-dotenv missing (or failed) -> built-in fallback, same non-clobbering rule.
            try:
                for _k, _v in _parse_env_file(_env).items():
                    os.environ.setdefault(_k, _v)
            except Exception:
                pass
        return  # first .env found wins


_load_dotenv()

# Open Food Facts asks for a descriptive User-Agent (app name + contact). Override with SNAP_USER_AGENT.
USER_AGENT = os.getenv("SNAP_USER_AGENT", "snap-to-sell/0.1 (MIA5100 project)")

# Shopping-backend retailer preference: reputable retailers get a ranking bonus; resale/marketplace
# sites (inconsistent listings/images) get a penalty. Override via SNAP_PREFERRED_SOURCES /
# SNAP_DEMOTED_SOURCES (comma-separated, matched as case-insensitive substrings of the source name).
_DEFAULT_PREFERRED = ("amazon,walmart,best buy,costco,target,staples,canadian tire,home depot,"
                      "lowe's,lowes,ikea,newegg,shoppers drug mart,loblaws,real canadian superstore,"
                      "no frills,metro,sobeys,london drugs,rexall,giant tiger,dollarama,indigo,apple")
_DEFAULT_DEMOTED = ("ebay,kijiji,poshmark,etsy,aliexpress,wish,mercari,facebook,depop,temu,alibaba,"
                    "dhgate,vinted,offerup,letgo")

# ---- open data endpoints (free, static) ----
# Open Food Facts (food) + Open Products Facts (non-food: household, electronics, etc.).
# NOTE: the legacy cgi/search.pl Perl search is deprecated (HTTP 503); OFF search now uses the
# Search-a-licious service. Barcode product lookups (/api/v2/product) are unaffected.
OFF_SEARCH_SALICIOUS = "https://search.openfoodfacts.org/search"   # current OFF search API
OFF_PRODUCT_URL = "https://world.openfoodfacts.org/api/v2/product/{code}.json"
OPF_SEARCH_URL = "https://world.openproductsfacts.org/cgi/search.pl"  # legacy (best-effort)
OPF_PRODUCT_URL = "https://world.openproductsfacts.org/api/v2/product/{code}.json"
OPEN_PRICES_URL = "https://prices.openfoodfacts.org/api/v1/prices"
SERPER_SHOPPING_URL = "https://google.serper.dev/shopping"  # Serper.dev Google Shopping
SERPER_SEARCH_URL = "https://google.serper.dev/search"      # Serper.dev web search (barcode -> name)
ECOMSOURCE_URL = "https://api.ecomsource.ai/api/v1"  # needs SNAP_ECOMSOURCE_ACCESS_KEY + _SECRET_KEY


def _f(name, default):
    try:
        return float(os.getenv(name, default))
    except ValueError:
        return float(default)


def _truthy(name):
    return os.getenv(name, "").strip().lower() in {"1", "true", "yes"}


def refresh():
    """Re-read all env-derived settings into module globals. Call after editing os.environ.
    Reloads .env first (without overriding anything already set) so a fresh key in .env is picked
    up on re-read, while notebook os.environ overrides still win."""
    _load_dotenv()
    global CONFIDENCE_THRESHOLD, IMAGE_MATCH_THRESHOLD, STRICT_PROVIDER, ALWAYS_SWAP, IMAGE_MODE, LOG_ENABLED
    global CURRENCY, HTTP_TIMEOUT, LLM_PROVIDER, RETRIEVE_BACKEND, SERPER_API_KEY, SHOPPING_GL
    global BARCODE_SOURCE
    global PREFERRED_SOURCES, DEMOTED_SOURCES, PREFERRED_CURRENCIES
    global ECOMSOURCE_ACCESS_KEY, ECOMSOURCE_SECRET_KEY
    global ANTHROPIC_API_KEY, GEMINI_API_KEY, OPENAI_API_KEY
    global ANTHROPIC_MODEL, GEMINI_MODEL, OPENAI_MODEL
    global IMAGE_MATCH_LLM, LLM_MATCH_MIN_CONF, LLM_MATCH_TOPK, PRICE_CONFIDENCE_GATE

    CONFIDENCE_THRESHOLD = _f("SNAP_CONFIDENCE_THRESHOLD", "0.5")     # below -> route to review
    IMAGE_MATCH_THRESHOLD = _f("SNAP_IMAGE_MATCH_THRESHOLD", "0.80")  # adopt catalogue image if >=
    # Same-SKU image verification via the vision LLM (compares the shelf photo with each candidate
    # catalogue image). On by default; falls back to the numeric CLIP/phash gate when offline.
    IMAGE_MATCH_LLM = os.getenv("SNAP_IMAGE_MATCH_LLM", "1").strip().lower() not in {"0", "false", "no", "off"}
    LLM_MATCH_MIN_CONF = _f("SNAP_LLM_MATCH_MIN_CONF", "0.7")  # adopt only if LLM confidence >= this
    try:
        LLM_MATCH_TOPK = max(1, int(os.getenv("SNAP_LLM_MATCH_TOPK", "2")))  # verify top-K candidates
    except ValueError:
        LLM_MATCH_TOPK = 2
    # Confidence gate: decline to price (route to review) when a shopping match is ambiguous or its
    # brand can't be confirmed, instead of publishing a wrong-product price. On by default.
    PRICE_CONFIDENCE_GATE = os.getenv("SNAP_PRICE_CONFIDENCE_GATE", "1").strip().lower() not in {"0", "false", "no", "off"}
    # Provider-only mode: recognition never uses the offline sidecar, so a wrong result proves
    # the hosted model failed (confirms real inference is running).
    STRICT_PROVIDER = _truthy("SNAP_STRICT_PROVIDER")
    # Demo override: adopt the retrieved catalogue image without requiring the same-SKU match.
    ALWAYS_SWAP = _truthy("SNAP_ALWAYS_SWAP")
    # Image strategy: "enhance" = clean the user's own photo (background removal) and only adopt an
    # external image if it's demonstrably better; "swap" = prefer the retrieved catalogue image;
    # "off" = keep the original photo.
    IMAGE_MODE = os.getenv("SNAP_IMAGE_MODE", "enhance").strip().lower()
    # Retrieval backend: "off" = Open Food Facts / Open Products Facts (free, no key);
    # "shopping" = Serper.dev Google Shopping (real retailer price + clean image; needs SERPER_API_KEY).
    RETRIEVE_BACKEND = os.getenv("SNAP_RETRIEVE_BACKEND", "off").strip().lower()
    # Barcode-detail source after OFF/OPF: "websearch" (Serper web search + LLM name extraction —
    # reuses the Serper key, cheap) | "ecomsource" (EcomSource API) | "none".
    BARCODE_SOURCE = os.getenv("SNAP_BARCODE_SOURCE", "websearch").strip().lower()
    SERPER_API_KEY = os.getenv("SERPER_API_KEY", "")
    SHOPPING_GL = os.getenv("SNAP_SHOPPING_GL", "ca")  # region for Google Shopping prices
    PREFERRED_SOURCES = [s.strip().lower() for s in
                         os.getenv("SNAP_PREFERRED_SOURCES", _DEFAULT_PREFERRED).split(",") if s.strip()]
    DEMOTED_SOURCES = [s.strip().lower() for s in
                       os.getenv("SNAP_DEMOTED_SOURCES", _DEFAULT_DEMOTED).split(",") if s.strip()]
    ECOMSOURCE_ACCESS_KEY = os.getenv("SNAP_ECOMSOURCE_ACCESS_KEY", "")
    ECOMSOURCE_SECRET_KEY = os.getenv("SNAP_ECOMSOURCE_SECRET_KEY", "")
    # Local-first: prefer prices already in these currencies; others (EUR/AUD/…) are penalised.
    PREFERRED_CURRENCIES = [c.strip().upper() for c in
                            os.getenv("SNAP_PREFERRED_CURRENCIES", "CAD,USD").split(",") if c.strip()]
    CURRENCY = os.getenv("SNAP_CURRENCY", "CAD")
    HTTP_TIMEOUT = _f("SNAP_HTTP_TIMEOUT", "10")
    # Per-image trace log: write <image-name>-log.txt with every stage's output. On by default.
    LOG_ENABLED = os.getenv("SNAP_LOG", "1").strip().lower() in {"1", "true", "yes", "on"}

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
