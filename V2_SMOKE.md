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

### InternVL smoke procedure

After the Qwen diagnostics, calibration stayed disabled until the second model smoke was reviewed. The following procedure completed the planned InternVL v2 smoke on the identical forest and image bytes. Its audit and the calibration decision follow below.

1. Import [`internvl35_v2_kaggle.ipynb`](notebooks/internvl35_v2_kaggle.ipynb) into a new Kaggle notebook. Enable a free GPU and Internet.
2. Attach `visdsr_v2_diagnostics_complete.zip` as the only VisDSR results input, using a private Dataset. The restore checks accept its original ZIP and Kaggle's extracted layout.
3. Leave `MODEL = "model2"`, `STAGE = "smoke"`, `SMOKE_REVIEWED = False`, and `MAIN_APPROVED = False` in the first code cell.
4. Run the notebook's cells from top to bottom. The unmodified notebook makes three InternVL requests, preserves Qwen's responses, and exports automatically. Its stage guards stop before calibration.
5. Download the new `visdsr_v2_results.zip` and review InternVL's raw responses, formatting, tokens, memory, and latency before deciding about calibration.

## InternVL smoke review: 3 October 2026

InternVL completed the same three conditions on `pilot2_0004`. All three responses are syntactically valid JSON; T-dir and R-dir satisfy the required schema, while G-dir contains an extra `find_result` on the second operation, a union. None has a correct final map or a fully correct step under official scoring.

| Condition | Valid study output | Final exact match | Correct steps | Latency | Input / output tokens |
| --- | ---: | ---: | ---: | ---: | ---: |
| T-dir | 1/1 | 0/1 | 0/4 | 22.28 s | 558 / 168 |
| R-dir | 1/1 | 0/1 | 0/4 | 51.23 s | 3,093 / 168 |
| G-dir | 0/1 | 0/1 | 0/4 | 53.57 s | 3,093 / 172 |

T-dir returns the correct roots for both finds, but misses the required path compression and meaningful union. Its final map also compresses E and F to B without operations traversing their paths, while leaving G pointing to H. R-dir has the same incorrect final map and returns D for the first find, whose root is C. The G-dir parent maps match these operations applied to fresh singleton parents, with the additional schema error described above. This comparison describes the returned states; it does not identify an internal cause.

### InternVL runtime and archive

- Model: `OpenGVLab/InternVL3_5-8B-HF`.
- Revision: `741a7d03020411e666c6109218ab71e08151ef86`.
- Code: `6b75e2dddb43afffe7e15cabc2d4892bbc43372b`.
- Hardware: two Tesla T4 GPUs, each reporting 14.56 GiB. Logged model devices are GPU 0 and GPU 1, without CPU offload.
- Quantization: bitsandbytes 4-bit NF4; logged compute dtype `torch.bfloat16`, framework-default attention.
- Generation: `do_sample=False`, `num_beams=1`, `max_new_tokens=2048`.
- Each image request has ten RGB 448-by-448 input tiles, with the same source PNG hash used for Qwen. Processor tensors and token counts differ across architectures.
- Mean latency: 42.36 seconds; total inference latency: 127.08 seconds, excluding loading.
- Largest per-device allocated peak: 7.34 GiB. The image calls recorded approximately 5.09 GiB on GPU 0 and 7.34 GiB on GPU 1; these are separate device measurements.
- All three responses begin with JSON, with no reasoning preamble. No response reached the output cap and no OOM was reported.
- Environment: Python 3.13.15, PyTorch 2.11.0+cu128, Transformers 4.57.1, accelerate 1.14.0, bitsandbytes 0.50.2, huggingface_hub 0.36.2.

The reviewed private `visdsr_v2_results (1).zip` has SHA-256 `613688b82925076dcb211980814499ba0e024227519f429aa9b1bc8811be2828` and size 229,146 bytes. It contains 46 payload files and the export marker: the previous 41 files plus three InternVL caches, their raw-response export, and the smoke score CSV. Every earlier Qwen/data payload is byte-identical.

