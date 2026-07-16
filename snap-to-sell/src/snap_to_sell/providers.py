"""Hosted multimodal provider client.

One place that talks to a paid/hosted vision+text model for BOTH recognition and listing
generation. Supports Anthropic (Claude), Gemini, and OpenAI, selected by env vars (see config).
If no key is configured, callers fall back to offline behaviour — this module simply raises
NoProviderError so the pipeline never hard-depends on a paid API.

Network calls use short timeouts and return parsed JSON dicts.
"""
import base64
import json
import mimetypes

import requests

from . import config, trace


class NoProviderError(RuntimeError):
    """No hosted provider configured (no API key)."""


class ProviderError(RuntimeError):
    """The hosted provider call failed or returned unusable output."""


def _b64_image(image_path: str):
    mime = mimetypes.guess_type(image_path)[0] or "image/jpeg"
    with open(image_path, "rb") as f:
        return mime, base64.b64encode(f.read()).decode("ascii")


def _extract_json(text: str) -> dict:
    """Pull a JSON object out of a model response, tolerating ```json fences."""
    t = text.strip()
    if t.startswith("```"):
        t = t.split("```", 2)[1]
        if t.lstrip().startswith("json"):
            t = t.lstrip()[4:]
    start, end = t.find("{"), t.rfind("}")
    if start == -1 or end == -1:
        raise ProviderError(f"no JSON object in model output: {text[:200]}")
    return json.loads(t[start:end + 1])


# Browser-like UA for fetching candidate product images (shopping thumbnails 403 the OFF UA).
_IMG_UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
           "(KHTML, like Gecko) Chrome/124.0 Safari/537.36")


def _b64_ref(ref: str):
    """(mime, b64) for an image given a local path or an http(s) URL."""
    if isinstance(ref, str) and ref.startswith("http"):
        r = requests.get(ref, timeout=config.HTTP_TIMEOUT, headers={"User-Agent": _IMG_UA})
        r.raise_for_status()
        mime = (r.headers.get("Content-Type") or "image/jpeg").split(";")[0].strip()
        if not mime.startswith("image/"):
            mime = "image/jpeg"
        return mime, base64.b64encode(r.content).decode("ascii")
    return _b64_image(ref)


def _prep_images(images):
    """Normalise an ``images`` argument into a list of (mime, b64). Each item may be a path/URL
    string or an already-prepared (mime, b64) tuple."""
    out = []
    for it in images or []:
        out.append(it if isinstance(it, tuple) else _b64_ref(it))
    return out


# --------------------------- Gemini ---------------------------

def _gemini(prompt: str, images: list) -> dict:
    url = (f"https://generativelanguage.googleapis.com/v1beta/models/"
           f"{config.GEMINI_MODEL}:generateContent?key={config.GEMINI_API_KEY}")
    parts = [{"text": prompt}]
    for mime, b64 in images:
        parts.append({"inline_data": {"mime_type": mime, "data": b64}})
    body = {
        "contents": [{"parts": parts}],
        "generationConfig": {"temperature": 0.2, "response_mime_type": "application/json"},
    }
    try:
        r = requests.post(url, json=body, timeout=config.HTTP_TIMEOUT,
                          headers={"User-Agent": config.USER_AGENT})
    except requests.RequestException as e:
        # never surface the URL (it contains the API key)
        raise ProviderError(f"gemini request failed: {type(e).__name__}") from None
    if r.status_code != 200:
        raise ProviderError(f"gemini {r.status_code}: {r.text[:200]}")
    cand = r.json()["candidates"][0]["content"]["parts"][0]["text"]
    return _extract_json(cand)


# --------------------------- OpenAI ---------------------------

