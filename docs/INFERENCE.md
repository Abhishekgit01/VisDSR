# Inference replication and local generation

The official study is complete: 400 Qwen and 400 InternVL main responses, plus 60 calibration responses per model. To reproduce those scores, use the [cached reproduction guide](../REPRODUCE_MAIN.md); it requires no model weights or GPU.

The procedures below are retained for a separate inference replication or infrastructure check. Re-running weights can produce different text across hardware and software environments. Keep replication outputs in a separate checkout and preserve the original released inputs.

## Kaggle notebooks

| Notebook | Purpose |
| --- | --- |
| [Qwen v2](../notebooks/qwen3_vl_v2_kaggle.ipynb) | Three-call smoke, bounded calibration, and selected main stage |
| [InternVL v2](../notebooks/internvl35_v2_kaggle.ipynb) | Three-call smoke and bounded calibration |
| [InternVL main](../notebooks/internvl35_main_kaggle.ipynb) | Main collection after Qwen completes, in batches of at most 100 new calls |

For a new smoke and calibration replication:

1. Download the Qwen v2 notebook from `main` and import it into Kaggle. Enable a GPU and Internet.
2. Keep `STAGE = "smoke"` and the review flags false. Run the cells from top to bottom. The default makes only three calls: T-dir, R-dir, and G-dir on the same four-operation calibration task.
3. Download `visdsr_v2_results.zip` from the Output panel. Review the raw answers, strict parsing, correctness, tokens, memory, and latency before selecting calibration.
4. After review, calibration runs at most 20 new responses per execution and reuses the smoke cache. Download each updated export. Attach the newest export as a private Dataset when resuming or starting InternVL.

The v2 project folder is `/kaggle/working/VisDSR_v2`. Backups check source fingerprints, calibration task bytes, and payload checksums. Earlier v1 exports are incompatible. Both a ZIP and Kaggle's extracted Dataset layout are supported. Exports omit the redundant nested cache ZIP that caused earlier upload problems.

## Main inference runner

After restoring the completed calibration, use the standalone [main runner](../notebooks/kaggle_main.py) from the project directory:

```bash
python -m notebooks.kaggle_main --model model1 --max-new-calls 100
```

It verifies the freeze and both calibration sets, generates and validates main inputs when missing, and makes at most 100 new Qwen calls. Rerunning resumes matching caches; use `model2` for InternVL after Qwen completes. One model runs at a time. Smaller chunks are supported. Each chunk exports automatically, including after a normal interruption.

The InternVL main notebook restores both calibrations and the main inputs, verifies the freeze and original images, and collects only missing InternVL responses. Completed Qwen responses are reused unchanged. With the complete released backup, all matching calls are already cached and no further inference is needed.

## Save progress outside the runtime

Every completed response is cached immediately; each bounded run also exports automatically. Download the new backup before continuing or ending a session. A lost runtime can still lose files that have not been saved outside that session.

For a background run, use **Save Version > Save & Run All** and download the saved version's output. An exported ZIP on an interactive runtime's temporary disk is not a durable backup. When resuming after a reset, attach the newest downloaded export and run notebook setup before the selected-stage cell; old Python variables do not survive the reset.

## Check task generation locally

Requires Python 3.11+, a C++17 compiler, Graphviz, and DejaVu fonts. Use a separate checkout so existing local data stays intact:

```bash
python -m pip install -r environment/requirements.txt
make build
python -m gen.generate --split pilot2
python -m gen.render --split pilot2
python -m gen.validate --split pilot2
python -m gen.render --split pilot2 --qa
python -m eval.run --split pilot2 --model mock --max-new-calls 20
```

The mock oracle checks caching and scoring without model inference; it supplies no study evidence. Image validation checks replayed truth, dimensions, geometry, pixels, filenames, and hashes. Main generation requires the reviewed freeze.

Numerical reproduction uses the original released PNG bytes. Local Graphviz versions can render different pixels, so these generation checks do not establish byte-for-byte reproduction of the original images. See the [rendering limits in the main report](../MAIN_RESULTS.md).
