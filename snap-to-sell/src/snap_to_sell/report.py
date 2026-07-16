"""Per-run HTML report.

Collects each processed item (original photo, how the listing was reached, the top retrieval
candidates considered, the final listing, and accuracy vs ground truth) and writes a single
self-contained ``output/pipeline-result-<YYYYMMDDHHmmss>.html``.

Usage:
    rep = RunReport()
    rep.add(image_path, validated, ground_truth={...})   # ground_truth optional
    path = rep.write_html()                               # -> output/pipeline-result-<ts>.html
"""
import base64
import datetime
import html
import io
import os
from dataclasses import asdict

from . import config


def _esc(s):
    return html.escape("" if s is None else str(s))


def _img_src(ref, max_px=360):
    """A usable <img src>: remote URLs pass through; local files are downscaled and inlined as
    base64 (so the report is one portable file without bloating to hundreds of MB)."""
    if not ref:
        return ""
    s = str(ref)
    if s.startswith("http"):
        return s
    try:
        from PIL import Image, ImageOps
        im = ImageOps.exif_transpose(Image.open(s)).convert("RGB")
        im.thumbnail((max_px, max_px))
        buf = io.BytesIO()
        im.save(buf, "JPEG", quality=72)
        return "data:image/jpeg;base64," + base64.b64encode(buf.getvalue()).decode()
    except Exception:
        try:
            with open(s, "rb") as f:
                return "data:image/jpeg;base64," + base64.b64encode(f.read()).decode()
        except Exception:
            return ""


def _contains(a, b):
    a, b = (a or "").lower(), (b or "").lower()
    return bool(a) and bool(b) and (a in b or b in a)


def _fmt_price(pi):
    try:
        if pi.point is not None:
            return f"{pi.currency} {pi.point:.2f}"
    except Exception:
        pass
    return "Price on request"


