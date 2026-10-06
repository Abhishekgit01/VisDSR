# Reproduce the completed main study

The [main-results release](https://github.com/Abhishekgit01/VisDSR/releases/tag/v2.0-results) contains the complete audited study data. Scoring and analysis require no GPU, model weights, API key, or paid service.

## Release files

| Asset | Contents |
| --- | --- |
| `visdsr-main-results.zip` | Original tasks and PNGs, 800 main caches, 120 calibration caches, raw JSONL responses, official scores, analysis tables and figures, export manifest, and separate diagnostics |
| `visdsr-main-verification.json` | Recovery audit, model revisions, counts, results, checksums, and reproduction limits |
| `summary-main.csv` | The frozen combined condition summaries |
| `comparisons-main.csv` | The frozen paired tests and bootstrap intervals |
| `accuracy-main.png` | The frozen combined accuracy figure |
| `SHA256SUMS.txt` | SHA-256 checksums for the five assets above |

The data ZIP preserves the exact bytes of the recovered final export. Its SHA-256 is:

```text
a9ddfc8c0e4d26cbe149211cc57b6e1ac9b2a318f94f00ba3dfda5d4f1eb9bea
```

The results tag includes this documentation. The 21 protected study files have the same hashes as the protocol frozen at commit `2beb395e176de5527ec3d0166529b51a4f1c17e3` (`v2.0-frozen`).

## 1. Use a fresh checkout

Requires Python 3.11 or newer. A C++ compiler and Graphviz are needed only for simulator or rendering checks, not cached scoring.

```bash
git clone --depth 1 --branch v2.0-results https://github.com/Abhishekgit01/VisDSR.git VisDSR-reproduce
cd VisDSR-reproduce
python -m venv .venv
source .venv/bin/activate
python -m pip install -r environment/requirements.txt
```

Use a new directory so the restore tool does not encounter conflicting files from another experiment. Existing files with different bytes cause restoration to stop.

## 2. Download and verify

Download the assets from the release page into this checkout. With the GitHub CLI, all assets can be downloaded together:

```bash
gh release download v2.0-results --repo Abhishekgit01/VisDSR --dir .
sha256sum --check SHA256SUMS.txt
```

The CLI is optional. If downloading only the ZIP through a browser, use `sha256sum visdsr-main-results.zip` and compare the result with the exact value above. The ZIP's internal manifest is checked again during restoration.

## 3. Restore and score the raw responses

```bash
python -m study_transfer --restore visdsr-main-results.zip
python -m eval.run --split pilot2 --model model1 --score-only
python -m eval.run --split pilot2 --model model2 --score-only
python -m eval.run --split main --model model1 --score-only
python -m eval.run --split main --model model2 --score-only
python -m analysis.analyze --split main --models model1 model2
```

Expected scored counts are 60 calibration responses per model and 400 main responses per model. `--score-only` requires every matching cache and raises an error if a response is missing. It cannot start inference. Restoration checks protocol fingerprints, file manifests and payload hashes; cached scoring checks the matching task, condition, prompt and image hashes.

The main final-map totals must be **3/400 for Qwen** and **4/400 for InternVL**. Invalid JSON or schema output remains incorrect; do not repair it for official scores.

## 4. Compare the regenerated tables

```bash
cmp summary-main.csv results/summary_main_model1_model2.csv
cmp comparisons-main.csv results/comparisons_main_model1_model2.csv
```

Successful `cmp` commands produce no output. The audit reproduced these two CSVs byte for byte using the frozen code. The accuracy figure is regenerated too, but identical PNG bytes are not required across Matplotlib environments.

The report is [MAIN_RESULTS.md](MAIN_RESULTS.md). The primary T-dir minus G-dir differences are 0.00 percentage points for Qwen and 2.50 for InternVL; both Holm-adjusted exact p-values are 1.00. The report explains the accuracy floor and the limitations of degenerate bootstrap intervals.

## Optional simulator check

```bash
make build
make test
make stress
```

These checks exercise the simulator and infrastructure. Mock-oracle responses and separate diagnostics are not main-study evidence. Numerical reproduction uses the original released image bytes; local rendering can differ across Graphviz versions, as documented in the report.

## Inference and provenance

The released caches are the official independent requests with fixed greedy generation and a 2,048-token limit. Re-running weights is a separate hardware-dependent replication and may not return identical text. It is unnecessary for score reproduction.

The [student explanation and assistance record](STUDENT_UNDERSTANDING.md) describes the algorithm, condition controls and AI-assisted implementation. The [preserved study plan](STUDY_V2.md), [main decision](MAIN_DECISION.md), [freeze](FREEZE.json), and historical reports distinguish development, calibration and main evaluation.
