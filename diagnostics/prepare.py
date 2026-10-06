"""Generate and verify the single fixed eight-forest diagnostic panel."""
from __future__ import annotations

import io
import json
import random
import subprocess
from pathlib import Path

import gen.render as renderer
from diagnostics.protocol import (CONTROLS, GENERATION_SEED, ORDER_SEED, PILOT,
                                  PROTOCOL_ID, REFERENCE_HASHES, build_case, source_hashes, write_json)
from gen.generate import choose_operations, initial_prelude, metadata, run_sim, valid_task
from gen.visual_checks import check_image
from tests.naive import simulate
from visdsr import ROOT, canonical, config, digest


def reference_index(reference_root: Path) -> dict:
    """Read only the published calibration/main tasks, checking their known hashes."""
    hashes = {}
    signatures = []
    for split, count in (("pilot2", 12), ("main", 80)):
        name = f"data/{split}/tasks.jsonl"
        content = (reference_root / name).read_bytes()
        if digest(content) != REFERENCE_HASHES[split]:
            raise RuntimeError(f"reference {split} tasks differ from the completed study")
        tasks = [json.loads(line) for line in content.decode().splitlines()]
        if len(tasks) != count:
            raise RuntimeError(f"incomplete reference {split}")
        hashes[name] = digest(content)
        signatures.extend(digest(canonical([task["initial"], task["operations"]]).encode())
                          for task in tasks)
    if len(set(signatures)) != 92:
        raise RuntimeError("duplicate reference task signatures")
    return {"release": "v2.0-results", "tasks": 92, "source_hashes": hashes,
            "signature_definition": "SHA-256 of canonical([initial, operations]); IDs and preludes excluded",
            "signatures": sorted(signatures)}


def generate_panel(reference: dict) -> list[dict]:
    rng = random.Random(GENERATION_SEED)
    known = set(reference["signatures"])
    initials = set()
    tasks = []
    for size, n, length in (("small", 8, 1), ("small", 8, 4),
                            ("large", 16, 1), ("large", 16, 4)):
        for index in range(2):
            for _ in range(500):
                prelude = initial_prelude(n, rng)
                initial = run_sim(n, prelude, [])["initial"]
                operations = choose_operations(initial, length, index == 0, rng)
                truth = run_sim(n, prelude, operations)
                task = {"id": f"diag_{len(tasks) + 1:04d}", "split": "diagnostics",
                        "structure": "dsu", "size": size, "n": n,
                        "prelude": prelude, "operations": operations, **truth}
                task["difficulty"] = metadata(initial, operations, truth["steps"])
                signature = digest(canonical([initial, operations]).encode())
                tie_ok = length == 1 or index != 0 or task["difficulty"]["equal_size_ties"] > 0
                acceptable = all((canonical(initial) not in initials, signature not in known,
                                  valid_task(task, length), tie_ok))
                if acceptable:
                    if truth != simulate(n, prelude, operations):
                        raise RuntimeError("C++ and independent Python reference disagree")
                    initials.add(canonical(initial))
                    known.add(signature)
                    tasks.append(task)
                    break
            else:
                raise RuntimeError(f"could not generate diagnostic {size}/{length}/{index}")
    return tasks


def validate_tasks(tasks: list[dict], reference: dict) -> None:
    if len(tasks) != 8 or len({task["id"] for task in tasks}) != 8:
        raise RuntimeError("pilot must contain eight unique task IDs")
    if len({canonical(task["initial"]) for task in tasks}) != 8:
        raise RuntimeError("pilot repeats an initial map")
    if reference["tasks"] != 92 or len(set(reference["signatures"])) != 92:
        raise RuntimeError("reference index must cover all 92 completed tasks")
    for split in ("pilot2", "main"):
        if reference["source_hashes"][f"data/{split}/tasks.jsonl"] != REFERENCE_HASHES[split]:
            raise RuntimeError("reference index belongs to a different study")
    cells = {}
    for task in tasks:
        cell = (task["n"], len(task["operations"]))
        cells.setdefault(cell, []).append(task)
        signature = digest(canonical([task["initial"], task["operations"]]).encode())
        if signature in reference["signatures"]:
            raise RuntimeError("diagnostic task overlaps a completed task")
        truth = {"initial": task["initial"], "steps": task["steps"]}
        if truth != simulate(task["n"], task["prelude"], task["operations"]):
            raise RuntimeError(f"independent reference mismatch: {task['id']}")
        if truth != run_sim(task["n"], task["prelude"], task["operations"]):
            raise RuntimeError(f"simulator mismatch: {task['id']}")
        expected_metadata = metadata(task["initial"], task["operations"], task["steps"])
        if not valid_task(task, len(task["operations"])) or task["difficulty"] != expected_metadata:
            raise RuntimeError(f"task balance or metadata failed: {task['id']}")
        if task["initial"] == task["steps"][-1]["state"]:
            raise RuntimeError("diagnostic update must change the final map")
    if set(cells) != {(8, 1), (8, 4), (16, 1), (16, 4)} or any(len(value) != 2 for value in cells.values()):
        raise RuntimeError("expected exactly two forests in each difficulty cell")
    for n in (8, 16):
        if {task["operations"][0]["kind"] for task in cells[(n, 1)]} != {"find", "union"}:
            raise RuntimeError("one-operation cells require a find and a union")
        if not any(task["difficulty"]["equal_size_ties"] for task in cells[(n, 4)]):
            raise RuntimeError("each multi-operation cell must include a union tie")


