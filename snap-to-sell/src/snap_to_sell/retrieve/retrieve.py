"""Retrieve — turn a recognised identity into a canonical name, price and image.

Flow:
  1. Barcode-first (if the model read a barcode): authoritative record from Open Food Facts,
     Open Products Facts, then EcomSource (optional keys) -> an EXACT product name.
  2. Shopping backend (SNAP_RETRIEVE_BACKEND=shopping): one Serper.dev Google Shopping search
     using the exact name (or full label) -> clean retailer image + real price. Results are
     re-ranked by brand/size match, reputable-retailer preference, and home-currency preference.
  3. Otherwise Open Food Facts (Search-a-licious, with query relaxation) then Open Products Facts.
Prices carry their detected currency (so foreign listings aren't shown under the wrong symbol),
and CAD/USD are preferred (local-first). Any failure degrades to an offline bundle.
"""
import re
import sys

import requests

from ..interfaces import RetrievedBundle, PriceInfo, CandidateImage
from .. import config

_FIELDS = "code,product_name,generic_name,brands,categories_tags,image_front_url,image_url,quantity"
SEARCH_PAGE_SIZE = 5  # fetch N candidates, then re-rank against the recognised identity


def _headers():
    return {"User-Agent": config.USER_AGENT}


def _search_query(identity) -> str:
    # prefer the model's short search phrase; fall back to a compact brand+product+size string
    if getattr(identity, "search_query", ""):
        return identity.search_query.strip()
    parts = [identity.brand, identity.product, identity.size]
    return " ".join(p for p in parts if p).strip()


def _relaxed(query, max_tries=3):
    """Yield progressively shorter queries (drop trailing tokens), keeping the brand first.
    Used for OFF's keyword index, where descriptive strings over-constrain."""
    toks = query.split()
    tries = 0
    while toks and tries < max_tries:
        yield " ".join(toks)
        toks = toks[:-1]
        tries += 1


def _full_query(identity) -> str:
    """Full descriptive label (brand + product + variant + size) — good for Google Shopping, where
    a specific query returns fewer, better-ranked results (and costs a single credit). Falls back
    to the short search_query if the components are empty."""
    parts = [identity.brand, identity.product, identity.variant, identity.size]
    return " ".join(p for p in parts if p).strip() or _search_query(identity)


def _by_barcode(product_url, code):
    r = requests.get(product_url.format(code=code), timeout=config.HTTP_TIMEOUT, headers=_headers())
    r.raise_for_status()
    data = r.json()
    return data.get("product") if data.get("status") == 1 else None


def _search_off(query):
    """Open Food Facts search via Search-a-licious (current API). Returns a list of hits."""
    r = requests.get(config.OFF_SEARCH_SALICIOUS,
                     params={"q": query, "page_size": SEARCH_PAGE_SIZE, "fields": _FIELDS},
                     timeout=config.HTTP_TIMEOUT, headers=_headers())
    r.raise_for_status()
    return r.json().get("hits", [])


def _search_legacy(search_url, query):
    """Legacy cgi/search.pl (deprecated; best-effort for Open Products Facts). Returns a list."""
    r = requests.get(search_url,
                     params={"search_terms": query, "search_simple": 1,
                             "action": "process", "json": 1, "page_size": SEARCH_PAGE_SIZE},
                     timeout=config.HTTP_TIMEOUT, headers=_headers())
    r.raise_for_status()
    return r.json().get("products", [])


