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

from . import config


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


# --------------------------- Gemini ---------------------------

def _gemini(prompt: str, image_path: str | None) -> dict:
    url = (f"https://generativelanguage.googleapis.com/v1beta/models/"
           f"{config.GEMINI_MODEL}:generateContent?key={config.GEMINI_API_KEY}")
    parts = [{"text": prompt}]
    if image_path:
        mime, b64 = _b64_image(image_path)
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

def _openai(prompt: str, image_path: str | None) -> dict:
    content = [{"type": "text", "text": prompt}]
    if image_path:
        mime, b64 = _b64_image(image_path)
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

def _anthropic(prompt: str, image_path: str | None) -> dict:
    content = [{"type": "text", "text": prompt}]
    if image_path:
        mime, b64 = _b64_image(image_path)
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


def _call(prompt: str, image_path: str | None) -> dict:
    prov = config.active_provider()
    if prov == "anthropic":
        return _anthropic(prompt, image_path)
    if prov == "gemini":
        return _gemini(prompt, image_path)
    if prov == "openai":
        return _openai(prompt, image_path)
    raise NoProviderError("no hosted provider configured")


# --------------------------- public API ---------------------------

_IDENTIFY_PROMPT = (
    "You are identifying a single packaged retail product from a photo for a corner-store "
    "catalogue. Read the packaging text. Return ONLY a JSON object with keys: "
    "brand, product, variant, size, category, ocr_text, barcode, confidence, search_query. "
    "category is one of: confectionery, snacks, beverage, frozen, tobacco, alcohol, household, other. "
    "size includes units (e.g. '45 g', '500 mL'). barcode is the digits if visible else null. "
    "search_query is a SHORT catalogue-search phrase — brand + core product type + size ONLY "
    "(e.g. 'Duracell AA batteries 24'); OMIT marketing words like 'Power Boost', slogans and adjectives. "
    "confidence is 0..1 for how sure you are of the exact product. Use empty string for unknown fields."
)


def vlm_identify(image_path: str) -> dict:
    """Recognition: photo -> identity dict. Raises NoProviderError if offline."""
    return _call(_IDENTIFY_PROMPT, image_path)


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
    return _call(prompt, None)
