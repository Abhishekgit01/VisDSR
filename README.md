# VisDSR

VisDSR is a study of sequential reasoning over disjoint-set union (DSU) forests. It asks whether a model's accuracy changes when the same initial state is given as a parent map, an image of that parent map, or a forest diagram. It also tests whether asking the model to transcribe the initial state before applying operations changes its accuracy. DSU keeps each intermediate state checkable while still requiring path compression and union decisions across steps.

**Status:** The C++ DSU simulator passes the worked example and 5,000 seeded random comparisons with a separate Python reference. A 12-task pilot and its 24 images have been generated and validated locally. The Qwen3-VL-8B-Instruct checkpoint is pinned for a three-call Kaggle smoke test. No real model call or research result exists yet. Generated pilot artifacts are excluded from Git and can be reproduced with the commands below.

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

## Qwen smoke test on Kaggle

1. Import [`notebooks/visdsr_qwen3vl8b_kaggle.ipynb`](notebooks/visdsr_qwen3vl8b_kaggle.ipynb) into Kaggle. Enable a GPU accelerator and Internet. Run All with `RUN_MODE = "smoke"` (the default).
2. The notebook clones this repository or reads an attached project dataset, installs the local inference dependencies, regenerates and validates pilot images, and runs the first pilot task under T-dir, R-dir, and G-dir. It prints the raw responses, strict JSON parse results, exact-match checks, latency, and GPU memory. It then stops.
3. Review that report before changing `RUN_MODE` to `pilot`. The pilot contains 60 calls; the main study contains 400 and also requires a frozen protocol. Neither is enabled by the initial notebook run.

Qwen uses [Qwen/Qwen3-VL-8B-Instruct](https://huggingface.co/Qwen/Qwen3-VL-8B-Instruct), pinned to the commit in [`configs/experiment.yaml`](configs/experiment.yaml), with bitsandbytes 4-bit NF4 weights, greedy decoding, and a 2,048-token output cap. The checkpoint revision and generation settings are recorded with each response. The official [Transformers Qwen3-VL guide](https://huggingface.co/docs/transformers/model_doc/qwen3_vl) describes the inference interface. The second model family is deferred until the Qwen run succeeds.

The runner hashes the model ID, revision, settings, task ID, condition, exact prompt, and image bytes for each request. It writes each raw response before moving to the next request and refreshes `results/cache_snapshot.zip` after each call. The notebook exports `visdsr_results.zip` with data, results, configuration, and manifest. Download that archive or save it as a Kaggle Dataset input to resume in a new session. Kaggle runtime storage alone does not persist across fresh sessions.

After an approved pilot, record the calibration decision with `python -m gen.freeze --calibration-note '...'`. Commit and tag the frozen protocol before generating main tasks. `python -m eval.run --split pilot --model mock` checks plumbing only and must not be used as a study result. Generated tasks, images, responses, and figures remain excluded from Git until reviewed for release. The current repository contains no measured accuracy values. The study is limited to clean synthetic diagrams, a fixed prompt family, and exact-match scoring; a transcription error cannot by itself identify a model's internal failure mechanism.
