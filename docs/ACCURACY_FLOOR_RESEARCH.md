# Investigating the VisDSR accuracy floor

**Research review, 7 October 2026.** This document combines an exploratory audit of the completed main responses with primary literature and official model documentation. The proposed interventions have not been implemented or evaluated. The [published main results](../MAIN_RESULTS.md) remain the record of the frozen experiment.

**Implementation update:** the [fixed diagnostic pilot](DIAGNOSTICS.md) is now prepared and locally validated. GPU collection is pending; the accuracy interventions discussed below have not been evaluated.

## Recommendation

Start with separate extraction, calculation, and serialization controls. Then evaluate a small, prospectively specified comparison of procedural instructions and constrained JSON generation. Retain the original element counts, operation counts, DSU rules, full parent maps, and exact-match outcome. Investigate native reasoning modes as a separate experiment if calculation remains weak.

The strongest engineering alternative is to extract the forest with a vision-language model and execute the operations with a fixed DSU implementation. That would measure a model-plus-executor system and should receive its own results and claim.

## What the existing responses establish

The audit matched all 800 original main responses to their official task-condition score rows. Parsing and final-map correctness agree with every row. It reused the frozen parser, including its allowance for a complete JSON code fence. Additional metrics are descriptive and were computed after collection; five presentations share each of 80 tasks.

| Observation | Qwen | InternVL |
| --- | ---: | ---: |
| Exact final maps, all responses | 3/400 | 4/400 |
| Schema-valid responses | 262/400 | 119/400 |
| Exact final maps among valid responses | 3/262, 1.15% | 4/119, 3.36% |
| Invalid JSON | 103/400 | 43/400 |
| JSON that fails the task schema | 35/400 | 238/400 |
| Valid final maps identical to the initial map | 114/262 | 70/119 |
| Output-cap hits | 62/400 | 41/400 |
| Mean correctness on parents that should change, invalid responses scored zero | 3.38% | 2.88% |

All cap-hit responses failed validation. Cap hits overlap the two formatting categories above. Their counts must not be added as another set of failures.

Formatting is a substantial problem, especially InternVL's schema compliance. Calculation also deserves attention: many valid answers preserve the initial map, and exact correctness remains low within the valid subset. Conditioning on validity selects different responses; these rates do **not** estimate the accuracy a grammar intervention would produce.

Returning the initial map without performing any operation obtains **79.375% mean per-parent correctness** on these tasks while obtaining **zero complete final maps**. Most parent entries remain unchanged. Keep final-map exact match primary and report changed-parent correctness as an additional diagnostic.

For each response, changed-parent correctness is the fraction correct among labels whose true final parent differs from its initial parent. Average those fractions over all 400 responses per model, assigning invalid responses zero. This uses the simulator answer for evaluation only. [Aggregate audit and source hashes](accuracy_floor_cache_analysis.json) record the calculations and inputs.

The released Qwen diagnostics on the single forest `pilot2_0004` also matter: text and rendered-text extraction passed; diagram extraction, roots/sizes, text find, and text union failed. Two image-based find responses reached the output cap. This is evidence from one forest and cannot supply population rates or identify an internal cause.

## Research findings and their application

### 1. Test extraction and updates independently

