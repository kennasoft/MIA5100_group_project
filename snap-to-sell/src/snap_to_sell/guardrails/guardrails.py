"""Guardrails.

Three real checks before a listing reaches human review:
  1. Age-restriction: tobacco/alcohol flagged from identity + retrieved category tags.
  2. Confidence: low-confidence recognition routed to review.
  3. Claim grounding: numeric/spec tokens in the generated description that are NOT supported
     by the identity or retrieved attributes are flagged as potentially hallucinated.
Any flag sets compliance_status='flagged'; human review is always required.
"""
import re

from ..interfaces import ValidatedListing
from ..config import CONFIDENCE_THRESHOLD

AGE_RESTRICTED = {"tobacco", "cigarette", "cigarettes", "cigar", "cigars",
                  "vape", "vaping", "e-cigarette", "e-liquid", "nicotine",
                  "alcohol", "alcoholic", "beer", "wine", "spirits"}

_NUM_TOKEN = re.compile(r"\b\d[\d.,]*\s?(?:g|kg|mg|ml|l|%|oz|pack|x)?\b", re.I)


def _is_age_restricted(identity, bundle) -> bool:
    text = " ".join([identity.category] + list(bundle.category_tags)).lower()
    return any(k in text for k in AGE_RESTRICTED)


def _unverifiable_claims(listing, identity, bundle):
    """Flag numeric/spec tokens in the description not present in the source facts."""
    supported = " ".join([
        identity.brand, identity.product, identity.variant, identity.size,
        identity.ocr_text, bundle.canonical_name, " ".join(bundle.category_tags),
    ]).lower()
    supported_nums = set(re.sub(r"\s", "", m.group()) for m in _NUM_TOKEN.finditer(supported))
    flagged = []
    for m in _NUM_TOKEN.finditer((listing.description or "").lower()):
        tok = re.sub(r"\s", "", m.group())
        if tok and tok not in supported_nums:
            flagged.append(m.group().strip())
    return sorted(set(flagged))


def apply(listing, identity, bundle,
          confidence_threshold: float = CONFIDENCE_THRESHOLD) -> ValidatedListing:
    listing.flags.age_restricted = _is_age_restricted(identity, bundle)
    listing.flags.low_confidence = identity.confidence < confidence_threshold
    listing.flags.unverifiable_claims = _unverifiable_claims(listing, identity, bundle)

    flagged = (listing.flags.age_restricted or listing.flags.low_confidence
               or bool(listing.flags.unverifiable_claims))
    return ValidatedListing(
        listing=listing,
        compliance_status="flagged" if flagged else "clear",
        needs_review=True,  # human-in-the-loop always
    )
