# Main-study decision

Reviewed on 4 October 2026, after all 120 calibration responses were collected. This records the decision before generating or querying the main tasks.

## Decision

Proceed with the planned 80-task, five-condition, two-model study under the existing protocol. Keep the primary comparison, prompts, model revisions, images, generation settings, and scoring fixed. Calibration and diagnostics remain separate from main results.

The user requested completion of the full study and approved the revised protocol. The complete calibration has now been audited. Further calibration rounds or prompt selection would introduce another selection step; the next collection uses the preselected main seed.

The main run will estimate performance and format reliability on fresh tasks from the stated generator. Low text accuracy limits the sensitivity and interpretation of the planned modality comparison. A positive effect, significant test, or nonzero diagram accuracy is not a completion requirement. Results must not claim modality equivalence, identify an internal failure mechanism, or generalize beyond these checkpoints, quantization, prompts, output limit, and synthetic task distribution.

## Reviewed evidence

Each condition has twelve responses per model. Invalid output counts as incorrect.

| Condition | Qwen final exact matches | Qwen format failures | InternVL final exact matches | InternVL format failures |
| --- | ---: | ---: | ---: | ---: |
| T-dir | 2/12 | 0/12 | 0/12 | 1/12 |
| R-dir | 0/12 | 2/12 | 0/12 | 5/12 |
| G-dir | 0/12 | 4/12 | 0/12 | 11/12 |
| T-str | 0/12 | 6/12 | 1/12 | 9/12 |
| G-str | 0/12 | 6/12 | 0/12 | 12/12 |
| Total | 2/60 | 18/60 | 1/60 | 38/60 |

All three correct final maps also have correct full sequences. All six valid Qwen T-str transcriptions are correct; all six valid Qwen G-str transcriptions are wrong. All three valid InternVL T-str transcriptions are correct. These observations describe outputs and cannot establish their internal causes.

The combined backup is `visdsr_v2_results (7).zip`, SHA-256 `40569d0fb6fb3eea7c626474587a1488f8bf5f6ffb296c543fd3e4cdfde486ee`. All 164 payload checksums, 21 study source hashes, 120 exact cached requests, strict score tables, independent task answers, and 24 source image hashes passed review. Earlier responses are unchanged. The backup contains no main tasks or freeze record.

## Output and runtime limits

Nine Qwen responses and seven InternVL responses reached the 2,048-token output cap. Output length is therefore a demonstrated limitation. Keep the preselected limit and report cap exhaustion separately; official accuracy measures success under this bounded JSON-output protocol. It does not measure unrestricted DSU reasoning ability. No retry, preamble removal, answer repair, or exclusion of invalid responses is permitted.

| Model | Mean calibration latency | Estimate for 400 main calls | Largest per-device allocated peak |
| --- | ---: | ---: | ---: |
| Qwen3-VL-8B-Instruct | 115.66 s | 12.85 h | 5.24 GiB |
| InternVL3.5-8B-HF | 92.20 s | 10.24 h | 7.43 GiB |

The combined estimate is 23.10 hours of inference, excluding loading, validation, export, interruptions, and waiting for free GPU allocation. It extrapolates from a balanced calibration with the same difficulty cells; actual main duration is unknown.

Collect at most 100 new calls per execution. At the measured averages, a complete chunk would take about 3.21 hours for Qwen or 2.56 hours for InternVL, excluding setup. This gives four chunks per model. Use a smaller limit when the available session time is shorter. Every completed call is cached immediately, and each completed or normally interrupted chunk exports automatically. Download each backup outside Kaggle before relying on a later session.

The remaining GPU expenditure supports an independent estimate on the preselected task distribution, with twenty tasks per difficulty cell. Floor accuracy may persist. The larger dataset can estimate low success and format-failure rates more precisely, while the planned paired comparison must retain the interpretation limits above.

## Freeze and completion

The freeze audits both complete calibrations and records their summaries, the exact calibration task hash, and all protected study source hashes. Main generation must verify that freeze and reject calibration overlap. Run one model at a time on a free Kaggle GPU.

Completion requires all 800 unique main responses, recomputed official scores, paired analysis with its boundary limitations, a report, figures, and a released artifact sufficient to reproduce the numerical results. If execution stops early, document the achieved counts and the stopped stage. Calibration completion alone is not completion of the main study.
