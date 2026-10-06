# One overnight improvement comparison

**Prospective exploratory protocol, 7 October 2026; collection pending.** This implements the fixed 2×2 comparison in the [research review](ACCURACY_FLOOR_RESEARCH.md#second-a-separately-specified-intervention-comparison). It uses the same eight development forests as the [diagnostic pilot](DIAGNOSTICS.md), retaining 8/16 elements, one/four operations, exact DSU rules, full parent maps, and both pinned model revisions.

## Fixed comparison

| Arm | Prompt | Decoding | New calls |
| --- | --- | --- | --- |
| Baseline | Original rules and worked examples | Original greedy generation | 0: reuse the 32 identical diagnostic update requests |
| Grammar | Identical baseline prompt | XGrammar 0.2.8 | 32 |
| Procedure | Baseline plus the exact find/union procedure | Original greedy generation | 32 |
| Combined | Identical procedure prompt | XGrammar 0.2.8 | 32 |

Every arm covers all eight forests in text and diagram conditions for both checkpoints. The 96 diagnostic controls plus 96 additional improvement requests give **192 unique inference calls**, 96 per model. Existing compatible diagnostic responses can be restored and reused. No answer is selected, repaired, or regenerated because it is incorrect. All requests start independently.

The [freeze](../interventions/FREEZE.json) and [requests](../interventions/requests.json) specify the exact prospective protocol. The additional requests are shuffled with seed `2026100705` after the original diagnostic block. All settings retain greedy decoding, one beam, NF4, the pinned Transformers 4.57.1 and a 2,048-token cap. Sources for the completed study and the published 96-call diagnostic protocol are unchanged.

The procedural instructions specify traversal, compression, read-only component counting, union ties, preserving compression on no-op unions, and carrying the full predicted map between operations. They supply no computed roots or states for a task.

The [grammar builder](../interventions/protocol.py) uses only the task's node labels and supplied operations. It fixes compact JSON serialization and field order, operation indexes, step counts, all parent-map keys, and find-result presence. **Every allowed parent value remains possible**, including wrong maps and cyclic predictions. This is a serialization intervention as well as a structural constraint. It cannot guarantee a correct answer; truncation can still produce invalid output. The [official XGrammar adapter](https://github.com/mlc-ai/xgrammar/blob/main/python/xgrammar/contrib/hf.py) is used with a fresh logits processor for each call; compilation time is recorded separately from inference latency.

## A separate model-plus-executor baseline

The actual extraction answers from text, rendered text, and diagrams are reused for an assisted execution evaluation, requiring **zero extra model calls**. A fixed executor validates labels and forest acyclicity, derives component sizes from the predicted forest, and applies the supplied operations. It receives no gold parent values and performs no transcription correction. Invalid extractions and non-root cycles count as failures. Exact extraction, exact final map, and full-sequence correctness are reported separately.

This measures an assisted system. Its result is not unaided model accuracy and is not pooled with the four model-only arms or the completed main study.

## Kaggle execution

1. Import [dsu_improvements_overnight.ipynb](../notebooks/dsu_improvements_overnight.ipynb) into a new notebook. Enable Internet and **GPU T4 ×2**.
2. Leave `PARALLEL_MODELS = True` and `BACKUP_INPUT = "auto"`. A fresh run needs no previous-study ZIP. Attach a diagnostic backup if you already collected this development panel.
3. Choose **Save Version → Save & Run All**, wait until the saved run is Running, then you may close the browser or sleep the laptop. [Kaggle documents](https://www.kaggle.com/docs/notebooks) that this executes a fresh copy in a separate session and retains outputs in the completed version.
4. Open the saved version's Output after completion. Download **`visdsr_improvements_complete.zip`** if the final status is **192/192**. Otherwise download **`visdsr_improvements_backup.zip`** and resume with it attached.

Each model runs in a fresh subprocess pinned to its own physical GPU, with one model load for its 96 requests. The two-GPU mode executes both models concurrently; a single-GPU mode runs them sequentially. The run records GPU visibility and whether parallel execution was enabled. Host RAM and CUDA capacity still require real hardware verification. If one worker fails, the other can complete, and the parent saves an explicitly partial archive. The workers run until their fixed panels are complete. User interruptions or worker failures trigger a partial export. Each response atomically updates its raw cache and its model's own backup ZIP; model-specific ZIPs avoid concurrent writes to one archive.

The final archive includes the compatible original diagnostic archive, new source snapshots and freeze, all raw intervention answers, four-arm scores, paired corrected/lost counts, difficulty-cell identifiers, cap hits, assisted outputs, runtime errors, and a readable report. Restoration validates all checksums and request provenance before replacing any state and refuses conflicting answers. The original diagnostic archive remains independently usable.

The notebook has no clock-based cutoff. It finishes once its 192-response panel is complete, or records infrastructure failures and preserves the completed responses. Kaggle's own quota and session limits still apply; platform termination can prevent a saved version from completing. Runtime estimates use prior latencies and are not a completion guarantee.

## Interpretation fixed before collection

Final-map exact match is primary for all four arms; full-sequence correctness and changed-parent accuracy are secondary. Invalid output is incorrect. Compare each new arm to its matched baseline task and presentation; report both corrected and lost answers. Report every size/operation group, including zero-success groups. Keep the original diagnostic gate unchanged and compute it from its 96 controls only.

This eight-forest comparison is exploratory development evidence. It does not establish held-out improvement, support a powered significance claim, or authorize repeated prompt tuning until a preferred result appears. All arms are collected regardless of earlier accuracy. A future selected method requires its own prospective freeze and fresh held-out confirmation panel.

## Commands

```bash
python -m interventions check
python -m interventions decoder-check  # actual tokenizers and grammars; no model weights
python -m interventions overnight --output-dir /tmp/improvements
python -m interventions score
python -m interventions export --output /tmp/visdsr_improvements_backup.zip
python -m interventions restore --input /path/to/visdsr_improvements_backup.zip
```

CPU checks validate request identity, structural grammar behavior, the executor against independent simulator truths, paired scoring, backup integrity, and orchestration. GPU inference remains to be measured. No positive accuracy result is claimed in advance.

## Decoder implementation amendment, 7 October 2026

The first Kaggle setup stopped in `decoder-check` with Triton's `Pointer argument (at 0) cannot be accessed` error, before loading model weights or collecting responses. The original check allocated logits on each GPU but did not select that GPU as the current CUDA device for the kernel launch. The official XGrammar 0.2.8 adapter dispatches CUDA masking to Triton without a device guard. [PyTorch's device context](https://docs.pytorch.org/docs/stable/generated/torch.cuda.device_of.html) selects the tensor's device and restores the caller's selection; the [Triton issue](https://github.com/triton-lang/triton/issues/2441) reports the same failure on a second GPU.

The adapter now runs inside that device context in both preflight and inference. Preflight also compares all masked logits against the CPU reference for two valid prefix tokens on every visible GPU. This is an implementation correction before collection: requests, prompts, task difficulty, grammar rules, model revisions, and generation settings are unchanged. Only the separate intervention source freeze is updated; the original study and diagnostic freeze remain intact. CPU and simulated device-context regressions pass locally. The two-GPU regression requires CUDA hardware and remains covered by Kaggle's mandatory preflight.

To update the checkout from the failed setup, run `git pull --ff-only origin main` inside `/kaggle/working/VisDSR_improvements`, then rerun Configuration and Setup. Use **Save Version → Save & Run All** for overnight collection.
