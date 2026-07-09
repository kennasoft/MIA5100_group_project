"""Feedback store + mock publish. Stub uses CSV."""
import csv, os

CATALOGUE = os.path.join(os.path.dirname(__file__), "..", "..", "data", "catalogue.csv")
FEEDBACK = os.path.join(os.path.dirname(__file__), "..", "..", "data", "feedback.csv")


def publish(validated) -> None:
    l = validated.listing
    _append(CATALOGUE, ["title", "price", "image_url", "compliance"],
            [l.title, l.price.point, l.image_url, validated.compliance_status])


def record_correction(original, corrected) -> None:
    _append(FEEDBACK, ["field", "original", "corrected"], [original, corrected, ""])


def _append(path, header, row):
    exists = os.path.exists(path)
    with open(path, "a", newline="") as f:
        w = csv.writer(f)
        if not exists:
            w.writerow(header)
        w.writerow(row)
