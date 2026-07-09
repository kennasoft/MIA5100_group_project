"""End-to-end orchestration photo -> validated listing.

Runs real stages when configured (hosted model + Open Food Facts), and degrades gracefully to
offline behaviour otherwise, so it always produces a ValidatedListing.
"""
import sys
import json
from dataclasses import asdict

from .capture import preprocess
from .recognise import recognise
from .retrieve import retrieve
from .generate import generate
from .imagematch import select_image
from .guardrails import apply
from . import config


def run(image_path: str):
    clean = preprocess(image_path)
    identity = recognise(clean)
    bundle = retrieve(identity)
    draft = generate(identity, bundle)
    img_ref, swapped, enhanced = select_image(clean, bundle)
    draft.image_url = img_ref
    draft.flags.image_swapped = swapped
    draft.flags.image_enhanced = enhanced
    return apply(draft, identity, bundle)


if __name__ == "__main__":
    path = sys.argv[1] if len(sys.argv) > 1 else "data/testset/sample.jpg"
    prov = config.active_provider() or "offline (no API key)"
    print(f"[pipeline] provider: {prov}", file=sys.stderr)
    validated = run(path)
    print(json.dumps(asdict(validated), indent=2, default=str))
