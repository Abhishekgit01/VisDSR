# Understanding VisDSR

## DSU in plain language

`parent_[x]` stores the next node to follow from element `x`. A **root** points to itself. Following parents from any element eventually reaches its set's root.

`find(x)` first walks to that root. It then walks the same path again and makes every visited node point directly to the root. This is **full path compression**. The returned root is the same, but the parent map can change. For example, if `D → C → A` and `A` is a root, `find(D)` returns `A` and changes `D`'s parent to `A`.

`unite(a,b)` calls `find` on both arguments first, so either path may compress. If the roots differ, **union-by-size** attaches the smaller set's root under the larger set's root. If the sizes are equal, the root found from `b` attaches under the root found from `a`. Set size changes only when two sets merge. If both arguments already have the same root, there is no merge, but their `find` calls may still change parent pointers.

## Why there are five conditions

Every condition starts from the same DSU state and applies the same operations. Only the presentation of that starting state and the request for transcription change.

- **T-dir:** canonical text; the baseline for applying DSU rules.
- **R-dir:** the same text rendered as pixels; this separates receiving text as an image from reading a forest diagram.
- **G-dir:** a forest diagram; arrows go from child to parent.
- **T-str:** text plus a request to restate the initial map; this checks whether extra structured output helps even with text.
- **G-str:** diagram plus that transcription request; this checks whether explicit canonicalization changes diagram-task accuracy.

The **pilot** is a separate small set used to check difficulty and rendering before the design is frozen. The **main** set uses a different seed and supplies the paired comparisons. A paired comparison uses the same task under two conditions, so task difficulty is held constant. **Exact match** means the reported final parent map must equal the simulator's map, including the effects of path compression.

A wrong G-str transcription is recorded as a **structure-extraction failure**. A correct transcription followed by a wrong state is a **state-transition failure**. These labels describe observable outputs; they do not reveal what happened inside the model.

## AI-assisted work and review

The code and documentation currently in this repository were drafted or implemented with Codex assistance, including:

- **DSU simulator and protocol:** `sim/dsu.cpp`, including the iterative `find`, union-by-size `unite`, input parsing, and JSON output.
- **Task and image pipeline:** `gen/generate.py`, `gen/render.py`, `gen/visual_checks.py`, and `gen/validate.py`.
- **Model evaluation:** `eval/prompts.py`, `eval/validate.py`, `eval/score.py`, `eval/run.py`, `eval/diagnose.py`, and all files in `eval/providers/`.
- **Analysis and reproducibility:** `analysis/stats.py`, `analysis/analyze.py`, `manifest.py`, `visdsr.py`, `configs/experiment.yaml`, `configs/v2_tasks.json`, `study_transfer.py`, the environment requirements, and `Makefile`.
- **Test harness and examples:** `tests/naive.py`, `tests/stress.py`, `tests/examples.json`, and `tests/test_*.py`.
- **Repository setup and documentation:** `.gitignore`, `README.md`, `SPEC.md`, `REPORT.md`, `STUDY_V2.md`, `V2_SMOKE.md`, the Kaggle notebooks, `notebooks/kaggle_diagnostics.py`, and this explanation. The package `__init__.py` files are empty markers.

The C++ simulator was checked against the independent Python test oracle on the worked example and 5,000 seeded random cases. The pilot tasks and images were generated and validated. Two Qwen calibration pilots and a three-call InternVL smoke test were run on Kaggle; their audited findings and limits are in [`REPORT.md`](REPORT.md). The separate v2 Qwen smoke completed three calls on one task; all answers were wrong. Eight bounded v2 diagnostics also completed: text and rendered-text transcription were correct; diagram extraction and the five DSU checks were incorrect. InternVL's separate v2 smoke also completed on the same task: its text and rendered-text outputs passed the schema, its diagram output failed the schema, and all three final maps were incorrect. Both smoke archives passed cached replay. The current calibration uses one fixed representative set per model. InternVL has completed 60/60 responses, with one correct final map and 38 format failures. Qwen has completed 43/60 responses, with two correct final maps and eleven format failures. The [calibration results and run log](V2_SMOKE.md) documents the reviewed evidence and remaining calls. No main study has been run. These results describe the current calibration; the earlier stop decision belongs to the historical pilot report.
