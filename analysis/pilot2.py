"""Report the final calibration round by length, with separate diagnostic repairs."""
from __future__ import annotations

import argparse
import csv
import json
import re
from collections import Counter

from eval.prompts import CONDITIONS
from eval.score import score
from eval.validate import FormatError, parse
from visdsr import ROOT, config, read_tasks


def response_object(raw: str) -> dict | None:
    value = raw.strip()
    fence = re.fullmatch(r"```(?:json)?\s*\n?(.*?)\n?```", value,
                         flags=re.DOTALL | re.IGNORECASE)
    if fence:
        value = fence.group(1).strip()
    try:
        answer = json.loads(value)
    except json.JSONDecodeError:
        return None
    return answer if isinstance(answer, dict) else None


def diagnostic_transcription(task: dict, raw: str) -> int | None:
    """Read an embedded JSON parent map independently of step validity."""
    answer = response_object(raw)
    if answer is None:
        return None
    transcription = answer.get("transcription")
    if isinstance(transcription, str):
        try:
            transcription = json.loads(transcription)
        except json.JSONDecodeError:
            return None
    return int(transcription == task["initial"]) if isinstance(transcription, dict) else None


def diagnostic(task: dict, condition: str, raw: str) -> tuple[list[str], dict | None]:
    """Try two narrow repairs for diagnosis; never change the official score."""
    answer = response_object(raw)
    if answer is None:
        return [], None
    changes = []
    if condition == "G-str" and isinstance(answer.get("transcription"), str):
        try:
            embedded = json.loads(answer["transcription"])
        except json.JSONDecodeError:
            embedded = None
        if isinstance(embedded, dict):
            answer["transcription"] = embedded
            changes.append("parsed JSON-string transcription")
    steps = answer.get("steps")
    if isinstance(steps, list) and len(steps) == len(task["operations"]):
        for operation, step in zip(task["operations"], steps, strict=True):
            extra_find = isinstance(step, dict) and set(step) == {"op", "state", "find_result"}
            if operation["kind"] == "union" and extra_find:
                del step["find_result"]
                if "removed union find_result" not in changes:
                    changes.append("removed union find_result")
    if not changes:
        return [], None
    repaired = json.dumps(answer)
    try:
        parse(repaired, task, condition)
    except FormatError:
        return changes, None
    return changes, score(task, condition, repaired)


def report(model: str) -> None:
    tasks = {task["id"]: task for task in read_tasks("pilot2")}
    if len(tasks) != 12:
        raise ValueError("pilot2 must contain 12 tasks")
    with (ROOT / "results" / f"scores_pilot2_{model}.csv").open(newline="") as source:
        rows = list(csv.DictReader(source))
    with (ROOT / "results/raw" / f"pilot2_{model}.jsonl").open() as source:
        records = [json.loads(line) for line in source if line.strip()]
    expected = {(task_id, condition) for task_id in tasks for condition in CONDITIONS}
    by_pair = {(row["task_id"], row["condition"]): row for row in rows}
    raw_by_pair = {(record["task_id"], record["condition"]): record for record in records}
    complete = len(rows) == 60 and len(records) == 60
    if not complete or set(by_pair) != expected or set(raw_by_pair) != expected:
        raise ValueError("pilot2 scores and raw responses must cover all 60 unique pairs")
    revisions = {record["revision"] for record in records}
    model_ids = {record["model_id"] for record in records}
    if len(revisions) != 1 or len(model_ids) != 1:
        raise ValueError("pilot2 records contain multiple model IDs or revisions")
    details = []
    for task_id, condition in sorted(expected):
        task = tasks[task_id]
        row = by_pair[(task_id, condition)]
        record = raw_by_pair[(task_id, condition)]
        if row["split"] != "pilot2" or record["split"] != "pilot2":
            raise ValueError("pilot2 report received a different split")
        if row["model_id"] != record["model_id"]:
            raise ValueError(f"model ID differs between score and raw response: {task_id}/{condition}")
        strict = score(task, condition, record["raw_text"])
        for field in ("format_error", "final_correct", "full_sequence_correct", "failure_type"):
            if str(strict[field]) != row[field]:
                raise ValueError(f"saved {field} differs from raw response: {task_id}/{condition}")
        changes, repaired = diagnostic(task, condition, record["raw_text"])
        details.append({"task_id": task_id, "condition": condition,
                        "operations": len(task["operations"]),
                        "strict_format_error": row["format_error"],
                        "diagnostic_changes": "; ".join(changes),
                        "diagnostic_parse_success": int(repaired is not None),
                        "diagnostic_final_correct": repaired["final_correct"] if repaired else "",
                        "diagnostic_transcription_correct": diagnostic_transcription(task, record["raw_text"])})
    output = ROOT / "results" / f"pilot2_diagnostics_{model}.csv"
    with output.open("w", newline="") as target:
        writer = csv.DictWriter(target, fieldnames=list(details[0]))
        writer.writeheader()
        writer.writerows(details)
    print("VISDSR PILOT 2")
    print("Model:", next(iter(model_ids)))
    print("Exact revision:", next(iter(revisions)))
    print("Seed:", config()["pilot2_seed"])
    for length in (1, 2):
        print(f"{length}-op (6 tasks per condition; 3 per size)")
        for condition in CONDITIONS:
            subset = [by_pair[(task_id, condition)] for task_id, task in tasks.items()
                      if len(task["operations"]) == length]
            final = sum(int(row["final_correct"]) for row in subset)
            step = sum(float(row["per_step_accuracy"]) for row in subset) / len(subset)
            sequence = sum(int(row["full_sequence_correct"]) for row in subset)
            errors = sum(int(row["format_error"]) for row in subset)
            print(f"  {condition}: final {final}/6, step {step:.1%}, "
                  f"sequence {sequence}/6, format errors {errors}/6")
    print("Strict G-str transcription correct:",
          sum(int(row["transcription_correct"]) for row in rows
              if row["condition"] == "G-str" and row["transcription_correct"] != ""), "/12")
    repaired = [item for item in details if item["diagnostic_parse_success"]]
    print("Diagnostic repairs (not official scores):", len(repaired))
    print("Diagnostic final correct after repair:",
          sum(int(item["diagnostic_final_correct"]) for item in repaired))
    print("Diagnostic G-str transcription correct (independent of step format):",
          sum(int(item["diagnostic_transcription_correct"]) for item in details
              if item["condition"] == "G-str" and item["diagnostic_transcription_correct"] is not None), "/12")
    print("Repair types:", dict(Counter(item["diagnostic_changes"] for item in repaired)))
    print("Diagnostic details:", output)
    print("STOP: review both pilot rounds before any freeze or main run.")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", default="model1")
    args = parser.parse_args()
    report(args.model)


if __name__ == "__main__":
    main()
