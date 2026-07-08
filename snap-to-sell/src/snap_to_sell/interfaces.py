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


@dataclass
class RetrievedBundle:
    canonical_name: str = ""
    category_tags: List[str] = field(default_factory=list)
    price: PriceInfo = field(default_factory=PriceInfo)
    images: List[CandidateImage] = field(default_factory=list)


@dataclass
class Flags:
    age_restricted: bool = False
    low_confidence: bool = False
    unverifiable_claims: List[str] = field(default_factory=list)
    image_swapped: bool = False


@dataclass
class DraftListing:
    identity: ProductIdentity
    title: str = ""
    description: str = ""
    price: PriceInfo = field(default_factory=PriceInfo)
    image_url: str = ""
    flags: Flags = field(default_factory=Flags)


@dataclass
class ValidatedListing:
    listing: DraftListing
    compliance_status: str = "pending"  # "clear" | "flagged"
    needs_review: bool = True