def prepare(reference_root: Path, folder: Path = PILOT,
            font: Path | None = None, mono: Path | None = None) -> dict:
    if folder.exists() and any(folder.iterdir()):
        raise RuntimeError("input folder is not empty; keep the existing panel or choose a new folder")
    original = json.loads((ROOT / "FREEZE.json").read_text())
    for name, checksum in original["source_hashes"].items():
        if digest((ROOT / name).read_bytes()) != checksum:
            raise RuntimeError(f"completed-study source changed: {name}")
    reference = reference_index(reference_root)
    expected_reference = json.loads((ROOT / "diagnostics/reference_signatures.json").read_text())
    if reference != expected_reference:
        raise RuntimeError("reference signature index does not match the verified completed tasks")
    tasks = generate_panel(reference)
    validate_tasks(tasks, reference)
    font = font or Path(renderer.FONT)
    mono = mono or Path(renderer.MONO)
    old_font, old_mono = renderer.FONT, renderer.MONO
    mappings = {}
    hashes = {}
    folder.mkdir(parents=True, exist_ok=True)
    try:
        # Only host font locations differ; use the same DejaVu fonts and renderer.
        renderer.FONT, renderer.MONO = str(font), str(mono)
        for index, task in enumerate(tasks, 1):
            images = (renderer.text_image(canonical(task["initial"]), 1024),
                      renderer.diagram_image(task["initial"], 1024))
            mapping = {}
            for offset, (kind, image) in enumerate(zip(("text", "diagram"), images, strict=True)):
                name = f"img_{2 * index - 1 + offset:05d}.png"
                check_image(image, 1024)
                buffer = io.BytesIO()
                image.save(buffer, format="PNG")
                content = buffer.getvalue()
                (folder / name).write_bytes(content)
                hashes[name] = digest(content)
                mapping[f"{kind}_image"] = name
            mappings[task["id"]] = mapping
    finally:
        renderer.FONT, renderer.MONO = old_font, old_mono
    (folder / "tasks.jsonl").write_text("".join(canonical(task) + "\n" for task in tasks))
    write_json(folder / "images.json", mappings)
    cases = [build_case(task, control, mappings[task["id"]]) for task in tasks for control in CONTROLS]
    random.Random(ORDER_SEED).shuffle(cases)
    write_json(folder / "requests.json", cases)
    for name in ("tasks.jsonl", "images.json", "requests.json"):
        hashes[name] = digest((folder / name).read_bytes())
    graphviz = subprocess.run(["dot", "-V"], capture_output=True, text=True, check=True)
    frozen = {"protocol_id": PROTOCOL_ID, "status": "inputs frozen before inference",
              "generation_seed": GENERATION_SEED, "order_seed": ORDER_SEED,
              "tasks": 8, "requests_per_model": 48, "total_requests": 96,
              "controls": list(CONTROLS), "models": config()["models"],
              "system_prompt": SYSTEM_DESCRIPTION, "source_hashes": source_hashes(),
              "input_hashes": hashes, "reference": reference,
              "renderer": {"canvas": 1024, "graphviz": (graphviz.stdout + graphviz.stderr).strip(),
                           "font_sha256": digest(font.read_bytes()), "mono_sha256": digest(mono.read_bytes())},
              "limitations": ["Fresh exact maps and operation sequences do not establish new unlabeled topologies.",
                              "Eight forests support descriptive diagnostics, not a powered modality comparison."]}
    write_json(folder / "FREEZE.json", frozen)
    return frozen


SYSTEM_DESCRIPTION = "Reuse eval.prompts.SYSTEM for all six controls; user prompts distinguish copying, extraction, and updates."
