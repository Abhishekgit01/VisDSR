# VisDSR: pilot and feasibility report

**Result.** VisDSR built and tested a reproducible DSU reasoning pipeline, but the calibration runs did not support the planned comparison of text and diagrams. The two Qwen pilots had a near-zero text baseline. In a separate three-call InternVL3.5 smoke test, both image responses failed the required JSON format. No main study was run.

## Question and design

The planned question was whether a multimodal model's accuracy on sequential disjoint-set union (DSU) operations changes when the starting forest is presented as canonical text, text rendered as an image, or a diagram. Each task uses the same initial forest and operations in all five conditions: T-dir (text), R-dir (rendered text), G-dir (diagram), T-str (text plus initial-state transcription), and G-str (diagram plus transcription). The last two test whether asking for an explicit parent map changes the result.

A C++ simulator supplies ground truth for reachable DSU forests. `find` fully compresses its path; `union` runs both finds before merging by size, with a specified tie rule. Each response must contain the full parent map after every operation. The scorer checks the final state exactly and counts invalid JSON or missing fields as wrong. An independent Python oracle matched the simulator on a worked case and 5,000 seeded random cases. All presentations of a task use the same operation sequence and answer schema, except for the transcription field in structured conditions.

The first Qwen pilot had 12 tasks with four operations each. A second, separately seeded pilot had 12 shorter tasks: six with one operation and six with two, divided equally between 8 and 16 elements. Both used 1,024 × 1,024 clean RGB images. [Qwen3-VL-8B-Instruct](https://huggingface.co/Qwen/Qwen3-VL-8B-Instruct) was run locally on a free Kaggle GPU with 4-bit NF4 weights, greedy decoding, and a 2,048-token output cap. Every task-condition pair was an independent call. The model revision, settings, exact prompt and image hashes, and raw response were cached; strict scores were saved separately. No paid inference API was used.

## Calibration results

The table reports **final-state exact matches**. Parentheses show format errors, which already count as incorrect in the exact-match numerator.

| Condition | Qwen pilot 1: four operations | Qwen pilot 2: one or two operations |
| --- | ---: | ---: |
| T-dir | 0/12 (0 format errors) | 1/12 (0) |
| R-dir | 0/12 (0) | 0/12 (0) |
| G-dir | 0/12 (0) | 0/12 (1) |
| T-str | 0/12 (12) | 0/12 (1) |
| G-str | 0/12 (12) | 0/12 (12) |

In pilot 2, T-dir was correct on one of six one-operation tasks and none of the six two-operation tasks. All 12 G-str pilot-2 responses put the transcription in a JSON string rather than the required parent-map object. The prompt did not state that field's object type explicitly, so these format failures should not be interpreted as failures to read the diagram. Diagnostic repairs never change official scores.

The separate InternVL3.5 check used one existing pilot-2 task in T-dir, R-dir, and G-dir. [InternVL3_5-8B-HF](https://huggingface.co/OpenGVLab/InternVL3_5-8B-HF) loaded with 4-bit NF4 weights on a Tesla T4 without an out-of-memory error. T-dir returned valid, correct JSON (1/1). R-dir returned a correct JSON object only after a long `<think>` preamble, so its strict score is 0/1. G-dir began with `<think>` and ended mid-reasoning without an answer, so its strict score is 0/1. The three latencies were 7.16, 353.88, and 419.40 seconds. A one-task smoke test is a technical check, not an accuracy estimate for that model.

## Interpretation and stop decision

The Qwen text baseline was too low to support the planned paired modality comparison. A diagram score of zero cannot isolate a diagram effect when text scores are also almost always zero. The InternVL smoke test showed that this second model could load and answer a text task, but its two image responses did not meet the fixed output contract. Removing the R-dir preamble after the fact would change what the strict scorer measures; it is reported only as a diagnostic observation.

The protocol was **not frozen**. The fresh 80-task main set was not generated, and no confirmatory model calls or main-study statistical results were reported. The completed work is a calibration and feasibility result. It does not establish whether diagrams help or hurt DSU reasoning.

## Reproducibility and limits

The repository contains the simulator, seeded generator, renderer, evaluator, scorer, analysis code, tests, configuration, and Kaggle notebooks. `make test`, `make lint`, and `make stress` check the code; [`README.md`](README.md) lists the data-generation commands. The saved pilot archives were audited against the raw responses and current strict scorer. Their SHA-256 checksums and the InternVL archive checksum are in the README. Raw model responses and generated images remain private, so the public repository alone cannot independently reproduce the numerical results.

The runs used synthetic, clean diagrams, one fixed prompt family, two 8B model families with 4-bit quantization, and exact-match scoring. Invalid output does not reveal the model's internal failure mechanism. The small calibration sets and the one-task InternVL check should not be treated as confirmatory evidence. Implementation provenance, including AI-assisted work, is recorded in [`STUDENT_UNDERSTANDING.md`](STUDENT_UNDERSTANDING.md).
