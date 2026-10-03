# VisDSR: revised study and execution plan

Status: development draft on `study-v2`. No v2 model responses or main results exist. The completed v1 runs are described in `REPORT.md`; their code is preserved at commit `bf81065`. This document records the next study before its model calls.

## Research question and deliverable

How does accuracy on sequential disjoint-set union operations change when the initial forest is supplied as text, rendered text, or a diagram? Does asking for an explicit parent-map transcription change that difference?

The intended deliverable is a research repository with deterministic tasks, two open-weight model families, cached independent responses, paired analysis, and a short evidence-based report. The main evaluation has 80 tasks, five conditions per task, and two models: 800 responses in total. Heap tasks and a web interface are outside this study.

| Condition | Initial state | Required output |
| --- | --- | --- |
| T-dir | Canonical JSON text | State after every operation and each find result |
| R-dir | The same JSON string as a PNG | Same direct output |
| G-dir | DSU forest diagram | Same direct output |
| T-str | Canonical JSON text | Initial-map object plus direct output |
| G-str | The same diagram as G-dir | Initial-map object plus direct output |

The primary measure is final-parent-map exact match. The primary comparison is T-dir minus G-dir, paired by task. Full-sequence correctness also checks find results. These outcomes describe the stated synthetic task distribution and model settings.

## What the existing evidence establishes

The simulator matched an independent Python reference on the worked example and 5,000 seeded cases. The rendering and scoring pipelines have been exercised with real cached responses.

Qwen v1 pilot 1 scored zero final exact matches in each condition. Pilot 2 scored T-dir 1/12 and every other condition 0/12. Direct responses usually parsed; several text responses copied the initial map without the required state changes. The structured prompt did not explicitly require an object for transcription. These observations motivate clearer instructions and targeted diagnosis, rather than an inference that diagrams caused all failures.

InternVL's v1 smoke used one task. Text was strict-correct; rendered text returned an answer after a reasoning preamble; the diagram response ended during reasoning. This checks feasibility on one task, not model accuracy. Its pinned chat template does not itself append a thinking preamble, so the observed behavior still needs an inference check.

All v1 results remain historical. They will not be pooled with v2, rescored under a changed policy without labeling, or presented as main findings.

## Revised design

V2 preserves 8 and 16 elements, full path compression, union by size and the specified tie rule, the five conditions, the renderer, the output fields, and official scoring. The prompt explicitly states set-size counting and the transcription object type, and includes two short worked examples shared by all conditions. There is one candidate prompt family. Any engineering bug discovered before freeze is documented; main data never guides prompt changes.

Calibration will represent the actual main design:

| Dataset | 8 elements, 1 op | 8 elements, 4 ops | 16 elements, 1 op | 16 elements, 4 ops |
| --- | ---: | ---: | ---: | ---: |
| V2 calibration (`pilot2` internally) | 3 | 3 | 3 | 3 |
| V2 main | 20 | 20 | 20 | 20 |

Each dataset has a separate seed. Calibration one-operation tasks balance meaningful unions and finds on a depth-two path. Four-operation tasks include both operations and at least one meaningful union and path compression; tie cases are represented. The generator's initial forests come from a fixed family of reachable union constructions, which must be disclosed as a distribution limitation.

Models are pinned Qwen/Qwen3-VL-8B-Instruct and OpenGVLab/InternVL3_5-8B-HF, loaded through Transformers with 4-bit NF4 weights and greedy generation. One model runs at a time on a free Kaggle GPU. Each task-condition is an independent request with no tools, browsing, history, or model code execution. The exact source PNG is the same across models; processor behavior is logged separately.

## Execution order

