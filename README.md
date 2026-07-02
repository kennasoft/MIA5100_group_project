# Snap-to-Sell: AI-Assisted Listing Generation for Corner-Store Inventory

**MIA 5100 — Machine Learning — Group Project Proposal**
**Stream: Hands-On AI System Development Project (Build & Evaluate)**

A system where a corner-store owner photographs a packaged product on the shelf and the
pipeline identifies it, looks up comparable retail prices, swaps the casual shelf snap for a
clean high-resolution product image found online, and drafts a ready-to-publish sales
listing — title, description, suggested price, and any compliance flags — for a digital
storefront or delivery-app catalogue.

> **Status:** Draft proposal for team review. Scope, team roster, and deadline still to be
> confirmed on Brightspace before submission of the topic email to the instructor.

---

## 1. Problem Statement / Motivation

Independent corner stores and convenience retailers increasingly want to sell online —
through delivery platforms, their own storefronts, or aggregator catalogues — but
onboarding inventory is a manual, error-prone bottleneck. A typical shop carries hundreds
of fast-moving packaged goods (confectionery, snacks, beverages, frozen treats, tobacco,
household items). Creating a catalogue entry for each one by hand — finding the right
product name, writing a description, setting a price, attaching an image — is slow enough
that most small retailers never digitise their stock at all.

The core challenge this project addresses is: **can a single photograph of a packaged
retail product be turned, automatically and accurately enough to be useful, into a
publishable sales listing with a defensible suggested price?**

This is significant because the work sits squarely on the gap between off-the-shelf AI
capability and real deployment. Recognising "a chocolate bar" is trivial for modern
vision-language models; recognising _which_ SKU (brand, variant, and pack size), pulling a
_realistic local price_, and producing copy that does not misrepresent the product is
where accuracy degrades and where the interesting engineering and evaluation problems
live. Solving it lowers the barrier to e-commerce for a segment of retailers that is
usually left behind by automation.

## 2. Objectives and Research Question

**Primary research question.** _How accurately can a vision-language + retrieval pipeline
identify packaged corner-store products from a single shelf photo and generate a
publishable, correctly priced listing — and where, systematically, does it fail?_

Concrete objectives:

- Build an end-to-end pipeline: **photo in → structured listing out** (product identity,
  attributes, description, suggested price, a clean catalogue-quality product image, and a
  compliance flag).
- Quantify performance on three axes — **identification accuracy**, **price-estimation
  error**, and **listing quality** — against a held-out, hand-labelled test set.
- Characterise the **failure modes** (look-alike packaging, multipack ambiguity, glare,
  partial occlusion, regional/own-brand products) rather than reporting a single headline
  number.
- Add a **responsible-AI layer**: detect age-restricted products (e.g. tobacco) and flag
  hallucinated or unverifiable claims before a listing is published.

The deliberate framing is _investigation with an evaluation_, not a product build. Every
component leans on an existing model or API; the contribution is the integration, the
grounding/pricing logic, and the rigorous failure analysis.

## 3. Scope

**In scope.** Shelf-stable and frozen packaged consumer goods typically stocked by a
corner store: confectionery and gum, chips and snacks, soft drinks and water, ice cream
and frozen treats, packaged household sundries, and tobacco products (handled as the
age-restricted edge case). Single-item, reasonably framed photos taken on a phone.

**Out of scope (for this term).** Loose/unpackaged produce, deli or prepared food, bulk
items without packaging, multi-item "cluttered shelf" detection, barcode scanning as the
primary signal (it may be used as an optional verification input, but the research question
is about recognition _without_ relying on a clean barcode read), and live integration with
any real marketplace's publishing API.

Bounding scope to packaged goods is what makes the project tractable: packaging carries
rich, machine-readable signal (brand marks, product names, net weight, ingredient panels)
that supports recognition far better than the fine-grained used-goods resale problem we
originally considered.

## 3a. Related Work and Novelty

Each stage of the pipeline has prior art, but no published system integrates them for this
use case. A fuller review with APA citations is in
[`docs/literature_review.md`](docs/literature_review.md); the summary:

- **Listing generation.** ModICT (Li et al., 2024) generates descriptions from an image +
  keywords using a frozen LLM with in-context examples, and names the exact failure we guard
  against — generic, inaccurate copy for same-category products.
