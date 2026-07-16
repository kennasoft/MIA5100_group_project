"""
demo_app.py — Snap-to-Sell Class Demo
═══════════════════════════════════════════════════════════════════════════════
Run from the snap-to-sell project root:
    streamlit run demo_app.py

Requires:
    src/snap_to_sell/providers.py  (vlm_identify, draft_listing, search_price)
    src/snap_to_sell/config.py
    pip install imagehash requests opencv-python numpy

Optional (uses full pipeline if present):
    src/snap_to_sell/pipeline.py   (run)

NEW IN THIS VERSION
    - Background-removed / cleaned product image via OpenCV GrabCut
      (no rembg/onnxruntime/numba — avoids the llvmlite build issues
      those pull in on some machines)
    - Canonical "cleaner" image lookup against Open Food Facts, with a
      perceptual-hash same-SKU similarity check before ever swapping the
      user's photo for a catalogue one
═══════════════════════════════════════════════════════════════════════════════
"""
import sys, os, io, base64, json, textwrap, time
from pathlib import Path
import streamlit as st
import requests
import numpy as np
import cv2
from PIL import Image

try:
    import imagehash
except ImportError:
    imagehash = None

# ── Resolve project root so imports work whether you run from root or subfolder
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

# ─────────────────────────────────────────────────────────────────────────────
# Page config (must be first Streamlit call)
# ─────────────────────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Snap to Sell — Demo",
    page_icon="📸",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ─────────────────────────────────────────────────────────────────────────────
# Styles
# ─────────────────────────────────────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@500;600;700&family=Inter:wght@400;500&display=swap');

