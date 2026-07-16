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

> Author lists, venues, and page numbers below were verified against the primary sources
> (arXiv / DOI / publisher records) in July 2026 and reconciled with `references.bib`.

## Index

| # | Sub-problem | Authors (year) | Title / venue | Identifier / link | Access | Suggested filename | Supports stage |
|---|-------------|----------------|---------------|-------------------|--------|--------------------|----------------|
| 1 | Listing generation | Li, Hu, Luo, Ma, Ding & Zhang (2024) | *A multimodal in-context tuning approach for e-commerce product description generation* (ModICT; LREC-COLING 2024) | arXiv:2402.13587 · https://arxiv.org/abs/2402.13587 | Open (arXiv) | `2024_ModICT_Li_et_al.pdf` | Generate |
| 2 | Listing generation | Kathiriya, Mullapudi & Karangara (2023) | *Optimizing e-commerce listing: LLM-based description and keyword generation from multimodal data* (IJSR 12(10), 2123–2130) | Paper ID SR24304113521 · https://www.ijsr.net/getabstract.php?paperid=SR24304113521 | Open-access journal | `2023_IJSR_Kathiriya_ecommerce_listing.pdf` | Generate |
| 3 | Recognition | Peng, Xiao & Li (2020) | *RP2K: A large-scale retail product dataset for fine-grained image classification* | arXiv:2006.12634 · https://arxiv.org/abs/2006.12634 | Open (arXiv) | `2020_RP2K_Peng_et_al.pdf` | Recognise (benchmark) |
| 4 | Recognition | Pettersson, Riveiro & Löfström (2024) | *Multimodal fine-grained grocery product recognition using image and OCR text* (Machine Vision and Applications 35(4), 79) | doi:10.1007/s00138-024-01549-9 · https://doi.org/10.1007/s00138-024-01549-9 | Springer (open access) | `2024_Pettersson_multimodal_ocr_grocery.pdf` | Recognise (VLM+OCR design proof) |
| 5 | Recognition | Geng, Han, Lin, Zhu, Bai, Wang, He, Xiao & Lai (2018) | *Fine-grained grocery product recognition by one-shot learning* (CAPG-GP; ACM MM 2018, 1706–1714) | doi:10.1145/3240508.3240522 · dataset: http://zju-capg.org/capg-gp.html | ACM DL (may need library) | `2018_CAPG-GP_Geng_et_al.pdf` | Recognise (low-data) |
| 6 | Pricing | Chen & Chou (2018) | *The price is right: Predicting prices with product images* (Stanford CS229 project report) | https://cs229.stanford.edu/proj2017/final-reports/5237321.pdf | Open (report PDF) | `2018_price_is_right_Chen_Chou.pdf` | Pricing (baseline) |
| 7 | Pricing | Fathalla, Salah, Li, Li & Piccialli (2020) | *Deep end-to-end learning for price prediction of second-hand items* (Knowledge and Information Systems 62, 4541–4568) | doi:10.1007/s10115-020-01495-8 · https://doi.org/10.1007/s10115-020-01495-8 | Springer (paywalled → uOttawa library) | `2020_secondhand_pricing_Fathalla_KAIS.pdf` | Pricing (multimodal baseline) |
| 8 | Pricing | Wang, You, Zhang, Xie, Han, Wu, Huang & Chen (2025) | *LLP: LLM-based product pricing in e-commerce* | arXiv:2510.09347 · https://arxiv.org/abs/2510.09347 | Open (arXiv) | `2025_LLP_Wang_et_al.pdf` | Pricing + confidence design |
| 9 | Image retrieval | Stanley, Vanjara, Pan, Pirogova, Chakraborty & Chaudhuri (2020) | *SIR: Similar image retrieval for product search in e-commerce* (Walmart Labs) | arXiv:2009.13836 · https://arxiv.org/abs/2009.13836 | Open (arXiv) | `2020_SIR_Stanley_et_al.pdf` | Image match + restricted-item flag |
| 10 | Image matching | Shin, Park, Woo, Cho, Oh & Song (2022) | *e-CLIP: Large-scale vision-language representation learning in e-commerce* (CIKM 2022) | arXiv:2207.00208 · https://arxiv.org/abs/2207.00208 | Open (arXiv) | `2022_eCLIP_Shin_et_al.pdf` | Match embeddings + adult-item detection |

## Access notes

Openly downloadable and safe to add directly: **#1, #3, #8, #9, #10** (arXiv), **#4**
(Springer open access), **#2** (open-access journal IJSR), and **#6** (open Stanford CS229
report PDF). **#5** (CAPG-GP) has an open dataset page, but the paper sits in the ACM Digital
Library and may require library access. **#7** is a Springer article behind a paywall —
access it through the uOttawa library and cite the DOI rather than committing the file.

## Industry landscape (context, not peer-reviewed)

The commercial snap-to-sell/resale apps referenced for market context — **Synclyst,
Snap2List, FlipSnap, AISeller, Sell AI** — are cited as evidence of demand and feasibility,
not as academic sources. They are closed and unevaluated, so there is nothing to archive
here; product pages can be linked inline in the report if needed.

## Checklist before submission

1. Download the open-access PDFs (#1–#4, #6, #8, #9, #10) into this folder using the
   suggested filenames.
2. Access #5 and #7 via the uOttawa library; record the DOI/permalink if the PDF cannot be
   redistributed.
3. Author lists are already reconciled with `../final_report/references.bib` and
   `../literature_review.md` — keep the three in sync if any entry changes.
