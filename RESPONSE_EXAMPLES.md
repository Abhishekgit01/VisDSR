# Three scored response examples

These examples use the original released responses for one shared main task, `main_0004`. They illustrate a correct response, a valid but incorrect response, and a schema failure. The response blocks below are complete, verbatim model outputs.

Selection was made after collection for explanation: `main_0004` is the first task by ID with a fully correct main response. We chose its Qwen T-str success, Qwen T-dir state error, and InternVL G-str schema failure. These examples are not a representative sample or an additional statistical comparison. Aggregate results and interpretation limits are in [MAIN_RESULTS.md](MAIN_RESULTS.md).

## Shared task and expected answer

The eight-element task has one operation: `find(H)`. Its initial parent map is:

```json
{"A":"C","B":"C","C":"C","D":"F","E":"E","F":"E","G":"E","H":"B"}
```

`find(H)` follows `H → B → C`, returns `C`, and compresses the visited path. Only `H` needs a changed parent because `B` already points directly to `C`. The separate `D → F → E` path is untouched. The expected state is:

```json
{"A":"C","B":"C","C":"C","D":"F","E":"E","F":"E","G":"E","H":"C"}
```

The task truth was replayed against the independent Python reference. The two text conditions receive this initial map; G-str receives the original forest diagram for the same map. T-str and G-str additionally require an initial-map transcription.

| Example | Model / condition | Format error | Final map correct | Full sequence correct | First error step |
| --- | --- | ---: | ---: | ---: | --- |
| 1 | Qwen3-VL-8B / T-str | 0 | 1 | 1 | None |
| 2 | Qwen3-VL-8B / T-dir | 0 | 0 | 0 | 1 |
| 3 | InternVL3.5-8B / G-str | 1 | 0 | 0 | 1, assigned for invalid output |

## 1. Correct transcription and path compression

Qwen's complete T-str response:

```json
{"transcription":{"A":"C","B":"C","C":"C","D":"F","E":"E","F":"E","G":"E","H":"B"},"steps":[{"op":1,"state":{"A":"C","B":"C","C":"C","D":"F","E":"E","F":"E","G":"E","H":"C"},"find_result":"C"}]}
```

The transcription exactly matches the initial state, including `H → B`. The reported state changes that pointer to `H → C`, and `find_result` is `C`. All fields satisfy the T-str schema. The scorer returns `transcription_correct=1`, `per_step_accuracy=1.0`, and `failure_type="correct"`.

This is evidence of a correct answer on this task. It does not establish a general benefit from transcription; the full paired comparison is reported separately.

## 2. Correct returned root, incorrect parent state

Qwen's complete T-dir response:

```json
{"steps":[{"op":1,"state":{"A":"C","B":"C","C":"C","D":"F","E":"E","F":"E","G":"E","H":"B"},"find_result":"C"}]}
```

This response passes the schema and returns the correct root. Its reported parent map retains the initial `H → B` pointer, so it fails the required path-compression update:

| Checked value | Expected | Reported |
| --- | --- | --- |
| Parent of `H` after `find(H)` | `C` | `B` |
| Returned root | `C` | `C` |
| Other seven parent entries | Original values | Original values |

Final-map correctness uses exact equality. One wrong parent makes `final_correct=0`; the incorrect state also gives `per_step_accuracy=0.0`, `full_sequence_correct=0`, and `failure_type="state_transition_failure"`. The error is observable in the output; it does not reveal the model's internal reasoning.

## 3. Valid JSON, invalid response schema

InternVL's complete G-str response:

```json
{"parent_map":{"A":"A","B":"B","C":"C","D":"D","E":"E","F":"F","G":"G","H":"H"},"steps":[{"op":1,"state":{"A":"A","B":"B","C":"C","D":"D","E":"E","F":"F","G":"G","H":"H"},"find_result":"H"}]}
```

G-str requires exactly the top-level fields `transcription` and `steps`. The response uses `parent_map` in place of `transcription`. JSON decoding succeeds, but the frozen validator rejects the top-level schema with:

```text
top-level fields do not match the condition
```

The scorer records `format_error=1`, `failure_type="format_error"`, and zero correctness scores. State comparison is not reached. Its `first_error_step=1` is the scorer's assigned value for invalid output, rather than a measured first state-transition error. This response did not hit the output cap, so the observed schema failure is present in a completed output.

## Locate and recompute the examples

Download and restore the [audited main-results release](https://github.com/Abhishekgit01/VisDSR/releases/tag/v2.0-results) using [REPRODUCE_MAIN.md](REPRODUCE_MAIN.md). The original records are at these locations in that archive:

| Example | Raw JSONL file | Line, starting at 1 |
| --- | --- | ---: |
| 1 | `results/raw/main_model1.jsonl` | 20 |
| 2 | `results/raw/main_model1.jsonl` | 249 |
| 3 | `results/raw/main_model2.jsonl` | 183 |

Their matching cache files are:

- Example 1: `results/cache/d8644e521e905d299f89eb3db67d28aeb868f31b21f412a91ba09c084c90ee01.json`.
- Example 2: `results/cache/35f4d046e73dc0c291952659aafdf9663066fcd55fbd3c9f961b279796f76554.json`.
- Example 3: `results/cache/85e79a01c14d07c4aae52406584831232c0bd510e15aff507f2326c73878d660.json`.

After restoration, run this from the checkout root to recompute the three scores without inference:

```python
import json
from pathlib import Path

from eval.score import score

tasks = [json.loads(line) for line in Path("data/main/tasks.jsonl").read_text().splitlines()]
task = next(task for task in tasks if task["id"] == "main_0004")
cases = [("model1", "T-str"), ("model1", "T-dir"), ("model2", "G-str")]
fields = ("format_error", "final_correct", "full_sequence_correct", "first_error_step", "failure_type")
for model, condition in cases:
    path = Path(f"results/raw/main_{model}.jsonl")
    records = [json.loads(line) for line in path.read_text().splitlines()]
    matches = [record for record in records if record["task_id"] == task["id"] and record["condition"] == condition]
    if len(matches) != 1:
        raise ValueError(f"Expected one original response for {model}/{condition}")
    result = score(task, condition, matches[0]["raw_text"])
    print(model, condition, {field: result[field] for field in fields})
```

Each illustrated score was recomputed with the frozen scorer, checked against the released CSV row, and matched to its original cache and raw record. None of these three outputs reached the generation cap. The examples describe recorded behavior under the study's exact-output rules; the main report supplies the frequency estimates and statistical limits.
