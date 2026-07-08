import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from src.snap_to_sell.pipeline import run                       # noqa: E402
from src.snap_to_sell.interfaces import (                        # noqa: E402
    ValidatedListing, ProductIdentity, RetrievedBundle, DraftListing, PriceInfo, Flags)
from src.snap_to_sell.guardrails import apply                    # noqa: E402
from src.snap_to_sell import providers                           # noqa: E402


def test_pipeline_runs_end_to_end():
    v = run("data/testset/sample.jpg")
    assert isinstance(v, ValidatedListing)
    assert v.listing.title, "listing should have a title"
    assert v.compliance_status in {"clear", "flagged"}


def test_guardrails_flag_tobacco():
    ident = ProductIdentity(product="Cigarettes", category="tobacco", confidence=0.9)
    bundle = RetrievedBundle(canonical_name="Cigarettes", category_tags=["tobacco"])
    draft = DraftListing(identity=ident, title="Cigarettes", description="Cigarettes.")
    v = apply(draft, ident, bundle)
    assert v.listing.flags.age_restricted
    assert v.compliance_status == "flagged"


def test_guardrails_flag_hallucinated_number():
    ident = ProductIdentity(product="Chocolate Bar", category="confectionery",
                            size="45 g", confidence=0.9)
    bundle = RetrievedBundle(canonical_name="Chocolate Bar 45 g",
                             category_tags=["confectionery"])
    # description invents "90 g" which is not in the source facts
    draft = DraftListing(identity=ident, title="Chocolate Bar",
                         description="Delicious 90 g chocolate bar.")
    v = apply(draft, ident, bundle)
    assert v.listing.flags.unverifiable_claims, "should flag the invented 90 g"


def test_provider_offline_raises():
    # with no key configured, the provider must signal NoProviderError (not crash)
    if not providers.config.active_provider():
        try:
            providers.vlm_identify("data/testset/sample.jpg")
            assert False, "expected NoProviderError"
        except providers.NoProviderError:
            pass


if __name__ == "__main__":
    test_pipeline_runs_end_to_end()
    test_guardrails_flag_tobacco()
    test_guardrails_flag_hallucinated_number()
    test_provider_offline_raises()
    print("all tests passed")
