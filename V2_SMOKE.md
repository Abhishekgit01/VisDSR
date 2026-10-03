# VisDSR v2 smoke review

## Qwen: 3 October 2026

The three-call smoke completed on the same 8-element, four-operation task (`pilot2_0004`). All responses passed the existing output validator; none had the correct final map or a fully correct step. This establishes that the runner loads, generates, and caches responses. It does not establish adequate task accuracy or image understanding.

| Condition | Valid output | Final exact match | Correct steps | Latency | Output tokens |
| --- | ---: | ---: | ---: | ---: | ---: |
| T-dir | 1/1 | 0/1 | 0/4 | 40.74 s | 322 |
| R-dir | 1/1 | 0/1 | 0/4 | 101.14 s | 322 |
| G-dir | 1/1 | 0/1 | 0/4 | 99.41 s | 322 |

These are three conditions on one task, not three independent accuracy samples. Mean latency was 80.43 seconds. The rough 400-call extrapolation is 8.94 elapsed hours of inference, excluding loading; it omits structured-condition timing and other difficulty cells.

### Runtime and provenance

- Model: `Qwen/Qwen3-VL-8B-Instruct`.
- Revision: `0c351dd01ed87e9c1b53cbc748cba10e6187ff3b`.
- Code: `212d49d97064013256f5a8c4bc5965b4591d580d`.
- Hardware: two Tesla T4 GPUs, each reporting 14.56 GiB; the device map placed model components across both GPUs without CPU offload.
- Quantization: bitsandbytes 4-bit NF4; logged compute dtype `torch.bfloat16`, attention `sdpa`.
- Generation: `do_sample=False`, `num_beams=1`, `max_new_tokens=2048`.
- Input tokens: 558 for text, 1,556 for each image condition. No response reached the output cap.
- Largest per-device allocated peak: 5.19 GiB. The image calls recorded approximately 4.56 GiB on GPU 0 and 5.19 GiB on GPU 1. The reported peak is not total memory across both GPUs.
- Environment: Python 3.13.15, PyTorch 2.11.0+cu128, Transformers 4.57.1, accelerate 1.14.0, bitsandbytes 0.50.2, huggingface_hub 0.36.2.
- No out-of-memory error occurred in these calls. The installation and generation notices did not interrupt this run.

The reviewed private `visdsr_v2_results.zip` has SHA-256 `a201c4ddbcdb585d059e62d78f3772505cc6daf23847e1735c3906d19e504d6f`. It contains 32 payload files and the export marker: 12 calibration tasks, 24 images, image mapping and request order, three caches, their raw-response export, and the smoke score CSV. All payload checksums and 21 protected source hashes match. Exact prompts, image hashes, model revision, task hashes, generation parameters, raw records, and recomputed scores agree. All 12 task answers match the independent Python DSU reference. Restore and score-only replay reuse all three responses without model loading.

The Kaggle log records successful pixel validation with Graphviz 2.43.0. Local Graphviz 15.1.0 regenerates different diagram pixels, so full local pixel-regeneration validation did not pass. The original PNG bytes were preserved, checked against their manifest, and the two smoke images were inspected against the starting map. Exact rendering reproduction requires the recorded rendering environment. Do not regenerate the images independently for the second model.

### Observed errors

T-dir and R-dir returned identical raw strings. Each copied the initial parent map at every step. The first operation is `find(E)` on `E -> D -> C`; it must return `C` and change E's parent to C. Both responses returned B and left E pointing to D.

The G-dir response matches every step of these operations applied to a fresh forest in which each element is its own parent. The supplied diagram instead has two four-element sets, rooted at B and C. This comparison describes the output pattern; it does not prove why the model used that starting state.

### Smoke decision and diagnostic procedure

After the smoke, calibration and main stayed disabled while we checked these failures. The eight diagnostics have now completed; their audit is below. The procedure used the bounded checks in [`eval/diagnose.py`](eval/diagnose.py):

1. Initial-map extraction from text.
2. Initial-map extraction from rendered text.
3. Initial-map extraction from the diagram.
4. Root and set-size counting from text.
5. One path-compressing find from text.
6. One meaningful union from text.
7. The same isolated find from rendered text.
8. The same isolated find from the diagram.

All checks reuse the smoke forest, source images, pinned model, system instruction, and generation settings. Isolated operations use the existing simulator for truth. The helper writes separate diagnostic caches and checks bare JSON; these results are excluded from every official study score. It resumes matching caches and exports after each new response. Existing request mismatches stop before any new inference. There is no repeated diagnostic search for a desirable score.

Enable GPU and Internet in Kaggle. If the runtime restarted and lost its project files, attach the saved `visdsr_v2_results.zip` as a private Dataset through Add Input. The following cell defines its own imports and paths; it does not require earlier notebook variables. Replace the previous diagnostic cell with it and run only this cell:

```python
import subprocess
import sys
from pathlib import Path

root = Path("/kaggle/working/VisDSR_v2")
repo = "https://github.com/Abhishekgit01/VisDSR.git"

if (root / ".git").exists():
    subprocess.run(["git", "-C", str(root), "pull", "--ff-only",
                    "origin", "study-v2"], check=True)
elif not root.exists() or not any(root.iterdir()):
    subprocess.run(["git", "clone", "--depth", "1", "--branch",
                    "study-v2", repo, str(root)], check=True)
elif not (root / "notebooks/kaggle_diagnostics.py").exists():
    raise RuntimeError("This project copy has no Git checkout; use the current study-v2 project")

subprocess.run([sys.executable, str(root / "notebooks/kaggle_diagnostics.py"),
                "--model", "model1"], check=True)
```

