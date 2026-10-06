"""Paired improvement counts and a separately labelled model-plus-executor result."""
from __future__ import annotations

import csv
import io
import json

from diagnostics.protocol import evaluate, write_json
from interventions.executor import execute
from interventions.protocol import RESULTS, PROTOCOL_ID
from interventions.run import records
from visdsr import canonical


def score() -> dict:
    base, added = records()
    rows, assisted = [], []
    for item in base + added:
        if item["record"] is None:
            continue
        case, task = item["case"], item["task"]
        raw = item["record"]["response"]["raw_text"]
        if case["control"].startswith("update_"):
            result = evaluate(task, case, raw)
            rows.append({"model": item["model"]["name"], "task_id": task["id"],
                         "condition": case["control"], "arm": case.get("arm", "baseline"),
                         "elements": task["n"], "operations": len(task["operations"]), **result,
                         "latency_s": item["record"]["response"]["latency_s"],
                         "cap_hit": item["record"]["response"]["hit_output_cap"]})
        if case["control"].startswith("extract_"):
            extraction = evaluate(task, case, raw)
            result = {"valid": False, "correct": False, "final_correct": False,
                      "full_sequence_correct": False, "error": "invalid extraction response"}
            predicted_answer = None
            if extraction["valid"]:
                try:
                    predicted = json.loads(raw)["transcription"]
                    predicted_answer = execute(predicted, list(task["initial"]), task["operations"])
                    update = {**case, "control": "update_text"}
                    result = evaluate(task, update, canonical(predicted_answer))
                except ValueError as exc:
                    result["error"] = str(exc)
            assisted.append({"model": item["model"]["name"], "task_id": task["id"],
                             "input": case["control"], "extraction_correct": extraction["correct"],
                             "executor_answer": predicted_answer, **result})
    count = sum(item["record"] is not None for item in base + added)
    summary = {"protocol_id": PROTOCOL_ID, "saved": count, "planned": 192,
               "complete": count == 192, "comparisons": [], "assisted": []}
    for model in ("model1", "model2"):
        for condition in ("update_text", "update_diagram"):
            selected = [row for row in rows if row["model"] == model and row["condition"] == condition]
            baseline = {row["task_id"]: row for row in selected if row["arm"] == "baseline"}
            for arm in ("baseline", "grammar", "procedure", "combined"):
                values = [row for row in selected if row["arm"] == arm]
                pairs = [(baseline[row["task_id"]], row) for row in values if row["task_id"] in baseline]
                summary["comparisons"].append({"model": model, "condition": condition, "arm": arm,
                                               "saved": len(values), "planned": 8,
                                               "valid": sum(row["valid"] for row in values),
                                               "correct": sum(row["correct"] for row in values),
                                               "cap_hits": sum(row["cap_hit"] for row in values),
                                               "paired": len(pairs),
                                               "corrected": sum(not a["correct"] and b["correct"] for a, b in pairs),
                                               "lost": sum(a["correct"] and not b["correct"] for a, b in pairs)})
        for control in ("extract_text", "extract_rendered", "extract_diagram"):
            values = [row for row in assisted if row["model"] == model and row["input"] == control]
            summary["assisted"].append({"model": model, "input": control, "saved": len(values),
                                        "extraction_correct": sum(row["extraction_correct"] for row in values),
                                        "final_correct": sum(row["final_correct"] for row in values),
                                        "sequence_correct": sum(row["full_sequence_correct"] for row in values)})
    RESULTS.mkdir(parents=True, exist_ok=True)
    write_json(RESULTS / "summary.json", summary)
    write_json(RESULTS / "assisted.json", assisted)
    write_csv(rows)
    write_markdown(summary)
    return summary


def write_csv(rows: list[dict]) -> None:
    fields = ("model", "task_id", "condition", "arm", "elements", "operations", "valid", "correct",
              "final_correct", "full_sequence_correct", "changed_parent_accuracy", "error", "latency_s", "cap_hit")
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=fields)
    writer.writeheader()
    writer.writerows(sorted(rows, key=lambda row: (row["model"], row["task_id"], row["condition"], row["arm"])))
    temporary = RESULTS / "scores.csv.tmp"
    temporary.write_text(stream.getvalue())
    temporary.replace(RESULTS / "scores.csv")


def write_markdown(summary: dict) -> None:
    lines = ["# DSU improvement comparison", "", f"**Saved {summary['saved']}/192; complete={summary['complete']}.**", "",
             "| Model | Input | Arm | Saved/8 | Valid | Exact final map | Corrected vs baseline | Lost vs baseline |",
             "| --- | --- | --- | --- | --- | --- | --- | --- |"]
    for row in summary["comparisons"]:
        lines.append(f"| {row['model']} | {row['condition']} | {row['arm']} | {row['saved']}/8 | {row['valid']} | "
                     f"{row['correct']} | {row['corrected']} | {row['lost']} |")
    lines.extend(["", "## Model plus verified executor (separate system baseline)", "",
                  "Uses the model's actual extraction, without gold correction or new inference.", "",
                  "| Model | Extraction input | Saved/8 | Exact extraction | Exact final map | Full sequence |",
                  "| --- | --- | --- | --- | --- | --- |"])
    for row in summary["assisted"]:
        lines.append(f"| {row['model']} | {row['input']} | {row['saved']}/8 | {row['extraction_correct']} | "
                     f"{row['final_correct']} | {row['sequence_correct']} |")
    lines.extend(["", "## Limits", "", "This is an exploratory development comparison on eight forests. "
                  "It does not establish held-out improvement or revise the diagnostic gate. "
                  "All arms retain the same model revisions, NF4 precision, greedy decoding and 2,048-token cap. "
                  "The grammar fixes JSON field order and compact serialization while permitting every parent value. "
                  "Invalid outputs count as incorrect. Inspect scores.csv for all four difficulty cells; "
                  "results may improve, remain unchanged, or worsen. No content retries or answer repairs were used.", ""])
    temporary = RESULTS / "REPORT.md.tmp"
    temporary.write_text("\n".join(lines))
    temporary.replace(RESULTS / "REPORT.md")
