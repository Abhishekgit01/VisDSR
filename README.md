# VisDSR

VisDSR is a study of sequential reasoning over disjoint-set union (DSU) forests. It asks whether a model's accuracy changes when the same initial state is given as a parent map, an image of that parent map, or a forest diagram. It also tests whether asking the model to transcribe the initial state before applying operations changes its accuracy. DSU keeps each intermediate state checkable while still requiring path compression and union decisions across steps.

**Status:** The C++ DSU simulator passed a worked example and 5,000 seeded comparisons with a separate Python reference. Qwen3-VL-8B-Instruct completed the first 12-task, four-operation pilot on Kaggle. All three direct conditions scored 0/12 on final-state exact match, so the protocol remains unfrozen. A separate 12-task calibration round with one- and two-operation tasks is prepared. No main run has occurred; model responses and generated data are kept outside Git.

## Study design

Each task starts from a DSU forest reachable under full path compression and union-by-size. A `find` compresses its entire traversed path. A `union` runs both finds first; on an equal-size tie, the second argument's root attaches under the first argument's root. Every presentation of a task uses the same operations and output requirements.

| Condition | Initial state | Additional output |
| --- | --- | --- |
| T-dir | Canonical JSON parent map | None |
| R-dir | PNG of the same JSON string | None |
| G-dir | Forest diagram, with child-to-parent arrows | None |
| T-str | Canonical JSON parent map | Initial-state transcription |
| G-str | Forest diagram | Initial-state transcription |

The first pilot has 12 four-operation tasks. The second calibration round has 12 new tasks: three for each combination of 8 or 16 elements and 1 or 2 operations. The planned main design has 80 tasks: 20 for each combination of 8 or 16 elements and 1 or 4 operations. Its final difficulty is pending calibration. Each main task appears in all five conditions. The primary comparison is paired final-state exact-match accuracy for **G-dir versus T-dir**. The analysis code also computes a paired bootstrap confidence interval and an exact McNemar test; the other contrasts and error measures are described in [`SPEC.md`](SPEC.md). These are analysis plans, not findings.

| Path | Purpose |
| --- | --- |
| [`sim/dsu.cpp`](sim/dsu.cpp) | C++ simulator interface and operation protocol |
| [`gen/`](gen/) | Seeded tasks, image rendering, and validation |
| [`eval/`](eval/) | Prompts, local inference, validation, and scoring |
| [`analysis/`](analysis/) | Paired statistics and figure generation |
| [`tests/`](tests/) | Worked cases and independent simulator checks |
| [`notebooks/visdsr_qwen3vl8b_kaggle.ipynb`](notebooks/visdsr_qwen3vl8b_kaggle.ipynb) | Kaggle GPU setup and guarded Qwen run |

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

## Qwen calibration on Kaggle

The first pilot is complete and preserved in the private `visdsr_results.zip` export. The exact archive reviewed for calibration has SHA-256 `a7a3eaa8b3d51f1d18ff57bc7bbba97735cdb077da5936bd751ec86e33974fa8`. Its 60 responses matched the saved scores, and the direct conditions were at floor. The second round uses a new seed and shorter operation sequences. It uses the same task generator, renderer, prompts, DSU rules, model settings, and scoring. It is calibration data, not a main-study result.

1. Import the latest [`notebooks/visdsr_qwen3vl8b_kaggle.ipynb`](notebooks/visdsr_qwen3vl8b_kaggle.ipynb) into Kaggle. Enable a GPU and Internet. Attach the first-pilot `visdsr_results.zip` as a Kaggle input.
2. Run All with the default `RUN_MODE = "pilot2_smoke"`. It generates and validates the new tasks, makes three calls, exports a cumulative zip, and stops for review.
3. After reviewing that smoke report, set `RUN_MODE = "pilot2"` and `PILOT2_SMOKE_REVIEWED = True`. Run the settings cell, then the evaluation and export cells. The full round has 60 task-condition pairs and skips the three cached smoke calls.
4. Download the new `/kaggle/working/visdsr_results.zip`. The notebook prints strict scores by operation count and writes a separate diagnostic report. No freeze decision is made automatically.

Qwen uses [Qwen/Qwen3-VL-8B-Instruct](https://huggingface.co/Qwen/Qwen3-VL-8B-Instruct), pinned in [`configs/experiment.yaml`](configs/experiment.yaml), with bitsandbytes 4-bit NF4 weights, greedy decoding, and a 2,048-token output cap. The checkpoint revision and generation settings are recorded with each response. No paid inference API is used.

The runner hashes the model ID, revision, settings, task ID, condition, exact prompt, and image bytes. It writes every raw response before the next request and refreshes `results/cache_snapshot.zip` after each call. The notebook restores only `data/` and `results/` from an attached export, so an older archive cannot replace the current code or configuration. Keep the latest export outside Kaggle's temporary session storage.

After both rounds are reviewed, record the calibration decision with `python -m gen.freeze --calibration-note '...'`. Commit and tag the frozen protocol before generating main tasks. `python -m eval.run --split pilot2 --model mock` checks plumbing only and is not a study result. Generated tasks, images, responses, and figures remain excluded from Git until reviewed for release. Exact-match scoring cannot by itself identify a model's internal failure mechanism.
