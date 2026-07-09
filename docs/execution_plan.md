# Execution Plan — Snap-to-Sell (MIA 5100)

**Constraints:** ~2 working days · full pipeline, all stages functional · **paid hosted multimodal
model** for recognition + generation (everything else free/open) · graded on **report (30)** +
**presentation (20)**.

> **Why this is achievable.** One hosted multimodal API (Claude / Gemini / GPT-4o-mini) does
> **recognition, OCR, and listing generation** in a single call, eliminating the time otherwise
> spent standing up a VLM + LLM. The [pipeline](../snap-to-sell/) already runs end-to-end, so the
> **code is not the bottleneck — the test set and the report are.** This plan protects those two.

## 1. The three non-negotiables

1. **Start test-set collection in hour one.** It is the critical path. Target **~30 items**,
   including 4–6 tobacco items for the age-restriction metric.
2. **Write the report in parallel from the start**, not after the code works. The skeleton,
   figures, related-work prose, and references already exist.
3. **Only one paid component** — the hosted multimodal model. Everything else stays free/open. Set
   a hard spend cap of **$20** (realistic spend $0–5; see [cost](#5-cost)).

## 2. Stack (paid where it buys the most time)

| Stage | Choice | Cost |
|-------|--------|------|
| Capture / pre-process | OpenCV | free |
| **Recognise + OCR** | **Hosted multimodal API** (OpenAI GPT-4o-mini / GPT-5.4-mini, Claude Haiku, or Gemini Flash): image → structured identity JSON | paid* |
| **Generate** | **Same hosted API**: identity + retrieved attrs → grounded listing | paid* |
| Retrieve (name/price) | Open Food Facts + Open Products Facts + Open Prices | free |
| Image upgrade / match | OpenCLIP ViT-B/32 (or perceptual-hash) same-SKU verify | free |
| Guardrails | category tags + rules + confidence | free |
| Review UI / store | Gradio + CSV | free |
| Evaluation | pandas / scikit-learn | free |

\* The only spend. Defaults to OpenAI `gpt-4o-mini`; Claude Haiku or Gemini Flash also work (Gemini
has a standing free tier). Provider is chosen via `SNAP_LLM_PROVIDER`.

## 3. Workstreams

| WS | Area | Owner |
|----|------|-------|
| A | Model integration — hosted multimodal call + prompts (recognise + generate) | _assign_ |
| B | Data & Retrieval — **test set (critical path)** + OFF/OPF/Open Prices | _assign_ |
| C | Image match + Guardrails | _assign_ |
| D | Integration, UI & Eval | _assign_ |
| E | Report & Presentation (starts immediately) | _assign_ |

Working solo, run the workstreams in critical-path order (A/B first), and treat E as a parallel
track you touch every few hours rather than leaving to the end.

## 4. Schedule (half-day blocks)

**Block 1 — parallel start.** Scope lock (categories, ~30-item target). Begin
photographing/labelling and confirm OFF/OPF return hits. Get one hosted multimodal call returning
structured identity + draft listing for one image. Confirm secrets handling and that the pipeline
runs. Start Intro/Problem/Methodology in the report.

**Block 2 — first real path.** Recognition returns reliable identity + listing across sample
images. Retrieval live (OFF/OPF + Open Prices + image URL); ~20 items labelled. Image-match +
guardrails wired; review UI shows a real listing. *Gate: real photo → real listing end-to-end.*

**Block 3 — finish data, evaluate.** Complete the ~30-item test set with observed prices. Run the
full evaluation (id accuracy, price error, listing rating, age recall, image false-swap rate) vs
the naive baseline; quick failure-mode notes. Fix only the top breakages. *Gate: results table +
failure notes done.*

**Block 4 — write & rehearse (code freeze).** Fill Results / Implementation / Conclusion. Record a
backup demo GIF. Rehearse the timed 10-minute talk. *Gate: report PDF + slides done; dry-run < 10 min.*

## 5. Cost

Only the hosted model costs money. For ~30 items run repeatedly (~1,000–1,500 calls):
**~$0 on Gemini Flash free tier**, ~$1–2 on GPT-4o-mini or Claude Haiku, up to ~$15–20 if you use a
premium model for hard SKUs. Set a **$20 hard cap**.

## 6. Critical path & what to cut if a block slips

`Test set` and `hosted call` are the critical path; both must be solid early or Results slips.

Cut order under pressure (per-stage fallbacks, pipeline stays whole):

1. Shrink test set to ~20 items.
2. Image-upgrade: report match score only, always keep the original photo (skip the swap).
3. Guardrails: rules-only (drop CLIP-based checks), keep the tobacco flag.
4. Generation: template copy instead of full LLM prose.

## 7. Evaluation (≈30-item set)

Top-1/Top-3 identification, price median abs. % error (vs observed), blind listing-quality rating,
tobacco-flag recall, image false-swap rate — each vs a naive baseline (caption → generic listing,
no retrieval/guardrails).

## 8. Deliverables

IEEE 5-page report (`docs/final_report/final_report.tex` — skeleton ready) + 10-minute presentation
+ code/demo. The paid model is documented as an **optional accelerator**; the open-source path is
the reproducible default so the "open" framing holds.
