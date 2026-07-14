"""End-to-end orchestration photo -> validated listing.

Runs real stages when configured (hosted model + Open Food Facts), and degrades gracefully to
offline behaviour otherwise, so it always produces a ValidatedListing. When SNAP_LOG is on
(default), a detailed <image-name>-log.txt is written next to the image capturing every stage's
output — the raw model responses, retrieval queries and rankings, and the image/price/guardrail
decisions — so you can see exactly how the final result was reached.
"""
import os
import sys
import json
from dataclasses import asdict

from .capture import preprocess
from .recognise import recognise
from .retrieve import retrieve
from .generate import generate
from .imagematch import select_image
from .guardrails import apply
from . import config, trace


def _log_path(image_path: str) -> str:
    stem = os.path.splitext(os.path.basename(image_path))[0]
    return os.path.join(os.path.dirname(image_path), f"{stem}-log.txt")


def _config_snapshot() -> dict:
    return {
        "provider": config.active_provider() or "offline",
        "openai_model": config.OPENAI_MODEL,
        "strict_provider": config.STRICT_PROVIDER,
        "retrieve_backend": config.RETRIEVE_BACKEND,
        "barcode_source": config.BARCODE_SOURCE,
        "image_mode": config.IMAGE_MODE,
        "always_swap": config.ALWAYS_SWAP,
        "shopping_gl": config.SHOPPING_GL,
        "preferred_currencies": config.PREFERRED_CURRENCIES,
    }


def _run(image_path: str):
    trace.log("CONFIG", "settings for this run", _config_snapshot())
    clean = preprocess(image_path)
    trace.log("CAPTURE", f"normalised image -> {clean}")
    identity = recognise(clean)
    trace.log("RECOGNISE", "final identity", identity)
    bundle = retrieve(identity)
    trace.log("RETRIEVE", "final bundle", bundle)
    draft = generate(identity, bundle)
    trace.log("GENERATE", "draft listing",
              {"title": draft.title, "description": draft.description, "price": asdict(draft.price)})
    img_ref, swapped, enhanced = select_image(clean, bundle)
    draft.image_url = img_ref
    draft.flags.image_swapped = swapped
    draft.flags.image_enhanced = enhanced
    trace.log("IMAGE", f"mode={config.IMAGE_MODE} swapped={swapped} enhanced={enhanced}",
              {"image_used": img_ref})
    validated = apply(draft, identity, bundle)
    trace.log("GUARDRAILS", f"compliance={validated.compliance_status}",
              asdict(validated.listing.flags))
    return validated


def run(image_path: str, write_log=None):
    """Run the pipeline. Writes <image>-log.txt when logging is on (SNAP_LOG, default enabled)."""
    do_log = config.LOG_ENABLED if write_log is None else write_log
    if not do_log:
        return _run(image_path)
    trace.start(f"image = {image_path}")
    try:
        validated = _run(image_path)
        trace.log("RESULT", "validated listing (the final output shown to the user)", validated)
        return validated
    finally:
        trace.dump(_log_path(image_path))
        trace.stop()


if __name__ == "__main__":
    path = sys.argv[1] if len(sys.argv) > 1 else "data/testset/sample.jpg"
    print(f"[pipeline] provider: {config.active_provider() or 'offline (no API key)'}", file=sys.stderr)
    validated = run(path)
    if config.LOG_ENABLED:
        print(f"[pipeline] trace log -> {_log_path(path)}", file=sys.stderr)
    print(json.dumps(asdict(validated), indent=2, default=str))
