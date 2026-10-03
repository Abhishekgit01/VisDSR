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

### Decision and next run

Keep calibration and main disabled while checking these specific failures. Use the eight bounded diagnostics in [`eval/diagnose.py`](eval/diagnose.py):

1. Initial-map extraction from text.
2. Initial-map extraction from rendered text.
3. Initial-map extraction from the diagram.
4. Root and set-size counting from text.
5. One path-compressing find from text.
6. One meaningful union from text.
7. The same isolated find from rendered text.
8. The same isolated find from the diagram.

All checks reuse the smoke forest, source images, pinned model, system instruction, and generation settings. Isolated operations use the existing simulator for truth. The helper writes separate diagnostic caches and checks bare JSON; these results are excluded from every official study score. It resumes matching caches and exports after each new response. Existing request mismatches stop before any new inference. There is no repeated diagnostic search for a desirable score.

In the current Qwen Kaggle notebook, keep `STAGE = "smoke"`. Add one code cell below the existing cells and run it:

```python
run_command("git", "pull", "--ff-only", "origin", "study-v2")
try:
    run_command(sys.executable, "-m", "eval.diagnose",
                "--model", "model1", "--export", str(EXPORT))
finally:
    export_results()
```

Download the updated `visdsr_v2_results.zip` from Output and review the diagnostic responses. The eight checks stop automatically; they do not launch calibration. The original three smoke caches remain intact. This module and review document do not change any protected study source, so the existing v2 backup remains compatible.

InternVL's v2 smoke is still pending. No v2 calibration, freeze, or main run has occurred. [`STUDY_V2.md`](STUDY_V2.md) is the preserved pre-run plan; this file records subsequent observations.
