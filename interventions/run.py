"""One model load for its 48 controls and 48 additional improvement requests."""
from __future__ import annotations

import datetime
import json
import os
from pathlib import Path

from diagnostics.protocol import PILOT, RESULTS as DIAGNOSTIC_RESULTS, evaluate, load_panel, write_json
from diagnostics.run import check_record, collection_lock, prepared_records
from interventions.protocol import RESULTS, load_protocol, provenance
from visdsr import canonical, digest


def records() -> tuple[list[dict], list[dict]]:
    frozen, tasks, cases = load_protocol()
    diagnostic, _, originals = load_panel()
    base = prepared_records(diagnostic, tasks, originals, PILOT, DIAGNOSTIC_RESULTS)
    by_id = {task["id"]: task for task in tasks}
    items = []
    for model in diagnostic["models"]:
        for case in cases:
            task = by_id[case["task_id"]]
            request = provenance(frozen, task, case, model)
            path = RESULTS / "cache" / model["name"] / (case["case_id"] + ".json")
            record = json.loads(path.read_text()) if path.exists() else None
            if record is not None:
                check_record(record, request)
                if case["grammar"] and record["response"].get("grammar_version") != "0.2.8":
                    raise RuntimeError("cached constrained response lacks the pinned grammar provenance")
            items.append({"model": model, "case": case, "task": task,
                          "request": request, "path": path, "record": record})
    if set((RESULTS / "cache").glob("*/*.json")) - {item["path"] for item in items}:
        raise RuntimeError("unexpected intervention cache files")
    return base, items


def collect(model_name: str, output: Path) -> None:
    if model_name not in ("model1", "model2"):
        raise ValueError("unknown model")
    from interventions.provider import InterventionModel
    from interventions.transfer import export_backup
    # Separate per-model locks allow one process on each T4. This runner's joint
    # job lock also excludes a second improvement run in the same project.
    with collection_lock(RESULTS / model_name):
        base, added = records()
        selected = [item for item in base + added if item["model"]["name"] == model_name]
        local = None
        try:
            for item in selected:
                if item["record"] is not None:
                    continue
                if local is None:
                    local = InterventionModel(item["model"])
                case, task = item["case"], item["task"]
                image = (PILOT / case["image"]).read_bytes() if case["image"] else None
                response = local.answer(case, task, image, item["model"])
                response["worker_gpu_visibility"] = os.environ.get("CUDA_VISIBLE_DEVICES", "all")
                record = {"request": item["request"], "response": response,
                          "response_sha256": digest(canonical(response).encode()),
                          "timestamp_utc": datetime.datetime.now(datetime.timezone.utc).isoformat()}
                check_record(record, item["request"])
                write_json(item["path"], record)
                item["record"] = record
                # Each process owns its ZIP; the parent combines both at the end.
                export_backup(output / f"visdsr_improvements_{model_name}_backup.zip")
                result = evaluate(task, case, response["raw_text"])
                count = sum(item["record"] is not None for item in selected)
                print(f"{model_name} {count}/96 {case['case_id']}: saved; "
                      f"valid={result['valid']}, correct={result['correct']}", flush=True)
        finally:
            export_backup(output / f"visdsr_improvements_{model_name}_backup.zip")
