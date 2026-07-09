"""Evaluation harness.

Runs the pipeline over data/testset/labels.csv and reports the metrics from the report:
identification accuracy, category accuracy, price error, age-restriction recall, and the
image-swap rate. Missing image files are skipped. Writes per-item results to
data/testset/eval_results.csv.

Note: with no API key the pipeline reads hand-labelled '<image>.json' sidecars, so recognition
accuracy will look perfect — that path exercises the harness. Real accuracy numbers come from
running with a hosted provider (set GEMINI_API_KEY or OPENAI_API_KEY).
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from src.snap_to_sell.pipeline import run  # noqa: E402

HERE = os.path.dirname(__file__)
TESTSET = os.path.join(HERE, "..", "data", "testset")
LABELS = os.path.join(TESTSET, "labels.csv")
OUT = os.path.join(TESTSET, "eval_results.csv")


def _truthy(v):
    return str(v).strip().lower() in {"1", "true", "yes", "y"}


def _contains(a, b):
    a, b = (a or "").lower(), (b or "").lower()
    return bool(a) and bool(b) and (a in b or b in a)


def main():
    import pandas as pd

    if not os.path.exists(LABELS):
        print("No labels.csv. WS2: populate data/testset/labels.csv.")
        return

    df = pd.read_csv(LABELS)
    rows = []
    for _, r in df.iterrows():
        img = os.path.join(TESTSET, str(r["image"]))
        if not os.path.exists(img):
            print(f"skip (missing image): {r['image']}")
            continue
        v = run(img)
        ident = v.listing.identity
        pred_price = v.listing.price.point
        gt_price = float(r["gt_price"]) if str(r.get("gt_price", "")).strip() else None
        price_err = (abs(pred_price - gt_price) / gt_price * 100
                     if pred_price and gt_price else None)
        rows.append({
            "image": r["image"],
            "id_correct": _contains(str(r["product"]), ident.product)
                          or _contains(str(r["product"]), v.listing.title),
            "cat_correct": _contains(str(r.get("category", "")), ident.category),
            "pred_price": pred_price,
            "gt_price": gt_price,
            "price_err_pct": price_err,
            "gt_age": _truthy(r.get("age_restricted", False)),
            "pred_age": v.listing.flags.age_restricted,
            "image_swapped": v.listing.flags.image_swapped,
            "compliance": v.compliance_status,
        })

    if not rows:
        print("No test items evaluated (no images present).")
        return

    res = pd.DataFrame(rows)
    n = len(res)
    id_acc = res["id_correct"].mean()
    cat_acc = res["cat_correct"].mean()
    price = res["price_err_pct"].dropna()
    price_mape = price.mean() if len(price) else float("nan")
    age = res[res["gt_age"]]
    age_recall = age["pred_age"].mean() if len(age) else float("nan")
    swap_rate = res["image_swapped"].mean()

    res.to_csv(OUT, index=False)
    print(f"\n=== Snap-to-Sell evaluation (n={n}) ===")
    print(f"Identification accuracy : {id_acc:.1%}")
    print(f"Category accuracy       : {cat_acc:.1%}")
    print(f"Price median abs error  : {price_mape:.1f}%  (on {len(price)} priced items)")
    print(f"Age-restriction recall  : {age_recall:.1%}  (on {len(age)} restricted items)")
    print(f"Image-swap rate         : {swap_rate:.1%}")
    print(f"per-item results written to {os.path.relpath(OUT)}")


if __name__ == "__main__":
    main()
