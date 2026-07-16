"""Image match / upgrade.

Decide whether a retrieved catalogue image depicts the SAME product as the shelf photo, so we
only swap in a cleaner image when we're confident. Preferred backend is OpenCLIP cosine
similarity; if torch/open_clip aren't installed we fall back to a perceptual-hash (imagehash)
similarity, which is lightweight and CPU-only. A wrong swap is worse than keeping the original,
so the threshold gates adoption.
"""
import io
import os
from dataclasses import asdict

import requests

from .. import config, trace, providers
from ..config import IMAGE_MATCH_THRESHOLD, HTTP_TIMEOUT, USER_AGENT

_clip = None  # lazy cache: (model, preprocess, tokenizer) or False


def _load_image(ref: str):
    from PIL import Image
    if ref.startswith("http"):
        r = requests.get(ref, timeout=HTTP_TIMEOUT, headers={"User-Agent": USER_AGENT})
        r.raise_for_status()
        return Image.open(io.BytesIO(r.content)).convert("RGB")
    return Image.open(ref).convert("RGB")


def _clip_score(a, b) -> float:
    global _clip
    if _clip is None:
        try:
            import open_clip, torch  # noqa: F401
            model, _, prep = open_clip.create_model_and_transforms(
                "ViT-B-32", pretrained="laion2b_s34b_b79k")
            _clip = (model.eval(), prep, __import__("torch"))
        except Exception:
            _clip = False
    if not _clip:
        raise RuntimeError("clip unavailable")
    model, prep, torch = _clip
    with torch.no_grad():
        ia = model.encode_image(prep(a).unsqueeze(0))
        ib = model.encode_image(prep(b).unsqueeze(0))
        ia /= ia.norm(dim=-1, keepdim=True)
        ib /= ib.norm(dim=-1, keepdim=True)
        return float((ia @ ib.T).item())


def _hash_score(a, b) -> float:
    import imagehash
    ha, hb = imagehash.phash(a), imagehash.phash(b)
    bits = len(ha.hash) ** 2
    return 1.0 - (ha - hb) / bits  # 1.0 = identical


def match_score(original_path: str, candidate_ref: str) -> float:
    """Similarity in 0..1 between the shelf photo and a candidate image (URL or path)."""
    try:
        a, b = _load_image(original_path), _load_image(candidate_ref)
    except Exception:
        return 0.0
    try:
        return _clip_score(a, b)
    except Exception:
        try:
            return _hash_score(a, b)
        except Exception:
            return 0.0


def choose_image(original_path, bundle, threshold: float = IMAGE_MATCH_THRESHOLD):
    """Return (image_ref, swapped). Adopt the best retrieved catalogue image when it confidently
    matches the same SKU (score >= threshold), or unconditionally in demo mode
    (SNAP_ALWAYS_SWAP); otherwise keep the original photo."""
    best_ref, best = None, 0.0
    for cand in bundle.images:
        sc = match_score(original_path, cand.url)
        cand.match_score = sc
        if sc >= best:
            best_ref, best = cand.url, sc
    if best_ref and (config.ALWAYS_SWAP or best >= threshold):
        return best_ref, True
    return original_path, False


# --------------------------- enhancement + quality gate ---------------------------

def enhance_image(path):
    """Clean the user's OWN photo into a catalogue-style image via background removal
    (white background). Returns the new path, or None if rembg isn't installed / fails —
    so the pipeline never breaks."""
    try:
        from rembg import remove
        from PIL import Image
    except Exception:
        return None
    try:
        cut = remove(Image.open(path).convert("RGBA"))          # transparent background
        bg = Image.new("RGBA", cut.size, (255, 255, 255, 255))
        comp = Image.alpha_composite(bg, cut).convert("RGB")
        stem = os.path.splitext(path)[0]
        if stem.endswith(".norm"):
            stem = stem[:-len(".norm")]
        out = stem + ".clean.png"
        comp.save(out)
        return out
    except Exception:
        return None


def _quality(ref):
    """(megapixels, sharpness) for an image ref, or None. Sharpness = variance of Laplacian."""
    try:
        img = _load_image(ref)
    except Exception:
        return None
    import numpy as np
    w, h = img.size
    arr = np.asarray(img.convert("L"), dtype="float64")
    try:
        import cv2
        sharp = float(cv2.Laplacian(arr.astype("uint8"), cv2.CV_64F).var())
    except Exception:
        gx, gy = np.diff(arr, axis=1), np.diff(arr, axis=0)
        sharp = float(gx.var() + gy.var())
    return (w * h) / 1e6, sharp


