# snap-to-sell

Photo of a packaged corner-store product → recognise → retrieve price/image → generate a grounded
listing → verify a same-SKU image swap → guardrails (age-restriction, hallucination, confidence)
→ human review → publish. Built on a free open-data backbone (Open Food Facts + Open Prices) with
an **optional** hosted multimodal model (OpenAI / Anthropic / Gemini) as an accelerator.

## Quick start

    pip install -r requirements.txt
    python -m src.snap_to_sell.pipeline data/testset/duracell_aa.jpg   # runs offline out of the box
    make test                                                     # tests
    make eval                                                     # metrics over data/testset/

Runs with **no API key** using offline fallbacks (hand-labelled `<image>.json` sidecars for
recognition, template listing copy, perceptual-hash image match). This is the demo/eval mode.

## Enable the hosted model (real recognition + generation)

    cp .env.example .env      # add OPENAI_API_KEY (default) — or ANTHROPIC_API_KEY / GEMINI_API_KEY
    set -a; source .env; set +a
    python -m src.snap_to_sell.pipeline data/testset/duracell_aa.jpg

The pipeline prints which provider is active. Provider is chosen by `SNAP_LLM_PROVIDER`
(defaults to OpenAI `gpt-4o-mini`). See `../docs/execution_plan.md` for the cost note.

## How it degrades (never breaks)

| Stage | Real | Offline fallback |
|-------|------|------------------|
| capture | OpenCV normalise | passthrough |
| recognise | hosted VLM (OpenAI/Anthropic/Gemini) | `<image>.json` sidecar → unknown |
| retrieve | Open Food Facts + Open Prices | identity-grounded bundle |
| generate | hosted LLM (grounded) | deterministic template |
| imagematch | OpenCLIP | perceptual hash → keep original |
| guardrails | age + confidence + claim-grounding | (always real) |

## Layout

`src/snap_to_sell/` — stages + `interfaces.py` (frozen data contract; change with team agreement) +
`providers.py` (hosted-model client) + `config.py` (env knobs). `app/ui.py` Gradio review UI ·
`eval/harness.py` metrics · `data/testset/` images + `labels.csv`.
See `../docs/execution_plan.md` and `../docs/task_breakdown.md`.
