"""Bounded, resumable inference in an isolated diagnostic cache namespace."""
from __future__ import annotations

import datetime
import fcntl
import json
import math
from contextlib import contextmanager
from pathlib import Path

from diagnostics.protocol import (PILOT, RESULTS, evaluate, load_panel,
                                  request_provenance, write_json)
from diagnostics.report import write_report
from eval.providers.local import LocalModel
from visdsr import canonical, digest


def check_record(record: dict, provenance: dict) -> None:
    if record.get("request") != provenance:
        raise RuntimeError("cached diagnostic request changed; refusing to replace it")
    response = record.get("response", {})
    if record.get("response_sha256") != digest(canonical(response).encode()):
        raise RuntimeError("cached diagnostic response hash mismatch")
    model = provenance["model"]
    parameters = {"do_sample": False, "num_beams": 1, "max_new_tokens": model["max_output_tokens"]}
    invalid_settings = any((response.get("model_id") != model["id"],
                            response.get("revision") != model["revision"],
                            response.get("effective_generation_parameters") != parameters))
    if invalid_settings:
        raise RuntimeError("cached diagnostic model revision or generation settings changed")
    if not isinstance(response.get("raw_text"), str):
        raise RuntimeError("diagnostic response has no raw text")
    count = response.get("output_tokens")
    if type(count) is not int or not 0 <= count <= model["max_output_tokens"]:
        raise RuntimeError("invalid recorded output token count")
    if type(response.get("hit_output_cap")) is not bool or response["hit_output_cap"] != (count == model["max_output_tokens"]):
        raise RuntimeError("diagnostic cap flag and token count disagree")
    latency = response.get("latency_s")
    if type(latency) not in (int, float) or not math.isfinite(latency) or latency < 0:
        raise RuntimeError("invalid diagnostic latency")
    for field in ("input_tensor_shapes", "settings", "gpus", "gpu_peaks_bytes"):
        if field not in response:
            raise RuntimeError(f"diagnostic response is missing provenance: {field}")


def prepared_records(frozen: dict, tasks: list[dict], cases: list[dict],
                     pilot: Path, results: Path) -> list[dict]:
    """Validate every existing record before any model can load."""
    by_id = {task["id"]: task for task in tasks}
    prepared = []
    expected_paths = set()
    for model in frozen["models"]:
        for case in cases:
            task = by_id[case["task_id"]]
            provenance = request_provenance(frozen, task, case, model, pilot)
            path = results / "cache" / model["name"] / f"{case['case_id']}.json"
            expected_paths.add(path)
            record = json.loads(path.read_text()) if path.exists() else None
            if record is not None:
                check_record(record, provenance)
            prepared.append({"model": model, "case": case, "task": task,
                             "request": provenance, "path": path, "record": record})
    if set((results / "cache").glob("*/*.json")) - expected_paths:
        raise RuntimeError("unexpected files in the diagnostic cache namespace")
    return prepared


def rows_from_records(prepared: list[dict]) -> list[dict]:
    rows = []
    for item in prepared:
        record = item["record"]
        if record is None:
            continue
        response = record["response"]
        result = evaluate(item["task"], item["case"], response["raw_text"])
        rows.append({"model": item["model"]["name"], "task_id": item["task"]["id"],
                     "control": item["case"]["control"], "elements": item["task"]["n"],
                     "operations": len(item["task"]["operations"]), **result,
                     "cap_hit": response["hit_output_cap"], "latency_s": response["latency_s"],
                     "output_tokens": response["output_tokens"]})
    return rows


@contextmanager
def collection_lock(results: Path):
    """Prevent two batches from issuing duplicate requests; crashes release the lock."""
    results.mkdir(parents=True, exist_ok=True)
    with (results / ".collection.lock").open("a") as handle:
        try:
            fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise RuntimeError("another diagnostic batch is running in this results directory") from exc
        try:
            yield
        finally:
            fcntl.flock(handle, fcntl.LOCK_UN)


def run(model_name: str, max_new_calls: int = 12, score_only: bool = False,
        export: Path | None = None, pilot: Path = PILOT, results: Path = RESULTS) -> dict:
    with collection_lock(results):
        return collect(model_name, max_new_calls, score_only, export, pilot, results)


def collect(model_name: str, max_new_calls: int, score_only: bool,
            export: Path | None, pilot: Path, results: Path) -> dict:
    if model_name not in ("model1", "model2"):
        raise ValueError("model must be model1 or model2")
    if type(max_new_calls) is not int or not 1 <= max_new_calls <= 48:
        raise ValueError("choose between 1 and 48 new calls; default is 12")
    frozen, tasks, cases = load_panel(pilot)
    prepared = prepared_records(frozen, tasks, cases, pilot, results)
    selected = [item for item in prepared if item["model"]["name"] == model_name]
    cached = sum(item["record"] is not None for item in selected)
    if score_only and cached != 48:
        raise RuntimeError(f"score-only requires all 48 {model_name} records; found {cached}")
    print(f"DIAGNOSTIC PILOT: {model_name}, {cached}/48 cached, at most {max_new_calls} new calls", flush=True)
    local = None
    new_calls = 0

    def checkpoint() -> dict:
        result = write_report(results, rows_from_records(prepared))
        if export is not None:
            from diagnostics.transfer import export_backup
            export_backup(export, pilot, results)
        return result

    try:
        for item in selected:
            if item["record"] is not None or score_only:
                continue
            if new_calls >= max_new_calls:
                break
            model, case = item["model"], item["case"]
            if local is None:
                print(f"Loading {model['id']} at pinned revision {model['revision']}", flush=True)
                local = LocalModel(model)
            image = (pilot / case["image"]).read_bytes() if case["image"] else None
            response = local.call_model(case["user_prompt"], image, model)
            record = {"request": item["request"], "response": response,
                      "response_sha256": digest(canonical(response).encode()),
                      "timestamp_utc": datetime.datetime.now(datetime.timezone.utc).isoformat()}
            check_record(record, item["request"])
            write_json(item["path"], record)
            item["record"] = record
            new_calls += 1
            checkpoint()
            result = evaluate(item["task"], case, response["raw_text"])
            print(f"{cached + new_calls}/48 {case['case_id']}: saved; "
                  f"valid={result['valid']}, correct={result['correct']}", flush=True)
    finally:
        summary = checkpoint()
        if export is not None:
            print(f"BACKUP SNAPSHOT: {export}; {summary['scored']}/96 responses saved", flush=True)
    count = summary["models"][model_name]["scored"]
    print(f"CHECKPOINT: {model_name} {count}/48; combined {summary['scored']}/96; gate={summary['gate']}", flush=True)
    print(summary["next_step"], flush=True)
    if export is not None:
        print(f"BACKUP READY: {export}; download it before ending the session", flush=True)
    return summary


def score_saved(pilot: Path = PILOT, results: Path = RESULTS) -> dict:
    frozen, tasks, cases = load_panel(pilot)
    return write_report(results, rows_from_records(prepared_records(frozen, tasks, cases, pilot, results)))
