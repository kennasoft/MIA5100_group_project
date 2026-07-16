"""Pack/case awareness in shopping retrieval: detect multipacks, down-rank them for single-unit
queries, and normalise an adopted pack price to per-unit — WITHOUT corrupting genuine single
units (a box of '150 count' bags or '20 tea bags' is one retail unit, not a multipack)."""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import importlib
R = importlib.import_module("src.snap_to_sell.retrieve.retrieve")  # module, not the re-exported fn
from src.snap_to_sell.interfaces import ProductIdentity      # noqa: E402


def test_pack_info_detects_explicit_multipacks():
    assert R._pack_info("Coca-Cola 12 x 355 mL")[0] == 12
    assert R._pack_info("Instant Ramen Pack of 24")[0] == 24
    assert R._pack_info("Chips 6-pack")[0] == 6
    assert R._pack_info("Spring Water 24 Pack")[0] == 24
    assert R._pack_info("Pepsi Case of 24 Cans")[0] == 24
    assert R._pack_info("Value Pack Cookies") == (1, True)     # multipack word, unknown count


def test_pack_info_leaves_single_units_alone():
    # Bare "N <noun>" is ambiguous and must NOT be treated as a multipack.
    for title in ("Ziploc Sandwich Bags 150 Count", "Twinings Lemon & Ginger 20 Tea Bags",
                  "Tylenol Extra Strength 200 Caplets", "Metamucil Fibre 754 g"):
        assert R._pack_info(title) == (1, False), title


def test_query_multipack_flag():
    assert R._query_is_multipack(ProductIdentity(size="8 x 200 mL"))      # Allen's juice 8-pack
    assert R._query_is_multipack(ProductIdentity(variant="24 pack"))
    assert not R._query_is_multipack(ProductIdentity(size="25 g"))
    assert not R._query_is_multipack(ProductIdentity(size="355 mL"))


def test_multipack_downranked_for_single_unit_query():
    single = ProductIdentity(brand="Indomie", product="Instant Noodles", size="70 g")
    unit = {"title": "Indomie Instant Noodles Chicken 70 g", "source": "Amazon.ca", "price": "$0.99"}
    case = {"title": "Indomie Instant Noodles Chicken Pack of 40", "source": "Amazon.ca", "price": "$28.88"}
    assert R._score_shopping(single, unit) > R._score_shopping(single, case)


def test_price_normalised_to_per_unit():
    single = ProductIdentity(brand="Cola", product="Soda", size="355 mL")
    case = {"title": "Cola Soda 24 Pack cans", "source": "Amazon.ca", "price": "$28.80"}
    b = R._bundle_from_shopping(case, ambiguous=False, identity=single)
    assert abs(b.price.point - 1.20) < 0.01                    # 28.80 / 24
    assert "per-unit from 24-pack" in b.price.basis


def test_pack_info_extra_and_french_patterns():
    assert R._pack_info("Fleischmann's Corn Starch 454 g -- 12 per case")[0] == 12
    assert R._pack_info("Heinz Lot de 8 feves au four 415 g")[0] == 8
    assert R._pack_info("Coca-Cola paquet de 12")[0] == 12
    assert R._pack_info("Red Bull 8 canettes 250 mL")[0] == 8
    assert R._pack_info("Eau boite de 24")[0] == 24


def test_price_outlier_rejected():
    # A kayak returned among snack candidates must not win on price.
    items = [
        {"title": "SkyFlakes Crackers 25 g", "source": "Walmart", "price": "$0.99", "imageUrl": "x"},
        {"title": "SkyFlakes Crackers 6 pack", "source": "Amazon.ca", "price": "$4.99", "imageUrl": "x"},
        {"title": "Aqua Marina Recreational Kayak", "source": "Amazon.ca", "price": "$599.99", "imageUrl": "x"},
    ]
    idy = ProductIdentity(brand="SkyFlakes", product="Crackers", size="25 g")
    best, ambiguous, ranked = R._pick_shopping(idy, items)
    assert "Kayak" not in best["title"]                        # outlier rejected


def test_multipack_query_keeps_pack_price():
    # Allen's juice IS an 8-pack: the 8-pack price is correct, do NOT divide it.
    multi = ProductIdentity(brand="Allen's", product="Apple Juice", size="8 x 200 mL")
    item = {"title": "Allen's Apple Juice 8 x 200 mL", "source": "Walmart", "price": "$3.99"}
    b = R._bundle_from_shopping(item, ambiguous=False, identity=multi)
    assert abs(b.price.point - 3.99) < 0.01
    assert "per-unit" not in b.price.basis
