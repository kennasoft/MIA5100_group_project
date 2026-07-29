import streamlit as st
import anthropic
import base64
from PIL import Image
import io
import json
import re
import urllib.parse

# ─────────────────────────────────────────────────────────────────────────────
# HOW THE APP WORKS (read this first)
# ─────────────────────────────────────────────────────────────────────────────
# 1. USER takes a photo (webcam) or uploads one (file picker)
# 2. IMAGE is base64-encoded and sent to Claude's vision API
# 3. CLAUDE returns a structured JSON listing (title, desc, price, tags, etc.)
# 4. APP renders the listing + lets user edit it
# 5. PLATFORM LINK opens the marketplace's "create listing" page in a new tab
#    and the user pastes the pre-formatted text. Real API posting requires
#    OAuth tokens from each platform (shown as comments below).
# ─────────────────────────────────────────────────────────────────────────────

# ── Page config ───────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Snap to Sell",
    page_icon="📸",
    layout="centered",
    initial_sidebar_state="collapsed",
)

# ── Styles ────────────────────────────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@400;500;600;700&family=Inter:wght@400;500&display=swap');

html, body, [class*="css"] {
    font-family: 'Inter', sans-serif;
    background-color: #0D1117;
    color: #E6EDF3;
}
.snap-header { text-align: center; padding: 2rem 0 0.8rem; }
.snap-title {
    font-family: 'Space Grotesk', sans-serif;
    font-size: 2.6rem; font-weight: 700;
    letter-spacing: -0.03em; color: #FFF; margin: 0;
}
.snap-title span { color: #F5A623; }
.snap-subtitle { font-size: 0.97rem; color: #8B949E; margin-top: 0.35rem; }

/* Listing card */
.listing-card {
    background: #161B22; border: 1px solid #30363D;
    border-radius: 12px; padding: 1.6rem; margin-top: 1.2rem;
}
.listing-card-label {
    font-family: 'Space Grotesk', sans-serif;
    font-size: 0.68rem; font-weight: 600;
    letter-spacing: 0.15em; text-transform: uppercase;
    color: #F5A623; margin-bottom: 0.5rem;
}
.listing-title {
    font-family: 'Space Grotesk', sans-serif;
    font-size: 1.35rem; font-weight: 700; color: #FFF;
    margin: 0 0 0.8rem; line-height: 1.3;
}
.listing-desc { font-size: 0.92rem; color: #C9D1D9; line-height: 1.65; }
.meta-row { display: flex; gap: 1.4rem; margin: 0.9rem 0 0.3rem; flex-wrap: wrap; }
.meta-item { display: flex; flex-direction: column; gap: 0.12rem; }
.meta-label { font-size: 0.7rem; color: #6E7681; letter-spacing: 0.09em; text-transform: uppercase; font-weight: 500; }
.meta-value { font-size: 0.88rem; color: #E6EDF3; font-weight: 600; font-family: 'Space Grotesk', sans-serif; }
.card-divider { border: none; border-top: 1px solid #21262D; margin: 1rem 0; }
.tags-row { display: flex; flex-wrap: wrap; gap: 0.4rem; margin-top: 0.9rem; }
.tag {
    background: #21262D; border: 1px solid #30363D;
    border-radius: 20px; padding: 0.2rem 0.65rem;
    font-size: 0.77rem; color: #8B949E; font-weight: 500;
}
.condition-note {
    font-size: 0.83rem; color: #8B949E; padding: 0.55rem 0.8rem;
    background: #21262D; border-radius: 6px;
    border-left: 3px solid #F5A623; margin-top: 0.9rem;
}

/* Platform buttons section */
.platform-section {
    background: #161B22; border: 1px solid #30363D;
    border-radius: 10px; padding: 1.2rem; margin-top: 1rem;
}
.platform-section-title {
    font-family: 'Space Grotesk', sans-serif;
    font-size: 0.8rem; font-weight: 600;
    letter-spacing: 0.1em; text-transform: uppercase;
    color: #8B949E; margin-bottom: 0.8rem;
}
.how-it-works {
    background: #0D1117; border: 1px solid #21262D;
    border-radius: 8px; padding: 0.9rem 1rem;
    font-size: 0.82rem; color: #8B949E; line-height: 1.6;
    margin-top: 0.6rem;
}
.how-it-works code {
    background: #21262D; padding: 0.1rem 0.35rem;
    border-radius: 4px; color: #F5A623; font-size: 0.78rem;
}

/* Streamlit overrides */
.stButton > button {
    background: #F5A623 !important; color: #0D1117 !important;
    font-family: 'Space Grotesk', sans-serif !important;
    font-weight: 700 !important; font-size: 0.92rem !important;
    border: none !important; border-radius: 8px !important;
    padding: 0.5rem 1.4rem !important; width: 100% !important;
}
.stButton > button:hover { opacity: 0.85 !important; color: #0D1117 !important; }
div[data-testid="stTextInput"] input,
div[data-testid="stTextArea"] textarea {
    background-color: #161B22 !important; border: 1px solid #30363D !important;
    color: #E6EDF3 !important; border-radius: 8px !important;
}
div[data-testid="stSelectbox"] > div {
    background-color: #161B22 !important; border: 1px solid #30363D !important;
    border-radius: 8px !important; color: #E6EDF3 !important;
}
footer { visibility: hidden; }
#MainMenu { visibility: hidden; }
</style>
""", unsafe_allow_html=True)

# ── Header ────────────────────────────────────────────────────────────────────
st.markdown("""
<div class="snap-header">
    <h1 class="snap-title">📸 Snap to <span>Sell</span></h1>
    <p class="snap-subtitle">Take a photo — get a ready-to-post marketplace listing in seconds.</p>
</div>
""", unsafe_allow_html=True)
st.markdown("---")

# ── API key ───────────────────────────────────────────────────────────────────
with st.expander("⚙️ Settings — Anthropic API Key", expanded=False):
    api_key_input = st.text_input(
        "Anthropic API Key", type="password",
        placeholder="sk-ant-...",
        help="Get your key at console.anthropic.com — never stored.",
    )

try:
    ANTHROPIC_API_KEY = st.secrets["ANTHROPIC_API_KEY"]
except Exception:
    ANTHROPIC_API_KEY = api_key_input or None

# ── Platform picker ───────────────────────────────────────────────────────────
PLATFORMS = ["Auto-detect", "Facebook Marketplace", "Kijiji", "eBay", "Depop", "Craigslist"]
platform_choice = st.selectbox("Target platform", PLATFORMS)

# ─────────────────────────────────────────────────────────────────────────────
# STEP 1 — GET THE IMAGE
# Two input modes: file upload OR live webcam via st.camera_input().
# Both return the same UploadedFile-like object so the rest of the pipeline
# is identical.
# ─────────────────────────────────────────────────────────────────────────────
st.markdown("#### 📷 Get your photo")

# st.tabs() creates a tab strip — each tab is its own UI block.
tab_upload, tab_camera = st.tabs(["⬆️  Upload a file", "🤳  Use webcam"])

image = None  # will hold a PIL Image once either source provides one

with tab_upload:
    # st.file_uploader() opens the OS file picker.
    # Returns an UploadedFile object (or None if nothing picked yet).
    uploaded_file = st.file_uploader(
        "Choose a photo", type=["jpg", "jpeg", "png", "webp"],
        label_visibility="collapsed",
    )
    if uploaded_file:
        image = Image.open(uploaded_file)

with tab_camera:
    # ─────────────────────────────────────────────────────────────────────────
    # HOW st.camera_input() WORKS
    # ─────────────────────────────────────────────────────────────────────────
    # Streamlit asks the browser for webcam permission via the
    # MediaDevices.getUserMedia() Web API.  The widget renders a live preview
    # and a "Take photo" button.  When clicked, the frame is JPEG-encoded
    # client-side and sent to the Python server as an UploadedFile — exactly
    # the same type as st.file_uploader(), so the rest of the code is shared.
    #
    # Limitations to know for your report:
    #   • Only works over HTTPS or localhost (browser security policy).
    #   • On mobile: the phone camera opens instead of a webcam — great UX!
    #   • No audio, no video — single frame only.
    # ─────────────────────────────────────────────────────────────────────────
    camera_photo = st.camera_input(
        "Point your camera at the item and click Take photo",
        label_visibility="collapsed",
    )
    if camera_photo:
        image = Image.open(camera_photo)

# ── Show preview + generate button ───────────────────────────────────────────
if image:
    # Resize for display
    display = image.copy()
    if display.width > 600:
        r = 600 / display.width
        display = display.resize((600, int(display.height * r)), Image.LANCZOS)
    st.image(display, use_container_width=True)

    if st.button("✨ Generate Listing"):
        if not ANTHROPIC_API_KEY:
            st.error("Add your Anthropic API key in ⚙️ Settings above.")
            st.stop()

        with st.spinner("Analyzing your item…"):

            # ─────────────────────────────────────────────────────────────────
            # STEP 2 — ENCODE THE IMAGE FOR THE API
            # Claude's vision API accepts images as base64-encoded strings.
            # We convert the PIL Image → bytes → base64 string.
            # ─────────────────────────────────────────────────────────────────
            buf = io.BytesIO()
            fmt = image.format or "JPEG"
            if fmt not in ("JPEG", "PNG", "WEBP"):
                fmt = "JPEG"
            img_to_save = image.convert("RGB") if fmt == "JPEG" and image.mode in ("RGBA", "P") else image
            img_to_save.save(buf, format=fmt)
            img_b64 = base64.standard_b64encode(buf.getvalue()).decode()
            media_type = {"JPEG": "image/jpeg", "PNG": "image/png", "WEBP": "image/webp"}[fmt]

            # ─────────────────────────────────────────────────────────────────
            # STEP 3 — CALL CLAUDE WITH VISION + STRUCTURED OUTPUT PROMPT
            # We tell Claude to return ONLY JSON so we can parse it reliably.
            # Asking for a fixed schema = structured output without extra libs.
            # ─────────────────────────────────────────────────────────────────
            platform_note = (
                f"The seller wants to post on {platform_choice}. "
                f"Tailor the writing style and keywords for that platform."
                if platform_choice != "Auto-detect"
                else "Suggest the single best platform from: Facebook Marketplace, Kijiji, eBay, Depop, Craigslist."
            )

            prompt = f"""You are an expert resale listing copywriter.
Analyze the item in this photo carefully and produce a marketplace listing.
{platform_note}

Return ONLY a valid JSON object — no markdown fences, no preamble — with exactly these fields:
{{
  "item_name": "concise item name",
  "category": "Electronics | Furniture | Clothing | Books | Sporting Goods | Tools | Other",
  "condition": "New | Like New | Good | Fair | Poor",
  "condition_notes": "one honest sentence about visible condition",
  "listing_title": "compelling title under 80 characters",
  "description": "3–4 sentence marketplace description: hook, features, condition, call to action",
  "tags": ["keyword1", "keyword2", "keyword3", "keyword4", "keyword5"],
  "price_low": 0,
  "price_high": 0,
  "currency": "CAD",
  "platform": "best platform for this specific item"
}}"""

            client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
            try:
                response = client.messages.create(
                    model="claude-sonnet-4-6",
                    max_tokens=1000,
                    messages=[{
                        "role": "user",
                        "content": [
                            {
                                "type": "image",
                                "source": {
                                    "type": "base64",
                                    "media_type": media_type,
                                    "data": img_b64,
                                },
                            },
                            {"type": "text", "text": prompt},
                        ],
                    }],
                )
                raw = response.content[0].text
                clean = re.sub(r"```json|```", "", raw).strip()
                result = json.loads(clean)

            except json.JSONDecodeError:
                st.error("Couldn't parse AI response. Try again.")
                st.code(raw, language="text")
                st.stop()
            except anthropic.AuthenticationError:
                st.error("Invalid API key.")
                st.stop()
            except Exception as e:
                st.error(f"API error: {e}")
                st.stop()

        # ─────────────────────────────────────────────────────────────────────
        # STEP 4 — RENDER THE LISTING CARD
        # ─────────────────────────────────────────────────────────────────────
        price_low  = result.get("price_low", 0)
        price_high = result.get("price_high", 0)
        currency   = result.get("currency", "CAD")
        price_str  = f"${price_low}–${price_high} {currency}" if price_low else "—"
        platform_used = platform_choice if platform_choice != "Auto-detect" else result.get("platform", "—")
        tags_html = "".join(f'<span class="tag">{t}</span>' for t in result.get("tags", []))

        st.markdown(f"""
<div class="listing-card">
    <div class="listing-card-label">Generated listing</div>
    <h2 class="listing-title">{result.get("listing_title", "—")}</h2>
    <div class="meta-row">
        <div class="meta-item"><span class="meta-label">Category</span><span class="meta-value">{result.get("category","—")}</span></div>
        <div class="meta-item"><span class="meta-label">Condition</span><span class="meta-value">{result.get("condition","—")}</span></div>
        <div class="meta-item"><span class="meta-label">Suggested price</span><span class="meta-value">{price_str}</span></div>
        <div class="meta-item"><span class="meta-label">Platform</span><span class="meta-value">{platform_used}</span></div>
    </div>
    <hr class="card-divider"/>
    <p class="listing-desc">{result.get("description","—")}</p>
    <div class="tags-row">{tags_html}</div>
    <div class="condition-note">💡 {result.get("condition_notes","—")}</div>
</div>
""", unsafe_allow_html=True)

        st.markdown("<br>", unsafe_allow_html=True)

        # ── Editable fields ───────────────────────────────────────────────────
        st.markdown("#### ✏️ Edit before posting")
        edit_title = st.text_input("Title", value=result.get("listing_title", ""))
        edit_desc  = st.text_area("Description", value=result.get("description", ""), height=120)
        edit_price = st.text_input("Your asking price", value=str(price_low))

        # Build the final listing text (shared across all platforms)
        listing_text = f"{edit_title}\n\n{edit_desc}\n\nAsking: ${edit_price} {currency} — firm / or best offer.\n\nTags: {', '.join(result.get('tags', []))}"

        # ─────────────────────────────────────────────────────────────────────
        # STEP 5 — PLATFORM POSTING
        # ─────────────────────────────────────────────────────────────────────
        # Strategy: open the platform's "create listing" page in a new browser
        # tab, and give the user a pre-formatted block to paste in.
        #
        # WHY NOT FULL AUTO-POST?
        #   Every platform requires OAuth 2.0 authentication — the user must
        #   grant your app permission through their account.  That flow needs:
        #     1. A registered developer app on each platform
        #     2. A redirect URI (needs a deployed server, not just localhost)
        #     3. Access/refresh token management
        #   For production, see the comments inside each platform block below.
        # ─────────────────────────────────────────────────────────────────────
        st.markdown("#### 🚀 Post your listing")
        st.markdown("""
<div class="platform-section">
<div class="platform-section-title">Choose where to post</div>
""", unsafe_allow_html=True)

        col1, col2, col3 = st.columns(3)

        # ── Facebook Marketplace ──────────────────────────────────────────────
        with col1:
            # Facebook has no public Marketplace API for posting.
            # The only path is: open their "create item" page, user pastes.
            # In production with a Facebook App + user token you could use
            # the Commerce API: POST /me/marketplace_listings (limited access).
            fb_url = "https://www.facebook.com/marketplace/create/item"
            st.link_button("📘 Facebook Marketplace", fb_url, use_container_width=True)

        # ── Kijiji ───────────────────────────────────────────────────────────
        with col2:
            # Kijiji has no public API. Opens their "post ad" flow.
            # In production: Kijiji Pro dealers get a private feed/API.
            kijiji_url = "https://www.kijiji.ca/p-post-ad.html"
            st.link_button("🟡 Kijiji", kijiji_url, use_container_width=True)

        # ── eBay ─────────────────────────────────────────────────────────────
        with col3:
            # eBay has a real Sell API. To auto-post you'd use:
            #   POST https://api.ebay.com/sell/inventory/v1/inventory_item/{sku}
            # This needs: OAuth 2.0 → user token → inventory item → offer → publish.
            # For now we open their quick-list page with a title pre-filled in URL.
            ebay_title = urllib.parse.quote(edit_title[:80])
            ebay_url = f"https://www.ebay.ca/sell/listing?title={ebay_title}"
            st.link_button("🔴 eBay", ebay_url, use_container_width=True)

        st.markdown("</div>", unsafe_allow_html=True)

        # ── Pre-formatted text to paste ───────────────────────────────────────
        st.markdown("**📋 Your listing text — copy and paste into the platform:**")
        st.code(listing_text, language=None)

        # ── How it works explainer (good for your report/demo) ────────────────
        with st.expander("🔧 How real API posting would work (for the report)"):
            st.markdown(f"""
<div class="how-it-works">
<strong>Current flow (demo):</strong><br>
1. Claude vision analyzes the image → returns JSON<br>
2. App renders the listing + lets you edit<br>
3. A link opens the platform's listing page in a new tab<br>
4. You paste the pre-formatted text<br><br>

<strong>Production flow (what you'd build next):</strong><br>
1. Same steps 1–2<br>
2. User clicks "Connect {platform_used}" → OAuth redirect to the platform<br>
3. Platform issues an <code>access_token</code> (stored server-side, never in the app)<br>
4. App calls the platform's REST API with the token + listing payload<br>
5. Listing goes live automatically — no paste needed<br><br>

<strong>eBay example API call:</strong><br>
<code>POST https://api.ebay.com/sell/inventory/v1/inventory_item/&lt;sku&gt;</code><br>
Headers: <code>Authorization: Bearer &lt;access_token&gt;</code><br>
Body: title, description, price, condition, images (base64 or URL)<br><br>

<strong>Facebook / Kijiji:</strong> No public posting API — scraping or partner access only.
</div>
""", unsafe_allow_html=True)

        # ── Raw JSON ──────────────────────────────────────────────────────────
        with st.expander("🔍 Raw AI output (JSON)"):
            st.json(result)

else:
    # Empty state
    st.info("👆 Upload a photo or take one with your webcam to get started.")

    # Quick explainer for visitors
    with st.expander("How does this work?"):
        st.markdown("""
1. **Snap or upload** a photo of the item you want to sell
2. **Claude AI** identifies the item, writes the title and description, and suggests a price range
3. **Edit** anything you want to change
4. **Post** to Facebook Marketplace, Kijiji, or eBay (opens in a new tab with your text ready to paste)
        """)