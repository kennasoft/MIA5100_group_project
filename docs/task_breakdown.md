# Task Board — Snap-to-Sell

Owner × half-day block. Companion to [`execution_plan.md`](execution_plan.md). Interfaces frozen in
`snap-to-sell/src/snap_to_sell/interfaces.py` — WS-D owns changes.

## Workstreams

| WS | Area | Owner |
|----|------|-------|
| A | Model integration (hosted multimodal: recognise + generate) | _assign_ |
| B | Data & Retrieval (test set + OFF/OPF/Open Prices) | _assign_ |
| C | Image match + Guardrails | _assign_ |
| D | Integration, UI & Eval | _assign_ |
| E | Report & Presentation | _assign_ |

## Block 1 — parallel start

| WS | Task |
|----|------|
| A | API key + one multimodal call returns identity + draft listing for a sample image |
| B | Begin photographing/labelling; confirm OFF/OPF return hits for chosen categories |
| C | Stand up OpenCLIP (or perceptual hash); load embeddings on a sample pair |
| D | Secrets handling; confirm pipeline runs; own the data contract |
| E | Draft Intro + Problem + Methodology |

## Block 2 — first real path

| WS | Task |
|----|------|
| A | Prompt returns reliable identity + grounded listing across samples |
| B | Retrieval live (OFF/OPF + Open Prices + image URL); ~20 items labelled |
| C | Same-SKU match + tobacco/confidence guardrails wired |
| D | Real modules behind the interfaces; Gradio UI shows a real listing |
| E | Draft Implementation & Design (use architecture figure) |
| — | **Gate: real photo → real listing end-to-end** |

## Block 3 — finish data + evaluate

| WS | Task |
|----|------|
| B | Complete ~30-item test set + observed prices |
| D+E | Full evaluation vs baseline; failure-mode notes |
| A+C | Fix top breakages only (change-freeze) |
| — | **Gate: results table + failure notes done** |

## Block 4 — write + rehearse (code freeze)

| WS | Task |
|----|------|
| all | Fill Results / Implementation / Conclusion in the report |
| E | APA references, figure captions, proofread |
| D | Record backup demo GIF |
| all | Rehearse timed 10-min talk (dry-run < 10 min) |
| — | **Gate: report PDF + slides done** |

Slip rule: shrink test set → drop image swap → rules-only guardrails → template copy. Keep the
pipeline whole (fallbacks in `execution_plan.md` §6).
