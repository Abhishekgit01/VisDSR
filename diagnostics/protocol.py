"""Fixed pilot controls, response contracts, and provenance checks."""
from __future__ import annotations

import io
import json
import random
from pathlib import Path

from PIL import Image

from eval.prompts import SYSTEM, prompt
from eval.validate import FormatError, parse
from gen.visual_checks import check_image
from visdsr import ROOT, STUDY_SOURCE_FILES, canonical, config, digest

PROTOCOL_ID = "visdsr-dsu-diagnostics-20261007"
GENERATION_SEED = 2026100603
ORDER_SEED = 2026100604
REFERENCE_HASHES = {
    "pilot2": "ca666bbc955326c4999bf002878e4ebde864b583ac89ced8b7328d8b8aa2674b",
    "main": "59814ee150757ff77a944de13c9630cf317c99cf4df9c519ee46e9fb2280ccf4",
}
CONTROLS = ("extract_text", "extract_rendered", "extract_diagram",
            "update_text", "update_diagram", "copy_solution")
PILOT = ROOT / "diagnostics/pilot"
RESULTS = ROOT / "results/followup" / PROTOCOL_ID
SOURCES = (*STUDY_SOURCE_FILES, "FREEZE.json", "tests/naive.py",
           "diagnostics/__init__.py", "diagnostics/protocol.py",
           "diagnostics/prepare.py", "diagnostics/run.py",
           "diagnostics/overnight.py",
           "diagnostics/report.py", "diagnostics/transfer.py",
           "diagnostics/__main__.py", "diagnostics/reference_signatures.json",
           "notebooks/dsu_diagnostics_kaggle.ipynb")


def write_json(path: Path, value: object) -> None:
    """Replace an artifact atomically, including after an interrupted run."""
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, indent=2) + "\n")
    temporary.replace(path)


def source_hashes() -> dict[str, str]:
    return {name: digest((ROOT / name).read_bytes()) for name in SOURCES}


def solution(task: dict) -> dict:
    return {"steps": [{"op": number, **step}
                      for number, step in enumerate(task["steps"], 1)]}


def build_case(task: dict, control: str, mapping: dict) -> dict:
    if control not in CONTROLS:
        raise ValueError(f"unknown control: {control}")
    image_name = None
    condition = "T-dir"
    if control == "extract_rendered":
        condition, image_name = "R-dir", mapping["text_image"]
    elif control in ("extract_diagram", "update_diagram"):
        condition, image_name = "G-dir", mapping["diagram_image"]
    if control.startswith("extract_"):
        introduction = (
            f"Disjoint-set union over labels {', '.join(task['initial'])}.\n"
            "A root is its own parent. Each diagram arrow points from child to parent; "
            "roots have no outgoing arrow.\n"
        )
        initial = ("Initial state: " + canonical(task["initial"]) if image_name is None
                   else "Initial state: see the attached PNG.")
        text = introduction + initial + (
            '\nTranscribe the initial parent map only. There are no operations to perform. '
            'Return {"transcription":{...}} with every label exactly once as a key '
            'and its parent label as the value. Return no other fields, prose, or Markdown.'
        )
    elif control == "copy_solution":
        text = (
            f"Disjoint-set union over labels {', '.join(task['initial'])}.\n"
            "The following is the simulator-supplied correct solution. Copy this JSON "
            "object exactly; no calculation is needed. Preserve every step, label, "
            "parent, and find result. Return no other fields, prose, or Markdown.\n"
            "Solution to copy: " + canonical(solution(task))
        )
    else:
        # Retain the existing rules and worked examples for the update baseline.
        text = prompt(task, condition)
    return {"case_id": f"{task['id']}__{control}", "task_id": task["id"],
            "control": control, "condition": condition, "image": image_name,
            "system_prompt": SYSTEM, "user_prompt": text}


