"""Record pilot calibration before generating the main dataset."""
from __future__ import annotations

import argparse
import csv
import datetime
import json

from eval.prompts import CONDITIONS
from visdsr import ROOT, digest, read_tasks


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--calibration-note", required=True,
                        help="observed pilot results and the reviewed main-design decision")
    args = parser.parse_args()
    if (ROOT / "data/main/tasks.jsonl").exists():
        parser.error("main tasks already exist; do not re-freeze after main generation")
    expected_by_split = {}
    for split in ("pilot", "pilot2"):
        path = ROOT / "data" / split / "tasks.jsonl"
        if not path.exists():
            parser.error(f"missing {split} tasks; restore both pilot rounds before freezing")
        tasks = read_tasks(split)
        if len(tasks) != 12:
            parser.error(f"complete the 12-task {split} before freezing")
        expected_by_split[split] = {(task["id"], condition)
                                    for task in tasks for condition in CONDITIONS}
    completed = []
    for model in ("model1", "model2"):
        for split, expected in expected_by_split.items():
            path = ROOT / "results" / f"scores_{split}_{model}.csv"
            if not path.exists():
                break
            with path.open(newline="") as source:
                rows = list(csv.DictReader(source))
            observed = {(row["task_id"], row["condition"]) for row in rows
                        if row["split"] == split and row["model_id"] != "mock-oracle"}
            if observed != expected or len(rows) != len(expected):
                break
        else:
            completed.append(model)
    if not completed:
        parser.error("complete both 12-task pilot rounds for at least one real model")
    record = {"timestamp_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
              "calibration_note": args.calibration_note,
              "completed_pilot_models": completed,
              "config_sha256": digest((ROOT / "configs/experiment.yaml").read_bytes()),
              "prompt_sha256": digest((ROOT / "eval/prompts.py").read_bytes()),
              "pilot_tasks_sha256": digest((ROOT / "data/pilot/tasks.jsonl").read_bytes()),
              "pilot2_tasks_sha256": digest((ROOT / "data/pilot2/tasks.jsonl").read_bytes())}
    if args.dry_run:
        print(json.dumps(record, indent=2))
        return
    (ROOT / "FREEZE.json").write_text(json.dumps(record, indent=2) + "\n")
    print("recorded FREEZE.json; commit the frozen spec and tag it v1.0-frozen")


if __name__ == "__main__":
    main()
