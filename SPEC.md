# DSU experiment protocol

**Status:** Qwen calibration stopped after the planned two pilots. The shorter second pilot scored T-dir 1/12, R-dir 0/12, and G-dir 0/12 on final-state exact match. The text baseline remains at floor, so no freeze or main run has occurred. A separate three-call InternVL3.5 feasibility check is prepared on an existing pilot2 task.

## Task rules

Elements are labeled `A` onward. The state is a parent map; a root is its own parent. `find(x)` follows parent pointers to a root, points every node on that path directly to the root, and returns it. `union(a,b)` runs both finds before comparing set sizes. It attaches the smaller root below the larger one. On equal size, `b`'s root attaches below `a`'s root. A union within one set performs no merge, although its finds may compress paths.

Initial states are built from valid union sequences by `sim/dsu.cpp`; arbitrary parent maps are not sampled. `tests/naive.py` is an independent test oracle and is not used to generate study truth.

## Tasks and images

| Split | 8 elements | 16 elements |
| --- | ---: | ---: |
| Pilot 1, 4 operations | 6 tasks | 6 tasks |
| Pilot 2, 1 operation | 3 tasks | 3 tasks |
| Pilot 2, 2 operations | 3 tasks | 3 tasks |
| Main, 1 operation | 20 tasks | 20 tasks |
| Main, 4 operations | 20 tasks | 20 tasks |

Both pilot rounds and the main study use different seeds, and the generator rejects overlap across splits. Every main task appears in T-dir, R-dir, G-dir, T-str, and G-str. The initial forest must contain a depth-two node and at least two non-singleton trees; large states need at least three trees. Pilot 2 balances three meaningful unions and three depth-two finds across its six one-operation tasks. Every two-operation pilot task has a depth-two path-compressing find followed by a meaningful union; each size cell includes an equal-size tie. The planned main one-operation tasks alternate between meaningful unions and depth-two finds. Four-operation tasks include both a meaningful union and a depth-two find, with at most one no-op union. The original main task plan is inactive after Qwen calibration.

Images are 1024 × 1024 RGB PNGs with a white background and black marks. R-dir renders the exact canonical string supplied in T-dir. G-dir and G-str use the same diagram bytes. Forest arrows point from child to parent. No result is encoded by color.

## Responses and measures

The model returns JSON with the full parent map after each operation and the returned root for each `find`. T-str and G-str also return the initial parent map in `transcription`. Invalid JSON or missing/invalid fields count as incorrect in the primary measure; content errors are not retried.

The **task** is the paired unit of analysis. The primary DSU measure is final-state exact match. The primary paired comparison is G-dir versus T-dir; reported differences use **T-dir minus G-dir** in percentage points. Report both accuracies, a 10,000-resample paired bootstrap 95% confidence interval for the difference, an exact McNemar p-value, and, when both model families are eventually tested, Holm correction across the two model tests.

Secondary measures are per-step exact match, full-sequence success, first error step, transcription accuracy, format-error rate, and recovery after a wrong intermediate state. Secondary contrasts are T-dir minus R-dir, R-dir minus G-dir, G-str minus G-dir, T-str minus T-dir, and the difference between the latter two. Treat T-dir versus R-dir descriptively; a nonsignificant test does not establish equivalence. Wrong transcription is labeled a structure-extraction failure, without claiming access to the model's internal perception.

## Freeze

Use at most two pilot/calibration rounds. Pilot 2 uses a new seed and shorter sequences while keeping the first pilot intact. The pilot 1 prompt wording and strict scorer are retained verbatim, so the structured-format failures remain visible. A separate diagnostic may remove an extra `find_result` from union steps or parse a JSON-string transcription to assess content, but it never changes official scores. If calibration supports a main study, record the decision in `FREEZE.json`, commit the protocol, and tag that commit `v1.0-frozen`. Generate the 80 main tasks with the separate main seed only then. Qwen calibration did not support that step, so `FREEZE.json` has not been created. The InternVL3.5 smoke test checks a different model family on an existing pilot2 task; it does not change the Qwen pilot data or constitute a main run. Do not add conditions, prompts, metrics, structures, or models to the main study after freeze. Record any necessary bug fix in Git history and state whether it changes generated data or results.