def _is_better(candidate_ref, base_path, margin=0.95):
    """True only if the candidate is at least as good as the base on BOTH resolution and
    sharpness (so we never downgrade to a grainier catalogue image)."""
    cq, bq = _quality(candidate_ref), _quality(base_path)
    if not cq or not bq:
        return False
    return cq[0] >= bq[0] * margin and cq[1] >= bq[1] * margin


def _llm_select(original_path, bundle, identity):
    """LLM same-SKU judge over the top-K retrieved candidates. Returns (ref, confidence, reason)
    for the first candidate the model confirms is the same product at >= the confidence floor,
    else (None, 0.0, ""). Raises NoProviderError only if the model is unreachable (offline)."""
    ident = asdict(identity) if (identity is not None and not isinstance(identity, dict)) else identity
    for cand in bundle.images[:config.LLM_MATCH_TOPK]:
        try:
            v = providers.verify_same_product(original_path, cand.url, ident)
        except providers.NoProviderError:
            raise
        except Exception as e:  # noqa: BLE001 — candidate image failed to fetch/parse; skip it
            trace.log("IMAGE", f"LLM verify skipped ({type(e).__name__}) for {str(cand.url)[:70]}")
            continue
        cand.match_score = v["confidence"]
        cand.match_reason = v["reason"]
        trace.log("IMAGE", f"LLM same-SKU: {v['same_product']} conf={v['confidence']:.2f}",
                  {"url": cand.url, "reason": v["reason"]})
        if v["same_product"] and v["confidence"] >= config.LLM_MATCH_MIN_CONF:
            return cand.url, v["confidence"], v["reason"]
    return None, 0.0, ""


def _numeric_select(original_path, bundle):
    """Fallback same-SKU gate: OpenCLIP/phash similarity vs the match threshold (used offline or
    when SNAP_IMAGE_MATCH_LLM is disabled)."""
    best_ref, best = None, 0.0
    for cand in bundle.images:
        sc = match_score(original_path, cand.url)
        cand.match_score = sc
        if sc >= best:
            best_ref, best = cand.url, sc
    if best_ref and (config.ALWAYS_SWAP or best >= IMAGE_MATCH_THRESHOLD):
        return best_ref, best, "numeric similarity"
    return None, best, ""


def _select_candidate(original_path, bundle, identity):
    """Pick an adoptable same-SKU catalogue image (or None). Prefers the LLM judge; falls back to
    the numeric gate offline or when the LLM is disabled. When the LLM runs and rejects every
    candidate, that verdict is authoritative (we do NOT fall through to the brittle numeric gate)."""
    if not bundle.images:
        return None, 0.0, ""
    if config.IMAGE_MATCH_LLM and config.active_provider():
        try:
            return _llm_select(original_path, bundle, identity)
        except providers.NoProviderError:
            pass  # became offline mid-run -> numeric fallback
    return _numeric_select(original_path, bundle)


def select_image(original_path, bundle, identity=None):
    """Return (image_ref, swapped, enhanced) per config.IMAGE_MODE:
      - "off":     keep the original photo.
      - "swap":    adopt a same-SKU catalogue image whenever the match gate confirms one.
      - "enhance": clean the user's own photo; adopt an external image only if it is also a
                   confirmed match AND not lower quality (so we never downgrade a good photo).
    Same-SKU confirmation uses the vision LLM when available (see _select_candidate).
    """
    mode = config.IMAGE_MODE
    candidate, score, reason = _select_candidate(original_path, bundle, identity)
    trace.log("IMAGE", f"mode={mode}; candidate={'adoptable' if candidate else 'none'}; "
              f"score={round(score, 3)}; {reason}",
              [{"source": c.source, "url": c.url, "match_score": round(c.match_score, 3),
                "reason": c.match_reason} for c in bundle.images] or None)

    if mode == "off":
        return original_path, False, False

    if mode == "swap":
        # In swap mode the user wants the catalogue image: a confirmed same-SKU match is enough.
        if candidate:
            trace.log("IMAGE", "swap mode: adopted confirmed same-SKU catalogue image")
            return candidate, True, False
        trace.log("IMAGE", "swap mode: kept original photo (no confirmed match)")
        return original_path, False, False

    # default: "enhance" — keep the owner's (cleaned) photo unless a confirmed match is also better.
    cleaned = enhance_image(original_path)
    trace.log("IMAGE", "enhance mode: cleaned own photo = "
              f"{cleaned or 'unavailable (rembg not installed) -> kept normalized photo'}")
    base = cleaned or original_path
    if candidate and (config.ALWAYS_SWAP or _is_better(candidate, base)):
        trace.log("IMAGE", "enhance mode: confirmed match beat own photo -> swapped")
        return candidate, True, bool(cleaned)
    return base, False, bool(cleaned)
