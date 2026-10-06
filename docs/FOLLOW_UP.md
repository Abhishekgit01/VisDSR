# Follow-up proposal: reading, DSU updates, and response format

**Status: proposed future work, 6 October 2026.** Motivated by the completed [main study](../MAIN_RESULTS.md), this proposal describes a diagnostic pilot and requirements for later confirmation. It has not been implemented or run. Exact prompts, schemas, and confirmation sample size still require a separate frozen protocol.

## Motivation

The completed study found:

- Strict schema failures affected 138/400 Qwen responses and 281/400 InternVL responses.
- Among schema-valid structured responses, Qwen transcribed text correctly in 30/30 cases and diagrams correctly in 0/56. InternVL transcribed text correctly in 21/21; none of its diagram-transcription outputs passed the schema. These conditional rates exclude invalid responses.
- All seven correct final maps occurred on one-operation tasks. Neither model produced a correct final map on a four-operation task.

These observations motivate separate controls; they do not establish an internal mechanism or modality effect.

**Research question:** when the response contract and task are controlled, which difficulties remain in reading the initial forest, applying DSU rules to a correct supplied state, and returning a valid answer?

## Matched controls

Each checkpoint receives all six requests for every pilot forest. Every request starts a new conversation; no model answer is passed to another condition.

| Request | Supplied information | Required answer | Purpose |
| --- | --- | --- | --- |
| Extract text | Canonical initial parent map; no operations | Initial map in `transcription` | Text-copying and extraction control |
| Extract rendered text | PNG of that exact canonical string; no operations | The same transcription schema | Reading the map as pixels |
| Extract diagram | Forest diagram; no operations | The same transcription schema | Reading child-to-parent relationships |
| Update from text | Correct initial map and the operation sequence | Full map after each operation and each find result | DSU updates with a supplied correct state |
| Update from diagram | The same forest as a diagram and the same operations | The same step schema | Matched end-to-end diagram performance |
| Copy solution | Simulator-supplied correct step objects, explicitly identified as an answer to copy | The same step schema, with no extra text | Serialization and instruction-following control |

Copy-solution intentionally supplies the answer and measures compliance. Its expected response length matches the update conditions, although prompt length differs. Subtracting its accuracy from another condition would not estimate an independent formatting effect.

Extraction requests contain neither operations nor a solution. Update requests contain no solution or model-generated transcription. Check simulator answers against the independent Python reference.

Require bare JSON, exact keys, every node label, and the existing step fields: `op`, `state`, and `find_result` for finds. Extraction correctness requires the complete initial map; copy correctness requires every step and find result. For updates, final-map exact match is primary and full-sequence correctness is secondary. Invalid responses count as incorrect; do not repair answers or retry for content.

## Fixed diagnostic pilot

Use **eight fresh forests**, with two tasks in each cell of 8/16 elements and one/four operations. The one-operation cells each contain one path-compressing find and one meaningful union. Four-operation tasks contain both kinds of operation; the panel must include an equal-size union tie. Preserve the existing DSU rules, full-map answer requirement, and clean rendering conventions.

Generate reachable states from valid union preludes. Reject duplicate initial maps within the panel and overlap with completed tasks by comparing the initial map plus operation sequence, regardless of task ID or prelude history. Record task/image hashes and the overlap check before inference. Proposed generation seed: `2026100603`; the panel still needs validation. New labels alone do not establish new graph structures.

The six requests give **48 calls per checkpoint, 96 total** for the two revisions pinned in the main report. Retain NF4 quantization, greedy decoding, and the 2,048-token cap. Save prompts, inputs, raw answers, token counts, cap hits, latency, environment details, and scores. Randomize request order with seed `2026100604`. Review one task from every difficulty cell manually before collection.

### Gate before confirmation

Complete this single fixed pilot for both checkpoints. For each checkpoint, require:

1. At least **7/8 strictly correct text extractions**.
2. At least **7/8 strictly correct copy-solution responses**.
3. At least **4/8 strictly correct update-from-text final maps**, including **at least 1/2 in every difficulty cell**.
4. Complete provenance and successful simulator, image, schema, and caching checks.

These are proposed practical thresholds, not significance tests or validated power estimates. Requiring success in every cell prevents passing solely on one-operation tasks. Eight forests cannot guarantee that a fresh collection avoids the accuracy floor.

If either checkpoint fails, report both complete pilots and defer confirmation. Do not search prompts until the gate passes. An integration bug requires a documented fix and separately identified replacement run. Later model, task, or prompt changes require another labelled proposal.

There is no minimum diagram accuracy or required direction of the text-diagram difference for passing this gate.

## Confirmation and analysis

If the gate passes, use new held-out tasks for the matched update conditions. First freeze the generator, seeds, difficulty allocation, model settings, prompts, schemas, scoring, stopping rules, and source hashes in a separate protocol and cache namespace.

Choose sample size through prospective simulation of the exact paired test. Specify the smallest practical effect, discordant-pair assumptions, desired power, multiplicity adjustment, and compute budget. Evaluate several discordance assumptions; the completed study's near-zero estimates do not prove adequate power. This calculation and final sample size remain open.

The paired unit is the forest/task. The primary comparison is **update-from-text minus update-from-diagram** in final-map exact match, including invalid answers as incorrect. Use exact McNemar tests with Holm adjustment across the two checkpoints. Difficulty summaries and full-sequence correctness are secondary.

Report pilot extraction, copying, and update correctness, schema failures, and cap hits with full denominators. Correctness among valid outputs is an additional conditional measure. Cap hits and schema failures may overlap; six presentations of one forest are not six independent tasks. Treat the eight-forest pilot as descriptive.

## What this could establish

Extraction contrasts could reveal difficulties producing maps from text or pixels. Updates compare a supplied correct text state with the matched diagram. Copying could reveal failures when calculation is unnecessary.

Findings remain specific to these checkpoints, settings, prompts, and synthetic forests. Different response contracts and prompt lengths prevent additive error decomposition. Successful copying does not prove DSU understanding; these controls do not reveal internal reasoning.
