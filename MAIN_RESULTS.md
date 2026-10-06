# VisDSR main study results

Audited on 6 October 2026. Both model collections and the combined analysis are complete. The [main-results release](https://github.com/Abhishekgit01/VisDSR/releases/tag/v2.0-results) supplies the audited reproduction artifact.

## Study and collection

The frozen study evaluates the same 80 fresh DSU tasks in five conditions for two model families: **800 independent main responses**. The 120 calibration responses and separate diagnostics are excluded from main estimates.

| Model | Pinned revision | Main responses |
| --- | --- | ---: |
| `Qwen/Qwen3-VL-8B-Instruct` | `0c351dd01ed87e9c1b53cbc748cba10e6187ff3b` | 400/400 |
| `OpenGVLab/InternVL3_5-8B-HF` | `741a7d03020411e666c6109218ab71e08151ef86` | 400/400 |

The source release is `v2.0-frozen`, commit `2beb395e176de5527ec3d0166529b51a4f1c17e3`. Both models used local Kaggle Tesla T4 inference, Transformers 4.57.1, 4-bit NF4 weights, and effective generation parameters `do_sample=False`, `num_beams=1`, `max_new_tokens=2048`. Every condition used the frozen prompts, operations, original image bytes, schema, and scoring policy. Incorrect answers and formatting failures were retained.

Each condition has 80 paired tasks, with 20 tasks in each element-count/operation-count cell: 8 or 16 elements and one or four operations. Initial forests come from the fixed reachable constructions documented in the [preserved study design](STUDY_V2.md). The results concern this distribution and bounded output protocol.

## Official outcomes

The primary outcome is exact match of the final parent map. Invalid output counts as incorrect. Full-sequence correctness additionally checks intermediate maps and find results; its totals equal final-map correctness in these collections.

| Condition | Qwen correct final maps | InternVL correct final maps | Qwen format failures | InternVL format failures |
| --- | ---: | ---: | ---: | ---: |
| T-dir: text parent map | 0/80 | 2/80 | 1/80 | 14/80 |
| R-dir: rendered parent map | 0/80 | 0/80 | 26/80 | 54/80 |
| G-dir: forest diagram | 0/80 | 0/80 | 37/80 | 74/80 |
| T-str: text with transcription | 3/80 | 2/80 | 50/80 | 59/80 |
| G-str: diagram with transcription | 0/80 | 0/80 | 24/80 | 80/80 |
| Total | 3/400 | 4/400 | 138/400 | 281/400 |

Qwen reached the output cap on 62 responses; InternVL reached it on 41. Recorded mean inference latency was 118.06 seconds for Qwen and 91.55 seconds for InternVL, excluding model loading and setup. Output caps are reported separately and are not additional failures to add to the format-error counts.

## Primary paired comparison

The primary contrast specified before main collection is **T-dir minus G-dir**, paired by task. The frozen analysis uses 10,000 task-level bootstrap resamples, exact two-sided McNemar tests, and Holm correction across the two model tests.

| Model | Difference, percentage points | Paired bootstrap 95% interval | Text-only correct / diagram-only correct | Exact McNemar p | Holm-adjusted p |
| --- | ---: | --- | --- | ---: | ---: |
| Qwen | 0.00 | [0.00, 0.00] | 0 / 0 | 1.00 | 1.00 |
| InternVL | 2.50 | [0.00, 6.25] | 2 / 0 | 0.50 | 1.00 |

These data do not establish a presentation effect or equivalence. Qwen is at an accuracy floor in both primary conditions. InternVL has only two discordant pairs. A percentile bootstrap resamples observed outcomes, so zero successes produce a degenerate interval; that does not imply zero uncertainty about performance on new tasks.

As a supplemental boundary check, two-sided 95% Wilson binomial intervals are [0.00%, 4.58%] for 0/80, [0.69%, 8.66%] for 2/80, and [1.28%, 10.45%] for 3/80. These marginal accuracy intervals supplement the paired analysis; they are not intervals for a modality difference or extra hypothesis tests. They use `z=1.959963984540054` and do not change official scores.

## Secondary observations

Qwen's T-str minus T-dir difference was 3.75 percentage points, with a paired bootstrap interval [0.00, 8.75], exact p=0.25, and Holm-adjusted p=1.00 within its secondary comparison family. InternVL's corresponding difference was zero, interval [-5.00, 5.00], exact p=1.00. These contrasts do not support a general transcription benefit.

Mean per-step correctness first averages the fraction of correct operations within a task, then averages the 80 tasks. An operation requires the correct parent map and, for a find, its result. The frozen scorer assigns zero per-step correctness to invalid outputs.

| Condition | Qwen mean per-step correctness | InternVL mean per-step correctness |
| --- | ---: | ---: |
| T-dir | 3.125% | 2.500% |
| R-dir | 0.000% | 0.000% |
| G-dir | 0.000% | 0.000% |
| T-str | 4.375% | 2.500% |
| G-str | 0.000% | 0.000% |

The first-error metric is 1 in 388/400 Qwen and 396/400 InternVL responses. Invalid outputs are assigned first-error step 1 by the scorer, so these counts combine formatting failures and parsed step-one errors. Qwen's remaining errors first occur at a later step in nine responses; its three fully correct sequences have no error step. InternVL's four fully correct sequences have no error step. Neither model has a recorded state recovery after an earlier incorrect state.

Among schema-valid structured responses, Qwen correctly transcribed 30/30 text inputs and 0/56 diagram inputs. InternVL correctly transcribed 21/21 text inputs; none of its 80 G-str outputs was schema-valid. Conditional transcription rates exclude invalid responses and must not be presented as overall success rates. These are observable extraction and formatting outcomes, not evidence of a particular internal model mechanism.

All seven main successes occurred on one-operation tasks. There were no correct final maps on four-operation tasks. Difficulty-cell totals pool the five presentations of each task and are descriptive, not independent-sample tests:

| Elements / operations | Qwen final correct / responses | InternVL final correct / responses |
| --- | ---: | ---: |
| 8 / 1 | 3/100 | 2/100 |
| 8 / 4 | 0/100 | 0/100 |
| 16 / 1 | 0/100 | 2/100 |
| 16 / 4 | 0/100 | 0/100 |

Frequent schema failures, the fixed output cap, and the low text baseline constrain interpretation. No answer was repaired, stripped of a preamble, retried for content, or omitted to improve these estimates. This study does not establish unrestricted DSU ability, human diagram comprehension, or a model's internal failure mechanism.

## Scored response examples

[Three annotated responses](RESPONSE_EXAMPLES.md) use the same one-operation main task to show a correct answer, a valid response that omits a path-compression update, and valid JSON that fails the required response schema. Each complete response is traceable to the released cache, raw JSONL line, and score row. These examples were selected after collection for explanation; they do not supply frequency estimates or additional comparisons.

## Recovery and verification

The completed outputs were recovered from Kaggle's saved-version files after the interactive runtime stopped. The final archive was `visdsr_v2_results (8).zip`, containing 1,140 payload files plus its export marker. A descriptive backup, `visdsr_v2_main_complete.zip`, preserves the exact same bytes.

Final archive SHA-256:

```text
a9ddfc8c0e4d26cbe149211cc57b6e1ac9b2a318f94f00ba3dfda5d4f1eb9bea
```

The preceding `visdsr_internvl_main_400.zip` checkpoint contains all 800 main responses, but predates the three combined-analysis files. Its 1,137 payload files match the final archive byte for byte. Its SHA-256 is:

```text
2d2433d439d2bba68be9d02619bae35d500b1751e444afba93e3ba7917f14ecf
```

The recovery audit verified:

- ZIP integrity, complete file manifests, and every payload checksum in the supplied archives.
- All 21 protected study source hashes and 164 frozen calibration payloads.
- Preservation of all 520 previously verified Qwen/calibration caches, 190 original input files, and the first InternVL batch's 620 combined caches.
- Exactly 400 unique main task-condition pairs per model and 60 calibration pairs per model.
- All 920 official cached records against exact prompts, task/image hashes, model revisions, and effective generation settings.
- All 920 official score rows recomputed from raw responses, and all 920 raw JSONL records matched to caches in the frozen request order.
- Reproduction of the combined summary and paired-comparison CSVs using the frozen analysis code.
- Replay of all 92 calibration/main task truths through the C++ simulator.

No model was loaded and no inference was repeated during recovery or audit. The audit preserved original PNGs and checked their bytes. It did not regenerate image pixels on this local host; the earlier Qwen audit documented a Graphviz version mismatch. The Kaggle collection logs record successful frozen-image validation before inference.

## Recompute from the backup

Follow the [complete reproduction instructions](REPRODUCE_MAIN.md) to download and verify the release assets in a fresh checkout. Both `v2.0-frozen` and the documentation-bearing `v2.0-results` tag contain the same protected study code. These commands require no GPU or model weights:

```bash
python -m pip install -r environment/requirements.txt
python -m study_transfer --restore /path/to/visdsr-main-results.zip
python -m eval.run --split main --model model1 --score-only
python -m eval.run --split main --model model2 --score-only
python -m analysis.analyze --split main --models model1 model2
```

The frozen analysis writes `summary_main_model1_model2.csv`, `comparisons_main_model1_model2.csv`, and `figures/accuracy_main_model1_model2.png` under `results/`. Calibration and diagnostics remain separate.

## Release and completion

The [results release](https://github.com/Abhishekgit01/VisDSR/releases/tag/v2.0-results) packages the byte-identical final export as `visdsr-main-results.zip`, its audit as `visdsr-main-verification.json`, the combined tables and figure, and asset checksums. The earlier calibration release remains available separately. Main collection, raw-response verification, combined analysis, and the results report are complete. The low-accuracy outcome is retained without further prompt selection or content retries.
