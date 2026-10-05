# Qwen main results

Reviewed on 5 October 2026. Qwen collection is complete; the two-model study remains in progress.

## Collection

- Model: `Qwen/Qwen3-VL-8B-Instruct`.
- Revision: `0c351dd01ed87e9c1b53cbc748cba10e6187ff3b`.
- Frozen source commit: `2beb395e176de5527ec3d0166529b51a4f1c17e3` (`v2.0-frozen`).
- 80 fresh main tasks, five conditions, 400 unique responses.
- Local 4-bit NF4 inference on Kaggle, with greedy decoding and a 2,048-token output limit.
- No new inference, answer repair, or accuracy-based retry was used during this review.

## Official scores

Invalid output counts as incorrect. Each condition has the same 80 tasks.

| Condition | Correct final maps | Format failures |
| --- | ---: | ---: |
| T-dir | 0/80 | 1/80 |
| R-dir | 0/80 | 26/80 |
| G-dir | 0/80 | 37/80 |
| T-str | 3/80 | 50/80 |
| G-str | 0/80 | 24/80 |
| Total | 3/400 | 138/400 |

62 responses reached the output-token cap. Mean recorded inference latency was 118.06 seconds per response, excluding model loading and setup.

The primary T-dir minus G-dir difference is zero percentage points: neither condition produced a correct final map. This accuracy floor limits sensitivity and does not establish modality equivalence. The three successes in T-str do not support a general claim that transcription improves reasoning. These results describe performance under the frozen bounded-output protocol, rather than unrestricted DSU ability or a model's internal failure mechanism.

## Verification

The reviewed archive was `visdsr_v2_results (10).zip`, with SHA-256:

```text
144f7023e48311b81e64d56fc57280ed3c2830ae9d37cdfe078fe8705d21bfde
```

`visdsr_qwen_main_complete.zip` is a descriptive copy of that archive with identical bytes. It has not been published as a reproduction release yet.

The audit checked:

- ZIP integrity and all 732 payload checksums.
- The freeze, 21 protected study source hashes, and 164 preserved calibration payloads.
- All 520 official cached requests: 400 Qwen main, 60 Qwen calibration, and 60 InternVL calibration.
- Exact prompts, task/image hashes, model revisions, generation settings, unique task-condition pairs, and the frozen main request order.
- Byte-for-byte preservation of all 503 prior caches and 190 prior input files from the preceding backup.
- All 520 score rows, recomputed from raw responses, and agreement between raw JSONL and cache records.
- Reproduction of the Qwen main summary and comparison tables using the frozen analysis code.
- Independent replay of all 92 task answers through the C++ simulator.

The original PNG bytes match the freeze and preceding export. Local pixel regeneration failed on a host using Graphviz 15.1.0; the run manifest records Graphviz 2.43.0. This review does not claim successful pixel reproduction on the local host. The original images were preserved. The InternVL runner must pass the existing image validation in Kaggle before inference.

## Remaining work

Collect InternVL's 400 main responses on the same frozen inputs, then audit the combined export, recompute the paired analysis, and finish the report and reproduction artifact. Calibration and diagnostics remain separate from main results. No further prompt or task selection is part of the official study.
