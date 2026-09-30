# VisDSR

VisDSR is a study of sequential reasoning over disjoint-set union (DSU) forests. It asks whether a model's accuracy changes when the same initial state is given as a parent map, an image of that parent map, or a forest diagram. It also tests whether asking the model to transcribe the initial state before applying operations changes its accuracy. DSU keeps each intermediate state checkable while still requiring path compression and union decisions across steps.

**Status:** The C++ DSU simulator passes the worked example and 5,000 seeded random comparisons with a separate Python reference. A 12-task pilot and its 24 images have been generated and validated locally. Exact model IDs and API keys are still missing, so no live model call or research result exists. Generated pilot artifacts are excluded from Git and can be reproduced with the commands below.

## Study design

Each task starts from a DSU forest reachable under full path compression and union-by-size. A `find` compresses its entire traversed path. A `union` runs both finds first; on an equal-size tie, the second argument's root attaches under the first argument's root. Every presentation of a task uses the same operations and output requirements.

| Condition | Initial state | Additional output |
| --- | --- | --- |
| T-dir | Canonical JSON parent map | None |
| R-dir | PNG of the same JSON string | None |
| G-dir | Forest diagram, with child-to-parent arrows | None |
| T-str | Canonical JSON parent map | Initial-state transcription |
| G-str | Forest diagram | Initial-state transcription |

The pilot design specifies 12 four-operation tasks. The main design specifies 80 tasks: 20 for each combination of 8 or 16 elements and 1 or 4 operations. Each main task appears in all five conditions. The primary comparison is paired final-state exact-match accuracy for **G-dir versus T-dir**. The analysis code also computes a paired bootstrap confidence interval and an exact McNemar test; the other contrasts and error measures are described in [`SPEC.md`](SPEC.md). These are analysis plans, not findings.

| Path | Purpose |
| --- | --- |
| [`sim/dsu.cpp`](sim/dsu.cpp) | C++ simulator interface and operation protocol |
| [`gen/`](gen/) | Seeded tasks, image rendering, and validation |
| [`eval/`](eval/) | Prompts, provider calls, validation, and scoring |
| [`analysis/`](analysis/) | Paired statistics and figure generation |
| [`tests/`](tests/) | Worked cases and independent simulator checks |

## Run locally

Requires Python 3.11+, a C++17 compiler, and Graphviz `dot` on `PATH`.

```bash
python -m pip install -r environment/requirements.txt
make build
make test
make lint
make stress
```

`make test` checks the Python infrastructure. `make stress` compares the C++ simulator against a separate test oracle on the worked example and 5,000 seeded random cases. The current simulator passes both. To regenerate the pilot:

```bash
python -m gen.generate --split pilot --structure dsu
python -m gen.render --split pilot
python -m gen.validate --split pilot
python -m gen.render --split pilot --qa
```

Validation replays each task through the C++ simulator and checks image dimensions, geometry, pixels, filenames, and manifest hashes. The last command exports a contact sheet for visual inspection. See [`tests/examples.json`](tests/examples.json) for a worked DSU case and [`STUDENT_UNDERSTANDING.md`](STUDENT_UNDERSTANDING.md) for the implementation explanation and AI-assistance record.

## From pilot to main study

1. Inspect the pilot images and model responses. Record the calibration decision before generating main tasks. The protocol allows at most one additional pilot round.
2. Set exact model IDs in [`configs/experiment.yaml`](configs/experiment.yaml). Provide API keys through `OPENAI_API_KEY` and `ANTHROPIC_API_KEY` environment variables; `.env` is ignored by Git.
3. Run the pilot with `python -m eval.run --split pilot --model model1 --allow-paid-run` (and `model2`). Live calls require the explicit flag. A local `--model mock` checks plumbing only and must not be used as a study result.
4. After a complete pilot run, record the decision with `python -m gen.freeze --calibration-note '...'`. Commit and tag the frozen protocol before generating a fresh main set.
5. Generate and render main tasks with `python -m gen.generate --split main --structure dsu` and `python -m gen.render --split main`. Then run both models, and use `python -m analysis.analyze` for the tables and accuracy figure.

Requests are shuffled with a fixed seed and cached by exact model ID, settings, prompt, and image hash. `python -m eval.run --split main --model model1 --score-only` re-scores cached responses without API calls. `python -m manifest` records source, configuration, dataset, image, and environment information once artifacts exist.

Generated tasks, images, responses, and figures are excluded from Git until reviewed for release. The current repository contains no measured accuracy values. The study is limited to clean synthetic diagrams, a fixed prompt family, two planned model evaluations, and exact-match scoring; a transcription error cannot by itself identify a model's internal failure mechanism.
