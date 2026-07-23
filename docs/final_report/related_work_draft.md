# Report Draft — Background / Related Work and Comparison of Approaches

**Snap-to-Sell (MIA 5100) — paste-ready prose for `final_report.tex`.**

> IEEE-style prose (no bullet lists in the body). Citation keys match
> `references.bib` (author lists verified against primary sources, July 2026).
> Drop these paragraphs under the report's *Background / Literature Review* and
> *Comparison of Approaches* headings; convert `\cite{}` calls as-is.

---

## Background / Literature Review (draft prose)

Automatically turning a product photograph into a publishable, priced listing draws on
four established research threads: listing-text generation, fine-grained product
recognition, price estimation, and product image retrieval. No prior work integrates all
four for packaged convenience-store goods, but each has matured enough to make an
end-to-end system feasible with off-the-shelf components.

Recent listing-generation research favours frozen foundation models over bespoke
encoder-decoders. ModICT \cite{li2024modict} generates product descriptions from an image
augmented with marketing keywords by keeping the visual encoder and language model frozen
and learning only the modules that assemble a multimodal in-context reference from a
similar product; it reports gains of up to 3.3\% Rouge-L and 9.4\% on a diversity metric.
Crucially, the authors identify the failure mode most relevant to our setting: descriptions
of same-category products collapse toward generic, inaccurate copy. Applied work on
LLM-based listing and keyword generation from image-plus-metadata \cite{kathiriya2023listing}
corroborates that multimodal prompting improves discoverability, though it treats product
identity and price as given rather than inferred.

Fine-grained recognition of packaged products is the most mature of the four threads.
Large-scale datasets such as {RP2K} \cite{peng2020rp2k}, with more than 500{,}000 shelf
images across 2{,}000 products annotated by size, shape, and flavour, and the
smartphone-captured {CAPG-GP} collection \cite{geng2018oneshot}, which supports one-shot
recognition from a single reference image, establish both a benchmark and a low-data
learning regime that mirror a real corner-store deployment. Directly relevant to our design,
multimodal recognition that fuses the product image with {OCR} of the packaging text
\cite{grocery2023ocr} outperforms image-only models, and the advantage is largest when
training data are scarce --- the empirical basis for our vision-language-plus-{OCR}
recognition stage.

Price estimation has moved from image-only regression toward retrieval-grounded, confidence-
aware generation. Early work regresses price directly from product images
\cite{chen2018priceright}, and multimodal models combining convolutional image features with
recurrent text encoders improve second-hand price prediction \cite{secondhand2020deep}, but
both are static and cannot track market movement. The most recent approach, {LLP}
\cite{llp2025}, retrieves comparable products to align with market dynamics, reasons over
their free-form text with a large language model, and --- most relevant to us --- applies a
confidence-based filter that rejects unreliable price suggestions. This validates our choice
to ground price in retrieved comparables and to route low-confidence estimates to human
review rather than publish a single confident number.

Finally, the image-upgrade stage --- replacing a casual shelf snap with a clean catalogue
image --- rests on product visual search. Similar-image retrieval over million-item catalogues
\cite{sir2020} and contrastive vision-language pretraining for e-commerce \cite{shin2022eclip}
provide the embedding-based matching we need to find a candidate image and, through
same-product verification, confirm it depicts the identical {SKU}. Both works also report a
capability we reuse for responsible-AI: detecting restricted or objectionable products
(e.g., e-cigarettes and adult items) from the same embeddings, letting one component serve
both image matching and age-restriction flagging.

## Comparison of Approaches (draft prose)

Across these works, three patterns recur. First, the field has converged on frozen,
pretrained models adapted through in-context examples or retrieval rather than trained from
scratch, which is what makes a term-length integration realistic. Second, multimodal fusion
consistently outperforms single-modality baselines --- image with {OCR} for recognition
\cite{grocery2023ocr}, and image with text for pricing \cite{secondhand2020deep} --- with the
largest gains in the low-data regime we expect. Third, the most recent systems add an explicit
reliability mechanism: {LLP} \cite{llp2025} filters low-confidence prices, and retrieval-based
matching \cite{sir2020,shin2022eclip} treats "same product" as a decision to be verified rather
than assumed.

The approaches differ mainly in grounding. Listing generators \cite{li2024modict} ground text in
a retrieved in-context example but not in a verified product identity or price; image-only price
models \cite{chen2018priceright} use no market signal at all; only the newest pricing work
\cite{llp2025} grounds estimates in live comparables. Our design inherits the strongest choice
from each thread --- {OCR}-fused recognition, comparable-grounded and confidence-gated pricing,
and verified image matching --- and composes them into a single evaluated pipeline. The
distinguishing decision is that image replacement is gated by a same-{SKU} match check: an
attractive but incorrect image is treated as a worse outcome than keeping the original photo,
and the false-swap rate is measured explicitly. A compact comparison of the reviewed systems by
sub-problem, modality, grounding signal, and reusable component appears in Table~\ref{tab:related}
(see the comparison table in `docs/literature_review.md`).
