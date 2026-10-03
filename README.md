# VisDSR

VisDSR is a study of sequential reasoning over disjoint-set union (DSU) forests. It asks whether a model's accuracy changes when the same initial state is given as a parent map, an image of that parent map, or a forest diagram. It also tests whether asking the model to transcribe the initial state before applying operations changes its accuracy. DSU keeps each intermediate state checkable while still requiring path compression and union decisions across steps.

**Status:** The C++ DSU simulator passed a worked example and 5,000 seeded comparisons with a separate Python reference. Qwen3-VL-8B-Instruct completed two calibration pilots; its shorter second pilot scored T-dir 1/12, R-dir 0/12, and G-dir 0/12. An InternVL3.5 smoke test on one task returned strict-correct JSON for T-dir but invalid output for both image conditions. The protocol remains unfrozen, and no full InternVL pilot or main run has occurred. Model responses and generated data remain outside Git.

The [pilot and feasibility report](REPORT.md) summarizes the completed runs, stop decision, and limitations.

## Study design

Each task starts from a DSU forest reachable under full path compression and union-by-size. A `find` compresses its entire traversed path. A `union` runs both finds first; on an equal-size tie, the second argument's root attaches under the first argument's root. Every presentation of a task uses the same operations and output requirements.

| Condition | Initial state | Additional output |
| --- | --- | --- |
| T-dir | Canonical JSON parent map | None |
| R-dir | PNG of the same JSON string | None |
| G-dir | Forest diagram, with child-to-parent arrows | None |
| T-str | Canonical JSON parent map | Initial-state transcription |
| G-str | Forest diagram | Initial-state transcription |

The first pilot used 12 four-operation tasks. The second calibration round used 12 new tasks: three for each combination of 8 or 16 elements and 1 or 2 operations. The original main design specifies 80 tasks: 20 for each combination of 8 or 16 elements and 1 or 4 operations. That plan is inactive after Qwen calibration. Each main task appears in all five conditions. The primary comparison is paired final-state exact-match accuracy for **G-dir versus T-dir**. The analysis code also computes a paired bootstrap confidence interval and an exact McNemar test; the other contrasts and error measures are described in [`SPEC.md`](SPEC.md). These are analysis plans, not findings.

| Path | Purpose |
| --- | --- |
| [`sim/dsu.cpp`](sim/dsu.cpp) | C++ simulator interface and operation protocol |
| [`gen/`](gen/) | Seeded tasks, image rendering, and validation |
| [`eval/`](eval/) | Prompts, local inference, validation, and scoring |
| [`analysis/`](analysis/) | Paired statistics and figure generation |
| [`tests/`](tests/) | Worked cases and independent simulator checks |
| [`notebooks/visdsr_qwen3vl8b_kaggle.ipynb`](notebooks/visdsr_qwen3vl8b_kaggle.ipynb) | Kaggle GPU setup and guarded Qwen run |
| [`notebooks/internvl35_visdsr.ipynb`](notebooks/internvl35_visdsr.ipynb) | Kaggle three-call InternVL3.5 feasibility check |

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

## Calibration result

The first, four-operation Qwen pilot scored 0/12 in each direct condition. The second pilot used 12 new one- and two-operation tasks without changing the prompts, renderer, DSU rules, model settings, or scorer. It scored T-dir 1/6 on one-operation tasks and 0/6 on two-operation tasks; R-dir and G-dir scored 0/12 each. The near-zero text baseline does not support the planned modality comparison, so the Qwen main run is stopped. G-str returned string transcriptions in all 12 second-pilot calls; the prompt did not explicitly require a JSON object for that field, which limits interpretation of its format errors.

The reviewed private archives have SHA-256 `a7a3eaa8b3d51f1d18ff57bc7bbba97735cdb077da5936bd751ec86e33974fa8` (first pilot) and `f40e0ce44178ef39fb1a87e7ff155d975c31ff270b0ca9ace74ab4390829726b` (both pilots). The latter contains 60 unique second-pilot responses. Raw responses, request hashes, image hashes, cached records, and strict scores were checked against one another; the 24 pilot task answers matched a separate Python DSU oracle. Both archives stay private. These are calibration observations, not main-study findings.

Qwen uses [Qwen/Qwen3-VL-8B-Instruct](https://huggingface.co/Qwen/Qwen3-VL-8B-Instruct), pinned in [`configs/experiment.yaml`](configs/experiment.yaml), with bitsandbytes 4-bit NF4 weights, greedy decoding, and a 2,048-token output cap. The checkpoint revision and generation settings are recorded with each response. No paid inference API is used.

The runner hashes the model ID, revision, settings, task ID, condition, exact prompt, and image bytes. It writes every raw response before the next request and refreshes `results/cache_snapshot.zip` after each call. The notebooks restore only `data/` and `results/` from an attached export, so an older archive cannot replace the current code or configuration. Keep the latest export outside Kaggle's temporary session storage.

## InternVL3.5 feasibility check

The separate [`InternVL notebook`](notebooks/internvl35_visdsr.ipynb) ran three calls on the same existing pilot2 task with the pinned [OpenGVLab/InternVL3_5-8B-HF](https://huggingface.co/OpenGVLab/InternVL3_5-8B-HF) checkpoint. T-dir returned valid, correct JSON (1/1). R-dir returned a correct JSON answer only after a `<think>` preamble, so its **official strict score is 0/1**. G-dir also began with `<think>` and ended mid-reasoning without an answer, for an official score of 0/1. Removing the R-dir preamble is a diagnostic observation, not a change to the scorer or reported result. One task is insufficient to estimate accuracy by condition.

The model loaded on a Tesla T4 with 4-bit NF4 weights; peak allocated GPU memory was 6.84 GiB, with no out-of-memory error. The three calls took 7.16, 353.88, and 419.40 seconds respectively. The reviewed private export has SHA-256 `25ca9faf910ad1b6cd537dc2ead0993509cc4cf996c111c0fa963e5a76ecb71b`; its three raw responses, cache records, prompt and image hashes, and strict scores agree. The earlier Qwen task data and 120 cache records were preserved. This archive remains outside Git.

The full InternVL pilot and all main runs remain stopped. The attached Kaggle notebook used an older export cell that included a redundant nested `cache_snapshot.zip`; the current repository notebook omits it. Keep the downloaded original as a backup and use a copy without the nested ZIP if a future Kaggle upload is approved.

No `FREEZE.json` has been written, and main task generation remains stopped. Any further model run needs a documented decision after this smoke test. `python -m eval.run --split pilot2 --model mock` checks plumbing only and is not a study result. Generated tasks, images, responses, and figures remain excluded from Git until reviewed for release. Exact-match scoring cannot by itself identify a model's internal failure mechanism.