All payload checksums and 21 protected source hashes match. Both models used identical task hashes, system prompts, user prompts, prompt hashes, and source-image hashes in each condition. Model IDs, pinned revisions, and effective generation parameters match the configuration. In an isolated checkout, score-only replay reproduced all six official smoke scores and both raw exports with model loading explicitly disabled. The twelve task answers also matched the independent DSU reference.

The Kaggle log records successful full image validation with Graphviz 2.43.0. Local inspection of the preserved smoke diagram agrees with the initial parent map. No images were regenerated for this audit; the local Graphviz-version limitation remains as recorded above.

### Reviewed decision: one representative calibration

The smoke checks establish working, cached inference with verified inputs and known output errors. They do not establish adequate DSU accuracy or a modality effect. Both models have so far been scored on one shared four-operation task, so the observed zero final accuracy cannot estimate performance across the planned difficulty cells.

Proceed with the single fixed calibration set from `STUDY_V2.md`: twelve tasks, all five conditions, and sixty responses per model, including the three already cached smoke responses. Keep the tasks, images, prompts, model settings, output schema, and scorer unchanged. The root and update failures are retained; no additional prompt-selection round or failure retries are planned. A second diagnostic round on the same forest would not measure the remaining difficulty cells or structured conditions, so the next evidence comes from the representative calibration.

Start with InternVL in the current session and collect at most twenty new calls per chunk. Then run Qwen calibration from the newest combined backup. There are 57 new calls remaining per model. Calibration will measure accuracy, format failures, and latency by condition, element count, and operation count before any main-run decision. Neither model is excluded because of its smoke score.

Main remains blocked. After both models reach 60/60 calibration responses, audit all raw requests and scores, review whether the baseline supports the intended modality comparison, and record the main decision before freezing. If the text baseline remains at the floor, the report must describe that limitation; these smoke checks do not authorize a claim of modality equivalence.

### Run the next InternVL calibration chunk

Use the current InternVL notebook with its saved project files. In its first code cell, change only `STAGE` to `"calibration"` and `SMOKE_REVIEWED` to `True`. Keep `MODEL = "model2"`, `MAIN_APPROVED = False`, and `NEW_CALLS_PER_CHUNK = 20`.

1. Run the edited first code cell.
2. Run the code cell under **3. Build and validate tasks and images**. It validates the restored calibration data and reports 60 requests planned, three caches already present.
3. Run the code cell under **4. Run the selected stage**. It reuses the three smoke responses and makes at most twenty new calls. After a complete first chunk, progress should be **23/60**.
4. Download the automatically exported `visdsr_v2_results.zip` after the chunk. Keep the newest backup outside the session before continuing.
5. Rerun only the selected-stage cell for the next chunk, downloading each export. Full chunks advance to **43/60**, then **60/60** with seventeen new calls in the last chunk. On interruption, retain the partial export and resume matching caches.

If the runtime has reset, attach the newest combined export as the only VisDSR results input and rerun notebook setup before the selected-stage cell. The newest reviewed combined backup at this point is `visdsr_v2_results (1).zip`, not the earlier Qwen-only diagnostic ZIP.

### Resume calibration after a kernel reset

A new kernel has no `STAGE`, `ROOT`, or `run_command` variables. The standalone recovery cell below resumes the reviewed InternVL calibration without those globals. Enable GPU and Internet. Attach the newest downloaded combined export as the only VisDSR results Dataset if this session has lost its working files. If no calibration calls have completed, use the reviewed `visdsr_v2_results (1).zip`.

Replace the failing selected-stage cell with this code and run only that cell:

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
    raise RuntimeError("Use the current study-v2 project files")

