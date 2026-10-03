"""Eight bounded checks of extraction and DSU updates, separate from study scores."""
from __future__ import annotations

import argparse
import datetime
import json
from pathlib import Path

from eval.prompts import SYSTEM, prompt
from eval.providers.local import LocalModel
from eval.run import image_mapping, request_key
from eval.validate import FormatError, parse
from gen.generate import root, run_sim
from study_transfer import export_archive
from visdsr import ROOT, canonical, config, digest, read_tasks


def build_cases(task: dict, images: dict[str, bytes]) -> list[dict]:
    """Use the smoke forest and images; isolate operations without changing study data."""
    introduction = "\n".join(prompt(task, "T-dir").splitlines()[:4])
    cases = []
    for condition in ("T-dir", "R-dir", "G-dir"):
        initial = ("Initial state: " + canonical(task["initial"]) if condition == "T-dir"
                   else "Initial state: see the attached PNG.")
        text = "\n".join((introduction, initial,
                          'Transcribe the initial parent map only. Do not perform any operations. Return {"transcription":{...}} with a JSON object containing every label and its parent. Return no other fields or text.'))
        cases.append({"id": f"extract_{condition}", "kind": "extraction", "condition": condition,
                      "prompt": text, "image": images.get(condition), "task": task,
                      "expected": {"transcription": task["initial"]}})
    roots = {label: root(task["initial"], label)[0] for label in task["initial"]}
    sizes = {label: list(roots.values()).count(label) for label in sorted(set(roots.values()))}
    text = "\n".join((introduction, "Initial state: " + canonical(task["initial"]),
                      'Without modifying the forest, report each element\'s root in roots and each root\'s total set size in sizes. Return {"roots":{...},"sizes":{...}} only. roots contains every element label; sizes contains one integer count for each root.'))
    cases.append({"id": "roots_sizes_T-dir", "kind": "roots_sizes", "condition": "T-dir",
                  "prompt": text, "image": None, "task": task,
                  "expected": {"roots": roots, "sizes": sizes}})
    for kind, condition in (("find", "T-dir"), ("union", "T-dir"),
                            ("find", "R-dir"), ("find", "G-dir")):
        operation = next(operation for operation in task["operations"] if operation["kind"] == kind)
        truth = run_sim(task["n"], task["prelude"], [operation])
        isolated = {**task, "operations": [operation], "steps": truth["steps"]}
        answer = {"steps": [{"op": 1, **truth["steps"][0]}]}
        cases.append({"id": f"{kind}_{condition}", "kind": "transition", "condition": condition,
                      "prompt": prompt(isolated, condition), "image": images.get(condition),
                      "task": isolated, "expected": answer})
    return cases


def evaluate(case: dict, raw: str) -> dict:
    try:
        answer = json.loads(raw.strip())
        if case["kind"] == "transition":
            parse(raw, case["task"], case["condition"])
        else:
            if not isinstance(answer, dict) or set(answer) != set(case["expected"]):
                raise FormatError("unexpected top-level diagnostic fields")
            labels = set(case["task"]["initial"])
            field = "transcription" if case["kind"] == "extraction" else "roots"
            parents = answer[field]
            if not isinstance(parents, dict) or set(parents) != labels:
                raise FormatError(f"{field} must contain every label")
            if any(not isinstance(value, str) or value not in labels for value in parents.values()):
                raise FormatError(f"{field} contains invalid labels")
            if case["kind"] == "roots_sizes":
                sizes = answer["sizes"]
                if not isinstance(sizes, dict) or not sizes or not set(sizes) <= labels:
                    raise FormatError("sizes must map root labels to integer counts")
                if any(type(value) is not int or value <= 0 for value in sizes.values()):
                    raise FormatError("sizes must contain positive integer counts")
    except (json.JSONDecodeError, FormatError) as exc:
        return {"parse_success": False, "diagnostic_correct": False, "error": str(exc)}
    return {"parse_success": True, "diagnostic_correct": answer == case["expected"], "error": ""}