- **Recognition.** Large fine-grained retail datasets exist (RP2K; CAPG-GP), and multimodal
  **image + packaging-OCR** fusion is shown to beat image-only recognition, especially with
  few samples — direct empirical support for our Recognise design.
- **Pricing.** Work spans image-only regression (Chen & Chou, 2018) and multimodal
  image+text models; the newest, LLP (2025), **retrieves comparables** and **rejects
  low-confidence prices** — validating our retrieval-grounded, confidence-gated pricing.
- **Image upgrade.** Product visual-search work (SIR, 2020; e-CLIP, 2022) supplies the
  embedding-based matching we need — and notably also handles restricted-item detection,
  reusable for our age-restriction guardrail.

**Where we differ.** No academic work chains recognition → comparable pricing → _verified_
image replacement → grounded listing generation into one evaluated pipeline. Commercial
snap-to-sell apps (Synclyst, Snap2List, FlipSnap, AISeller, Sell AI) ship the pipeline but
target used-goods resale, are closed, and publish no evaluation. Our contribution is a
**reproducible, measured** system for **corner-store packaged goods**, with same-SKU image
verification (the false-swap rate) and selling-context responsible-AI (age-restricted items,
hallucination control) treated as first-class, evaluated concerns.

## 4. Proposed System Design

A staged pipeline with a human-in-the-loop checkpoint before anything is "published":

```
                ┌──────────────┐
   shelf photo  │  1. Capture  │  phone image, optional barcode crop
        ────────▶│ & pre-process│  deskew, crop, glare/exposure normalise
                └──────┬───────┘
                       ▼
                ┌──────────────┐   vision-language model + OCR of the
   identity ◀───│ 2. Recognise │   packaging text → {brand, product,
   + attributes └──────┬───────┘   variant, size, category}
                       ▼
                ┌──────────────┐   query retail/price + image sources for
   comparables ◀│ 3. Retrieve  │   the identified SKU → comparable prices,
   + candidate  └──────┬───────┘   canonical name, and candidate high-res
   images                          product images (licence-aware)
                       ▼
                ┌──────────────┐   LLM drafts title + description from
   draft list. ◀│ 4. Generate  │   *grounded* attributes only; price model
   + best image └──────┬───────┘   suggests price + range; select & verify
                                   the best-matching catalogue image
                       ▼
                ┌──────────────┐   age-restriction check, hallucination /
   safe draft ◀─│ 5. Guardrail │   unverifiable-claim check, image-match
                └──────┬───────┘   + licence check, low-confidence routing
                       ▼
                ┌──────────────┐   owner edits / approves; corrections feed
   published ◀──│ 6. Human     │   back as labelled data
                │   review     │
                └──────────────┘
```

Key design choices to justify in the report: using a **VLM + OCR fusion** rather than a
trained-from-scratch classifier (packaging text is the strongest single signal);
**grounding generation in retrieved attributes** to suppress hallucination; treating
price as an **estimate with a confidence range**, never a single confident number; and
**replacing the shelf snap with a verified high-resolution catalogue image** for the final
listing. The image swap is gated by an explicit **image–product match check** — a
retrieved image is only used if it is confidently the _same SKU_ as the photographed item
(an attractive but wrong image is worse than the original snap), with the owner's photo
kept as a fallback when no confident, licence-clear match is found.

## 5. Methodology

We will structure the work around **CRISP-DM**, adapted for a system that is assembled from
pretrained components rather than trained end-to-end:

1. **Business / Problem Understanding** — finalise the use case, success criteria, and the
   single product category we commit to (see §3), plus the responsible-AI requirements.
2. **Data Understanding** — assemble and profile candidate images and price references;
   identify gaps, look-alike clusters, and class imbalance (see §6).
3. **Data Preparation** — build the labelled test set (photos → ground-truth SKU + real
   observed price), define the listing-quality rubric, and a small prompt/few-shot set.
4. **Modelling** — assemble and tune the recognition, retrieval, and generation stages;
   compare at least two recognition approaches (e.g. VLM-only vs. VLM+OCR fusion) and at
   least two pricing strategies (retrieved-median vs. learned/heuristic adjustment).
5. **Evaluation** — score the pipeline on the held-out set against the metrics in §7;
   run the failure-mode analysis; compare to a naive baseline.
6. **Deployment (academic)** — deliver the IEEE paper, the timed presentation, and a
   documented, reproducible codebase + demo.

## 6. Data Strategy

