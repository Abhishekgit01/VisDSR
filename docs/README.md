# Documentation index

The current study is complete. Planning documents and earlier collection logs remain available as dated records; their original status statements describe those stages.

## Completed study

| Document | Read it for |
| --- | --- |
| [Main results](../MAIN_RESULTS.md) | Both models, paired analysis, verification, and limitations |
| [Scored response examples](../RESPONSE_EXAMPLES.md) | Three original answers and the exact scoring decisions on one shared task |
| [Reproduction guide](../REPRODUCE_MAIN.md) | Download, verify, restore, and reproduce the published scores without inference |
| [Results release](https://github.com/Abhishekgit01/VisDSR/releases/tag/v2.0-results) | Original inputs, raw responses, scores, figures, and audit |
| [Inference guide](INFERENCE.md) | Retained Kaggle notebooks, bounded runs, recovery, and local generation |
| [Algorithm and assistance record](../STUDENT_UNDERSTANDING.md) | DSU rules, condition controls, and implementation provenance |
| [Changelog](../CHANGELOG.md) | Project milestones through completion |
| [Citation](../CITATION.cff) | Software and results-release citation metadata |

## Proposed future work

[Reading, DSU updates, and response format](FOLLOW_UP.md) proposes six matched diagnostic requests, a fixed eight-forest pilot for both checkpoints, and a gate before a separate held-out confirmation study. It is a proposal, not an implemented or completed experiment.

## Preserved v2 planning and calibration

| Document | Role |
| --- | --- |
| [Study plan](../STUDY_V2.md) | Plan written before model calls; protected unchanged by the freeze |
| [Main decision](../MAIN_DECISION.md) | Calibration findings and rationale for the main collection |
| [Freeze record](../FREEZE.json) | Source and calibration hashes, model summaries, and recorded decision |
| [Smoke and calibration log](../V2_SMOKE.md) | Dated smoke, diagnostic, and calibration reviews |
| [Qwen collection review](../QWEN_MAIN_RESULTS.md) | The 5 October audit before the second model completed |

The [protocol-freeze release](https://github.com/Abhishekgit01/VisDSR/releases/tag/v2.0-frozen) includes `visdsr-calibration.zip`: twelve tasks, 24 original images, 120 official raw caches, smoke outputs, and separate diagnostics. Its SHA-256 is:

```text
40569d0fb6fb3eea7c626474587a1488f8bf5f6ffb296c543fd3e4cdfde486ee
```

The completed main release also contains those calibration records. The [reproduction guide](../REPRODUCE_MAIN.md) provides their score-only replay commands. Calibration comparisons remain descriptive and separate from the main analysis.

## Historical v1 feasibility study

The v1 code is preserved at commit `bf81065`. Its [protocol](../SPEC.md) and [report](../REPORT.md) describe a separate study:

| Run | T-dir | R-dir | G-dir |
| --- | ---: | ---: | ---: |
| Qwen pilot 1, twelve four-operation tasks | 0/12 | 0/12 | 0/12 |
| Qwen pilot 2, twelve one/two-operation tasks | 1/12 | 0/12 | 0/12 |
| InternVL smoke, one task | 1/1 | 0/1 | 0/1 |

The Qwen text baseline was near zero. InternVL's image outputs began with reasoning text; the diagram response did not finish an answer. These runs did not establish whether diagrams help or hurt DSU reasoning. They motivated clearer output instructions and a representative calibration set for v2. Historical responses are not pooled with v2.

The old [Qwen notebook](../notebooks/visdsr_qwen3vl8b_kaggle.ipynb) and [InternVL smoke notebook](../notebooks/internvl35_visdsr.ipynb) belong to v1. Use the [inference guide](INFERENCE.md) for current notebooks.

Reviewed private archive SHA-256 checksums:

- First Qwen pilot: `a7a3eaa8b3d51f1d18ff57bc7bbba97735cdb077da5936bd751ec86e33974fa8`.
- Both Qwen pilots: `f40e0ce44178ef39fb1a87e7ff155d975c31ff270b0ca9ace74ab4390829726b`.
- InternVL smoke plus preserved Qwen data: `25ca9faf910ad1b6cd537dc2ead0993509cc4cf996c111c0fa963e5a76ecb71b`.

These v1 archives have not been released; checksums alone do not reproduce their numerical results. The public v2 releases contain the reviewed calibration and main reproduction artifacts.