1. Finish the offline checks. Verify simulator invariants, all five response schemas, image mapping, cache resume, archive restore, and refusal of v1 data. Exercise interruption after a small number of mock calls. Inspect small and large images manually. Use a separate project folder for v2 so the older working files remain usable.
2. Run Qwen smoke only: one calibration task in T-dir, R-dir, and G-dir. Export immediately. Inspect raw responses, strict parsing, final correctness, input/output token counts, output-cap exhaustion, device placement, memory, latency, model revision, and effective settings. Review before enabling calibration.
3. If the smoke leaves a specific uncertainty, use at most eight separately cached diagnostic calls for that model: parent-map extraction from text/images, root and set-size checks, and isolated find/union updates. Diagnostics stay outside all five-condition study scores. Fix a demonstrated integration or instruction problem before another smoke; retain failed responses.
4. Run InternVL smoke on the identical task and image bytes, restore the Qwen export, and review it under the same criteria. Inspect the official processor and chat template if reasoning preambles persist. Preserve the raw output; stripping a preamble is a diagnostic, not an official answer repair.
5. Complete the single representative calibration set for both models: 60 responses per model including its three smoke responses. Collect correctness and format rates by condition, size, and sequence length. Estimate main runtime from all five conditions rather than the three direct smoke calls. Do not repeat calibration until a desirable result appears.
6. Write the reviewed main decision, audit calibration caches against the exact request and task hashes, freeze the protocol, and tag the commit. Main generation remains blocked until this record exists. Generate 80 fresh tasks only after freeze and verify no calibration overlap.
7. Run main inference in bounded chunks of new calls. Default to 20 new calls per chunk; choose a larger chunk only from measured latency and remaining session time. Each completed call is written atomically. Export after each chunk, save/download the output, and restore it in the next session. Inference failures retain all completed calls; incorrect content is not retried.
8. Recompute official scores from caches with no inference. Require exactly 400 unique task-condition pairs for each model and identical task IDs across models. Generate paired statistics, figures, and error tables. Audit representative failures against simulator truth and inspect anomalous outputs.
9. Write the report and README from the verified results. Publish the exact frozen code and a reviewed reproduction artifact or clear access instructions. A reader must be able to recompute numerical results; code and private-archive checksums alone are insufficient. Review release files and commit messages before updating the public repository.

## Decision rules and claims

Technical acceptance requires correct data and image hashes, supported model loading, verified independent prompts, durable raw-response caching, adequate output length, and a documented review of response formatting and runtime. A smoke is a technical check, not an accuracy estimate.

The original brief's approximately 75% hard-text target is a desired calibration target. It is not a test of a modality effect. Low accuracy must not trigger model exclusion, repeated prompt selection, or omission of failures. If both presentations remain at the floor, the study can describe capability and format limitations; it cannot establish modality equivalence or explain an internal mechanism. The freeze note must state whether the intended modality interpretation is supported by calibration and justify the remaining GPU expenditure. A stop is reported explicitly rather than called a completed 800-call study.

No positive effect or statistically significant result is required for completion. After freeze, prompts, image generation, models, scoring, and metrics remain fixed. A necessary bug fix gets a new commit, an impact statement, and a decision about invalidating affected calls.

## Analysis and completion checks

Report both primary accuracies, T-dir minus G-dir in percentage points, a 10,000-resample paired bootstrap interval, exact McNemar results, and Holm adjustment across the two model tests. Treat secondary contrasts as secondary. Include format errors in official accuracy and report their rates separately. Include per-step correctness, full-sequence correctness, transcription accuracy, first-error step, and recovery. Report difficulty-cell summaries descriptively.

An all-zero or all-one empirical distribution gives a degenerate percentile bootstrap interval. Explain that boundary limitation and provide a binomial accuracy interval as an additional descriptive check. Neither a degenerate bootstrap interval nor a nonsignificant test establishes equivalence. Eighty paired tasks may give imprecise small-effect estimates; any power statement must model discordant pairs.

The project is complete when its accepted scope has audited responses, scores reproducible from the released artifact, final figures and report, a README that agrees with the evidence, accurate AI-assistance provenance, and a student explanation of the simulator, controls, failure modes, and conclusions. Completion and claims must state any stopped stage or missing model.

## Ready workflow

The revised notebooks are `notebooks/qwen3_vl_v2_kaggle.ipynb` and `notebooks/internvl35_v2_kaggle.ipynb`. Their stages are `smoke`, `calibration`, and `main`. Both default to smoke and false review flags. Calibration and main make at most 20 new calls per execution, then export; rerunning resumes from matching caches. Main also requires the audited freeze record.

V2 uses `/kaggle/working/VisDSR_v2` and `visdsr_v2_results.zip`. Backup metadata checks the study source, fixed calibration task bytes, and all payload hashes. A v1 ZIP cannot serve as a v2 backup. Analysis filenames include the dataset and model selection. Keep the newest downloaded export before ending a session. A runtime disappearing before export can still lose responses held only on the remote disk.

## Runtime and immediate action

The v1 Qwen pilots imply roughly 6–10 GPU hours for 400 calls, excluding session setup; this is a planning range, not a promise for v2. InternVL's two image smoke calls took about six to seven minutes each. Structured conditions and longer tasks have not been timed, so a reliable InternVL main estimate is still unavailable. Free GPU allocation and interruption make elapsed completion time longer than inference time.

Kaggle documents a 12-hour execution limit per GPU session and separate execution for Save & Run All. Plan bounded chunks and restored inputs; downloading a backup is required before relying on a later session. Source: https://www.kaggle.com/docs/notebooks

The next live action is the three-call Qwen smoke. The notebook defaults to that stage and must stop after it. Its report and export determine the following action.
