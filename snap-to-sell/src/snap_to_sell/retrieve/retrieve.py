"""Retrieve.

Free open-data backbone. Order of preference:
  1. Barcode product lookup (/api/v2/product) — reliable, NOT deprecated — OFF then OPF.
  2. Name search: Open Food Facts via the current **Search-a-licious** API
     (the legacy cgi/search.pl returns HTTP 503 and is deprecated), then Open Products Facts
     legacy search as a best-effort for non-food items.
Plus Open Prices for a community price. Any failure degrades to an offline bundle from the identity.
"""
import sys

import requests

from ..interfaces import RetrievedBundle, PriceInfo, CandidateImage
from .. import config

_FIELDS = "code,product_name,generic_name,brands,categories_tags,image_front_url,image_url,quantity"


def _headers():
    return {"User-Agent": config.USER_AGENT}


def _search_query(identity) -> str:
    parts = [identity.brand, identity.product, identity.variant, identity.size]
    return " ".join(p for p in parts if p).strip()


def _by_barcode(product_url, code):
    r = requests.get(product_url.format(code=code), timeout=config.HTTP_TIMEOUT, headers=_headers())
    r.raise_for_status()
    data = r.json()
    return data.get("product") if data.get("status") == 1 else None


def _search_off(query):
    """Open Food Facts search via Search-a-licious (current API)."""
    r = requests.get(config.OFF_SEARCH_SALICIOUS,
                     params={"q": query, "page_size": 1, "fields": _FIELDS},
                     timeout=config.HTTP_TIMEOUT, headers=_headers())
    r.raise_for_status()
    hits = r.json().get("hits", [])
    return hits[0] if hits else None


def _search_legacy(search_url, query):
    """Legacy cgi/search.pl (deprecated; best-effort for Open Products Facts)."""
    r = requests.get(search_url,
                     params={"search_terms": query, "search_simple": 1,
                             "action": "process", "json": 1, "page_size": 1},
                     timeout=config.HTTP_TIMEOUT, headers=_headers())
    r.raise_for_status()
    prods = r.json().get("products", [])
    return prods[0] if prods else None


def _open_price(code):
    try:
        r = requests.get(config.OPEN_PRICES_URL, params={"product_code": code, "size": 20},
                         timeout=config.HTTP_TIMEOUT, headers=_headers())
        r.raise_for_status()
        prices = sorted(float(i["price"]) for i in r.json().get("items", []) if i.get("price"))
        if prices:
            mid = prices[len(prices) // 2]
            return PriceInfo(currency=config.CURRENCY, point=round(mid, 2),
                             low=prices[0], high=prices[-1],
                             basis=f"open_prices median (n={len(prices)})")
    except Exception:
        pass
    return None


def _as_text(v) -> str:
    """Coerce a field that may be a str, list, dict (localized), or None to a string.
    Search-a-licious returns some fields (e.g. brands) as lists, unlike the legacy API."""
    if v is None:
        return ""
    if isinstance(v, list):
        return ", ".join(str(x) for x in v if x)
    if isinstance(v, dict):
        return str(v.get("en") or next((x for x in v.values() if x), ""))
    return str(v)


def _first_brand(v) -> str:
    if isinstance(v, list):
        return str(v[0]).strip() if v else ""
    return str(v or "").split(",")[0].strip()


def _bundle_from_record(prod, code, source) -> RetrievedBundle:
    name = (_as_text(prod.get("product_name")) or _as_text(prod.get("generic_name"))).strip()
    brand = _first_brand(prod.get("brands"))
    canonical = " ".join(x for x in [brand, name, _as_text(prod.get("quantity"))] if x).strip() or name
    tags = [str(t).replace("en:", "") for t in (prod.get("categories_tags") or [])]
    images = []
    img = _as_text(prod.get("image_front_url")) or _as_text(prod.get("image_url"))
    if img:
        images.append(CandidateImage(url=img, licence="CC-BY-SA 3.0", source=source, match_score=0.0))
    price = (_open_price(code) if code else None) or PriceInfo(currency=config.CURRENCY,
                                                              basis="no price found")
    return RetrievedBundle(canonical_name=canonical, category_tags=tags, price=price, images=images)


def _offline_bundle(identity) -> RetrievedBundle:
    canonical = " ".join(x for x in [identity.brand, identity.product,
                                     identity.variant, identity.size] if x).strip()
    tags = [identity.category] if identity.category else []
    images = []
    if getattr(identity, "catalogue_image_url", None):  # optional demo image from sidecar
        images.append(CandidateImage(url=identity.catalogue_image_url,
                                     licence="(demo)", source="sidecar", match_score=0.0))
    return RetrievedBundle(canonical_name=canonical or identity.product, category_tags=tags,
                           price=PriceInfo(currency=config.CURRENCY, basis="offline: no retrieval"),
                           images=images)


def retrieve(identity) -> RetrievedBundle:
    query = _search_query(identity)
    code = identity.barcode

    # 1) barcode product lookup (reliable, not deprecated) — OFF then OPF
    if code:
        for product_url, source in ((config.OFF_PRODUCT_URL, "Open Food Facts"),
                                    (config.OPF_PRODUCT_URL, "Open Products Facts")):
            try:
                prod = _by_barcode(product_url, code)
                if prod:
                    return _bundle_from_record(prod, code, source)
            except Exception as e:
                print(f"[retrieve] {source} barcode lookup failed: {e}", file=sys.stderr)

    # 2) name search — OFF via Search-a-licious, then OPF legacy (best-effort)
    if query:
        try:
            prod = _search_off(query)
            if prod:
                return _bundle_from_record(prod, prod.get("code"), "Open Food Facts")
        except Exception as e:
            print(f"[retrieve] OFF search failed: {e}", file=sys.stderr)
        try:
            prod = _search_legacy(config.OPF_SEARCH_URL, query)
            if prod:
                return _bundle_from_record(prod, prod.get("code"), "Open Products Facts")
        except Exception as e:
            print(f"[retrieve] OPF search unavailable: {e}", file=sys.stderr)

    print("[retrieve] no catalogue hit; using offline bundle", file=sys.stderr)
    return _offline_bundle(identity)