subprocess.run(
    [sys.executable, str(root / "notebooks/kaggle_diagnostics.py"),
     "--model", "model2", "--calibration"],
    check=True,
)
```

The recovery script installs the existing pinned dependencies, restores saved data when required, checks all three exact smoke caches without inference, builds the simulator, and performs the notebook's full task/image validation. It resumes one calibration chunk with at most twenty new calls and exports automatically on completion or normal interruption. It preserves matching caches and source images. Missing smoke caches or failed validation stop before new inference. Main remains disabled.

Download `/kaggle/working/visdsr_v2_results.zip` when `BACKUP READY` appears. Rerun this same cell for later chunks, keeping each updated backup outside the session. Full chunks from the smoke archive progress through 23/60, 43/60, and 60/60. This recovery change does not alter any protected protocol source or the existing backup format.

The reviewed archive contains six official smoke responses and eight Qwen diagnostic responses. The full calibration stage, freeze, and main run have not started. [`STUDY_V2.md`](STUDY_V2.md) is the preserved pre-run plan; this file records subsequent observations and the decision to start calibration.

## InternVL calibration progress: 4 October 2026

The first calibration chunk added twenty responses and reused the three smoke responses, giving **23/60** completed InternVL requests. Qwen still has its three official smoke responses and eight separate diagnostic records. There are 37 InternVL and 57 Qwen calibration requests remaining. Neither full calibration nor the main study is complete.

| Condition | Responses reviewed | Final exact matches | Format failures |
| --- | ---: | ---: | ---: |
| T-dir | 5 | 0 | 0 |
| R-dir | 5 | 0 | 3 |
| G-dir | 5 | 0 | 5 |
| T-str | 3 | 0 | 3 |
| G-str | 5 | 0 | 5 |
| Total | 23 | 0 | 16 |

All seven valid study outputs also have incorrect final maps. Format errors comprise eight top-level field mismatches, five invalid union-step fields, and three invalid JSON responses. Three diagram responses reached the 2,048-token cap. The counts by condition and difficulty cell are incomplete and unequal; this chunk supplies no paired modality-effect estimate or final calibration decision.

### Partial archive audit

The reviewed private `visdsr_v2_results (2).zip` has SHA-256 `d4ee5fdf79f9117cf0e7ba282f3d39cd4d551c0199db8bf24578a433003b074c` and size 300,953 bytes. It contains 68 payload files and the export marker. All 46 payload files from the previous combined smoke archive are byte-identical. The new files are twenty InternVL caches, a 23-response calibration raw export, and its score CSV. The run manifest records commit `9452a80f8b696c9aa1ddd4c28280b0e03e3f8bf2`.

Every payload checksum and all 21 protected source hashes passed. An isolated checkout restored the archive, checked each of the 23 requests against its prescribed model revision, settings, exact system/user prompts, task hash, image hash, and cache key, and recomputed the official scores. The CSV rows and raw JSONL records match the caches exactly; no duplicate or unaccounted InternVL request was found. All twelve task answers match the independent Python DSU reference and all 24 image hashes match their manifest. Dry-run planning reports sixty requests with 23 caches present. No model was loaded or called during the audit.

Recorded mean latency across these 23 responses is 98.63 seconds, including the three earlier smoke responses. The largest per-device allocated peak is 7.43 GiB. These partial timings include three output-cap failures and do not supply a reliable main-run estimate. The model configuration, tasks, images, prompts, and scorer remain unchanged.

### Continue the fixed calibration

In the current Kaggle session, rerun the same standalone recovery cell with `--model model2 --calibration`. It preserves existing responses and makes at most twenty new calls. A complete next chunk reaches **43/60**; the following chunk makes seventeen new calls and reaches **60/60**. Download the automatically exported `visdsr_v2_results.zip` after each chunk and review the complete archive when InternVL reaches sixty responses.

If the runtime has lost its working files, attach the newest downloaded backup as the only VisDSR results input before running recovery. The newest reviewed backup at this point is `visdsr_v2_results (2).zip`. Continue once through the preselected requests; incorrect responses are retained, and no content retries or protocol changes are introduced from these interim scores. Main remains blocked pending complete calibration for both models and the documented freeze decision.
