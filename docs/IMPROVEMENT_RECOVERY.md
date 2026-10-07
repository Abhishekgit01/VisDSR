# Recovering the lost improvement collection

The 7 October 2026 draft log recorded 192 completed responses and a successful export. The subsequent session check found no project directory, response caches, or ZIP. The only saved version failed during decoder preflight before inference, using source from before the CUDA device-selection fix. Its output cannot contain the later draft's model answers. The earlier main-study release remains available.

The [recovery notebook](../notebooks/visdsr_improvements_recovery.ipynb) performs replacement collection of the same frozen 192-request development panel. It pins commit `9b4d02bb189b66daf2ec99790270f0f481301247`, which includes the tested CUDA correction. Tasks, prompts, grammar rules, checkpoints, decoding settings, scoring, and both models' requests are unchanged. The discarded draft is not treated as a separate replication, and its progress log is not used to reconstruct raw answers.

## Start a saved run

1. Import `visdsr_improvements_recovery.ipynb` into Kaggle. Enable Internet and GPU T4 ×2. This replacement run needs no previous-study ZIP.
2. Use **Save Version → Save & Run All** immediately. The notebook's configuration, setup, and collection cells reject interactive execution using `KAGGLE_KERNEL_RUN_TYPE`; this avoids accidentally launching another long draft run. The run type is documented in a [firsthand Kaggle environment inspection](https://www.kaggle.com/general/147433).
3. Open the **new saved version's Log**, rather than the old failed version. It should print `SAVED RUN MODE: Batch`, the full pinned source commit, `GPU MASK CHECK: 2 CUDA devices tested`, and both `STARTING model1` and `STARTING model2`.
4. The collection continues until all 192 requests finish, with no notebook time cutoff. After the saved version completes, open its **Output** and download `visdsr_improvements_complete.zip`. If collection is partial, download `visdsr_improvements_backup.zip` and attach it before starting another saved run.

The final export records the data-loss replacement in `run_status.json` inside the checksummed archive. Raw response caches and scores are not edited by this note. Compatible downloaded diagnostic or improvement backups can still be restored; cached requests are skipped.

If setup reports missing Configuration, or Export reports missing `run_status.json`, the preceding steps did not complete in that runtime. Launch the complete notebook with the top-right **Save Version → Save & Run All** button. If those messages appear in the new saved version's Log, inspect its first Configuration, setup, or collection error; running Export alone cannot create missing model answers.

**A ZIP on temporary runtime storage is not a durable backup.** Saved execution and interactive execution are separate: [Kaggle staff explain](https://www.kaggle.com/product-feedback/275813) that Save & Run All reruns the notebook in the background, while Quick Save can preserve current files when its output-saving option is enabled. Saved-version output downloads are also supported by the [official CLI](https://github.com/Kaggle/kaggle-cli/blob/main/docs/kernels.md#kaggle-kernels-output). Platform termination, quota limits, or infrastructure failures may still prevent retention of a run's outputs; this notebook cannot guarantee external persistence.

## Scope and verification

This is a replacement development collection, not a new accuracy claim or a changed experiment. The fixed-source implementation already completed the earlier interactive collection and its two-GPU mask checks. The recovery wrapper is verified locally for clean notebook syntax, rejection of interactive inference, and acceptance of the saved-run configuration. Physical GPU execution and Kaggle's retention of the replacement run must be confirmed in that saved version.
