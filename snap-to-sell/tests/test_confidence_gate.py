"""Price confidence gate: the shopping path declines to price a match (routing to review) when
it is ambiguous or the recognised brand can't be confirmed in the chosen listing title."""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import importlib
R = importlib.import_module("src.snap_to_sell.retrieve.retrieve")
from src.snap_to_sell import config                          # noqa: E402
from src.snap_to_sell.interfaces import ProductIdentity      # noqa: E402


def test_brand_confirmed_helper():
    assert R._brand_confirmed(ProductIdentity(brand="Heinz"), "Heinz Tomato Ketchup 1.5 L")
    assert not R._brand_confirmed(ProductIdentity(brand="Heinz"), "Aqua Marina Kayak")
    assert not R._brand_confirmed(ProductIdentity(brand=""), "Some Random Product")  # unbranded


def test_gate_suppresses_price_on_brand_mismatch(monkeypatch):
    monkeypatch.setattr(config, "PRICE_CONFIDENCE_GATE", True)
    monkeypatch.setattr(config, "SERPER_API_KEY", "k")
    monkeypatch.setattr(config, "RETRIEVE_BACKEND", "shopping")
    # a garbage result set for an unbranded query
    monkeypatch.setattr(R, "_search_shopping",
                        lambda q: [{"title": "Aqua Marina Kayak", "source": "Amazon", "price": "$599.99", "imageUrl": "x"}])
    monkeypatch.setattr(R, "_barcode_record", lambda code: (None, None))
    idy = ProductIdentity(product="Cream Crackers", size="200 g", search_query="cream crackers")
    b = R.retrieve(idy)
    assert b.price.point is None                              # declined to price
    assert b.ambiguous
    assert "declined" in b.price.basis


def test_gate_allows_confirmed_brand(monkeypatch):
    monkeypatch.setattr(config, "PRICE_CONFIDENCE_GATE", True)
    monkeypatch.setattr(config, "SERPER_API_KEY", "k")
    monkeypatch.setattr(config, "RETRIEVE_BACKEND", "shopping")
    monkeypatch.setattr(R, "_search_shopping",
                        lambda q: [{"title": "Heinz Tomato Ketchup 1.5 L", "source": "Walmart", "price": "$6.99", "imageUrl": "x"}])
    monkeypatch.setattr(R, "_barcode_record", lambda code: (None, None))
    idy = ProductIdentity(brand="Heinz", product="Tomato Ketchup", size="1.5 L", search_query="Heinz ketchup 1.5 L")
    b = R.retrieve(idy)
    assert b.price.point == 6.99                              # confirmed brand -> price kept
