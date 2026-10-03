"""Record pilot calibration before generating the main dataset."""
from __future__ import annotations

import argparse
import csv
import datetime
import json

from eval.prompts import CONDITIONS, SYSTEM, prompt
from eval.run import image_mapping, request_key
from eval.score import score
from visdsr import ROOT, canonical, config, digest, protocol_hashes, read_tasks


def audit_calibration(model: dict, tasks: list[dict], mapping: dict) -> dict:
    """Recompute all scores from matching raw caches; CSV IDs alone cannot freeze."""
    path = ROOT / "results" / f"scores_pilot2_{model['name']}.csv"
    if not path.exists():
        raise RuntimeError(f"complete calibration for {model['name']} before freezing")
    with path.open(newline="") as source:
        rows = list(csv.DictReader(source))
    expected_rows = []
    latencies = []
    for task in tasks:
        for condition in CONDITIONS:
            text = prompt(task, condition)
            image = None
            if condition.startswith(("R", "G")):
                column = "text_image" if condition.startswith("R") else "diagram_image"
                image = (ROOT / "data/pilot2/img" / mapping[task["id"]][column]).read_bytes()
                hash_column = "text_sha256" if column == "text_image" else "diagram_sha256"
                if digest(image) != mapping[task["id"]][hash_column]:
                    raise RuntimeError("calibration image hash mismatch")
            key, prompt_hash, image_hash = request_key(model, text, image, task["id"], condition)
            cached = ROOT / "results/cache" / f"{key}.json"
            if not cached.exists():
                raise RuntimeError(f"missing matching raw cache: {model['name']}/{task['id']}/{condition}")
            record = json.loads(cached.read_text())
            expected = {"cache_key": key, "task_id": task["id"], "split": "pilot2",
                        "condition": condition, "model_id": model["id"],
                        "revision": model["revision"], "protocol_id": config()["protocol_id"],
                        "task_sha256": digest(canonical(task).encode()),
                        "prompt_hash": prompt_hash, "image_hash": image_hash,
                        "system_prompt": SYSTEM, "user_prompt": text}
            if any(record.get(name) != value for name, value in expected.items()):
                raise RuntimeError(f"calibration cache provenance differs: {cached.name}")
            parameters = {"do_sample": False, "num_beams": 1,
                          "max_new_tokens": model["max_output_tokens"]}
            if record.get("effective_generation_parameters") != parameters:
                raise RuntimeError("effective generation parameters are missing or changed")
            result = {"model": model["name"], "model_id": model["id"],
                      **score(task, condition, record["raw_text"])}
            expected_rows.append({name: str(value) for name, value in result.items()})
            latencies.append(record["latency_s"])

    def by_pair(row):
        return row["task_id"], row["condition"]

    if sorted(rows, key=by_pair) != sorted(expected_rows, key=by_pair):
        raise RuntimeError("calibration CSV does not match scores recomputed from raw caches")
    return {"model": model["name"], "responses": len(rows),
            "mean_latency_s": sum(latencies) / len(latencies),
            "by_condition": {condition: {
                "final_correct": sum(int(row["final_correct"]) for row in rows
                                     if row["condition"] == condition),
                "format_errors": sum(int(row["format_error"]) for row in rows
                                     if row["condition"] == condition),
            } for condition in CONDITIONS}}


def freeze_v2(note: str, dry_run: bool) -> None:
    tasks = read_tasks("pilot2")
    if len(tasks) != 12:
        raise RuntimeError("v2 requires a complete 12-task representative calibration")
    mapping = image_mapping("pilot2")
    summaries = [audit_calibration(model, tasks, mapping) for model in config()["models"]]
    record = {
        "protocol_id": config()["protocol_id"],
        "timestamp_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "calibration_note": note,
        "completed_pilot_models": [summary["model"] for summary in summaries],
        "calibration_summaries": summaries,
        "source_hashes": protocol_hashes(),
        "config_sha256": digest((ROOT / "configs/experiment.yaml").read_bytes()),
        "prompt_sha256": digest((ROOT / "eval/prompts.py").read_bytes()),
        "pilot2_tasks_sha256": digest((ROOT / "data/pilot2/tasks.jsonl").read_bytes()),
    }
    if dry_run:
        print(json.dumps(record, indent=2))
    else:
        (ROOT / "FREEZE.json").write_text(json.dumps(record, indent=2) + "\n")
        print("recorded audited FREEZE.json; commit and tag the reviewed protocol v2.0-frozen")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--calibration-note", required=True,
                        help="observed pilot results and the reviewed main-design decision")
    args = parser.parse_args()
    if (ROOT / "data/main/tasks.jsonl").exists():
        parser.error("main tasks already exist; do not re-freeze after main generation")
    if config().get("protocol_version") == 2:
        try:
            freeze_v2(args.calibration_note, args.dry_run)
        except (ValueError, RuntimeError, FileNotFoundError) as exc:
            parser.error(str(exc))
        return
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
