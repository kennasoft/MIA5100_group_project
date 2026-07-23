"""LLM same-SKU image-match gate (imagematch.match). Uses a stubbed provider so no network or
API key is touched — verifies the gate logic, the confidence floor, and the offline fallback."""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from src.snap_to_sell import config, providers                 # noqa: E402
from src.snap_to_sell.imagematch import match as M              # noqa: E402
from src.snap_to_sell.interfaces import (                        # noqa: E402
    RetrievedBundle, CandidateImage, ProductIdentity)


def _bundle(*urls):
    return RetrievedBundle(images=[CandidateImage(url=u, source="test") for u in urls])


def _online(monkeypatch, verifier):
    """Force an active provider and stub the LLM verifier."""
    monkeypatch.setattr(config, "OPENAI_API_KEY", "sk-test")
    monkeypatch.setattr(config, "LLM_PROVIDER", "openai")
    monkeypatch.setattr(config, "IMAGE_MATCH_LLM", True)
    monkeypatch.setattr(config, "LLM_MATCH_MIN_CONF", 0.7)
    monkeypatch.setattr(config, "LLM_MATCH_TOPK", 2)
    monkeypatch.setattr(providers, "verify_same_product", verifier)


def test_llm_accepts_same_sku_and_records_reason(monkeypatch):
    seen = {"n": 0}

    def verify(photo, cand, identity=None):
        seen["n"] += 1
        if seen["n"] == 1:
            return {"same_product": False, "confidence": 0.95, "reason": "different brand"}
        return {"same_product": True, "confidence": 0.86, "reason": "same brand/variant/size"}

    _online(monkeypatch, verify)
    b = _bundle("urlA", "urlB")
    ref, score, reason = M._select_candidate("photo.jpg", b, ProductIdentity(product="X"))
    assert ref == "urlB" and score == 0.86 and "same" in reason
    assert b.images[0].match_reason == "different brand"        # rejection is recorded too


def test_llm_confidence_floor(monkeypatch):
    _online(monkeypatch, lambda p, c, identity=None:
            {"same_product": True, "confidence": 0.5, "reason": "unsure"})
    ref, _, _ = M._select_candidate("photo.jpg", _bundle("u"), None)
    assert ref is None                                           # below LLM_MATCH_MIN_CONF -> no swap


def test_offline_uses_numeric_fallback(monkeypatch):
    # No provider configured -> LLM path skipped, numeric gate used, never raises.
    monkeypatch.setattr(config, "OPENAI_API_KEY", "")
    monkeypatch.setattr(config, "ANTHROPIC_API_KEY", "")
    monkeypatch.setattr(config, "GEMINI_API_KEY", "")
    monkeypatch.setattr(config, "LLM_PROVIDER", "")
    assert config.active_provider() == ""
    ref, score, reason = M._select_candidate("/nope.jpg", _bundle("/also-nope.jpg"), None)
    assert ref is None                                          # unreadable images -> no match, no crash