html, body, [class*="css"] { font-family:'Inter',sans-serif; background:#0D1117; color:#E6EDF3; }

/* ── header ── */
.demo-header { padding:1.6rem 0 0.4rem; }
.demo-title  { font-family:'Space Grotesk',sans-serif; font-size:2.2rem; font-weight:700;
               letter-spacing:-.03em; color:#fff; margin:0; }
.demo-title span { color:#F5A623; }
.demo-sub    { font-size:.9rem; color:#8B949E; margin:.3rem 0 0; }

/* ── section label ── */
.sec-label { font-family:'Space Grotesk',sans-serif; font-size:.68rem; font-weight:600;
             letter-spacing:.14em; text-transform:uppercase; color:#F5A623; margin-bottom:.5rem; }

/* ── listing card ── */
.card { background:#161B22; border:1px solid #30363D; border-radius:14px;
        padding:1.5rem 1.6rem; margin-top:.6rem; }
.card-title { font-family:'Space Grotesk',sans-serif; font-size:1.3rem; font-weight:700;
              color:#fff; margin:0 0 .8rem; line-height:1.3; }
.card-desc  { font-size:.9rem; color:#C9D1D9; line-height:1.65; margin-bottom:1rem; }
.card-price { font-family:'Space Grotesk',sans-serif; font-size:2rem; font-weight:700; color:#F5A623; }
.card-price-label { font-size:.75rem; color:#6E7681; margin-left:.3rem; }

/* ── meta grid ── */
.meta-grid { display:flex; flex-wrap:wrap; gap:1.2rem; margin:.9rem 0; }
.meta-item { display:flex; flex-direction:column; gap:.1rem; }
.meta-key  { font-size:.68rem; color:#6E7681; text-transform:uppercase;
             letter-spacing:.09em; font-weight:600; }
.meta-val  { font-size:.88rem; color:#E6EDF3; font-weight:600;
             font-family:'Space Grotesk',sans-serif; }

/* ── tag pills ── */
.tags { display:flex; flex-wrap:wrap; gap:.35rem; margin-top:.8rem; }
.tag  { background:#21262D; border:1px solid #30363D; border-radius:20px;
        padding:.2rem .65rem; font-size:.76rem; color:#8B949E; font-weight:500; }

/* ── recognition panel ── */
.recog-panel { background:#0D1117; border:1px solid #21262D; border-radius:10px;
               padding:1rem 1.1rem; font-size:.83rem; color:#8B949E; line-height:1.7; }
.recog-panel b { color:#E6EDF3; font-weight:600; }

/* ── confidence bar ── */
.conf-track { background:#21262D; border-radius:20px; height:6px;
              width:100%; margin:.3rem 0 .6rem; }
.conf-fill  { background:#F5A623; border-radius:20px; height:6px; }

/* ── status badge ── */
.badge { display:inline-block; font-size:.72rem; font-weight:700; padding:.2rem .7rem;
         border-radius:20px; margin-bottom:.6rem; }
.badge-ok   { background:#0f3a1f; color:#3fb950; }
.badge-warn { background:#3d2100; color:#e3b341; }
.badge-err  { background:#3a0f0f; color:#f85149; }

/* ── source note ── */
.source-note { background:#21262D; border-left:3px solid #F5A623; border-radius:0 6px 6px 0;
               padding:.55rem .8rem; font-size:.8rem; color:#8B949E; margin-top:.9rem; }

/* ── divider ── */
hr.card-div { border:none; border-top:1px solid #21262D; margin:.9rem 0; }

/* ── Streamlit overrides ── */
.stButton>button { background:#F5A623!important; color:#0D1117!important;
                   font-family:'Space Grotesk',sans-serif!important; font-weight:700!important;
                   font-size:.95rem!important; border:none!important; border-radius:8px!important;
                   padding:.55rem 1.4rem!important; width:100%!important; }
.stButton>button:hover { opacity:.85!important; }
[data-testid="stSidebar"] { background:#0D1117!important;
                             border-right:1px solid #21262D!important; }
div[data-testid="stTextInput"] input,
div[data-testid="stSelectbox"] > div { background:#161B22!important;
                                        border:1px solid #30363D!important;
                                        color:#E6EDF3!important; border-radius:8px!important; }
footer,#MainMenu { visibility:hidden; }
</style>
""", unsafe_allow_html=True)

# ─────────────────────────────────────────────────────────────────────────────
# Sidebar — settings
# ─────────────────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("### ⚙️ Settings")

    provider = st.selectbox("LLM provider",
                            ["openai", "anthropic", "gemini"],
                            index=0)

    if provider == "openai":
        api_key   = st.text_input("OpenAI API key", type="password", placeholder="sk-...")
        llm_model = st.selectbox("Vision model", ["gpt-4o-mini", "gpt-4o"], index=0)
    elif provider == "anthropic":
        api_key   = st.text_input("Anthropic API key", type="password", placeholder="sk-ant-...")
        llm_model = st.selectbox("Vision model",
                                 ["claude-haiku-4-5-20251001", "claude-sonnet-4-6"], index=0)
    else:
        api_key   = st.text_input("Gemini API key", type="password", placeholder="AIza...")
        llm_model = st.selectbox("Vision model",
                                 ["gemini-2.5-flash", "gemini-2.0-flash"], index=0)

    st.markdown("---")
    retrieve_backend = st.selectbox(
        "Price retrieval backend",
        ["openai_search", "off", "shopping"],
        index=0,
        help=(
            "openai_search → live web search via OpenAI Responses API\n"
            "off → Open Food Facts catalogue (food only, free)\n"
            "shopping → Serper.dev Google Shopping (needs SERPER_API_KEY)"
        ),
    )

    if retrieve_backend == "openai_search":
        search_model = st.selectbox(
            "Search model",
            ["gpt-4o-mini-search-preview", "gpt-4o-search-preview"],
            index=0,
        )
        openai_key_for_search = api_key if provider == "openai" else st.text_input(
            "OpenAI key (for search)", type="password", placeholder="sk-..."
        )
    elif retrieve_backend == "shopping":
        serper_key = st.text_input("Serper API key", type="password", placeholder="...")
    else:
        search_model = ""

    st.markdown("---")
    currency = st.selectbox("Currency", ["CAD", "USD"], index=0)

    st.markdown("---")
    enable_image_upgrade = st.checkbox("🖼️ Try to clean / find better product image", value=True)
    similarity_threshold = st.slider(
        "Same-SKU similarity threshold", 0.0, 1.0, 0.55, 0.05,
        help="Minimum image similarity required before swapping in a catalogue photo. "
             "Below this, the app keeps your original (background-removed) photo instead."
    )

    st.caption("MIA 5100 — Snap-to-Sell demo")

# ─────────────────────────────────────────────────────────────────────────────
# Set env vars from sidebar (providers.py + config.py read from os.environ)
# ─────────────────────────────────────────────────────────────────────────────
def apply_env():
    os.environ["SNAP_LLM_PROVIDER"]   = provider
    os.environ["SNAP_CURRENCY"]       = currency
    os.environ["SNAP_RETRIEVE_BACKEND"] = retrieve_backend

    if provider == "openai":
        os.environ["OPENAI_API_KEY"]  = api_key
        os.environ["SNAP_OPENAI_MODEL"] = llm_model
    elif provider == "anthropic":
        os.environ["ANTHROPIC_API_KEY"] = api_key
        os.environ["SNAP_ANTHROPIC_MODEL"] = llm_model
    else:
        os.environ["GEMINI_API_KEY"]  = api_key
        os.environ["SNAP_GEMINI_MODEL"] = llm_model

    if retrieve_backend == "openai_search":
        os.environ["SNAP_OPENAI_SEARCH_MODEL"] = search_model
        key = openai_key_for_search if provider != "openai" else api_key
        if key:
            os.environ["OPENAI_API_KEY"] = key
    elif retrieve_backend == "shopping" and serper_key:
        os.environ["SERPER_API_KEY"] = serper_key

    # refresh config module globals
    try:
        from snap_to_sell import config as cfg
        cfg.refresh()
    except ImportError:
        pass

# ─────────────────────────────────────────────────────────────────────────────
# Image cleanup / canonical-image lookup helpers  (NEW)
# ─────────────────────────────────────────────────────────────────────────────
def clean_product_image(pil_img: Image.Image) -> Image.Image:
    """
    Remove background using OpenCV GrabCut, composite onto white.
    Assumes the product is roughly centered in frame (true for most
    "hold item in front of camera" shelf/counter photos). Falls back
    to the original image untouched if anything goes wrong.
    """
    try:
        img_rgb = np.array(pil_img.convert("RGB"))
        img_bgr = cv2.cvtColor(img_rgb, cv2.COLOR_RGB2BGR)
        h, w = img_bgr.shape[:2]

        mask = np.zeros((h, w), np.uint8)
        bgd_model = np.zeros((1, 65), np.float64)
        fgd_model = np.zeros((1, 65), np.float64)

        # Rectangle covering the central ~90% of the frame — GrabCut treats
        # everything outside it as definite background to seed the cut.
        rect = (int(w * 0.05), int(h * 0.05), int(w * 0.9), int(h * 0.9))

        cv2.grabCut(img_bgr, mask, rect, bgd_model, fgd_model, 5, cv2.GC_INIT_WITH_RECT)
        fg_mask = np.where((mask == 2) | (mask == 0), 0, 1).astype("uint8")

        # If GrabCut collapsed to (near) nothing, bail out to the original
        # rather than returning an all-white image.
        if fg_mask.sum() < 0.02 * fg_mask.size:
            return pil_img

        white_bg = np.full_like(img_bgr, 255)
        composited = np.where(fg_mask[:, :, np.newaxis] == 1, img_bgr, white_bg)
        return Image.fromarray(cv2.cvtColor(composited, cv2.COLOR_BGR2RGB))
    except Exception:
        return pil_img


def image_similarity(original: Image.Image, candidate: Image.Image) -> float:
    """
    0-1 perceptual-hash similarity between two images — the same-SKU
    guardrail used before ever swapping in a catalogue photo.
    Returns 1.0 (treated as "identical, don't block") if imagehash
    isn't installed, so the app degrades gracefully rather than crashing.
    """
    if imagehash is None:
        return 1.0
    try:
        h1 = imagehash.phash(original.convert("RGB"))
        h2 = imagehash.phash(candidate.convert("RGB"))
        return 1 - (h1 - h2) / 64.0
    except Exception:
        return 0.0


def find_canonical_image(identity: dict) -> dict | None:
    """
    Search Open Food Facts by brand + product name (text search — no
    barcode required). Returns {"image_url": str, "product_name": str}
    for the first hit that has a product image, or None if nothing
    usable was found.
    """
    brand = (identity.get("brand") or "").strip()
    product = (identity.get("product") or "").strip()
    query = f"{brand} {product}".strip()
    if not query:
        return None

    try:
        resp = requests.get(
            "https://world.openfoodfacts.org/cgi/search.pl",
            params={
                "search_terms": query,
                "search_simple": 1,
                "action": "process",
                "json": 1,
                "page_size": 5,
            },
            timeout=6,
        )
        resp.raise_for_status()
        products = resp.json().get("products", [])
    except Exception:
        return None

    for p in products:
        img_url = p.get("image_front_url") or p.get("image_url")
        if img_url:
            return {"image_url": img_url, "product_name": p.get("product_name", query)}
    return None


def download_image(url: str) -> Image.Image | None:
    """Fetch a remote image and return it as a PIL Image, or None on failure."""
    try:
        resp = requests.get(url, timeout=6)
        resp.raise_for_status()
        return Image.open(io.BytesIO(resp.content)).convert("RGB")
    except Exception:
        return None


def upgrade_image(original: Image.Image, identity: dict, sim_threshold: float) -> dict:
    """
    Full image-upgrade step: try to find a canonical catalogue photo for
    the identified product; if found AND it passes the same-SKU similarity
    check, use it. Otherwise fall back to a background-removed version of
    the user's own photo. Always returns a dict with the fields the UI
    needs, never raises.
    """
    out = {
        "clean_image": None,
        "image_source": "",
        "image_similarity": None,
        "image_swap_rejected": False,
    }

    canonical = find_canonical_image(identity)
    if canonical:
        candidate_img = download_image(canonical["image_url"])
        if candidate_img is not None:
            sim = image_similarity(original, candidate_img)
            out["image_similarity"] = sim
            if sim >= sim_threshold:
                out["clean_image"] = candidate_img
                out["image_source"] = f"Open Food Facts match: {canonical['product_name']}"
                return out
            else:
                out["image_swap_rejected"] = True

    # Fallback: no catalogue match, download failed, or similarity too low
    out["clean_image"] = clean_product_image(original)
    out["image_source"] = "background-removed original (no catalogue match)"
    return out

# ─────────────────────────────────────────────────────────────────────────────
# Pipeline helpers
# ─────────────────────────────────────────────────────────────────────────────
def _save_image(pil_img: Image.Image) -> Path:
    """Save PIL image to a temp file, return path."""
    tmp = Path("/tmp/snap_demo_upload.jpg")
    rgb = pil_img.convert("RGB")
    rgb.save(tmp, format="JPEG", quality=92)
    return tmp


def run_pipeline(pil_img: Image.Image) -> dict:
    """
    Run recognition → retrieval → generation → (optional) image upgrade.

    Tries the full pipeline.run() first. Falls back to calling
    providers directly so the demo works even if some pipeline
    modules aren't present yet.

    Returns a flat dict with all display fields.
    """
    apply_env()
    img_path = str(_save_image(pil_img))

    # ── Try full pipeline ──────────────────────────────────────────────────
    try:
        from snap_to_sell.pipeline import run as pipeline_run
        validated = pipeline_run(img_path)
        result = _from_validated(validated)
    except ImportError:
        result = None  # pipeline not fully set up yet — use providers directly
    except Exception as e:
        st.warning(f"Full pipeline error ({e}) — falling back to direct provider calls.")
        result = None

    if result is None:
        result = _run_providers(img_path)

    # ── Image upgrade step (NEW) — runs regardless of pipeline vs fallback ──
    if enable_image_upgrade and result.get("identity"):
        try:
            upgrade = upgrade_image(pil_img, result["identity"], similarity_threshold)
            result.update(upgrade)
        except Exception as e:
            result["image_upgrade_warning"] = str(e)

    return result


def _run_providers(img_path: str) -> dict:
    """Direct provider calls when full pipeline isn't available."""
    from snap_to_sell import providers, config as cfg

    result = {"_mode": "providers"}

    # 1. Recognition
    try:
        identity = providers.vlm_identify(img_path)
        result["identity"] = identity
    except providers.NoProviderError:
        raise RuntimeError("No API key configured — add one in the sidebar.")
    except Exception as e:
        raise RuntimeError(f"Recognition failed: {e}")

    # 2. Price retrieval
    retrieved = {}
    if cfg.RETRIEVE_BACKEND == "openai_search":
        try:
            from snap_to_sell.retrieve_openai import retrieve_openai
            from snap_to_sell.interfaces import ProductIdentity
            ident_obj = ProductIdentity(**{k: identity.get(k, "") for k in
                        ["brand","product","variant","size","category","ocr_text",
                         "search_query","confidence","barcode"]})
            bundle = retrieve_openai(ident_obj)
            retrieved = {
                "canonical_name": bundle.canonical_name,
                "price_point": bundle.price.point,
                "price_low":   bundle.price.low,
                "price_high":  bundle.price.high,
                "currency":    bundle.price.currency,
                "basis":       bundle.price.basis,
                "tags":        bundle.category_tags,
            }
        except Exception as e:
            result["retrieval_warning"] = str(e)
    elif cfg.RETRIEVE_BACKEND == "off":
        try:
            from snap_to_sell.retrieve import retrieve
            from snap_to_sell.interfaces import ProductIdentity
            from dataclasses import asdict
            ident_obj = ProductIdentity(**{k: identity.get(k, "") for k in
                        ["brand","product","variant","size","category","ocr_text",
                         "search_query","confidence","barcode"]})
            bundle = retrieve(ident_obj)
            retrieved = asdict(bundle)
        except Exception as e:
            result["retrieval_warning"] = str(e)

    result["retrieved"] = retrieved

    # 3. Listing generation
    try:
        listing = providers.draft_listing(identity, retrieved)
        result["title"]       = listing.get("title", "")
        result["description"] = listing.get("description", "")
    except Exception as e:
        result["title"]       = f"{identity.get('brand','')} {identity.get('product','')}".strip()
        result["description"] = "Could not generate description."
        result["generation_warning"] = str(e)

    # Flatten price
    result["price_point"] = retrieved.get("price_point")
    result["price_low"]   = retrieved.get("price_low")
    result["price_high"]  = retrieved.get("price_high")
    result["currency"]    = retrieved.get("currency", cfg.CURRENCY)
    result["price_basis"] = retrieved.get("basis", "")
    result["tags"]        = retrieved.get("tags") or retrieved.get("category_tags") or []

    return result


def _from_validated(validated) -> dict:
    """Map a ValidatedListing (from pipeline.run) to display dict."""
    from dataclasses import asdict
    d = asdict(validated)
    l = d.get("listing", {})
    i = l.get("identity", {})
    p = l.get("price", {})
    return {
        "_mode":       "pipeline",
        "identity":    i,
        "title":       l.get("title", ""),
        "description": l.get("description", ""),
        "price_point": p.get("point"),
        "price_low":   p.get("low"),
        "price_high":  p.get("high"),
        "currency":    p.get("currency", "CAD"),
        "price_basis": p.get("basis", ""),
        "tags":        d.get("listing", {}).get("flags", {}),
        "compliance":  validated.compliance_status,
        "retrieved":   {},
    }

# ─────────────────────────────────────────────────────────────────────────────
# Display helpers
# ─────────────────────────────────────────────────────────────────────────────
def _price_str(r: dict) -> str:
    lo, hi, pt = r.get("price_low"), r.get("price_high"), r.get("price_point")
    cur = r.get("currency", "CAD")
    if lo and hi:
        return f"${lo:.0f} – ${hi:.0f} {cur}"
    if pt:
        return f"${pt:.0f} {cur}"
    return "Price not found"


def _conf_html(conf: float) -> str:
    pct = int(conf * 100)
    colour = "#3fb950" if conf >= 0.7 else "#e3b341" if conf >= 0.4 else "#f85149"
    return (f'<div class="conf-track"><div class="conf-fill" '
            f'style="width:{pct}%;background:{colour}"></div></div>'
            f'<span style="font-size:.75rem;color:{colour}">{pct}% confidence</span>')


def _badge(status: str) -> str:
    cls  = {"clear": "badge-ok", "flagged": "badge-warn"}.get(status, "badge-warn")
    label= {"clear": "✅ Ready to publish", "flagged": "⚠️ Needs review"}.get(status, status)
    return f'<span class="badge {cls}">{label}</span>'


def _tag_html(tags) -> str:
    if isinstance(tags, list):
        items = tags
    elif isinstance(tags, dict):
        items = [k for k, v in tags.items() if v is True]
    else:
        items = []
    return '<div class="tags">' + "".join(f'<span class="tag">{t}</span>' for t in items) + '</div>'

# ─────────────────────────────────────────────────────────────────────────────
# Main layout
# ─────────────────────────────────────────────────────────────────────────────
st.markdown("""
<div class="demo-header">
  <h1 class="demo-title">📸 Snap to <span>Sell</span></h1>
  <p class="demo-sub">Upload a photo → AI identifies the item → generates a marketplace listing</p>
</div>
""", unsafe_allow_html=True)

st.markdown("---")

# Two-column layout: left = input, right = output
col_in, col_out = st.columns([1, 1], gap="large")

# ── LEFT: image input ─────────────────────────────────────────────────────────
with col_in:
    st.markdown('<div class="sec-label">📷 Item photo</div>', unsafe_allow_html=True)
    tab_up, tab_cam = st.tabs(["⬆️ Upload file", "🤳 Webcam"])

    image = None

    with tab_up:
        f = st.file_uploader("Choose a photo", type=["jpg","jpeg","png","webp"],
                             label_visibility="collapsed")
        if f:
            image = Image.open(f)

    with tab_cam:
        snap = st.camera_input("Point camera at item → Take photo",
                               label_visibility="collapsed")
        if snap:
            image = Image.open(snap)

    if image:
        st.image(image, width="stretch")
        st.markdown("<br>", unsafe_allow_html=True)
        run_btn = st.button("✨ Identify & Generate Listing")
    else:
        st.info("Upload a photo or use the webcam to get started.")
        run_btn = False

# ── RIGHT: results ────────────────────────────────────────────────────────────
with col_out:
    st.markdown('<div class="sec-label">🏷️ Generated listing</div>', unsafe_allow_html=True)

    if run_btn and image:
        if not api_key:
            st.error(f"Add your {provider.title()} API key in the sidebar.")
            st.stop()

        t0 = time.time()
        with st.spinner("Recognising item…"):
            try:
                result = run_pipeline(image)
            except Exception as e:
                st.error(str(e))
                st.stop()
        elapsed = time.time() - t0

        # Cache result (and original image) so it stays visible on reruns
        st.session_state["last_result"] = result
        st.session_state["last_image"]  = image

    result = st.session_state.get("last_result")
    orig_image = st.session_state.get("last_image")

    if result:
        identity  = result.get("identity", {})
        title     = result.get("title", "—")
        desc      = result.get("description", "—")
        price_str = _price_str(result)
        conf      = float(identity.get("confidence") or 0)
        compliance= result.get("compliance", "")
        basis     = result.get("price_basis", "")
        tags      = result.get("tags", [])
        mode      = result.get("_mode", "")

        # ── Listing card ──────────────────────────────────────────────────────
        st.markdown(f"""
<div class="card">
  <div class="card-title">{title}</div>
  <p class="card-desc">{desc}</p>

  <hr class="card-div"/>

  <div class="meta-grid">
    <div class="meta-item">
      <span class="meta-key">Brand</span>
      <span class="meta-val">{identity.get("brand") or "—"}</span>
    </div>
    <div class="meta-item">
      <span class="meta-key">Product</span>
      <span class="meta-val">{identity.get("product") or "—"}</span>
    </div>
    <div class="meta-item">
      <span class="meta-key">Size</span>
      <span class="meta-val">{identity.get("size") or "—"}</span>
    </div>
    <div class="meta-item">
      <span class="meta-key">Category</span>
      <span class="meta-val">{identity.get("category") or "—"}</span>
    </div>
    <div class="meta-item">
      <span class="meta-key">Suggested price</span>
      <span class="meta-val">{price_str}</span>
    </div>
  </div>

  {_conf_html(conf)}
  {_badge(compliance) if compliance else ""}
  {_tag_html(tags)}

  {f'<div class="source-note">💡 Price source: {basis}</div>' if basis else ""}
</div>
""", unsafe_allow_html=True)

        # ── Cleaned / canonical image section (NEW) ────────────────────────────
        if result.get("clean_image") is not None and orig_image is not None:
            st.markdown("<br>", unsafe_allow_html=True)
            st.markdown('<div class="sec-label">🖼️ Product image</div>', unsafe_allow_html=True)
            c1, c2 = st.columns(2)
            with c1:
                st.image(orig_image, caption="Original", width="stretch")
            with c2:
                st.image(result["clean_image"], caption=result.get("image_source", "Cleaned"),
                         width="stretch")

            sim = result.get("image_similarity")
            if result.get("image_swap_rejected"):
                st.warning(
                    f"Catalogue image found but similarity too low "
                    f"({sim:.0%} < {similarity_threshold:.0%} threshold) — "
                    f"kept your original (background-removed) photo instead."
                )
            elif sim is not None and "Open Food Facts" in result.get("image_source", ""):
                st.caption(f"Same-SKU similarity check passed: {sim:.0%}")

        if result.get("image_upgrade_warning"):
            st.warning(f"Image upgrade: {result['image_upgrade_warning']}")

        # ── Editable copy section ──────────────────────────────────────────────
        st.markdown("<br>", unsafe_allow_html=True)
        st.markdown('<div class="sec-label">✏️ Edit & copy</div>', unsafe_allow_html=True)

        edit_title = st.text_input("Title", value=title, key="edit_title")
        edit_desc  = st.text_area("Description", value=desc, height=110, key="edit_desc")
        edit_price = st.text_input("Asking price", value=price_str, key="edit_price")

        listing_text = f"{edit_title}\n\n{edit_desc}\n\nAsking: {edit_price}"
        st.code(listing_text, language=None)

        # ── Diagnostics ───────────────────────────────────────────────────────
        with st.expander("🔍 Raw recognition output"):
            st.json(identity)

        if result.get("retrieved"):
            with st.expander("📦 Retrieval data"):
                st.json(result["retrieved"])

        for w in ["retrieval_warning", "generation_warning"]:
            if result.get(w):
                st.warning(f"{w}: {result[w]}")

        st.caption(
            f"Mode: {mode} · Provider: {provider} · "
            f"Retrieval: {retrieve_backend} · "
            f"Model: {llm_model} · "
            f"Image upgrade: {'on' if enable_image_upgrade else 'off'}"
        )

    else:
        st.markdown("""
<div class="recog-panel">
  Upload or snap a photo on the left, then click<br>
  <b>✨ Identify &amp; Generate Listing</b> to see the result here.
  <br><br>
  The AI will return:<br>
  <b>·</b> Brand, product, size, category<br>
  <b>·</b> Current retail price range (web search)<br>
  <b>·</b> Ready-to-post title and description<br>
  <b>·</b> A cleaned / catalogue-matched product photo, when a confident match exists
</div>
""", unsafe_allow_html=True)