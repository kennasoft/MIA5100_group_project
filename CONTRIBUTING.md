# Contributing

Short rules to keep the build from turning into merge chaos.

## Ground rules

- **Don't change `snap-to-sell/src/snap_to_sell/interfaces.py` without team agreement.** Everyone
  builds against those dataclasses; changing a field breaks other people's stages.
- **Replace your stub in place.** Keep the function name and signature; swap the body. The
  pipeline must keep running end-to-end at all times (stub → real is a drop-in).
- **A stubbed-but-connected stage beats a perfect-but-unintegrated one.** If you're blocked,
  leave the stub and flag it early.
- **Commit small and often**, with a clear message. Run `make test` before you push.

## Workstreams

See [`docs/task_breakdown.md`](docs/task_breakdown.md) and [`docs/execution_plan.md`](docs/execution_plan.md).

## Running things

    cd snap-to-sell
    make run      # run the pipeline on the sample image
    make test     # smoke test (pipeline runs end-to-end)
    make ui       # Gradio review UI (needs: pip install gradio)
    make eval     # evaluation harness (needs data/testset/labels.csv)

Heavy models (VLM / LLM / CLIP) run in the shared Colab notebooks under `snap-to-sell/notebooks/`;
export reusable code back into the matching `src/snap_to_sell/` module.

## Report

LaTeX source in `docs/final_report/`. Build with `pdflatex` + `bibtex` (needs a TeX distro).
Add references to `references.bib` (key `lastnameYYYYkeyword`) and cite with `\cite{key}`.
Figures live in `docs/final_report/figures/` and are already referenced by name.