def reject_duplicate_keys(pairs: list[tuple]) -> dict:
    result = {}
    for key, value in pairs:
        if key in result:
            raise FormatError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def evaluate(task: dict, case: dict, raw: str) -> dict:
    """Bare JSON only; invalid outputs remain incorrect and never trigger retries."""
    empty = {"valid": False, "correct": False, "final_correct": False,
             "full_sequence_correct": False, "changed_parent_accuracy": 0.0, "error": ""}
    try:
        answer = json.loads(raw.strip(), object_pairs_hook=reject_duplicate_keys)
        if case["control"].startswith("extract_"):
            if not isinstance(answer, dict) or set(answer) != {"transcription"}:
                raise FormatError("expected only transcription")
            state = answer["transcription"]
            labels = set(task["initial"])
            if not isinstance(state, dict) or set(state) != labels:
                raise FormatError("transcription must contain every label exactly once")
            if any(not isinstance(value, str) or value not in labels for value in state.values()):
                raise FormatError("invalid parent label")
            return {**empty, "valid": True, "correct": state == task["initial"],
                    "changed_parent_accuracy": ""}
        # Parse the already decoded object to avoid the old code-fence allowance.
        answer = parse(canonical(answer), task, "T-dir")
    except (json.JSONDecodeError, FormatError) as exc:
        return {**empty, "error": str(exc)}
    final = answer["steps"][-1]["state"]
    truth = task["steps"][-1]["state"]
    final_correct = final == truth
    full_correct = answer == solution(task)
    changed = [label for label in truth if truth[label] != task["initial"][label]]
    accuracy = sum(final[label] == truth[label] for label in changed) / len(changed)
    correct = full_correct if case["control"] == "copy_solution" else final_correct
    return {**empty, "valid": True, "correct": correct, "final_correct": final_correct,
            "full_sequence_correct": full_correct, "changed_parent_accuracy": accuracy}


def load_panel(folder: Path = PILOT, require_review: bool = True) -> tuple[dict, list[dict], list[dict]]:
    frozen = json.loads((folder / "FREEZE.json").read_text())
    if frozen["protocol_id"] != PROTOCOL_ID or frozen["source_hashes"] != source_hashes():
        raise RuntimeError("diagnostic sources differ from the input freeze; do not reuse this cache")
    if frozen["models"] != config()["models"]:
        raise RuntimeError("diagnostic model settings changed")
    for name, checksum in frozen["input_hashes"].items():
        path = folder / name
        if path.is_symlink() or digest(path.read_bytes()) != checksum:
            raise RuntimeError(f"diagnostic input changed: {name}")
    tasks = [json.loads(line) for line in (folder / "tasks.jsonl").read_text().splitlines()]
    mappings = json.loads((folder / "images.json").read_text())
    cases = [build_case(task, control, mappings[task["id"]])
             for task in tasks for control in CONTROLS]
    random.Random(ORDER_SEED).shuffle(cases)
    if len(tasks) != 8 or json.loads((folder / "requests.json").read_text()) != cases:
        raise RuntimeError("diagnostic request plan differs from the frozen inputs")
    for mapping in mappings.values():
        for field in ("text_image", "diagram_image"):
            with Image.open(io.BytesIO((folder / mapping[field]).read_bytes())) as image:
                check_image(image, 1024)
    review_path = folder / "REVIEW.json"
    if require_review:
        review = json.loads(review_path.read_text())
        by_id = {task["id"]: task for task in tasks}
        cells = {(by_id[name]["n"], len(by_id[name]["operations"])) for name in review["task_ids"]}
        if review.get("reviewed_inputs_sha256") != digest(canonical(frozen["input_hashes"]).encode()):
            raise RuntimeError("visual review belongs to different inputs")
        if cells != {(8, 1), (8, 4), (16, 1), (16, 4)}:
            raise RuntimeError("review one task in every difficulty cell before inference")
    return frozen, tasks, cases


def request_provenance(frozen: dict, task: dict, case: dict, model: dict, folder: Path = PILOT) -> dict:
    image_hash = digest((folder / case["image"]).read_bytes()) if case["image"] else ""
    value = {"protocol_id": PROTOCOL_ID, "freeze_sha256": digest(canonical(frozen).encode()),
             "task_sha256": digest(canonical(task).encode()), "case": case,
             "image_sha256": image_hash, "model": model}
    return {"cache_key": digest(canonical(value).encode()), **value}
