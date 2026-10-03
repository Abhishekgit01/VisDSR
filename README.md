# VisDSR

VisDSR studies sequential reasoning over disjoint-set union (DSU) forests. It asks how model accuracy changes when the same starting state is supplied as a parent map, an image of that map, or a forest diagram. Two additional conditions ask the model to transcribe the initial state before applying operations.

DSU makes every intermediate state checkable while requiring path compression, set-size comparisons, and a fixed union tie rule. A C++ simulator supplies ground truth, and an independent Python reference checks it.

**Status:** V2 remains unfrozen. Qwen's three smoke responses parsed but were incorrect. Eight bounded diagnostics then found correct text and rendered-text transcription, incorrect diagram extraction, and incorrect roots and isolated DSU updates on the same forest. The next live run is InternVL's three-call smoke using the preserved tasks and images. V2 calibration and main remain disabled.

Calibration covers the same difficulty cells as the planned main run: 8 or 16 elements, with one or four operations. Earlier Qwen pilots and an InternVL smoke test are preserved as feasibility results in [`REPORT.md`](REPORT.md). The pre-run design is in [`STUDY_V2.md`](STUDY_V2.md); audits and the next execution steps are in [`V2_SMOKE.md`](V2_SMOKE.md).

## Study design

| Condition | Initial state | Additional output |
| --- | --- | --- |
| T-dir | Canonical JSON parent map | None |
| R-dir | PNG of the same JSON string | None |
| G-dir | Forest diagram with child-to-parent arrows | None |
| T-str | Canonical JSON parent map | Initial-map transcription |
| G-str | The same diagram as G-dir | Initial-map transcription |

All conditions use identical operations and require the parent map after each operation, plus every `find` result. Transcription is a JSON object. Invalid output counts as incorrect; responses are preserved without repairs or content retries.

The planned main study has 80 fresh tasks, five conditions, and two open-weight families: [Qwen3-VL-8B-Instruct](https://huggingface.co/Qwen/Qwen3-VL-8B-Instruct) and [InternVL3.5-8B-HF](https://huggingface.co/OpenGVLab/InternVL3_5-8B-HF). That is 800 independent responses. Models use pinned revisions, local 4-bit NF4 weights, and greedy decoding. No paid inference API is used.

The primary measure is final-parent-map exact match. The primary comparison is **T-dir minus G-dir**, paired by task. Secondary measures include full-sequence correctness, transcription accuracy, and format errors. Main execution requires reviewed calibration and an audited protocol freeze; preparation does not establish a modality effect.

## Run on Kaggle

Start with a new notebook and the revised Qwen file:

- [`qwen3_vl_v2_kaggle.ipynb`](notebooks/qwen3_vl_v2_kaggle.ipynb)
- [`internvl35_v2_kaggle.ipynb`](notebooks/internvl35_v2_kaggle.ipynb)

1. Download the Qwen notebook from the `study-v2` branch and import it into Kaggle. Enable a free GPU and Internet.
2. Keep `STAGE = "smoke"` and the review flags false. Run the cells from top to bottom. The default makes only three calls: T-dir, R-dir, and G-dir on the same four-operation calibration task.
3. Download `visdsr_v2_results.zip` from the Output panel. Review the raw answers, strict parsing, correctness, tokens, memory, and latency before selecting calibration.
4. After review, calibration runs at most 20 new responses per execution and reuses the smoke cache. Download each updated export. Attach the newest export as a private Dataset when resuming or starting InternVL.

The v2 project folder is `/kaggle/working/VisDSR_v2`. Its backup checks source fingerprints, calibration task bytes, and payload checksums. Earlier v1 exports are incompatible. Both a ZIP and Kaggle's extracted Dataset layout are supported. Exports omit the redundant nested cache ZIP that caused earlier upload problems.

Every completed response is cached immediately; each bounded run also exports automatically. A lost runtime can still lose files that have not been exported and saved outside the session. Do not rely on Kaggle's temporary disk as the only copy.

## Check locally

Requires Python 3.11+, a C++17 compiler, Graphviz, and DejaVu fonts.

```bash
python -m pip install -r environment/requirements.txt
make build
make test
make lint
make stress
```

Generate the revised calibration in a separate checkout so historical local data stays intact:

```bash
python -m gen.generate --split pilot2
python -m gen.render --split pilot2
python -m gen.validate --split pilot2
python -m gen.render --split pilot2 --qa
python -m eval.run --split pilot2 --model mock --max-new-calls 20
```

The mock oracle checks caching and scoring without model inference; it supplies no study evidence. `make stress` checks the worked example and 5,000 seeded simulator cases. Image validation checks replayed truth, dimensions, geometry, pixels, filenames, and hashes. Main generation is blocked until the reviewed freeze exists.

| Path | Purpose |
| --- | --- |
| [`sim/dsu.cpp`](sim/dsu.cpp) | DSU simulator and operation protocol |
| [`gen/`](gen/) | Seeded tasks, rendering, validation, and freeze audit |
| [`eval/`](eval/) | Shared prompts, local inference, caching, and strict scoring |
| [`analysis/`](analysis/) | Paired statistics and figures |
| [`study_transfer.py`](study_transfer.py) | Checked v2 backup export and restore |
| [`tests/`](tests/) | Independent DSU reference and infrastructure checks |
| [`STUDENT_UNDERSTANDING.md`](STUDENT_UNDERSTANDING.md) | Algorithm explanation and AI-assistance provenance |

## Historical feasibility results

The v1 code is preserved at commit `bf81065`. Its [`SPEC.md`](SPEC.md) and [`REPORT.md`](REPORT.md) describe a separate protocol, with unchanged official scores:

| Run | T-dir | R-dir | G-dir |
| --- | ---: | ---: | ---: |
| Qwen pilot 1, 12 four-operation tasks | 0/12 | 0/12 | 0/12 |
| Qwen pilot 2, 12 one/two-operation tasks | 1/12 | 0/12 | 0/12 |
| InternVL smoke, one task | 1/1 | 0/1 | 0/1 |

The Qwen text baseline was near zero. InternVL's image outputs began with reasoning text; the diagram response did not finish an answer. These runs did not establish whether diagrams help or hurt DSU reasoning. They motivated clearer output instructions and a representative calibration set for v2. Historical responses will not be pooled with v2.

Reviewed private archive SHA-256 checksums:

- First Qwen pilot: `a7a3eaa8b3d51f1d18ff57bc7bbba97735cdb077da5936bd751ec86e33974fa8`.
- Both Qwen pilots: `f40e0ce44178ef39fb1a87e7ff155d975c31ff270b0ca9ace74ab4390829726b`.
- InternVL smoke plus preserved Qwen data: `25ca9faf910ad1b6cd537dc2ead0993509cc4cf996c111c0fa963e5a76ecb71b`.

The raw responses and generated data remain outside Git. The public repository alone cannot reproduce those historical numerical results. A final v2 release must include a reviewed reproduction artifact or access instructions, along with the frozen code, audited scores, figures, and report. The project uses clean synthetic images and exact-match scoring; these outputs do not identify a model's internal failure mechanism.
