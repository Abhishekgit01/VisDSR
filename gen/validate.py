"""Check generated DSU tasks, image geometry, pixels, and manifest hashes."""
from __future__ import annotations

import argparse
import csv
import re

from PIL import Image, ImageChops

from gen.generate import metadata, run_sim, valid_task
from gen.render import diagram_image, layout, text_image
from gen.visual_checks import check_image
from visdsr import ROOT, SPLITS, canonical, config, digest, read_tasks


def task_signature(task: dict) -> str:
    return canonical([task["initial"], task["operations"]])


def validate(split: str) -> dict[str, int]:
    cfg = config()
    tasks = read_tasks(split)
    if split == "pilot":
        per_cell, lengths = cfg["dsu"]["pilot_tasks_per_cell"], [4]
    elif split == "pilot2":
        per_cell = cfg["dsu"]["pilot2_tasks_per_cell"]
        lengths = cfg["dsu"]["pilot2_sequence_lengths"]
    else:
        per_cell, lengths = cfg["dsu"]["main_tasks_per_cell"], cfg["dsu"]["sequence_lengths"]
    expected_cells = {(size, length): per_cell for size in ("small", "large") for length in lengths}
    actual_cells = {cell: 0 for cell in expected_cells}
    if len(tasks) != sum(expected_cells.values()):
        raise ValueError(f"expected {sum(expected_cells.values())} {split} tasks, found {len(tasks)}")
    if len({task["id"] for task in tasks}) != len(tasks):
        raise ValueError("duplicate task IDs")
    if len({task_signature(task) for task in tasks}) != len(tasks):
        raise ValueError("duplicate task content")

    folder = ROOT / "data" / split
    with (folder / "manifest.csv").open(newline="") as source:
        rows = list(csv.DictReader(source))
    by_id = {row["task_id"]: row for row in rows}
    if len(rows) != len(tasks) or set(by_id) != {task["id"] for task in tasks}:
        raise ValueError("image manifest does not match tasks")
    image_dir = folder / "img"
    expected_names = {f"img_{number:05d}.png" for number in range(1, len(tasks) * 2 + 1)}
    actual_names = {path.name for path in image_dir.glob("img_*.png")}
    if actual_names != expected_names:
        raise ValueError("anonymous image filenames are missing or unexpected")
    seen_images = set()
    checked_edges = 0
    for task in tasks:
        if task["split"] != split or task["structure"] != "dsu":
            raise ValueError(f"wrong split or structure: {task['id']}")
        cell = (task["size"], len(task["operations"]))
        if cell not in actual_cells:
            raise ValueError(f"unexpected task cell: {task['id']}")
        actual_cells[cell] += 1
        expected_size = cfg["dsu"][f"{task['size']}_size"]
        labels = list("ABCDEFGHIJKLMNOPQRSTUVWXYZ"[:expected_size])
        if task["n"] != expected_size or list(task["initial"]) != labels:
            raise ValueError(f"wrong element labels or size: {task['id']}")
        truth = run_sim(task["n"], task["prelude"], task["operations"])
        if truth != {"initial": task["initial"], "steps": task["steps"]}:
            raise ValueError(f"simulator truth mismatch: {task['id']}")
        if metadata(task["initial"], task["operations"], task["steps"]) != task["difficulty"]:
            raise ValueError(f"difficulty metadata mismatch: {task['id']}")
        if not valid_task(task, len(task["operations"])):
            raise ValueError(f"balance constraints failed: {task['id']}")
        positions, edges = layout(task["initial"], cfg["render"]["canvas"])
        expected_edges = sum(node != parent for node, parent in task["initial"].items())
        if len(positions) != task["n"] or len(edges) != expected_edges:
            raise ValueError(f"node or edge count mismatch: {task['id']}")
        checked_edges += len(edges)
        expected_images = {
            "text_image": ("text_sha256", text_image(canonical(task["initial"]), cfg["render"]["canvas"])),
            "diagram_image": ("diagram_sha256", diagram_image(task["initial"], cfg["render"]["canvas"])),
        }
        for column, (hash_column, expected_image) in expected_images.items():
            name = by_id[task["id"]][column]
            if not re.fullmatch(r"img_\d{5}\.png", name) or name in seen_images:
                raise ValueError(f"invalid or reused image filename: {name}")
            seen_images.add(name)
            path = image_dir / name
            content = path.read_bytes()
            if digest(content) != by_id[task["id"]][hash_column]:
                raise ValueError(f"manifest hash mismatch: {name}")
            with Image.open(path) as source:
                actual = source.copy()
            check_image(actual, cfg["render"]["canvas"])
            if ImageChops.difference(actual, expected_image).getbbox() is not None:
                raise ValueError(f"rendered pixels differ from task state: {name}")
    if actual_cells != expected_cells or seen_images != expected_names:
        raise ValueError("task cells or image mapping are incomplete")
    if split == "pilot2":
        one_op = [task for task in tasks if len(task["operations"]) == 1]
        if sum(task["operations"][0]["kind"] == "find" for task in one_op) != 3:
            raise ValueError("pilot2 one-operation finds and unions are not balanced")
        for size in ("small", "large"):
            two_op = [task for task in tasks
                      if task["size"] == size and len(task["operations"]) == 2]
            if not any(task["difficulty"]["equal_size_ties"] for task in two_op):
                raise ValueError(f"pilot2 {size} two-operation tasks lack an equal-size tie")
    for other in SPLITS:
        other_file = ROOT / "data" / other / "tasks.jsonl"
        if other != split and other_file.exists():
            overlap = {task_signature(task) for task in tasks} & {
                task_signature(task) for task in read_tasks(other)}
            if overlap:
                raise ValueError(f"{split} and {other} contain overlapping tasks")
    return {"tasks": len(tasks), "images": len(seen_images), "checked_edges": checked_edges}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--split", choices=SPLITS, required=True)
    args = parser.parse_args()
    result = validate(args.split)
    print(f"validated {args.split}: {result['tasks']} tasks, {result['images']} anonymous RGB images, "
          f"{result['checked_edges']} parent edges")


if __name__ == "__main__":
    main()
