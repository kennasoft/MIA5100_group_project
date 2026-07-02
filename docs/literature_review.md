# Literature Review (Draft) — Snap-to-Sell for Corner-Store Inventory

**MIA 5100 — Machine Learning — Group Project**
**Stream: Hands-On AI System Development Project (Build & Evaluate)**

> **Draft for team review.** Citations below use APA style per the
> [uOttawa citation guidelines](https://www.uottawa.ca/library/writing-citing/citation-styles).
> A few preprint author lists are marked **[verify authors]** — confirm each against the
> linked source before the report is finalised (arXiv IDs / DOIs are given so this is quick).
> The instructions ask for 5–10 landmark papers; ten are profiled here across the four
> sub-problems, plus an industry-landscape note.

---

## 1. Scope of the Review

No single published system does what we propose — photograph a packaged corner-store product
and return a priced, image-upgraded, publishable listing. But the system decomposes into four
well-studied sub-problems, each with a mature literature:

1. **Automatic listing / description generation** from product images.
2. **Fine-grained packaged (retail/grocery) product recognition.**
3. **Image-based and multimodal price estimation.**
4. **Product image retrieval and same-product verification** (for the image-upgrade step).

We review each in turn, note strengths and limitations, then summarise emerging trends and the
gap our project targets.

## 2. Automatic Listing / Description Generation

**Li, Y., Hu, B., Luo, W., Ma, L., Ding, Y., & Zhang, M. (2024). *A multimodal in-context
tuning approach for e-commerce product description generation* (ModICT). Proceedings of
LREC-COLING 2024. arXiv:2402.13587. https://arxiv.org/abs/2402.13587**

- *Problem.* Generate a product description from an image plus marketing keywords.
- *Method.* Keeps the visual encoder and LLM **frozen**; learns only the modules that build a
  multimodal in-context reference (a similar product example) and dynamic prompts.
- *Findings.* Improves accuracy (+3.3% Rouge-L) and diversity (+9.4% D-5) over conventional
  encoder-decoder baselines.
- *Strengths / relevance.* Directly informs our **Generate** stage and validates leaning on a
  frozen LLM with retrieved in-context examples rather than training from scratch. It also
  names our exact risk — same-category products get **generic, inaccurate copy**.
- *Limitations.* Text only; no pricing, no image sourcing, no factual-grounding guarantee for
  a *selling* (misrepresentation) context.

**[verify authors] (2024). Optimizing e-commerce listing: LLM-based description and keyword
generation from multimodal data. *International Journal of Science and Research (IJSR), 13*.
https://www.ijsr.net/getabstract.php?paperid=SR24304113521**

- *Problem / method.* Uses an LLM over image + metadata (size, weight, colour) to auto-generate
  search-optimised descriptions and keywords.
- *Relevance.* Applied evidence that image-plus-metadata LLM listing generation works and lifts
  discoverability/conversion.
- *Limitations.* Applied/industry framing, limited methodological rigour and no public
  benchmark; treats identity and price as given rather than inferred.

## 3. Fine-Grained Packaged Product Recognition

**Peng, J., Xiao, C., & Li, Y. (2020). *RP2K: A large-scale retail product dataset for
fine-grained image classification.* arXiv:2006.12634. https://arxiv.org/abs/2006.12634**

- *Contribution.* 500,000+ shelf images across 2,000 products, captured in real stores under
  natural lighting, with annotations for size, shape, and flavour/scent.
- *Relevance.* A ready benchmark for our **Recognise** stage that matches our real-world
  setting (shelf photos, fine-grained variants).
- *Limitations.* Classification only — no listing text, no price; catalogue is region-specific.

**[verify authors] (2023). *Multimodal fine-grained grocery product recognition using image and
OCR text.* https://www.researchgate.net/publication/375000319**

- *Problem / method.* Fuses the product **image with OCR of the packaging text** for
  fine-grained recognition.
- *Findings.* Multimodal (image + OCR) beats unimodal, **especially with few training samples**.
- *Strengths / relevance.* This is the empirical backbone of our core design choice — VLM + OCR
  fusion — and supports feasibility under a small, self-collected dataset.
- *Limitations.* Recognition only; no downstream listing or pricing.

**[verify authors] (2018). *Fine-grained grocery product recognition by one-shot learning*
(CAPG-GP dataset). Proceedings of ACM Multimedia 2018.
http://zju-capg.org/capg-gp.html**

- *Contribution.* Smartphone-captured grocery dataset (box/bag/tube packaging) with one-shot
  recognition — i.e., recognising a product from a **single** reference image.
- *Relevance.* Directly relevant to the low-data reality of a corner-store deployment where you
  cannot collect many photos per SKU.
- *Limitations.* Small scale; older backbone; recognition only.

## 4. Image-Based and Multimodal Price Estimation

**Chen, S., & Chou, E. (2018). *The price is right: Predicting prices with product images.*
https://www.semanticscholar.org/paper/55774d24c98f8e77275a5e3629ed1503a22497b8**

- *Problem / method.* Regress/classify price directly from a product image using CNN features
  (with HOG/linear baselines).
- *Findings.* Deep CNN features outperform hand-crafted baselines for price prediction.
- *Relevance.* Establishes that images carry price signal — useful as a **baseline** to beat.
- *Limitations.* Image-only; no market/comparable grounding; accuracy is coarse.

**[verify authors] (2020). Deep end-to-end learning for price prediction of second-hand items.
*Knowledge and Information Systems, 62.* https://doi.org/10.1007/s10115-020-01495-8**

- *Problem / method.* Multimodal (CNN image + LSTM text) end-to-end price prediction for
  second-hand goods.
- *Relevance.* Closest prior modality mix to ours; shows image+text improves price estimates.
- *Limitations.* Static regression — does not track market dynamics; no retrieval of live
  comparables (which is central to our design).

**[verify authors] (2025). *LLP: LLM-based product pricing in e-commerce.* arXiv:2510.09347.
https://arxiv.org/pdf/2510.09347**

- *Problem / method.* First **LLM-based generative** pricing framework; **retrieves similar
  products** to track market change, then reasons over free-form text; adds a
  **confidence-based filter to reject unreliable price suggestions**; deployed on Xianyu.
- *Strengths / relevance.* Strongly validates two of our design choices: **retrieval-grounded
  pricing** and **confidence-gated output** (we route low-confidence prices to human review).
- *Limitations.* Second-hand C2C focus, not packaged FMCG; heavy fine-tuning (SFT + GRPO)
  beyond our term's scope — we will approximate with retrieval + heuristics.

## 5. Product Image Retrieval and Same-Product Verification

*(The evidence base for the image-upgrade step: finding a clean, high-res image that is the
**same** product, not merely similar.)*

**[verify authors] (2020). *SIR: Similar image retrieval for product search in e-commerce.*
arXiv:2009.13836. https://arxiv.org/pdf/2009.13836**

- *Problem / method.* Embedding + approximate-nearest-neighbour retrieval of visually similar
  products across a catalogue of millions; includes a **variant-item detection** application
  and detection of **objectionable themes (explicitly e-cigarettes)**.
- *Strengths / relevance.* Maps onto both our needs at once — retrieving/verifying the
  matching product image **and** the responsible-AI flagging of restricted items.
- *Limitations.* Retrieval quality depends on catalogue coverage; "similar" is not "identical,"
  which is precisely the false-swap risk we must measure.

**[verify authors] (2022). *e-CLIP: Large-scale vision-language representation learning in
e-commerce.* arXiv:2207.00208. https://arxiv.org/pdf/2207.00208**

- *Problem / method.* Contrastive image–text pretraining on raw product data; evaluated on
  category classification, attribute extraction, **product matching**, clustering, and
  **adult-product recognition**.
- *Strengths / relevance.* Provides the embedding backbone for our **image–product match
  check** and, again, for restricted-item detection.
- *Limitations.* Large-scale pretraining assumed; we will use an off-the-shelf CLIP-style model
  rather than train our own.

## 6. Comparison of Approaches

| Work | Sub-problem | Modalities | Core approach | Grounding / market signal | Directly reusable for us |
|------|-------------|-----------|---------------|---------------------------|--------------------------|
| ModICT (Li et al., 2024) | Listing text | Image + keywords | Frozen LLM + in-context reference | In-context example only | Generate stage |
| IJSR (2024) | Listing text/keywords | Image + metadata | LLM prompt over metadata | None | Generate stage |
| RP2K (Peng et al., 2020) | Recognition | Image | Fine-grained CNN classification | n/a | Recognise benchmark |
| Multimodal OCR (2023) | Recognition | Image + OCR | Multimodal fusion | n/a | **VLM+OCR design proof** |
| CAPG-GP (2018) | Recognition | Image | One-shot learning | n/a | Low-data recognition |
| Price is Right (Chen & Chou, 2018) | Pricing | Image | CNN regression | None | Pricing baseline |
| Second-hand pricing (2020) | Pricing | Image + text | CNN+LSTM regression | None (static) | Multimodal price baseline |
| LLP (2025) | Pricing | Text + retrieval | LLM + retrieval + confidence filter | **Retrieved comparables** | **Pricing + confidence design** |
| SIR (2020) | Image retrieval | Image | ANN over embeddings | Catalogue | **Image match + restricted flag** |
| e-CLIP (2022) | Matching | Image + text | Contrastive pretraining | Catalogue | **Match embeddings + adult-item** |

## 7. Emerging Trends

1. **Frozen foundation models over training from scratch.** Both listing generation (ModICT)
   and pricing (LLP) now lean on frozen VLMs/LLMs with in-context examples or retrieval,
   matching what a one-term project can realistically assemble.
2. **Multimodal fusion beats unimodal**, especially with limited data — image + OCR for
   recognition, image + text for pricing.
3. **Retrieval-augmented, confidence-aware pricing.** The field is moving from static
   image→price regression toward retrieving live comparables and rejecting low-confidence
   estimates — exactly our design.
4. **Contrastive (CLIP-style) embeddings** are the default tool for product matching *and*,
   notably, for detecting restricted/objectionable products — letting one component serve both
   our image-upgrade and age-restriction requirements.

## 8. Identified Gap and Novelty

- **No integrated, evaluated pipeline.** Each stage is solved in isolation; we found no
  published work chaining recognition → comparable-based pricing → verified image replacement
  → grounded listing generation, evaluated end-to-end.
- **Corner-store FMCG framing is underexplored.** Prior work targets shelf-audit recognition,
  fashion/electronics resale, or generic e-commerce — not the packaged convenience-goods
  listing-and-pricing use case.
- **Image replacement *with verification* is novel as a studied step.** Retrieval literature
  optimises "similar"; we make **same-SKU verification and the false-swap rate** first-class,
  measurable outcomes.
- **Responsible-AI in a selling context** — age-restricted-item flagging (tobacco) and
  hallucination/misrepresentation control — is largely absent from the listing-generation
  literature.
- **Commercial-but-closed prior art.** Snap-to-sell resale apps (Synclyst, Snap2List, FlipSnap,
  AISeller, Sell AI) already ship the *pipeline*, but target used goods, are proprietary, and
  publish **no evaluation**. Our contribution is therefore a **reproducible, measured** system
  with an explicit failure analysis, not a novel widget.

## 9. Industry Landscape (context, not peer-reviewed)

For completeness, several commercial tools perform photo→listing for **resale**: Synclyst,
Snap2List, FlipSnap, AISeller, and Sell AI. They confirm demand and feasibility but are closed
and unevaluated; they are cited as market context, not as academic references.

## References (APA — draft)

Chen, S., & Chou, E. (2018). *The price is right: Predicting prices with product images.*

Li, Y., Hu, B., Luo, W., Ma, L., Ding, Y., & Zhang, M. (2024). *A multimodal in-context tuning
approach for e-commerce product description generation.* Proceedings of LREC-COLING 2024.
https://arxiv.org/abs/2402.13587

Peng, J., Xiao, C., & Li, Y. (2020). *RP2K: A large-scale retail product dataset for
fine-grained image classification.* arXiv. https://arxiv.org/abs/2006.12634

*[verify authors]* (2018). *Fine-grained grocery product recognition by one-shot learning.*
Proceedings of the 26th ACM International Conference on Multimedia.

*[verify authors]* (2020). Deep end-to-end learning for price prediction of second-hand items.
*Knowledge and Information Systems, 62*(3). https://doi.org/10.1007/s10115-020-01495-8

*[verify authors]* (2020). *SIR: Similar image retrieval for product search in e-commerce.*
arXiv. https://arxiv.org/abs/2009.13836

*[verify authors]* (2022). *e-CLIP: Large-scale vision-language representation learning in
e-commerce.* arXiv. https://arxiv.org/abs/2207.00208

*[verify authors]* (2023). *Multimodal fine-grained grocery product recognition using image and
OCR text.* ResearchGate. https://www.researchgate.net/publication/375000319

*[verify authors]* (2024). Optimizing e-commerce listing: LLM-based description and keyword
generation from multimodal data. *International Journal of Science and Research, 13.*
https://www.ijsr.net/getabstract.php?paperid=SR24304113521

*[verify authors]* (2025). *LLP: LLM-based product pricing in e-commerce.* arXiv.
https://arxiv.org/abs/2510.09347

---

*Prepared as a draft for team validation. Confirm all author lists, venues, and page numbers
against the primary sources, and re-run any figures through the uOttawa academic-integrity
guidance before submission.*
