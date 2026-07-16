"""Frozen data contract between pipeline stages.

Change only with team agreement: everyone builds against these shapes.
"""
from dataclasses import dataclass, field
from typing import Optional, List


@dataclass
class ProductIdentity:
    brand: str = ""
    product: str = ""
    variant: str = ""
    size: str = ""
    category: str = ""
    ocr_text: str = ""
    barcode: Optional[str] = None
    confidence: float = 0.0
    search_query: str = ""  # short brand+product+size query for retrieval (not the rich label)
    catalogue_image_url: Optional[str] = None  # optional: force a demo catalogue image (offline)


@dataclass
class PriceInfo:
    currency: str = "CAD"
    point: Optional[float] = None
    low: Optional[float] = None
    high: Optional[float] = None
    basis: str = ""  # e.g. "open_prices median (n=3)"


@dataclass
class CandidateImage:
    url: str = ""
    licence: str = ""
    source: str = ""
    match_score: float = 0.0
    match_reason: str = ""  # why the same-SKU judge (LLM) accepted/rejected this image


@dataclass
class RankedCandidate:
    """A retrieval candidate considered during the pick, kept for reporting/audit."""
    title: str = ""
    price: Optional[float] = None       # listing price as shown by the retailer
    currency: str = ""
    source: str = ""
    image_url: str = ""
    category: str = ""
    score: float = 0.0                  # ranking score used to choose
    detail: str = ""                    # human note: pack/retailer/currency signals
    chosen: bool = False                # True for the candidate actually adopted


@dataclass
class RetrievedBundle:
    canonical_name: str = ""
    category_tags: List[str] = field(default_factory=list)
    price: PriceInfo = field(default_factory=PriceInfo)
    images: List[CandidateImage] = field(default_factory=list)
    ambiguous: bool = False  # several close/weak search hits -> pick uncertain, route to review
    candidates: List[RankedCandidate] = field(default_factory=list)  # top ranked hits (for reporting)


@dataclass
class Flags:
    age_restricted: bool = False
    low_confidence: bool = False
    unverifiable_claims: List[str] = field(default_factory=list)
    image_swapped: bool = False      # adopted an external catalogue image
    image_enhanced: bool = False     # cleaned the user's own photo (background removal)
    retrieval_ambiguous: bool = False  # catalogue match was uncertain (several close/weak hits)


@dataclass
class DraftListing:
    identity: ProductIdentity
    title: str = ""
    description: str = ""
    price: PriceInfo = field(default_factory=PriceInfo)
    image_url: str = ""
    flags: Flags = field(default_factory=Flags)
    candidates: List[RankedCandidate] = field(default_factory=list)  # retrieval candidates considered


@dataclass
class ValidatedListing:
    listing: DraftListing
    compliance_status: str = "pending"  # "clear" | "flagged"
    needs_review: bool = True