There is **no ready-made dataset** for "corner-store photo → listing + price," so data work
is itself part of the contribution and must be planned honestly.

- **Recognition images.** Combine (a) a self-collected set of phone photos of real
  shelf/products under varied lighting and angles, and (b) public packaged-goods / retail
  product datasets where licensing permits, to widen brand coverage. Each image is labelled
  with ground-truth SKU and attributes.
- **Price references.** Prefer a **structured retail/marketplace data source over scraping
  Google**, which is rate-limited, ToS-restricted, and brittle for price extraction. We
  will evaluate available retail price APIs / open product databases (e.g. open product
  catalogues keyed by GTIN, and any permitted retail pricing feeds) and document exactly
  what each allows. The "search skill" becomes a thin, well-bounded retrieval layer, not
  an open web scrape.
- **Product images.** The same retrieval layer returns candidate catalogue images per SKU.
  We will favour sources whose **licensing permits commercial/listing reuse** (open product
  catalogues, brand/manufacturer assets, permitted retail feeds) and record provenance and
  licence per image. Images are only adopted after the match check in §4; the original
  photo is retained as a licence-clear fallback.
- **Ground-truth prices.** For the test set, record a _real observed local price_ per item
  so price error can be measured against reality, not against another estimate.

Licensing, consent for any in-store photography, and ToS compliance for every data source
will be documented in the report.

## 7. Evaluation Plan

| Axis                 | Metric(s)                                                                                                              | Notes                                              |
| -------------------- | ---------------------------------------------------------------------------------------------------------------------- | -------------------------------------------------- |
| Identification       | Top-1 / Top-3 SKU accuracy; brand-level vs. variant-level accuracy                                                     | Report separately — brand is easy, variant is hard |
| Attribute extraction | Field-level precision/recall (size, flavour, count)                                                                    | Sourced from OCR + VLM                             |
| Price estimation     | MAPE / median absolute % error vs. real observed price; % within tolerance band                                        | Estimate-with-range, not point accuracy            |
| Listing quality      | Human rating rubric (accuracy, completeness, no hallucinated claims), inter-rater agreement                            | Blind rating by team                               |
| Image upgrade        | Image–product match accuracy (correct SKU); % of items given a higher-res image; false-swap rate (wrong image adopted) | False swaps penalised heavily                      |
| Responsible-AI       | Age-restricted-item recall; hallucinated-claim catch rate                                                              | Safety-critical, weight accordingly                |
| Efficiency           | Latency and approximate cost per item                                                                                  | Practicality of deployment                         |

A **naive baseline** (e.g. VLM caption → generic listing, no retrieval grounding, no
guardrails) anchors every comparison so improvements are attributable.

## 8. Responsible AI Considerations

- **Age-restricted products.** Tobacco (and similar) must be detected and flagged; the
  system should never silently produce a publishable listing for a restricted item without
  surfacing the restriction. This is a first-class evaluation axis, not an afterthought.
- **Misrepresentation / hallucination.** In a selling context, an invented spec or claim is
  a real harm. Generation is grounded in retrieved/extracted attributes, and a verification
  check flags unverifiable claims before review.
- **Image accuracy and rights.** Swapping in a web image creates two risks: showing a
  _wrong_ product (a different SKU/size that misleads buyers) and using a _copyrighted_
  image without permission. Both are mitigated — the match check blocks wrong-SKU images,
  and only licence-clear sources are adopted, with provenance recorded — and the false-swap
  rate is measured explicitly (§7).
- **Pricing fairness and transparency.** Prices are presented as ranges with the basis
  shown, so the owner makes the final call.
- **Data provenance and consent.** All training/eval imagery and price data is sourced with
  documented permission and ToS compliance.

## 9. Proposed Technical Stack

- **Language / environment:** Python 3.12+, notebooks for EDA, a small `src/` package for
  the pipeline.
- **Vision / OCR:** a pretrained vision-language model for recognition + an OCR engine for
  packaging text; classical CV (OpenCV) for capture pre-processing.
- **Generation:** an LLM with structured-output prompting for listing copy, grounded in
  extracted/retrieved attributes.
- **Retrieval / pricing:** a bounded retail price/product-catalogue API layer (final source
  selected in Data Understanding) plus light heuristics for the price range.
- **Image upgrade:** candidate-image retrieval from licence-aware sources, with image
  embeddings (e.g. CLIP-style similarity) to rank and verify that the selected high-res
  image matches the photographed SKU before adoption.
