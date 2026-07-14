# Research Sources — Snap-to-Sell

Provenance folder for the primary sources cited in
[`../literature_review.md`](../literature_review.md) and
[`../final_report/references.bib`](../final_report/references.bib). This index is the
single place that maps every reference to its canonical link, identifier, access status,
licence, and the pipeline stage it supports.

**Why this folder exists (and how to fill it).** Course policy asks for APA-cited,
2020-onward sources accessed via the University of Ottawa library. Drop the retrieved PDF
for each open-access source into this folder using the **Suggested filename** below so the
index and the files line up. Paywalled sources (Springer) should be accessed through the
uOttawa library rather than redistributed here — record the library-access DOI instead of
committing the PDF. ResearchGate/journal-portal items should only be added if their licence
permits redistribution; otherwise keep the link and access them directly.

> Author lists marked **[verify authors]** must be confirmed against the primary source and
> reconciled in `references.bib` before the report is submitted (the arXiv IDs / DOIs below
> make this quick).

## Index

| # | Sub-problem | Citation (short) | Year | Identifier / link | Access | Suggested filename | Supports stage |
|---|-------------|------------------|------|-------------------|--------|--------------------|----------------|
| 1 | Listing generation | Li, Hu, Luo, Ma, Ding & Zhang — *ModICT: A multimodal in-context tuning approach for e-commerce product description generation* (LREC-COLING) | 2024 | arXiv:2402.13587 · https://arxiv.org/abs/2402.13587 | Open (arXiv) | `2024_ModICT_Li_et_al.pdf` | Generate |
| 2 | Listing generation | *Optimizing e-commerce listing: LLM-based description and keyword generation from multimodal data* (IJSR, 13) **[verify authors]** | 2024 | https://www.ijsr.net/getabstract.php?paperid=SR24304113521 | Open-access journal | `2024_IJSR_ecommerce_listing.pdf` | Generate |
| 3 | Recognition | Peng, Xiao & Li — *RP2K: A large-scale retail product dataset for fine-grained image classification* | 2020 | arXiv:2006.12634 · https://arxiv.org/abs/2006.12634 | Open (arXiv) | `2020_RP2K_Peng_et_al.pdf` | Recognise (benchmark) |
| 4 | Recognition | *Multimodal fine-grained grocery product recognition using image and OCR text* **[verify authors]** | 2023 | https://www.researchgate.net/publication/375000319 | ResearchGate (check licence) | `2023_multimodal_ocr_grocery.pdf` | Recognise (VLM+OCR design proof) |
| 5 | Recognition | *Fine-grained grocery product recognition by one-shot learning* (CAPG-GP, ACM MM) **[verify authors]** | 2018 | Dataset: http://zju-capg.org/capg-gp.html · paper via ACM DL | ACM DL (may be paywalled) | `2018_CAPG-GP_oneshot.pdf` | Recognise (low-data) |
| 6 | Pricing | Chen & Chou — *The price is right: Predicting prices with product images* | 2018 | https://www.semanticscholar.org/paper/55774d24c98f8e77275a5e3629ed1503a22497b8 | Open (report PDF) | `2018_price_is_right_Chen_Chou.pdf` | Pricing (baseline) |
| 7 | Pricing | *Deep end-to-end learning for price prediction of second-hand items* (Knowledge and Information Systems, 62) **[verify authors]** | 2020 | doi:10.1007/s10115-020-01495-8 · https://doi.org/10.1007/s10115-020-01495-8 | Springer (paywalled → uOttawa library) | `2020_secondhand_pricing_KAIS.pdf` | Pricing (multimodal baseline) |
| 8 | Pricing | *LLP: LLM-based product pricing in e-commerce* **[verify authors]** | 2025 | arXiv:2510.09347 · https://arxiv.org/abs/2510.09347 | Open (arXiv) | `2025_LLP_llm_pricing.pdf` | Pricing + confidence design |
| 9 | Image retrieval | *SIR: Similar image retrieval for product search in e-commerce* **[verify authors]** | 2020 | arXiv:2009.13836 · https://arxiv.org/abs/2009.13836 | Open (arXiv) | `2020_SIR_similar_image_retrieval.pdf` | Image match + restricted-item flag |
| 10 | Image matching | *e-CLIP: Large-scale vision-language representation learning in e-commerce* **[verify authors]** | 2022 | arXiv:2207.00208 · https://arxiv.org/abs/2207.00208 | Open (arXiv) | `2022_eCLIP.pdf` | Match embeddings + adult-item detection |

## Access notes

Six sources are openly downloadable from arXiv and can be added directly: **#1, #3, #8, #9,
#10** (arXiv) and **#6** (open report PDF). **#2** is an open-access journal (IJSR). **#4**
is on ResearchGate — confirm the posting licence before committing the PDF; otherwise keep
the link only. **#5** (CAPG-GP) has an open dataset page, but the paper itself sits in the
ACM Digital Library and may require library access. **#7** is a Springer article behind a
paywall — access it through the uOttawa library and cite the DOI rather than committing the
file.

## Industry landscape (context, not peer-reviewed)

The commercial snap-to-sell/resale apps referenced for market context — **Synclyst,
Snap2List, FlipSnap, AISeller, Sell AI** — are cited as evidence of demand and feasibility,
not as academic sources. They are closed and unevaluated, so there is nothing to archive
here; product pages can be linked inline in the report if needed.

## Checklist before submission

1. Download the open-access PDFs (#1, #3, #6, #8, #9, #10; plus #2/#4 if licence permits)
   into this folder using the suggested filenames.
2. Access #5 and #7 via the uOttawa library; record the DOI/permalink if the PDF cannot be
   redistributed.
3. Resolve every **[verify authors]** entry against the primary source and update
   `../final_report/references.bib` and `../literature_review.md` to match.
