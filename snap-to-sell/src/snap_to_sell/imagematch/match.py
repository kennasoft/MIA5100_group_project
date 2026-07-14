"""Image match / upgrade.

Decide whether a retrieved catalogue image depicts the SAME product as the shelf photo, so we
only swap in a cleaner image when we're confident. Preferred backend is OpenCLIP cosine
similarity; if torch/open_clip aren't installed we fall back to a perceptual-hash (imagehash)
similarity, which is lightweight and CPU-only. A wrong swap is worse than keeping the original,
so the threshold gates adoption.
"""
import io
import os

import requests

from .. import config
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


def select_image(original_path, bundle):
    """Return (image_ref, swapped, enhanced) per config.IMAGE_MODE:
      - "off":     keep the original photo.
      - "swap":    adopt the retrieved catalogue image only if it matches and is not worse.
      - "enhance": clean the user's own photo; adopt an external image only if it beats it.
    """
    mode = config.IMAGE_MODE
    # best retrieved candidate that clears the same-SKU match gate (or the demo override)
    best_ref, best = None, 0.0
    for cand in bundle.images:
        sc = match_score(original_path, cand.url)
        cand.match_score = sc
        if sc >= best:
            best_ref, best = cand.url, sc
    candidate = best_ref if (best_ref and (config.ALWAYS_SWAP or best >= IMAGE_MATCH_THRESHOLD)) else None

    if mode == "off":
        return original_path, False, False

    if mode == "swap":
        if candidate and (config.ALWAYS_SWAP or _is_better(candidate, original_path)):
            return candidate, True, False
        return original_path, False, False

    # default: "enhance"
    cleaned = enhance_image(original_path)
    base = cleaned or original_path
    if candidate and (config.ALWAYS_SWAP or _is_better(candidate, base)):
        return candidate, True, bool(cleaned)
    return base, False, bool(cleaned)