def _open_price(code):
    try:
        r = requests.get(config.OPEN_PRICES_URL, params={"product_code": code, "size": 20},
                         timeout=config.HTTP_TIMEOUT, headers=_headers())
        r.raise_for_status()
        vals = [(float(i["price"]), _as_text(i.get("currency")).upper())
                for i in r.json().get("items", []) if i.get("price")]
        if not vals:
            return None
        pref = [v for v in vals if v[1] in config.PREFERRED_CURRENCIES] or vals
        pref.sort(key=lambda x: x[0])
        val, cur = pref[len(pref) // 2]
        return PriceInfo(currency=cur or config.CURRENCY, point=round(val, 2),
                         low=pref[0][0], high=pref[-1][0],
                         basis=f"open_prices median (n={len(pref)})")
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


# --------------------------- N-best re-ranking ---------------------------

def _tokens(v):
    return set(re.findall(r"[a-z0-9]+", _as_text(v).lower()))


def _score_hit(identity, hit) -> float:
    """Score a candidate hit against the recognised identity: brand match dominates, then
    name-token overlap, then size/quantity agreement (a size conflict is penalised)."""
    id_brand = _tokens(identity.brand)
    id_name = _tokens(f"{identity.brand} {identity.product} {identity.variant}")
    id_size = _tokens(identity.size)
    h_brand = _tokens(hit.get("brands"))
    h_name = _tokens(f"{_as_text(hit.get('product_name'))} {_as_text(hit.get('generic_name'))}")
    h_qty = _tokens(hit.get("quantity"))

    score = 0.0
    if id_brand and (id_brand & h_brand):
        score += 3.0                              # brand match is the strongest signal
    score += 0.5 * len(id_name & (h_brand | h_name))
    if id_size and h_qty:
        score += 2.0 if (id_size & h_qty) else -1.0  # reward/penalise size agreement
    return score


def _pick(identity, hits):
    """Return (best_hit, ambiguous). Ambiguous if the top match is weak or the top two are close."""
    if not hits:
        return None, False
    scored = sorted(((_score_hit(identity, h), h) for h in hits), key=lambda x: x[0], reverse=True)
    best_score, best = scored[0]
    ambiguous = best_score < 2.0
    if len(scored) > 1 and (best_score - scored[1][0]) < 1.0:
        ambiguous = True
    return best, ambiguous


def _bundle_from_record(prod, code, source, ambiguous=False) -> RetrievedBundle:
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
    return RetrievedBundle(canonical_name=canonical, category_tags=tags, price=price,
                           images=images, ambiguous=ambiguous)


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


# --------------------------- Serper.dev Google Shopping backend ---------------------------

_CURRENCY_SIGNS = [("CA$", "CAD"), ("C$", "CAD"), ("AU$", "AUD"), ("A$", "AUD"), ("US$", "USD"),
                   ("NZ$", "NZD"), ("€", "EUR"), ("£", "GBP"), ("¥", "JPY"), ("₹", "INR"), ("$", "USD")]


def _to_float(numstr):
    numstr = numstr.strip()
    if "," in numstr and "." in numstr:
        numstr = numstr.replace(",", "")                      # 1,234.56 -> 1234.56
    elif "," in numstr:                                       # comma-only
        numstr = numstr.replace(",", ".") if re.search(r",\d{2}$", numstr) else numstr.replace(",", "")
    try:
        return float(numstr)
    except ValueError:
        return None


def _parse_price(s):
    """Return (value, currency_code_or_None) from a price string like 'CA$21.99' or '19,99 €'.
    Detecting the real currency stops foreign-listing prices being shown under the wrong symbol."""
    txt = _as_text(s)
    currency = None
    up = txt.upper()
    for code in ("CAD", "USD", "EUR", "GBP", "AUD", "JPY", "INR", "NZD"):
        if code in up:
            currency = code
            break
    if currency is None:
        for sign, code in _CURRENCY_SIGNS:
            if sign in txt:
                currency = code
                break
    m = re.search(r"\d[\d.,]*", txt)
    return (_to_float(m.group()) if m else None), currency


def _search_shopping(query):
    """Serper.dev Google Shopping. Returns a list of shopping results."""
    r = requests.post(config.SERPER_SHOPPING_URL,
                      json={"q": query, "gl": config.SHOPPING_GL, "num": SEARCH_PAGE_SIZE},
                      timeout=config.HTTP_TIMEOUT,
                      headers={"X-API-KEY": config.SERPER_API_KEY, "Content-Type": "application/json"})
    r.raise_for_status()
    return r.json().get("shopping", [])


def _score_shopping(identity, item) -> float:
    id_all = _tokens(f"{identity.brand} {identity.product} {identity.variant} {identity.size}")
    id_brand = _tokens(identity.brand)
    id_size = _tokens(identity.size)
    t = _tokens(item.get("title"))
    score = 0.0
    if id_brand and (id_brand & t):
        score += 3.0
    score += 0.5 * len(id_all & t)
    if id_size and (id_size & t):
        score += 2.0
    if item.get("imageUrl"):
        score += 0.5
    # retailer preference: reputable retailers up, resale/marketplace sites down
    src = _as_text(item.get("source")).lower()
    if src and any(p in src for p in config.PREFERRED_SOURCES):
        score += 1.5
    elif src and any(d in src for d in config.DEMOTED_SOURCES):
        score -= 1.5
    # local-first: prefer prices already in a home currency (CAD/USD); penalise foreign listings
    _, cur = _parse_price(item.get("price"))
    if cur in config.PREFERRED_CURRENCIES:
        score += 1.0
    elif cur:
        score -= 1.5
    return score


def _pick_shopping(identity, items):
    if not items:
        return None, False
    scored = sorted(((_score_shopping(identity, it), it) for it in items),
                    key=lambda x: x[0], reverse=True)
    best_score, best = scored[0]
    ambiguous = best_score < 2.0
    if len(scored) > 1 and (best_score - scored[1][0]) < 1.0:
        ambiguous = True
    return best, ambiguous


def _bundle_from_shopping(item, ambiguous=False) -> RetrievedBundle:
    title = _as_text(item.get("title"))
    pv, cur = _parse_price(item.get("price"))
    if pv is None and item.get("priceValue") is not None:
        try:
            pv = float(item["priceValue"])
        except (TypeError, ValueError):
            pv = None
    src = _as_text(item.get("source"))
    if pv is not None:
        price = PriceInfo(currency=cur or config.CURRENCY, point=round(float(pv), 2),
                          basis="Google Shopping" + (f" ({src})" if src else ""))
    else:
        price = PriceInfo(currency=config.CURRENCY, basis="no price found")
    images = []
    img = _as_text(item.get("imageUrl"))
    if img:
        images.append(CandidateImage(url=img, licence="(retailer)", source="Google Shopping",
                                     match_score=0.0))
    return RetrievedBundle(canonical_name=title, category_tags=[], price=price,
                           images=images, ambiguous=ambiguous)


# --------------------------- barcode-first authoritative lookup ---------------------------

def _digits(s):
    return re.sub(r"\D", "", _as_text(s)).lstrip("0")


def _ecom_matches(prod, code) -> bool:
    """True if the EcomSource product actually carries the queried barcode. Guards against the
    API returning an unrelated product (as it can for codes it doesn't have)."""
    want = _digits(code)
    if not want:
        return True
    ids = {_digits(i.get("identifier")) for i in (prod.get("identifiers") or [])}
    opts = _ecom_summary(prod).get("options") or {}
    ids.add(_digits(opts.get("externally_assigned_product_identifier")))
    return want in ids


def _ecomsource(code):
    """EcomSource (api.ecomsource.ai) lookup by UPC/EAN. Returns the barcode-matching product, or
    None (including when the API returns an unrelated product). Note: /search/product has no price
    — price comes from the shopping backend or Open Prices."""
    digits = re.sub(r"\D", "", code or "")
    itype = "ean" if len(digits) == 13 else "upc"
    country = (config.SHOPPING_GL or "us").upper()
    r = requests.post(config.ECOMSOURCE_URL + "/search/product",
                      json={"identifier": code, "identifierType": itype,
                            "countryCode": country, "refresh": False},
                      timeout=config.HTTP_TIMEOUT,
                      headers={"X-Access-Key": config.ECOMSOURCE_ACCESS_KEY,
                               "X-Secret-Key": config.ECOMSOURCE_SECRET_KEY,
                               "Content-Type": "application/json"})
    r.raise_for_status()
    data = r.json()
    if isinstance(data, list):
        items = data
    elif isinstance(data, dict):
        items = data.get("products") or data.get("data") or data.get("results") or [data]
    else:
        items = []
    for prod in items:
        if isinstance(prod, dict) and _ecom_matches(prod, code):
            return prod
    return None


def _ecom_summary(prod) -> dict:
    s = prod.get("summary")
    if isinstance(s, list) and s:
        return s[0] or {}
    return s if isinstance(s, dict) else {}


def _ecom_image(prod) -> str:
    for container in (prod.get("images"), _ecom_summary(prod).get("images")):
        for im in (container or []):
            if isinstance(im, str) and im.startswith("http"):
                return im
            if isinstance(im, dict):
                u = im.get("link") or im.get("url") or im.get("imageUrl") or im.get("hiRes")
                if u:
                    return _as_text(u)
    return _as_text(prod.get("mainImage") or _ecom_summary(prod).get("mainImage"))


def _barcode_record(code):
    """Authoritative product record by barcode: Open Food Facts, then Open Products Facts, then
    EcomSource (if keys are set). Returns (record, source) or (None, None)."""
    for product_url, source in ((config.OFF_PRODUCT_URL, "Open Food Facts"),
                                (config.OPF_PRODUCT_URL, "Open Products Facts")):
        try:
            prod = _by_barcode(product_url, code)
            if prod:
                return prod, source
        except Exception as e:
            print(f"[retrieve] {source} barcode lookup failed: {e}", file=sys.stderr)
    if config.ECOMSOURCE_ACCESS_KEY and config.ECOMSOURCE_SECRET_KEY:
        try:
            prod = _ecomsource(code)
            if prod:
                return prod, "EcomSource"
        except Exception as e:
            print(f"[retrieve] EcomSource lookup failed: {e}", file=sys.stderr)
    return None, None


def _exact_name(prod, source) -> str:
    """Exact product name from a barcode record (used to drive a precise shopping search)."""
    if source == "EcomSource":
        summ = _ecom_summary(prod)
        brand = _as_text(summ.get("brand"))
        title = _as_text(summ.get("itemName"))
    else:
        brand = _first_brand(prod.get("brands"))
        title = _as_text(prod.get("product_name")) or _as_text(prod.get("generic_name"))
        qty = _as_text(prod.get("quantity"))
        if qty and qty.lower() not in title.lower():
            title = f"{title} {qty}".strip()
    name = title.strip()
    if brand and brand.lower() not in name.lower():
        name = f"{brand} {name}".strip()
    return name


def _bundle_from_ecomsource(prod, ambiguous=False) -> RetrievedBundle:
    summ = _ecom_summary(prod)
    brand = _as_text(summ.get("brand"))
    name = _as_text(summ.get("itemName"))
    canonical = name if (not brand or brand.lower() in name.lower()) else f"{brand} {name}".strip()
    tags = [_as_text(summ.get(k)) for k in
            ("classification1", "classification2", "classification3", "classification4")
            if summ.get(k)]
    lp = summ.get("listPrice")
    cur = _as_text(summ.get("listPriceCurrency")).upper() or None
    price = PriceInfo(currency=config.CURRENCY, basis="no price found")
    if lp is not None:
        try:
            price = PriceInfo(currency=cur or config.CURRENCY, point=round(float(lp), 2),
                              basis="EcomSource (Amazon)")
        except (TypeError, ValueError):
            pass
    images = []
    img = _ecom_image(prod)
    if img:
        images.append(CandidateImage(url=img, licence="(retailer)", source="EcomSource",
                                     match_score=0.0))
    return RetrievedBundle(canonical_name=canonical or name, category_tags=tags,
                           price=price, images=images, ambiguous=ambiguous)


def _bundle_from_barcode(prod, source, code) -> RetrievedBundle:
    if source == "EcomSource":
        return _bundle_from_ecomsource(prod)
    return _bundle_from_record(prod, code, source)


def retrieve(identity) -> RetrievedBundle:
    code = identity.barcode

    # 1) Barcode-first: authoritative record (OFF -> OPF -> EcomSource) -> exact product name.
    bc_prod, bc_source = (_barcode_record(code) if code else (None, None))
    exact = _exact_name(bc_prod, bc_source) if bc_prod else ""

    # 2) Shopping backend: search by the EXACT barcode name (or the full label) -> better image + price.
    if config.RETRIEVE_BACKEND == "shopping" and config.SERPER_API_KEY:
        shop_q = exact or _full_query(identity)
        if shop_q:
            try:
                items = _search_shopping(shop_q)   # single call = one credit
            except Exception as e:
                print(f"[retrieve] shopping search failed ({shop_q!r}): {e}", file=sys.stderr)
                items = []
            best, ambiguous = _pick_shopping(identity, items)
            if best:
                bundle = _bundle_from_shopping(best, ambiguous)
                if exact:
                    bundle.canonical_name = exact   # trust the barcode-derived exact name
                return bundle
        if bc_prod:                                  # shopping missed, but the barcode record stands
            return _bundle_from_barcode(bc_prod, bc_source, code)
        print("[retrieve] shopping: no hit; using offline bundle", file=sys.stderr)
        return _offline_bundle(identity)

    # 3) OFF/OPF backend: use the barcode record if we have one ...
    if bc_prod:
        return _bundle_from_barcode(bc_prod, bc_source, code)

    # ... otherwise name search: OFF Search-a-licious (relaxed) then OPF legacy.
    query = _search_query(identity)
    if query:
        for q in _relaxed(query):
            try:
                hits = _search_off(q)
            except Exception as e:
                print(f"[retrieve] OFF search failed ({q!r}): {e}", file=sys.stderr)
                break  # an API error (e.g. 503) won't be fixed by relaxing the query
            best, ambiguous = _pick(identity, hits)
            if best:
                return _bundle_from_record(best, best.get("code"), "Open Food Facts", ambiguous)
        try:
            best, ambiguous = _pick(identity, _search_legacy(config.OPF_SEARCH_URL, query))
            if best:
                return _bundle_from_record(best, best.get("code"), "Open Products Facts", ambiguous)
        except Exception as e:
            print(f"[retrieve] OPF search unavailable: {e}", file=sys.stderr)

    print("[retrieve] no catalogue hit; using offline bundle", file=sys.stderr)
    return _offline_bundle(identity)