class RunReport:
    def __init__(self, title="Snap-to-Sell — pipeline run"):
        self.title = title
        self.items = []  # (image_path, validated, ground_truth)

    def add(self, image_path, validated, ground_truth=None):
        self.items.append((image_path, validated, ground_truth or {}))

    # ---------------- per-item pieces ----------------

    def _narrative(self, image_path, v):
        idy = v.listing.identity
        chosen = next((c for c in v.listing.candidates if c.chosen), None)
        parts = []
        parts.append(
            f"Recognised as <b>{_esc(idy.brand)} {_esc(idy.product)}</b> "
            f"{_esc(idy.variant)} {_esc(idy.size)} — category <i>{_esc(idy.category)}</i>, "
            f"confidence {getattr(idy, 'confidence', 0):.2f}"
            + (f", barcode {_esc(idy.barcode)}" if idy.barcode else "") + ".")
        parts.append(
            f"Retrieval searched <code>{_esc(idy.search_query or (idy.brand + ' ' + idy.product))}</code> "
            f"and ranked {len(v.listing.candidates)} candidate(s).")
        if chosen:
            parts.append(
                f"Chose <b>{_esc(chosen.title)}</b> (score {chosen.score}"
                + (f"; {_esc(chosen.detail)}" if chosen.detail else "") + ").")
        parts.append(f"Price: <b>{_fmt_price(v.listing.price)}</b> "
                     f"<span class='muted'>({_esc(v.listing.price.basis)})</span>.")
        if v.listing.flags.image_swapped:
            parts.append("Image: swapped in a verified same-SKU catalogue image.")
        elif v.listing.flags.image_enhanced:
            parts.append("Image: cleaned the owner's own photo (background removal).")
        else:
            parts.append("Image: kept the original photo (no confident better match).")
        flags = []
        if v.listing.flags.age_restricted:
            flags.append("age-restricted")
        if v.listing.flags.retrieval_ambiguous:
            flags.append("retrieval ambiguous")
        if v.listing.flags.low_confidence:
            flags.append("low confidence")
        parts.append(f"Guardrails: compliance <b>{_esc(v.compliance_status)}</b>"
                     + (f"; flags: {', '.join(flags)}" if flags else "") + ".")
        html_txt = "<p>" + "</p><p>".join(parts) + "</p>"
        # attach the raw trace log if it exists, for full transparency
        stem = os.path.splitext(image_path)[0]
        log = stem + "-log.txt"
        if os.path.exists(log):
            try:
                raw = open(log, encoding="utf-8", errors="ignore").read()
                html_txt += ("<details class='sub'><summary>raw processing log</summary>"
                             "<pre>" + _esc(raw) + "</pre></details>")
            except Exception:
                pass
        return html_txt

    def _candidates_html(self, v):
        cands = v.listing.candidates
        if not cands:
            return "<div class='muted'>No ranked candidates captured for this backend.</div>"
        cells = ""
        for c in cands:
            try:
                pnum = float(c.price)
            except (TypeError, ValueError):
                pnum = None
            price = (f"{c.currency} {pnum:.2f}" if pnum is not None else "—")
            badge = "<span class='pick'>chosen</span>" if c.chosen else ""
            img = _img_src(c.image_url)
            imgtag = (f"<img src='{img}'/>" if img
                      else "<div class='noimg'>no image</div>")
            cells += (
                f"<div class='cand{' chosen' if c.chosen else ''}'>"
                f"<div class='cand-img'>{imgtag}{badge}</div>"
                f"<div class='cand-price'>{_esc(price)}</div>"
                f"<div class='cand-cat'>{_esc(c.category or '-')}</div>"
                f"<div class='cand-title'>{_esc(c.title)}</div>"
                f"<div class='cand-detail'>score {c.score}"
                + (f" · {_esc(c.detail)}" if c.detail else "") + "</div></div>")
        return "<div class='cands'>" + cells + "</div>"

    def _final_html(self, image_path, v):
        l = v.listing
        ref = l.image_url if str(l.image_url).startswith("http") else (l.image_url or image_path)
        tag = ("catalogue image" if l.flags.image_swapped
               else "cleaned photo" if l.flags.image_enhanced else "original photo")
        badges = ""
        if l.flags.age_restricted:
            badges += "<span class='b b-age'>18+ age-restricted</span>"
        if v.compliance_status == "flagged":
            badges += "<span class='b b-rev'>needs review</span>"
        if not badges:
            badges += "<span class='b b-ok'>ready to publish</span>"
        img = _img_src(ref)
        imgtag = f"<img src='{img}'/>" if img else "<div class='noimg'>no image</div>"
        return (
            "<div class='final'>"
            f"<div class='final-img'>{imgtag}<span class='swaptag'>{tag}</span></div>"
            f"<div class='final-body'><div class='cat'>{_esc(l.identity.category or '-')}</div>"
            f"<div class='ftitle'>{_esc(l.title or 'Untitled')}</div>"
            f"<div class='fprice'>{_esc(_fmt_price(l.price))}</div>"
            f"<div class='fdesc'>{_esc(l.description or '')}</div>"
            f"<div class='badges'>{badges}</div></div></div>")

    def _accuracy_html(self, v, gt):
        idy = v.listing.identity
        if not gt:
            rows = [
                ("Model confidence", f"{getattr(idy, 'confidence', 0):.2f}"),
                ("Retrieval ambiguous", "yes" if v.listing.flags.retrieval_ambiguous else "no"),
                ("Needs review", "yes" if v.needs_review else "no"),
                ("Image", "swapped" if v.listing.flags.image_swapped
                 else "enhanced" if v.listing.flags.image_enhanced else "original"),
            ]
            note = "<div class='muted'>No ground truth supplied — showing pipeline confidence signals.</div>"
            return note + self._stat_table(rows)
        # ground-truth accuracy
        id_ok = _contains(str(gt.get("product", "")), idy.product) or \
            _contains(str(gt.get("product", "")), v.listing.title)
        cat_ok = _contains(str(gt.get("category", "")), idy.category)
        pred = v.listing.price.point
        try:
            g = float(gt.get("gt_price"))
        except (TypeError, ValueError):
            g = None
        perr = (abs(pred - g) / g * 100) if (pred and g) else None
        gt_age = str(gt.get("age_restricted", "")).strip().lower() in {"1", "true", "yes", "y"}
        age_ok = (gt_age == bool(v.listing.flags.age_restricted))
        rows = [
            ("Identification", ("✓ correct" if id_ok else "✗ wrong") +
             f" <span class='muted'>(gt: {_esc(gt.get('brand',''))} {_esc(gt.get('product',''))})</span>"),
            ("Category", ("✓" if cat_ok else "✗") + f" {_esc(idy.category)} vs {_esc(gt.get('category',''))}"),
            ("Price error", (f"{perr:.0f}%" if perr is not None else "n/a") +
             f" <span class='muted'>(pred {pred}, gt {gt.get('gt_price')})</span>"),
            ("Age-restriction", ("✓ match" if age_ok else "✗ mismatch") +
             f" <span class='muted'>(gt {'yes' if gt_age else 'no'})</span>"),
        ]
        return self._stat_table(rows, cls=("ok" if id_ok else "bad"))

    def _stat_table(self, rows, cls=""):
        body = "".join(f"<tr><th>{_esc(k)}</th><td>{v}</td></tr>" for k, v in rows)
        return f"<table class='stats {cls}'>{body}</table>"

    # ---------------- run-level summary ----------------

    def _summary_html(self):
        n = len(self.items)
        gts = [(v, gt) for _, v, gt in self.items if gt]
        cards = [("Items", str(n))]
        if gts:
            import statistics
            id_ok = cat_ok = 0
            perrs = []
            swaps = sum(1 for _, v, _ in self.items if v.listing.flags.image_swapped)
            for v, gt in gts:
                idy = v.listing.identity
                if _contains(str(gt.get("product", "")), idy.product) or \
                        _contains(str(gt.get("product", "")), v.listing.title):
                    id_ok += 1
                if _contains(str(gt.get("category", "")), idy.category):
                    cat_ok += 1
                try:
                    g = float(gt.get("gt_price"))
                    p = v.listing.price.point
                    if p and g:
                        perrs.append(abs(p - g) / g * 100)
                except (TypeError, ValueError):
                    pass
            cards += [
                ("Top-1 identification", f"{id_ok / len(gts):.0%}"),
                ("Category accuracy", f"{cat_ok / len(gts):.0%}"),
                ("Price median abs % err", f"{statistics.median(perrs):.0f}%" if perrs else "n/a"),
                ("Image-swap rate", f"{swaps / n:.0%}"),
            ]
        else:
            swaps = sum(1 for _, v, _ in self.items if v.listing.flags.image_swapped)
            cards.append(("Image-swap rate", f"{swaps / n:.0%}" if n else "n/a"))
        return "".join(
            f"<div class='kpi'><div class='kpi-v'>{_esc(v)}</div><div class='kpi-k'>{_esc(k)}</div></div>"
            for k, v in cards)

    # ---------------- render ----------------

    def write_html(self, out_dir="output"):
        os.makedirs(out_dir, exist_ok=True)
        ts = datetime.datetime.now().strftime("%Y%m%d%H%M%S")
        path = os.path.join(out_dir, f"pipeline-result-{ts}.html")
        rows = ""
        for i, (image_path, v, gt) in enumerate(self.items, 1):
            rows += (
                "<section class='row'>"
                f"<div class='rownum'>#{i}</div>"
                "<div class='col col-orig'><h4>Original</h4>"
                f"<img src='{_img_src(image_path)}'/>"
                f"<div class='fname'>{_esc(os.path.basename(image_path))}</div></div>"
                "<div class='col col-mid'>"
                "<details class='narr'><summary>How this listing was reached</summary>"
                f"{self._narrative(image_path, v)}</details>"
                "<h4>Top candidates considered</h4>"
                f"{self._candidates_html(v)}</div>"
                "<div class='col col-final'><h4>Final listing</h4>"
                f"{self._final_html(image_path, v)}"
                "<h4>Accuracy</h4>"
                f"{self._accuracy_html(v, gt)}</div>"
                "</section>")
        doc = _TEMPLATE.format(
            title=_esc(self.title),
            generated=datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            provider=_esc(config.active_provider() or "offline"),
            backend=_esc(config.RETRIEVE_BACKEND),
            summary=self._summary_html(),
            rows=rows)
        with open(path, "w", encoding="utf-8") as f:
            f.write(doc)
        return path