The recovery script installs the pinned dependencies, requires the existing or restored smoke caches, builds the simulator, and resumes diagnostics. A missing backup stops before any model call. It preserves the original images and exports progress after interruption. It does not regenerate tasks or images or rerun the smoke through inference.

Download the updated `visdsr_v2_results.zip` from Output and review the diagnostic responses. The eight checks stop automatically; they do not launch calibration. The original three smoke caches remain intact. This module and review document do not change any protected study source, so the existing v2 backup remains compatible.

## Qwen diagnostic review: 3 October 2026

All eight planned checks completed on `pilot2_0004`, with six valid outputs and two correct answers. These are targeted checks on one forest, excluded from official study scores; they are not an estimate of general model accuracy.

| Check | Valid output | Correct | Latency | Output tokens |
| --- | ---: | ---: | ---: | ---: |
| Initial-map extraction, text | Yes | Yes | 6.94 s | 37 |
| Initial-map extraction, rendered text | Yes | Yes | 59.47 s | 37 |
| Initial-map extraction, diagram | Yes | No | 60.90 s | 52 |
| Roots and set sizes, text | Yes | No | 6.86 s | 46 |
| Isolated find, text | Yes | No | 8.65 s | 48 |
| Isolated union, text | Yes | No | 12.78 s | 84 |
| Isolated find, rendered text | No | No | 375.24 s | 2,048 |
| Isolated find, diagram | No | No | 373.43 s | 2,048 |

The diagram extraction reported H and D as roots, although the source forest is rooted at B and C. The root-counting response reported sizes B=7 and H=2 for an eight-element forest; the correct sizes are B=4 and C=4. The isolated text find returned B and left E pointing to D; it must return C and set E's parent to C. The isolated text union left the map unchanged; it must set G's parent and C's parent to B.

Both image finds returned repeated extra steps for a task containing one operation, then reached the 2,048-token cap and ended with incomplete JSON. The rendered-text find repeated the initial map; the diagram find began from singleton parents. All original responses are preserved. Correct transcription in separate calls does not establish which state the model used during the operation calls, and these outputs do not establish an internal failure mechanism.

### Diagnostic archive and replay

The reviewed private `visdsr_v2_diagnostics_complete.zip` has SHA-256 `e16e1fe4cb4b808e21c01caf6fc8556af88e17bf0fe1d340336be021f53dd960` and size 216,503 bytes. It contains 41 payload files and the export marker, including eight diagnostic records and their summary. All 32 payload files from the original smoke archive are byte-identical. The three official smoke scores remain unchanged.

All payload checksums and 21 protected source hashes match. Each diagnostic's exact prompts, image hash, task hash, expected answer, model revision, request key, and diagnostic-code hash passed replay checks. The diagnostic source SHA-256 is `4cee9793285518d69352ef84e383105bf185f670c574d7c493e877e0529e7419`. The archive's run manifest records code commit `3875c2f90c4a25b59ff0eaf87911f372bb71795a`.

An isolated local checkout restored all files. Score-only replay reproduced all eight diagnostic results and the three original smoke scores with model loading explicitly disabled. The independent Python DSU reference matched all 12 calibration task answers and all four isolated-operation answers. No tasks or images were regenerated during this audit; the Graphviz reproduction limitation described above still applies.

The recorded model revision, NF4 quantization, two Tesla T4 GPUs, dependencies, and greedy generation parameters match the earlier smoke. Image requests include pixel tensors and image-grid metadata. The largest per-device allocated peak was 5.18 GiB. Total diagnostic inference latency was 904.28 seconds (15.07 minutes), excluding loading; no OOM was reported. Both failed image finds used all 2,048 allowed output tokens. The archived summary has `new_calls=0` because it was produced by the final score-only replay; the eight timestamped raw responses are present.

### Next live run: InternVL smoke

Keep Qwen calibration disabled while reviewing the second model. Do not select a new prompt, change the scoring rules, or repeat failed responses to obtain a better result. The next run is the already planned InternVL v2 smoke on the identical forest and image bytes.

1. Import [`internvl35_v2_kaggle.ipynb`](notebooks/internvl35_v2_kaggle.ipynb) into a new Kaggle notebook. Enable a free GPU and Internet.
2. Attach `visdsr_v2_diagnostics_complete.zip` as the only VisDSR results input, using a private Dataset. The restore checks accept its original ZIP and Kaggle's extracted layout.
3. Leave `MODEL = "model2"`, `STAGE = "smoke"`, `SMOKE_REVIEWED = False`, and `MAIN_APPROVED = False` in the first code cell.
4. Run the notebook's cells from top to bottom. The unmodified notebook makes three InternVL requests, preserves Qwen's responses, and exports automatically. Its stage guards stop before calibration.
5. Download the new `visdsr_v2_results.zip` and review InternVL's raw responses, formatting, tokens, memory, and latency before deciding about calibration.

No v2 calibration, freeze, or main run has occurred. [`STUDY_V2.md`](STUDY_V2.md) is the preserved pre-run plan; this file records subsequent observations.
