# Run the fixed diagnostic pilot

**Implementation ready, 7 October 2026; model collection pending.** This implements the eight-forest pilot in the [6 October proposal](FOLLOW_UP.md). It evaluates reading, DSU updates, and response compliance. The completed [main study](../MAIN_RESULTS.md) remains separate.

The [research review](ACCURACY_FLOOR_RESEARCH.md) explains why these controls are the next step. Grammar constraints, procedural-prompt ablations, native thinking modes, and assisted execution remain proposed interventions; this notebook does not enable them.

A separate [improvement-comparison notebook](INTERVENTIONS.md) now collects these same 96 controls plus 96 fixed prompt/grammar intervention requests in one run, with a separate executor evaluation. Compatible diagnostic backups remain usable. Use that notebook to collect both experiments together; this guide describes the preserved diagnostic-only workflow.

## Fixed protocol

| Item | Setting |
| --- | --- |
| Protocol ID | `visdsr-dsu-diagnostics-20261007` |
| Tasks | Eight fresh reachable forests, two in each 8/16-element × one/four-operation cell |
| Controls | Extract text, extract rendered text, extract diagram, update from text, update from diagram, copy solution |
| Calls | 48 per checkpoint, 96 total; one independent conversation per request |
| Checkpoints | The same two exact revisions as the completed main study |
| Generation | NF4, greedy, one beam, 2,048 output tokens |
| Seeds | Generation `2026100603`; request order `2026100604` |
| Output | Bare JSON, exact fields and labels; no answer repair or content retries |
| Cache | `results/followup/visdsr-dsu-diagnostics-20261007/` |

The [input freeze](../diagnostics/pilot/FREEZE.json) records source, task, image, model, and reference-corpus provenance. [Exact requests](../diagnostics/pilot/requests.json) are available before collection. The common system message reuses `eval.prompts.SYSTEM`; the extraction and copying user prompts explicitly identify their tasks. Update prompts retain the frozen rules and worked examples.

There is no exact initial-map/operation-sequence overlap with the 92 completed calibration/main tasks, and no repeated initial map within this panel. This check ignores task IDs and prelude histories. New labels do not establish new unlabeled graph structures; the generator retains the original reachable constructions.

All eight task truths were checked against C++ and the independent Python reference. The images preserve the original rendering conventions, and their bytes are committed so Kaggle does not regenerate them with a different Graphviz version. The [review record](../diagnostics/pilot/REVIEW.json) documents Codex visual inspection of text and diagram inputs in all four difficulty cells. This is not a human readability experiment.

## One overnight Kaggle run

1. Import [dsu_diagnostics_kaggle.ipynb](../notebooks/dsu_diagnostics_kaggle.ipynb) into a new Kaggle notebook. Enable **Internet** and **GPU T4 ×2**, or a single T4.
2. Leave `COLLECTION_TIME_LIMIT_HOURS = 7` and `BACKUP_INPUT = "auto"`. No previous study ZIP is needed for a fresh diagnostic pilot.
3. Choose **Save Version → Save & Run All**. Wait until the saved version is running. You can then close your browser or sleep the laptop; the collection runs on Kaggle.
4. Tomorrow, open that **saved version → Output**, rather than the interactive editor's Output. Check `visdsr_diagnostics_report.md` and download **`visdsr_diagnostics_complete.zip`** when the report shows **96/96**. Send the ZIP for review.
5. If it shows **PARTIAL COLLECTION**, download **`visdsr_diagnostics_backup.zip`** and resume with that backup attached. Collection completeness includes incorrect and malformed answers; it does not guarantee an accuracy-gate pass.