- **Evaluation:** scikit-learn / pandas for metrics, a small human-rating harness for
  listing quality.

_(Final library choices are confirmed during the Modelling phase; this is the proposed
starting point, not a commitment.)_

## 10. Proposed Repository Structure

```
snap-to-sell/
├── README.md                  # this proposal, evolving into project docs
├── pyproject.toml             # dependencies and project config
│
├── data/
│   ├── images/                # collected & labelled product photos
│   ├── labels/                # ground-truth SKU + attributes + observed price
│   └── references/            # price-source pulls, product catalogue exports
│
├── src/snap_to_sell/
│   ├── capture/               # image pre-processing
│   ├── recognise/             # VLM + OCR fusion → structured identity
│   ├── retrieve/              # price + image/catalogue lookup layer
│   ├── imagematch/            # candidate-image ranking & SKU-match verification
│   ├── generate/              # grounded listing-copy generation
│   ├── guardrails/            # age-restriction + hallucination checks
│   └── evaluate/              # metrics and failure-mode tooling
│
├── notebooks/                 # EDA, experiments, ablations
├── reports/figures/           # figures for the IEEE paper
└── docs/
    ├── final_report/          # IEEE conference paper (LaTeX or template)
    ├── literature_review.md   # background / related work
    └── task_breakdown.md      # per-member assignments by CRISP-DM phase
```

## 11. Deliverables (per MIA 5100 instructions)

| Deliverable          | Points | Format                                               |
| -------------------- | ------ | ---------------------------------------------------- |
| Project Presentation | 20     | PowerPoint, 10 minutes (timed), presented in class   |
| Final Report         | 30     | 5-page **IEEE conference paper** (IEEEtran template) |

**Required IEEE report sections** (Hands-On stream): Abstract · Introduction / Background ·
Problem Statement / Motivation · Methodology · Implementation & Design (model(s),
architecture, data sources & preprocessing, training, optimisation) · Results (quantitative

- qualitative, baseline comparison) · Conclusion (findings, limitations, future work) ·
  References.

**Presentation** must cover: Introduction/Background · Problem Statement/Motivation ·
Implementation Details · Results · Discussion · Summary & Conclusion.

References follow uOttawa academic referencing (APA); prioritise publications from 2020
onward, accessed via the University of Ottawa library. No copy-paste; figures referenced
appropriately.

## 12. Proposed Timeline

| Phase | Work                                                                         | Target |
| ----- | ---------------------------------------------------------------------------- | ------ |
| 0     | Topic email to instructor (prevent overlap); team registered on Brightspace  | TBD    |
| 1     | Problem Understanding — lock category, success criteria, responsible-AI reqs | TBD    |
| 2     | Data Understanding — source images + price refs, profile                     | TBD    |
| 3     | Data Preparation — build labelled test set + rubric                          | TBD    |
| 4     | Modelling — assemble pipeline, ablations                                     | TBD    |
| 5     | Evaluation — metrics, failure analysis, baseline                             | TBD    |
| 6     | Deployment — paper, slides, demo, code cleanup                               | TBD    |

_(Dates to be set against the Brightspace deadline once confirmed.)_

## 13. Team

Teams of up to five (5) students; all members contribute equally and share the grade.

| Member            | Email                    | Role (proposed) |
| ----------------- | ------------------------ | --------------- |
| Ikenna Okonkwo    | ikenna.okonkwo@gmail.com | TBD             |
| Loic Tiemani      | Loic.Tiemani@uottawa.ca  | TBD             |
| Frank Boahen      | fboah074@uottawa.ca      | TBD             |
| Adhikary Adhikary | madhi020@uottawa.ca      | TBD             |
| _TBD_             | _TBD_                    | TBD             |

Per-phase assignments to be tracked in `docs/task_breakdown.md`.

## 14. Academic Integrity

All sources cited in APA per the
[uOttawa citation guidelines](https://www.uottawa.ca/library/writing-citing/citation-styles);
no copy-paste from sources; figures appropriately referenced. See
[uOttawa's academic-integrity policy](https://www.uottawa.ca/library/writing-citing/avoid-plagiarism-academic-fraud).

---

_Draft proposal prepared for team review. The scope, roster, timeline, and final tool
choices are starting points to be validated and refined by the team before the topic is
submitted to the instructor._
