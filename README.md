# VisDSR

VisDSR is a study of sequential reasoning over disjoint-set union (DSU) forests. It asks whether a model's accuracy changes when the same initial state is given as a parent map, an image of that parent map, or a forest diagram. It also tests whether asking the model to transcribe the initial state before applying operations changes its accuracy. DSU keeps each intermediate state checkable while still requiring path compression and union decisions across steps.

**Status:** The C++ DSU simulator passed a worked example and 5,000 seeded comparisons with a separate Python reference. Qwen3-VL-8B-Instruct completed both calibration pilots. On the shorter second pilot, T-dir scored 1/12 and R-dir and G-dir scored 0/12, so the Qwen main run is stopped. The protocol remains unfrozen. An InternVL3.5 three-call smoke test is prepared; no main run has occurred. Model responses and generated data remain outside Git.

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

The separate [`InternVL notebook`](notebooks/internvl35_visdsr.ipynb) uses the official fully trained [OpenGVLab/InternVL3_5-8B-HF](https://huggingface.co/OpenGVLab/InternVL3_5-8B-HF) checkpoint at a pinned revision. It uses the same existing pilot2 task and prompt bytes and makes only T-dir, R-dir, and G-dir calls for one task. The Kaggle GPU result has not yet been observed.

1. Import the InternVL notebook into Kaggle, enable GPU and Internet, and attach only the private `visdsr_pilot2_complete.zip` as Input. Kaggle may unpack the archive; the notebook accepts either form.
2. Run All. Review the three strict parse results, model revision, GPU memory, and latency before considering more calls.
3. Download `visdsr_internvl35_smoke.zip` from `/kaggle/working` Output. The notebook uses a distinct filename so an earlier archive is easy to distinguish.

No `FREEZE.json` has been written, and main task generation remains stopped. A full InternVL pilot or any main run needs a documented decision after its smoke test. `python -m eval.run --split pilot2 --model mock` checks plumbing only and is not a study result. Generated tasks, images, responses, and figures remain excluded from Git until reviewed for release. Exact-match scoring cannot by itself identify a model's internal failure mechanism.