def run(model_name: str, max_new_calls: int = 8, score_only: bool = False,
        export: Path | None = None) -> list[dict]:
    if not 1 <= max_new_calls <= 8:
        raise ValueError("diagnostics allow between one and eight new calls")
    if config().get("protocol_version") != 2:
        raise ValueError("diagnostics require the reviewed v2 protocol")
    tasks = read_tasks("pilot2")
    task = next(task for task in tasks if len(task["operations"]) == 4)
    model = next(item for item in config()["models"] if item["name"] == model_name)
    mapping = image_mapping("pilot2")[task["id"]]
    images = {}
    for condition, column, checksum in (("R-dir", "text_image", "text_sha256"),
                                        ("G-dir", "diagram_image", "diagram_sha256")):
        image = (ROOT / "data/pilot2/img" / mapping[column]).read_bytes()
        if digest(image) != mapping[checksum]:
            raise RuntimeError("diagnostic input image hash mismatch")
        images[condition] = image
    cases = build_cases(task, images)
    code_hash = digest(Path(__file__).read_bytes())
    folder = ROOT / "results/diagnostics" / model_name
    local = None
    new_calls = 0
    rows = []
    prepared = []
    for case in cases:
        key, prompt_hash, image_hash = request_key(
            model, case["prompt"], case["image"], task["id"], "diagnostic:" + case["id"])
        provenance = {"cache_key": key, "diagnostic_id": case["id"], "source_task_id": task["id"],
                      "model_id": model["id"], "revision": model["revision"],
                      "protocol_id": config()["protocol_id"], "diagnostic_code_sha256": code_hash,
                      "source_task_sha256": digest(canonical(task).encode()),
                      "prompt_hash": prompt_hash, "image_hash": image_hash,
                      "system_prompt": SYSTEM, "user_prompt": case["prompt"],
                      "expected": case["expected"]}
        path = folder / f"{case['id']}.json"
        record = None
        if path.exists():
            record = json.loads(path.read_text())
            if any(record.get(name) != value for name, value in provenance.items()):
                raise RuntimeError("existing diagnostic request differs; review it before any replacement")
        elif score_only:
            raise RuntimeError(f"missing diagnostic cache: {case['id']}")
        prepared.append((case, path, provenance, record))
    for case, path, provenance, record in prepared:
        if record is None:
            if new_calls >= max_new_calls:
                continue
            if local is None:
                print(f"Loading {model['id']} for at most eight diagnostic requests", flush=True)
                local = LocalModel(model)
            result = local.call_model(case["prompt"], case["image"], model)
            record = {**provenance, "timestamp_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
                      **result}
            folder.mkdir(parents=True, exist_ok=True)
            temporary = path.with_suffix(".tmp")
            temporary.write_text(json.dumps(record, indent=2) + "\n")
            temporary.replace(path)
            new_calls += 1
            if export is not None:
                export_archive(export)
        result = evaluate(case, record["raw_text"])
        row = {"diagnostic_id": case["id"], **result, "latency_s": record["latency_s"],
               "hit_output_cap": record.get("hit_output_cap")}
        rows.append(row)
        print(f"{case['id']}: parse={result['parse_success']}, correct={result['diagnostic_correct']}, "
              f"latency_s={record['latency_s']:.2f}", flush=True)
        print("response:", record["raw_text"], flush=True)
        print("expected:", canonical(case["expected"]), flush=True)
    folder.mkdir(parents=True, exist_ok=True)
    summary = {"model": model_name, "source_task_id": task["id"], "diagnostics_scored": len(rows),
               "new_calls": new_calls, "checks": rows,
               "scope": "diagnostics only; excluded from all five-condition study scores"}
    temporary = folder / "summary.tmp"
    temporary.write_text(json.dumps(summary, indent=2) + "\n")
    temporary.replace(folder / "summary.json")
    if export is not None:
        export_archive(export)
    print(f"STOP: review {len(rows)}/8 diagnostic checks; no calibration or main requests ran")
    return rows


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", choices=[model["name"] for model in config()["models"]], required=True)
    parser.add_argument("--max-new-calls", type=int, choices=range(1, 9), default=8)
    parser.add_argument("--score-only", action="store_true")
    parser.add_argument("--export", type=Path, help="refresh the results backup after each new response")
    args = parser.parse_args()
    try:
        run(args.model, args.max_new_calls, args.score_only, args.export)
    except (ValueError, RuntimeError, FileNotFoundError) as exc:
        parser.exit(1, f"{exc}\n")


if __name__ == "__main__":
    main()