def _openai(prompt: str, images: list) -> dict:
    content = [{"type": "text", "text": prompt}]
    for mime, b64 in images:
        content.append({"type": "image_url",
                        "image_url": {"url": f"data:{mime};base64,{b64}"}})
    body = {
        "model": config.OPENAI_MODEL,
        "messages": [{"role": "user", "content": content}],
        "temperature": 0.2,
        "response_format": {"type": "json_object"},
    }
    try:
        r = requests.post("https://api.openai.com/v1/chat/completions", json=body,
                          timeout=config.HTTP_TIMEOUT,
                          headers={"Authorization": f"Bearer {config.OPENAI_API_KEY}",
                                   "User-Agent": config.USER_AGENT})
    except requests.RequestException as e:
        raise ProviderError(f"openai request failed: {type(e).__name__}") from None
    if r.status_code != 200:
        raise ProviderError(f"openai {r.status_code}: {r.text[:200]}")
    return _extract_json(r.json()["choices"][0]["message"]["content"])


# --------------------------- Anthropic (Claude) ---------------------------

def _anthropic(prompt: str, images: list) -> dict:
    content = [{"type": "text", "text": prompt}]
    for mime, b64 in images:
        content.append({"type": "image",
                        "source": {"type": "base64", "media_type": mime, "data": b64}})
    body = {
        "model": config.ANTHROPIC_MODEL,
        "max_tokens": 1024,
        "temperature": 0.2,
        "messages": [{"role": "user", "content": content}],
    }
    try:
        r = requests.post("https://api.anthropic.com/v1/messages", json=body,
                          timeout=config.HTTP_TIMEOUT,
                          headers={"x-api-key": config.ANTHROPIC_API_KEY,
                                   "anthropic-version": "2023-06-01",
                                   "content-type": "application/json",
                                   "User-Agent": config.USER_AGENT})
    except requests.RequestException as e:
        raise ProviderError(f"anthropic request failed: {type(e).__name__}") from None
    if r.status_code != 200:
        raise ProviderError(f"anthropic {r.status_code}: {r.text[:200]}")
    return _extract_json(r.json()["content"][0]["text"])


def _call(prompt: str, image_path: str | None = None, label: str = "", images=None) -> dict:
    """Dispatch a text (+ optional image) prompt to the active provider. Pass a single
    ``image_path`` for one image, or ``images`` (list of paths/URLs/(mime,b64)) for several."""
    prov = config.active_provider()
    imgs = _prep_images(images) if images is not None else ([_b64_ref(image_path)] if image_path else [])
    trace.log("LLM", f"{label or 'call'} -> {prov or 'offline'}",
              {"prompt": prompt[:600] + ("…" if len(prompt) > 600 else ""), "images": len(imgs)})
    if prov == "anthropic":
        out = _anthropic(prompt, imgs)
    elif prov == "gemini":
        out = _gemini(prompt, imgs)
    elif prov == "openai":
        out = _openai(prompt, imgs)
    else:
        raise NoProviderError("no hosted provider configured")
    trace.log("LLM", f"{label or 'call'} response", out)
    return out


# --------------------------- public API ---------------------------

_IDENTIFY_PROMPT = (
    "You are identifying a single packaged retail product from a photo for a corner-store "
    "catalogue. Read the packaging text. Return ONLY a JSON object with keys: "
    "brand, product, variant, size, category, ocr_text, barcode, confidence, search_query. "
    "category is one of: confectionery, snacks, beverage, frozen, tobacco, alcohol, household, other. "
    "size includes units (e.g. '45 g', '500 mL'). barcode is the digits if visible else null. "
    "be careful not to read the bars in the barcode as a digit (e.g. 1 or 7)."
    "search_query is a SHORT catalogue-search phrase — brand + core product type + size ONLY "
    "(e.g. 'Duracell AA batteries 24'); OMIT marketing words like 'Power Boost', slogans and adjectives. "
    "confidence is 0..1 for how sure you are of the exact product. Use empty string for unknown fields."
)


def vlm_identify(image_path: str) -> dict:
    """Recognition: photo -> identity dict. Raises NoProviderError if offline."""
    return _call(_IDENTIFY_PROMPT, image_path, "recognise")


