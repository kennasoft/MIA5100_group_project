"""Recognise.

Primary path: hosted multimodal model (providers.vlm_identify) reads the packaging and returns
a structured identity. Offline fallback: an optional sidecar '<image>.json' next to the photo
(a hand-labelled stand-in used for demos/eval without an API key); failing that, a low-confidence
'unknown' identity so the pipeline still runs.
"""
import json
import os
import sys

from ..interfaces import ProductIdentity
from .. import providers, config

_FIELDS = {"brand", "product", "variant", "size", "category",
           "ocr_text", "barcode", "confidence", "catalogue_image_url"}


def _from_dict(d: dict) -> ProductIdentity:
    clean = {k: d.get(k) for k in _FIELDS if d.get(k) is not None}
    try:
        clean["confidence"] = float(clean.get("confidence", 0.0))
    except (TypeError, ValueError):
        clean["confidence"] = 0.0
    return ProductIdentity(**clean)


def _sidecar_path(image_path: str):
    stem, _ = os.path.splitext(image_path)
    if stem.endswith(".norm"):          # strip preprocess suffix
        stem = stem[:-len(".norm")]
    return stem + ".json"


def recognise(image_path: str) -> ProductIdentity:
    # 1) hosted provider (real recognition)
    try:
        return _from_dict(providers.vlm_identify(image_path))
    except providers.NoProviderError:
        pass
    except Exception as e:  # provider/network error -> degrade, don't crash
        print(f"[recognise] provider failed, falling back: {e}", file=sys.stderr)

    # Provider-only mode: skip the sidecar so a wrong result proves inference failed.
    if config.STRICT_PROVIDER:
        return ProductIdentity(product="unknown", category="other", confidence=0.0)

    # 2) offline sidecar label (demo / eval without a key)
    side = _sidecar_path(image_path)
    if os.path.exists(side):
        with open(side) as f:
            ident = _from_dict(json.load(f))
        if not ident.confidence:
            ident.confidence = 0.5
        return ident

    # 3) last resort
    return ProductIdentity(product="unknown", category="other", confidence=0.0)