[VGCure](https://aclanthology.org/2025.acl-long.1482/) examines 22 visual graph tasks across 14 models and reports weaknesses in relational and structurally complex graph understanding. [ProcVQA](https://aclanthology.org/2025.findings-emnlp.1266/) separately evaluates visual extraction and question answering, finding that extraction success does not ensure reasoning success and that structural density affects errors. These results motivate decomposition; neither paper predicts a DSU accuracy gain for our checkpoints.

Use the six requests already described in [the diagnostic proposal](FOLLOW_UP.md): extract text, extract rendered text, extract diagram, update from a correct text state, update from diagram, and copy the simulator solution. Every request starts independently. Copying deliberately supplies the solution and measures response compliance.

Interpret these controls jointly:

- Good copying with poor updates motivates calculation interventions.
- Poor copying motivates inspection of response length, schema, and generation behavior.
- Good text extraction with poor diagram extraction motivates visual presentation checks.
- Good extraction with poor updates motivates procedural execution checks.

Different prompts and output lengths prevent treating these as an additive decomposition of errors.

### 2. Constrain the answer structure during generation

[JSONSchemaBench](https://arxiv.org/abs/2501.10868) evaluates efficiency, schema coverage, and answer quality. Its [initial study](https://arxiv.org/html/2501.10868v1) documents both overly restrictive and overly permissive grammar implementations. Its tested versions and tasks do not establish how a current engine will behave on VisDSR. Separately, [Tam et al.](https://aclanthology.org/2024.emnlp-industry.91/) found reasoning degradation under format restrictions in their experiments. Together these findings support measuring structural compliance and semantic accuracy independently.

For a new run, compile the input-dependent response contract:

- Exactly the permitted top-level keys.
- Exactly one step per supplied operation and the correct operation index.
- Every node label exactly once in each parent map.
- Parent and find-result values drawn from the task labels.
- `find_result` required for finds and absent for unions.

All possible parent assignments remain available. The grammar must not encode the simulator's correct roots, parent values, or intermediate states. Incorrect assignments remain incorrect under the same exact-match scoring.

[XGrammar's official Transformers adapter](https://github.com/mlc-ai/xgrammar/blob/main/python/xgrammar/contrib/hf.py) provides a logits processor for `model.generate()`. It requires a fresh processor per call and notes possible overhead. This offers a path compatible with the existing style of provider; compatibility with our pinned Transformers version, multimodal classes, tokenizer vocabulary, and quantized weights still requires testing.

Before inference, test schema acceptance and rejection, step length, operation-specific fields, missing/extra labels, tokenizer handling, and completion behavior. A token cap can still interrupt a structurally valid prefix. Keep an unconstrained comparison and record grammar-engine version, latency, token count, and cap hits.

### 3. Supply the precise execution procedure

The frozen prompt **already contains two worked examples**. Adding generic examples or another sentence requesting careful reasoning is a weakly targeted intervention.

[Least-to-most prompting](https://arxiv.org/abs/2205.10625) studies solving simpler subproblems sequentially on symbolic and compositional tasks. [Scratchpad research](https://arxiv.org/abs/2112.00114) studies intermediate computation for tasks including program execution. These motivate a procedural ablation; their results do not establish that a prompt alone will fix our models.

Specify the actual DSU procedure:

1. Follow the operand's parent chain to a self-parented root.
2. Save that root, then compress only the traversed path.
3. For union, run this procedure for `a`, then for `b` on the updated state.
4. Count all members of the two sets by read-only root traversal. Counting must not introduce additional path compression.
5. Attach the smaller root under the larger root; on a tie attach `b`'s root under `a`'s root.
6. If both roots are equal, retain any compression already performed and skip the merge.
7. Carry the resulting map to the next operation and emit every parent entry.

These instructions supply an algorithm, not the task's computed answer. For a trace-producing arm, define its fields and parser before collection. For a multi-call execution arm, carry the model's own predicted state forward, count every call, and report error propagation. Supplying gold intermediate states would define an assisted control.

### 4. Evaluate documented reasoning modes and output budgets

[Qwen3-VL](https://github.com/QwenLM/Qwen3-VL) releases separate Instruct and Thinking checkpoints. The completed study used Instruct; enabling a flag does not turn those weights into the [8B Thinking checkpoint](https://huggingface.co/Qwen/Qwen3-VL-8B-Thinking). The project's current benchmark settings also differ from our greedy, 2,048-token protocol. Those differences justify controlled evaluation, rather than an attribution of our failures to decoding alone.

[InternVL's official 8B-HF documentation](https://huggingface.co/OpenGVLab/InternVL3_5-8B-HF#thinking-mode) enables thinking through a particular system prompt and recommends sampling with temperature 0.6 to limit repetition. That protocol produces a thinking section before the answer and conflicts with the frozen JSON-only instruction. Its documentation reports using test-time scaling on reasoning benchmarks, with no significant benefit on perception benchmarks in that evaluation.

For a separate reasoning experiment:

- Pin the new Qwen checkpoint and the exact InternVL mode instructions.
- Define one final-answer boundary and parser prospectively; retain the full raw output.
- Use a bounded reasoning-plus-answer budget, initially a proposed 4,096 tokens, and measure whether it is adequate. Compare the baseline at the same cap to investigate the effect of increasing the budget.
- Record sampling parameters and seeds; use one answer per request in the initial comparison.
- Separate a budget comparison from a checkpoint/mode comparison. Changing weights, instructions, sampling, and token limits together evaluates a package of changes.

Neither observed truncation nor successful reasoning on unrelated benchmarks establishes that a larger token budget will improve DSU exact match. Multi-sample selection would add compute and a selection procedure and needs a separate evaluation.

### 5. Improve presentation when extraction is the limiting observation

The renderer creates 1,024-pixel RGB images with geometry checks. Those checks do not demonstrate that a processor preserves legible labels and arrowheads. Inspect effective resize/tiling settings and representative processed inputs, and manually check root interpretation and child-to-parent direction.

Test one fixed presentation change at a time, such as larger labels, clearer arrowheads, or a different layout, on the same forests. Record it as a presentation ablation. Supplying a correct parent table alongside a diagram creates an additional-information condition.

[GraCoRe](https://aclanthology.org/2025.coling-main.531/) reports sensitivity to node ordering in textual graph tasks and finds that greater context capacity alone need not improve graph comprehension. This supports recording encoding and ordering, while leaving a diagram-layout benefit as an empirical question for VisDSR.

### 6. Add a model-plus-executor baseline

[PAL](https://arxiv.org/abs/2211.10435) uses language models to interpret problems and offloads execution to a program runtime. An adaptation for VisDSR is:

**Image → predicted parent map → forest validation → fixed DSU executor → complete state sequence.**

Validate labels and values, reject cycles other than self-parented roots, and derive component sizes from the predicted forest. Execute the supplied operations with the existing verified algorithm through an adapter that accepts a parent map. The current simulator input reconstructs states from union preludes, so this adapter requires implementation and verification.

Pass only the model's predicted map to that executor. Do not replace it with the true initial map or select a transcription using the answer. Report extraction accuracy and end-to-end exact match separately. Correct extraction plus a verified executor should yield correct updates by construction; incorrect extraction can still produce failures. Report this as assisted execution alongside the model-only baseline.

### 7. Reserve precision changes and training for later

[Liu et al.](https://aclanthology.org/2024.lrec-main.461/) examine quantized models' instruction following and reasoning. Their results retain such abilities in four-bit models and show larger degradation at two bits. This is insufficient evidence to blame our NF4 configuration for the observed floor.

A small paired eight-bit comparison could test precision sensitivity if memory permits. Preserve checkpoint, prompt, inputs, and decoding. A roughly eight-billion-parameter model requires about 16 GB for 16-bit weights alone, before cache and runtime memory, exceeding a single T4's reported 14.56 GiB. Two GPUs require actual sharding and memory verification.

VGCure's structure-aware training results also motivate a longer-term supervised adaptation study. It would need new training/development/test partitions separated by graph structure, followed by evaluation against the original unadapted checkpoints. The completed main tasks should remain evaluation evidence.

## Bounded execution plan

### First: implement the existing diagnostic pilot

Freeze the exact prompts, schemas, sources, and cache namespace, then validate eight fresh forests covering the existing four difficulty cells. Six controls × eight forests × two checkpoints gives **96 calls**. Preserve the [proposal's existing practical gates](FOLLOW_UP.md#gate-before-confirmation) and report the whole pilot if a gate fails. These thresholds are feasibility decisions, not statistical power guarantees.

### Second: a separately specified intervention comparison

If an intervention experiment is pursued, publish a new proposal before collecting its responses. A useful fixed design is:

| Arm | Procedural instructions | Constrained answer grammar |
| --- | --- | --- |
| A | Baseline update prompt | No |
| B | Baseline update prompt | Yes |
| C | Explicit DSU procedure | No |
| D | Explicit DSU procedure | Yes |

Apply all four arms to the same eight development forests in text and diagram conditions for both checkpoints: **128 update calls**. If Arm A's 32 calls are exactly identical to the diagnostic pilot's update calls, reuse them by verified input/prompt/settings hashes. The additional three arms require **96 calls**, giving **192 calls across diagnosis and intervention**. Without identical reusable calls, the total is 224.

This is an exploratory development panel. It does not amend the prior pilot's gates or authorize repeated prompt searches until a threshold is crossed. Freeze any chosen method before evaluation on a new held-out panel; choose confirmation size prospectively for the paired comparisons and compute budget. Retain failures, difficulty-cell summaries, invalid-output rates, cap hits, and actual compute costs. Make inference checkpoints downloadable after each bounded batch.

If grammar improves compliance while calculation remains weak, the next candidate is the separate native-reasoning experiment. If diagram extraction remains weak, investigate presentation or adaptation. A method can succeed as a system baseline while the unaided model study remains at the floor.

## Scope of this review

The cache audit ran without loading model weights or generating new answers. All interventions and call counts above are proposals. The research supports experiments with identifiable controls; it supplies no reliable percentage forecast for DSU accuracy or ACM selection.
