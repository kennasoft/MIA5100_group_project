"""Generate.

Primary path: hosted LLM drafts grounded title + description from the identity and retrieved
attributes only (providers.draft_listing). Offline fallback: a deterministic template built
from the same facts. Either way, price and the (later-chosen) image come from upstream stages,
so generation cannot invent a price.
"""
import sys
from dataclasses import asdict

from ..interfaces import DraftListing, Flags
from .. import providers


def _template(identity, bundle) -> tuple:
    title = bundle.canonical_name or f"{identity.brand} {identity.product}".strip()
    bits = [b for b in [identity.size, identity.category] if b]
    desc = (title + (". " + " ".join(bits) + "." if bits else ".")).replace("  ", " ").strip()
    return title, desc


def generate(identity, bundle) -> DraftListing:
    title, desc = _template(identity, bundle)  # safe default
    try:
        retrieved = {"canonical_name": bundle.canonical_name,
                     "category_tags": bundle.category_tags}
        d = providers.draft_listing(asdict(identity), retrieved)
        title = (d.get("title") or title).strip()
        desc = (d.get("description") or desc).strip()
    except providers.NoProviderError:
        pass
    except Exception as e:
        print(f"[generate] provider failed, using template: {e}", file=sys.stderr)

    return DraftListing(identity=identity, title=title, description=desc,
                        price=bundle.price, image_url="", flags=Flags())