def draft_listing(identity: dict, retrieved: dict) -> dict:
    """Generation: grounded listing dict {title, description}. Raises NoProviderError if offline.

    The model is instructed to use ONLY the supplied attributes (no invented specs)."""
    prompt = (
        "Write a concise e-commerce listing for a corner-store product using ONLY the facts "
        "below. Do NOT invent specifications, ingredients, weights, or claims not present in the "
        "facts. Return ONLY a JSON object with keys: title, description.\n\n"
        f"IDENTITY: {json.dumps(identity)}\n"
        f"RETRIEVED: {json.dumps(retrieved)}\n"
    )
    return _call(prompt, None, "generate listing")


def draft_listing_baseline(identity: dict) -> dict:
    """Naive baseline generation: an UNGROUNDED listing + best-guess price from the identity
    alone — no retrieval, no comparables, no guardrails. This is deliberately the weak anchor
    the full pipeline is compared against, so the model is allowed to guess (unlike the grounded
    draft_listing above). Returns {title, description, price}. Raises NoProviderError if offline."""
    prompt = (
        "You are a naive product-listing generator. From the product identity below ALONE, "
        "write a generic e-commerce listing and your single best guess at a typical retail "
        "price. You have NO catalogue, NO comparable prices, and NO other facts — just guess. "
        "Return ONLY a JSON object with keys: title, description, price. "
        "price is a number in Canadian dollars (CAD), or null if you truly cannot guess.\n\n"
        f"IDENTITY: {json.dumps(identity)}\n"
    )
    return _call(prompt, None, "baseline listing")


def extract_product_name(barcode: str, results: list) -> dict:
    """Extract the exact product name for a barcode from web search results (title + snippet).
    Returns {"product_name": "..."}. Raises NoProviderError if offline."""
    prompt = (
        "You are extracting a product name from web search results for a product barcode. "
        f"Barcode: {barcode}. Search results (title + snippet):\n{json.dumps(results)[:4000]}\n\n"
        "Return ONLY a JSON object {\"product_name\": \"...\"} with the exact product name "
        "(brand + product + size) that corresponds to this barcode. If no result clearly "
        "corresponds to this barcode, use an empty string."
    )
    return _call(prompt, None, "barcode name")


_VERIFY_PROMPT = (
    "You are verifying a product image match for an online listing. "
    "IMAGE A is a shop owner's own photo of a product. IMAGE B is a candidate catalogue image "
    "that may be swapped in to replace A. Decide whether B shows the SAME product as A — the "
    "same brand, the same variant/flavour/scent, AND the same size/pack count. Be strict: a "
    "different size, flavour, or a look-alike product from the same brand is NOT a match "
    "(showing a wrong image misleads buyers). Judge the product identity, not photo quality or "
    "background. Return ONLY a JSON object with keys: same_product (true/false), confidence "
    "(0..1, how sure you are), reason (one short sentence)."
)


def verify_same_product(photo_ref: str, candidate_ref: str, identity: dict | None = None) -> dict:
    """LLM same-SKU judge: does the candidate catalogue image show the SAME product as the photo?
    Sends both images to the vision model. Returns a normalised
    {"same_product": bool, "confidence": float, "reason": str}. Raises NoProviderError if offline;
    the candidate fetch may raise (e.g. a thumbnail that won't download) — callers should skip it."""
    prompt = _VERIFY_PROMPT
    if identity:
        prompt += f"\n\nFor context, IMAGE A was recognised as: {json.dumps(identity)}"
    out = _call(prompt, images=[photo_ref, candidate_ref], label="verify same-SKU")
    try:
        conf = float(out.get("confidence", 0) or 0)
    except (TypeError, ValueError):
        conf = 0.0
    return {
        "same_product": bool(out.get("same_product")),
        "confidence": max(0.0, min(1.0, conf)),
        "reason": str(out.get("reason", ""))[:300],
    }