[Kaggle's documentation](https://www.kaggle.com/docs/notebooks) states that Save & Run All executes a fresh copy in a separate session and records its outputs in a notebook version. Attach any resume backup as input before starting the saved run: files in an interactive runtime are not automatically available in that fresh session. A completed saved run retains its output files; platform termination or quota exhaustion can still prevent a version from completing. Ensure sufficient GPU quota before starting.

The runner fills Qwen's 48 requests, then InternVL's 48 in a separate process, releasing GPU and host memory between checkpoints. Compatible caches are skipped. Every completed answer is saved atomically and followed by a current score report and checksummed ZIP. It creates `visdsr_diagnostics_qwen_48.zip` after Qwen completes and `visdsr_diagnostics_complete.zip` only after all 96 records have been verified.

A seven-hour collection budget leaves time for setup and output saving within an overnight run. A failed inference process is recorded; the other model can still run within the remaining budget. On reaching the budget, the active subprocess is stopped and the notebook finishes with an explicitly partial report and backup. No content failures are retried. An unfinished request can be lost; previously completed raw caches are rescored and exported. Runtime availability and per-request latency determine whether all 96 fit in this budget.

The final outputs include raw answers and metadata, `scores.csv`, `summary.json`, a readable `REPORT.md`, and `run_status.json` with elapsed time and infrastructure errors. The readable report, summary, and run status are also copied to the top-level Kaggle Output for convenient inspection.

**A ZIP left in an unsaved interactive `/kaggle/working` runtime is not a durable backup.** Use the saved background run above and download its ZIP after completion. The notebook does not upload backups to an external service.

### Resume in a later session

Attach the latest downloaded diagnostic ZIP as a private Kaggle input dataset, import the same notebook, and start another Save & Run All version. Both models resume automatically. `BACKUP_INPUT = "auto"` finds diagnostic ZIPs and matching extracted dataset folders. An explicit path can identify either form.

The restore checks payload hashes, frozen inputs, source snapshots, and every request/response record before writing caches. Compatible older backups can be merged. A conflicting answer stops restoration; existing raw responses are not replaced. Reports are recomputed from the restored records.

The original `visdsr_v2_results.zip` belongs to the completed study and cannot resume this diagnostic pilot. Use a diagnostic backup or complete ZIP here.

## Local commands

No GPU is needed for checks, cached scoring, exports, or restores:

```bash
make build
python -m diagnostics check
python -m diagnostics score
python -m diagnostics export --output /tmp/visdsr_diagnostics_backup.zip
python -m diagnostics restore --input /path/to/visdsr_diagnostics_backup.zip
```

Actual inference requires the pinned inference dependencies and a CUDA GPU. For the full sequential run:

```bash
python -m diagnostics overnight --output-dir /tmp/diagnostic-output --time-limit-hours 7
```

For an optional bounded recovery batch:

```bash
python -m diagnostics run --model model1 --max-new-calls 12 \
  --export /tmp/visdsr_diagnostics_backup.zip
```

`--score-only` on `run` requires all 48 records for the selected checkpoint and never loads a model. The separate `score` command describes any partial panel. Simultaneous collection into the same cache directory is blocked to prevent duplicate requests.

## Scoring and the gate

Extraction requires the whole initial map. Copy-solution requires every supplied step and find result. Updates use exact final-map correctness as primary and full-sequence correctness as secondary. Find-result correctness is included in full-sequence scoring. Changed-parent accuracy is supplementary, with invalid answers assigned zero.

Unlike the old main parser's complete-code-fence allowance, this new contract requires bare JSON and rejects duplicate keys. These scores are a separate protocol and must not be pooled with the old main scores.

The gate is undecided until all 96 responses have been collected and their provenance verified. Both checkpoints must achieve:

- At least 7/8 correct text extractions.
- At least 7/8 correct copy-solution responses.
- At least 4/8 correct text-update final maps, including at least 1/2 in every difficulty cell.

These are practical feasibility thresholds. They do not provide a power calculation or guarantee improved accuracy. Diagram accuracy has no required minimum or direction.

If either checkpoint fails, report both complete pilots and defer confirmation. A later intervention requires a separately labelled, prospectively specified protocol. If both pass, define fresh held-out tasks and the confirmation sample size before further collection.

## Verification before publication

- All 50 local tests passed, including fourteen new diagnostic/recovery tests using provider stubs in temporary directories.
- Repository lint and whitespace checks passed.
- All 21 protected completed-study source hashes still match `FREEZE.json`.
- Pilot checks passed for all eight independent simulator truths, 16 RGB images, 48 requests per model, reference overlap, difficulty allocation, and the recorded visual inspection.

Provider stubs test infrastructure. They are not model responses or accuracy evidence. No GPU inference was used for implementation validation.
