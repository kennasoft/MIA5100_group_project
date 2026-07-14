"""Evaluation harness.

Runs the pipeline over data/testset/labels.csv and reports the metrics from the report:
identification accuracy, category accuracy, price error, age-restriction recall, and the
image-swap rate. Missing image files are skipped. Writes per-item results to
data/testset/eval_results.csv.

Two systems can be scored with the SAME metrics so the numbers are directly comparable:

  * Snap-to-Sell  — the full pipeline (recognise -> retrieve -> generate -> imagematch -> guardrails)
  * Baseline      — the naive anchor from the report: recognise -> UNGROUNDED generation only.
                    No retrieval grounding, no image upgrade, no guardrails. By construction it
                    never swaps images (false-swap rate 0) and never flags age-restricted items
                    (age recall 0) — that contrast is the point.

Usage:
    python eval/harness.py            # full pipeline only  -> eval_results.csv
    python eval/harness.py --baseline # naive baseline only -> eval_results_baseline.csv
    python eval/harness.py --both     # run both, print the side-by-side table for the report

Note: with no API key the pipeline reads hand-labelled '<image>.json' sidecars, so recognition
accuracy will look perfect and the baseline will mirror the full run — that path only exercises
the harness. Real, differentiated numbers come from running with a hosted provider
(set OPENAI_API_KEY, ANTHROPIC_API_KEY, or GEMINI_API_KEY).
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from src.snap_to_sell.pipeline import run  # noqa: E402
from src.snap_to_sell.capture import preprocess  # noqa: E402
from src.snap_to_sell.recognise import recognise  # noqa: E402
from src.snap_to_sell.interfaces import DraftListing, PriceInfo, Flags, ValidatedListing  # noqa: E402
from src.snap_to_sell import providers  # noqa: E402

HERE = os.path.dirname(__file__)
TESTSET = os.path.join(HERE, "..", "data", "testset")
LABELS = os.path.join(TESTSET, "labels.csv")
OUT_FULL = os.path.join(TESTSET, "eval_results.csv")
OUT_BASE = os.path.join(TESTSET, "eval_results_baseline.csv")


def _truthy(v):
    return str(v).strip().lower() in {"1", "true", "yes", "y"}


def _contains(a, b):
    a, b = (a or "").lower(), (b or "").lower()
    return bool(a) and bool(b) and (a in b or b in a)


# --------------------------- systems under test ---------------------------

def run_full(image_path):
    """The full Snap-to-Sell pipeline."""
    return run(image_path)


def run_baseline(image_path):
    """Naive baseline: recognise, then an UNGROUNDED listing + guessed price. No retrieval,
    no image upgrade, no guardrails. Returns a ValidatedListing so the same scorer applies."""
    from dataclasses import asdict

    clean = preprocess(image_path)
    identity = recognise(clean)

    # ungrounded generation: a generic listing + a best-guess price from the identity alone
    title = f"{identity.brand} {identity.product}".strip() or identity.product
    desc = title
    price_point = None
    try:
        d = providers.draft_listing_baseline(asdict(identity))
        title = (d.get("title") or title).strip()
        desc = (d.get("description") or desc).strip()
        p = d.get("price")
        price_point = float(p) if p not in (None, "", "null") else None
    except providers.NoProviderError:
        pass  # offline: keep the template title, no price guess
    except Exception as e:  # noqa: BLE001
        print(f"[baseline] provider failed, using template: {e}", file=sys.stderr)

    listing = DraftListing(
        identity=identity,
        title=title,
        description=desc,
        price=PriceInfo(point=price_point, basis="baseline guess (ungrounded)"),
        image_url="",           # baseline never upgrades the image
        flags=Flags(),          # baseline has no guardrails -> nothing flagged
    )
    return ValidatedListing(listing=listing, compliance_status="pending", needs_review=True)


# --------------------------- scoring (shared) ---------------------------

def evaluate(runner, out_path, label):
    """Run `runner` over the test set, write per-item CSV, return a metrics dict."""
    import pandas as pd

    if not os.path.exists(LABELS):
        print("No labels.csv. WS2: populate data/testset/labels.csv.")
        return None

    df = pd.read_csv(LABELS)
    rows = []
    for _, r in df.iterrows():
        img = os.path.join(TESTSET, str(r["image"]))
        if not os.path.exists(img):
            print(f"skip (missing image): {r['image']}")
            continue
        v = runner(img)
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
        return None

    res = pd.DataFrame(rows)
    price = res["price_err_pct"].dropna()
    age = res[res["gt_age"]]
    metrics = {
        "label": label,
        "n": len(res),
        "id_acc": res["id_correct"].mean(),
        "cat_acc": res["cat_correct"].mean(),
        "price_mape": price.mean() if len(price) else float("nan"),
        "n_priced": len(price),
        "age_recall": age["pred_age"].mean() if len(age) else float("nan"),
        "n_age": len(age),
        "swap_rate": res["image_swapped"].mean(),
    }
    res.to_csv(out_path, index=False)
    metrics["_csv"] = os.path.relpath(out_path)
    return metrics


def _print_single(m):
    print(f"\n=== {m['label']} evaluation (n={m['n']}) ===")
    print(f"Identification accuracy : {m['id_acc']:.1%}")
    print(f"Category accuracy       : {m['cat_acc']:.1%}")
    print(f"Price median abs error  : {m['price_mape']:.1f}%  (on {m['n_priced']} priced items)")
    print(f"Age-restriction recall  : {m['age_recall']:.1%}  (on {m['n_age']} restricted items)")
    print(f"Image-swap rate         : {m['swap_rate']:.1%}")
    print(f"per-item results written to {m['_csv']}")


def _fmt_pct(x):
    return "n/a" if x != x else f"{x:.1%}"   # x!=x catches NaN


def _fmt_mape(x):
    return "n/a" if x != x else f"{x:.1f}%"


def _print_both(base, full):
    """The side-by-side table that fills the slide-12 / report Results table."""
    rows = [
        ("Top-1 identification accuracy", _fmt_pct(base["id_acc"]), _fmt_pct(full["id_acc"])),
        ("Category accuracy",             _fmt_pct(base["cat_acc"]), _fmt_pct(full["cat_acc"])),
        ("Price median abs. % error",     _fmt_mape(base["price_mape"]), _fmt_mape(full["price_mape"])),
        ("Age-restriction recall",        _fmt_pct(base["age_recall"]), _fmt_pct(full["age_recall"])),
        ("Image-swap rate",               _fmt_pct(base["swap_rate"]), _fmt_pct(full["swap_rate"])),
    ]
    w0 = max(len(r[0]) for r in rows)
    print(f"\n=== Results: Baseline vs Snap-to-Sell (n={full['n']}) ===")
    print(f"{'Metric'.ljust(w0)} | {'Baseline'.rjust(12)} | {'Snap-to-Sell'.rjust(12)}")
    print(f"{'-'*w0}-+-{'-'*12}-+-{'-'*12}")
    for name, b, f in rows:
        print(f"{name.ljust(w0)} | {b.rjust(12)} | {f.rjust(12)}")
    print("\nNote: Top-3 accuracy and Listing-quality (blind human rating) are not automated — "
          "score those manually. 'Image-swap rate' approximates the false-swap rate; label "
          "per-image correctness to report true false swaps. Baseline never swaps or flags by design.")


def main():
    args = set(sys.argv[1:])
    try:
        from src.snap_to_sell import config
        active = config.active_provider() or "offline (no API key)"
    except Exception:  # noqa: BLE001
        active = "unknown"
    print(f"[harness] provider: {active}", file=sys.stderr)

    if "--both" in args:
        base = evaluate(run_baseline, OUT_BASE, "Baseline")
        full = evaluate(run_full, OUT_FULL, "Snap-to-Sell")
        if base and full:
            _print_both(base, full)
    elif "--baseline" in args:
        m = evaluate(run_baseline, OUT_BASE, "Baseline")
        if m:
            _print_single(m)
    else:
        m = evaluate(run_full, OUT_FULL, "Snap-to-Sell")
        if m:
            _print_single(m)


if __name__ == "__main__":
    main()
