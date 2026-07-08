"""Image match / upgrade.

Decide whether a retrieved catalogue image depicts the SAME product as the shelf photo, so we
only swap in a cleaner image when we're confident. Preferred backend is OpenCLIP cosine
similarity; if torch/open_clip aren't installed we fall back to a perceptual-hash (imagehash)
similarity, which is lightweight and CPU-only. A wrong swap is worse than keeping the original,
so the threshold gates adoption.
"""
import io

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
