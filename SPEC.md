# DSU experiment protocol

**Status:** Draft. It becomes frozen only after the pilot is calibrated, the exact model IDs are recorded, and a frozen Git commit is tagged. No pilot or main model run has occurred.

## Task rules

Elements are labeled `A` onward. The state is a parent map; a root is its own parent. `find(x)` follows parent pointers to a root, points every node on that path directly to the root, and returns it. `union(a,b)` runs both finds before comparing set sizes. It attaches the smaller root below the larger one. On equal size, `b`'s root attaches below `a`'s root. A union within one set performs no merge, although its finds may compress paths.

Initial states are built from valid union sequences by `sim/dsu.cpp`; arbitrary parent maps are not sampled. `tests/naive.py` is an independent test oracle and is not used to generate study truth.

## Tasks and images

| Split | 8 elements | 16 elements |
| --- | ---: | ---: |
| Pilot, 4 operations | 6 tasks | 6 tasks |
| Main, 1 operation | 20 tasks | 20 tasks |
| Main, 4 operations | 20 tasks | 20 tasks |

Pilot and main use different seeds, and the main generator rejects pilot overlap. Every main task appears in T-dir, R-dir, G-dir, T-str, and G-str. The initial forest must contain a depth-two node and at least two non-singleton trees; large states need at least three trees. One-operation tasks alternate between meaningful unions and finds at depth two or more. Four-operation tasks include both a meaningful union and a depth-two path-compressing find, with at most one no-op union.

Images are 1024 × 1024 RGB PNGs with a white background and black marks. R-dir renders the exact canonical string supplied in T-dir. G-dir and G-str use the same diagram bytes. Forest arrows point from child to parent. No result is encoded by color.

## Responses and measures

The model returns JSON with the full parent map after each operation and the returned root for each `find`. T-str and G-str also return the initial parent map in `transcription`. Invalid JSON or missing/invalid fields count as incorrect in the primary measure; content errors are not retried.

The **task** is the paired unit of analysis. The primary DSU measure is final-state exact match. The primary paired comparison is G-dir versus T-dir; reported differences use **T-dir minus G-dir** in percentage points. Report both accuracies, a 10,000-resample paired bootstrap 95% confidence interval for the difference, an exact McNemar p-value, and Holm correction across the two model tests.

Secondary measures are per-step exact match, full-sequence success, first error step, transcription accuracy, format-error rate, and recovery after a wrong intermediate state. Secondary contrasts are T-dir minus R-dir, R-dir minus G-dir, G-str minus G-dir, T-str minus T-dir, and the difference between the latter two. Treat T-dir versus R-dir descriptively; a nonsignificant test does not establish equivalence. Wrong transcription is labeled a structure-extraction failure, without claiming access to the model's internal perception.

## Freeze

Use at most two pilot/calibration rounds. After calibration, record the decision in `FREEZE.json`, commit the protocol, and tag that commit `v1.0-frozen`. Generate the 80 main tasks with the separate main seed only then. Do not add conditions, prompts, metrics, structures, or models to the main study after freeze. Record any necessary bug fix in Git history and state whether it changes generated data or results.