_TEMPLATE = """<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title}</title><style>
:root{{--ink:#1c1c28;--muted:#7a7a88;--line:#e9e9ef;--teal:#028090;--green:#0a7d3c;--red:#c0392b;}}
*{{box-sizing:border-box;}}
body{{margin:0;background:#f4f5f7;color:var(--ink);font:14px/1.5 -apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,Helvetica,Arial,sans-serif;}}
header{{background:#0b2a3b;color:#fff;padding:22px 26px;}}
header h1{{margin:0 0 4px;font-size:20px;}} header .meta{{color:#9fc7cf;font-size:12px;}}
.kpis{{display:flex;flex-wrap:wrap;gap:14px;padding:16px 26px;background:#fff;border-bottom:1px solid var(--line);}}
.kpi{{min-width:120px;}} .kpi-v{{font-size:22px;font-weight:750;color:var(--teal);}} .kpi-k{{font-size:11px;color:var(--muted);text-transform:uppercase;letter-spacing:.05em;}}
.row{{display:grid;grid-template-columns:200px 1.3fr 1fr;gap:18px;align-items:start;background:#fff;margin:16px 26px;padding:16px;border:1px solid var(--line);border-radius:14px;position:relative;}}
.rownum{{position:absolute;top:8px;left:10px;font-size:11px;color:var(--muted);font-weight:700;}}
.col h4{{margin:2px 0 8px;font-size:11px;letter-spacing:.06em;text-transform:uppercase;color:var(--muted);}}
.col-orig img{{width:100%;border-radius:10px;background:#f6f6f8;}}
.fname{{font-size:10px;color:var(--muted);margin-top:5px;word-break:break-all;}}
details{{margin-bottom:12px;}} summary{{cursor:pointer;color:var(--teal);font-weight:650;font-size:13px;}}
.narr p{{margin:6px 0;}} .muted{{color:var(--muted);}}
details.sub{{margin-top:8px;}} pre{{max-height:260px;overflow:auto;background:#f7f7fb;border:1px solid var(--line);border-radius:8px;padding:8px;font-size:10px;white-space:pre-wrap;}}
.cands{{display:grid;grid-template-columns:repeat(3,1fr);gap:8px;}}
.cand{{border:1px solid var(--line);border-radius:10px;padding:8px;font-size:11px;background:#fcfcfd;}}
.cand.chosen{{border-color:var(--green);box-shadow:0 0 0 1px var(--green) inset;}}
.cand-img{{position:relative;aspect-ratio:1/1;background:#f6f6f8;border-radius:6px;display:flex;align-items:center;justify-content:center;overflow:hidden;margin-bottom:6px;}}
.cand-img img{{width:100%;height:100%;object-fit:contain;}} .noimg{{color:#b7b7c2;font-size:10px;}}
.pick{{position:absolute;top:4px;left:4px;background:var(--green);color:#fff;font-size:9px;padding:2px 6px;border-radius:10px;}}
.cand-price{{font-weight:750;color:var(--green);}} .cand-cat{{color:var(--muted);text-transform:uppercase;font-size:9.5px;letter-spacing:.04em;}}
.cand-title{{font-weight:600;margin:2px 0;max-height:48px;overflow:hidden;}} .cand-detail{{color:var(--muted);font-size:10px;}}
.final{{border:1px solid var(--line);border-radius:12px;overflow:hidden;}}
.final-img{{position:relative;aspect-ratio:1/1;background:#f6f6f8;display:flex;align-items:center;justify-content:center;}}
.final-img img{{width:100%;height:100%;object-fit:contain;}}
.swaptag{{position:absolute;top:8px;left:8px;background:rgba(0,0,0,.62);color:#fff;font-size:10px;padding:3px 8px;border-radius:12px;}}
.final-body{{padding:10px 12px;}} .cat{{font-size:10px;color:var(--muted);text-transform:uppercase;letter-spacing:.05em;}}
.ftitle{{font-weight:700;margin:3px 0;}} .fprice{{color:var(--green);font-weight:800;font-size:17px;}}
.fdesc{{color:#5b5b6b;font-size:12px;margin:5px 0;}}
.badges{{margin-top:6px;}} .b{{font-size:10px;font-weight:650;padding:3px 8px;border-radius:12px;margin-right:5px;}}
.b-ok{{background:#e6f7ee;color:var(--green);}} .b-age{{background:#fdecea;color:var(--red);}} .b-rev{{background:#fff4e0;color:#b9770a;}}
table.stats{{width:100%;border-collapse:collapse;margin-top:6px;font-size:12px;}}
table.stats th{{text-align:left;color:var(--muted);font-weight:600;padding:4px 8px 4px 0;white-space:nowrap;vertical-align:top;width:34%;}}
table.stats td{{padding:4px 0;}} table.stats.bad th:first-child{{}}
@media(max-width:900px){{.row{{grid-template-columns:1fr;}}.cands{{grid-template-columns:repeat(3,1fr);}}}}
</style></head><body>
<header><h1>{title}</h1><div class="meta">generated {generated} · provider: {provider} · retrieval backend: {backend}</div></header>
<div class="kpis">{summary}</div>
{rows}
</body></html>"""
