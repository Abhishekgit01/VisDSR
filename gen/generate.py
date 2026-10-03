"""Seeded DSU task builder. All state transitions come from sim/dsu.cpp."""
from __future__ import annotations

import argparse
import json
import random
import subprocess

from visdsr import ROOT, SPLITS, canonical, config, digest, verify_freeze


def root(state: dict[str, str], label: str) -> tuple[str, int]:
    """Inspect a simulator-produced forest; this never modifies it."""
    seen = set()
    depth = 0
    while state[label] != label:
        if label in seen:
            raise ValueError("cycle in simulator output")
        seen.add(label)
        label = state[label]
        depth += 1
    return label, depth


def run_sim(n: int, prelude: list[dict], operations: list[dict]) -> dict:
    executable = ROOT / "sim/dsu"
    if not executable.exists():
        raise RuntimeError("compile the DSU simulator first: g++ -std=c++17 -O2 -Wall -Wextra -pedantic sim/dsu.cpp -o sim/dsu")
    lines = [f"{n} {len(prelude)} {len(operations)}"]
    for operation in prelude + operations:
        lines.append(f"{'U' if operation['kind'] == 'union' else 'F'} {ord(operation['a']) - 65} {ord(operation.get('b', 'A')) - 65}")
    result = subprocess.run([str(executable)], input="\n".join(lines) + "\n", text=True,
                            capture_output=True, timeout=10, check=False)
    if result.returncode:
        raise RuntimeError(f"sim/dsu failed: {result.stderr.strip()}")
    return json.loads(result.stdout)


def initial_prelude(n: int, rng: random.Random) -> list[dict]:
    labels = list("ABCDEFGHIJKLMNOPQRSTUVWXYZ"[:n])
    rng.shuffle(labels)
    # This construction yields a depth-two tree and at least two other
    # non-singleton trees using only the specified union rule.
    pairs = [(0, 1), (2, 3), (0, 2), (4, 5), (6, 7)]
    for i in range(8, n - 1, 2):
        pairs.append((i, i + 1))
    optional_merges = [(4, 6)] + [(i, i + 2) for i in range(8, n - 3, 4)]
    pairs.extend(pair for pair in optional_merges if rng.random() < 0.5)
    return [{"kind": "union", "a": labels[a], "b": labels[b]} for a, b in pairs]


def choose_operations(initial: dict, length: int, prefer_union: bool,
                      rng: random.Random) -> list[dict]:
    labels = list(initial)
    deep = [x for x in labels if root(initial, x)[1] >= 2]
    if not deep:
        raise ValueError("initial state has no depth-two node")
    different = [(a, b) for a in labels for b in labels if root(initial, a)[0] != root(initial, b)[0]]
    if not different:
        raise ValueError("initial state cannot support a meaningful union")
    if length == 1:
        if prefer_union:
            a, b = rng.choice(different)
            return [{"kind": "union", "a": a, "b": b}]
        return [{"kind": "find", "a": rng.choice(deep)}]
    a, b = rng.choice(different)
    operations = [{"kind": "find", "a": rng.choice(deep)}, {"kind": "union", "a": a, "b": b}]
    for _ in range(length - 2):
        if rng.random() < 0.5:
            operations.append({"kind": "find", "a": rng.choice(labels)})
        else:
            a, b = rng.sample(labels, 2)
            operations.append({"kind": "union", "a": a, "b": b})
    return operations


def metadata(initial: dict, operations: list[dict], steps: list[dict]) -> dict:
    before = initial
    result = {"number_of_unions": 0, "number_of_finds": 0, "no_op_unions": 0,
              "equal_size_ties": 0, "total_parent_changes": 0, "maximum_compressed_path_length": 0}
    for operation, step in zip(operations, steps, strict=True):
        after = step["state"]
        result["total_parent_changes"] += sum(before[x] != after[x] for x in before)
        if operation["kind"] == "find":
            result["number_of_finds"] += 1
            result["maximum_compressed_path_length"] = max(
                result["maximum_compressed_path_length"], root(before, operation["a"])[1])
        else:
            result["number_of_unions"] += 1
            ra, _ = root(before, operation["a"])
            rb, _ = root(before, operation["b"])
            if ra == rb:
                result["no_op_unions"] += 1
            else:
                sa = sum(root(before, x)[0] == ra for x in before)
                sb = sum(root(before, x)[0] == rb for x in before)
                result["equal_size_ties"] += sa == sb
        before = after
    return result


def valid_task(task: dict, length: int) -> bool:
    initial = task["initial"]
    depths = [root(initial, x)[1] for x in initial]
    roots = {root(initial, x)[0] for x in initial}
    large = len(initial) > 8
    non_singletons = sum(sum(root(initial, x)[0] == r for x in initial) > 1 for r in roots)
    if max(depths) < 2 or non_singletons < 2 or (large and len(roots) < 3):
        return False
    meta = task["difficulty"]
    if length == 1:
        return meta["no_op_unions"] == 0 and (
            meta["number_of_unions"] == 1 or meta["maximum_compressed_path_length"] >= 2)
    return all((
        meta["number_of_unions"] > meta["no_op_unions"],
        meta["maximum_compressed_path_length"] >= 2,
        meta["no_op_unions"] <= 1,
    ))


def build(split: str, dry_run: bool = False, limit: int | None = None) -> list[dict]:
    cfg = config()
    rng = random.Random(cfg[f"{split}_seed"])
    dsu = cfg["dsu"]
    if split == "pilot":
        per_cell, lengths = dsu["pilot_tasks_per_cell"], [4]
    elif split == "pilot2":
        per_cell, lengths = dsu["pilot2_tasks_per_cell"], dsu["pilot2_sequence_lengths"]
    else:
        per_cell, lengths = dsu["main_tasks_per_cell"], dsu["sequence_lengths"]
    cells = [("small", dsu["small_size"], count) for count in lengths]
    cells += [("large", dsu["large_size"], count) for count in lengths]
    plan = [{"size": name, "n": n, "operations": count, "tasks": per_cell} for name, n, count in cells]
    if dry_run:
        print(json.dumps({"split": split, "seed": cfg[f"{split}_seed"], "plan": plan}, indent=2))
        return []
    if split == "main":
        if cfg.get("protocol_version") == 2:
            verify_freeze()
        freeze = ROOT / "FREEZE.json"
        if not freeze.exists():
            raise RuntimeError("freeze the calibrated pilot with python -m gen.freeze before main generation")
        frozen = json.loads(freeze.read_text())
        if frozen["config_sha256"] != digest((ROOT / "configs/experiment.yaml").read_bytes()):
            raise RuntimeError("experiment config changed after freeze")
        if frozen["prompt_sha256"] != digest((ROOT / "eval/prompts.py").read_bytes()):
            raise RuntimeError("experiment prompts changed after freeze")
        pilot2 = ROOT / "data/pilot2/tasks.jsonl"
        if not pilot2.exists() or frozen.get("pilot2_tasks_sha256") != digest(pilot2.read_bytes()):
            raise RuntimeError("pilot2 tasks changed or are missing after freeze")
    tasks = []
    signatures = set()
    target = sum(cell["tasks"] for cell in plan)
    for name, n, count in cells:
        for index in range(per_cell):
            if limit is not None and len(tasks) >= limit:
                break
            for _ in range(500):
                prelude = initial_prelude(n, rng)
                initial = run_sim(n, prelude, [])["initial"]
                prefer_union = index % 2 == 0
                if split == "pilot2" and count == 1 and name == "large":
                    prefer_union = not prefer_union
                operations = choose_operations(initial, count, prefer_union, rng)
                truth = run_sim(n, prelude, operations)
                signature = canonical([truth["initial"], operations])
                task = {"id": f"{split}_{len(tasks) + 1:04d}", "split": split,
                        "structure": "dsu", "size": name, "n": n,
                        "prelude": prelude, "initial": truth["initial"],
                        "operations": operations, "steps": truth["steps"]}
                task["difficulty"] = metadata(task["initial"], operations, task["steps"])
                # Each multi-operation calibration size cell includes a tie.
                needs_tie = split == "pilot2" and count > 1 and index == 0
                tie_ok = not needs_tie or task["difficulty"]["equal_size_ties"] > 0
                if signature not in signatures and valid_task(task, count) and tie_ok:
                    signatures.add(signature)
                    tasks.append(task)
                    break
            else:
                raise RuntimeError(f"could not generate {name}/{count} task")
        if limit is not None and len(tasks) >= limit:
            break
    if split == "main" and limit is None and not any(task["difficulty"]["equal_size_ties"] for task in tasks):
        raise RuntimeError("main dataset has no equal-size union tie cases")
    output = ROOT / "data" / split / "tasks.jsonl"
    output.parent.mkdir(parents=True, exist_ok=True)
    for other in SPLITS:
        if other == split:
            continue
        other_path = ROOT / "data" / other / "tasks.jsonl"
        if other_path.exists():
            other_signatures = {canonical([item["initial"], item["operations"]])
                                for item in (json.loads(line) for line in other_path.read_text().splitlines())}
            if signatures & other_signatures:
                raise RuntimeError(f"{split}/{other} task overlap detected")
    output.write_text("".join(canonical(task) + "\n" for task in tasks))
    print(f"wrote {len(tasks)}/{target} {split} tasks to {output}")
    return tasks


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--split", choices=SPLITS, required=True)
    parser.add_argument("--structure", choices=["dsu"], default="dsu")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--limit", type=int)
    args = parser.parse_args()
    if args.limit is not None and args.limit <= 0:
        parser.error("--limit must be positive")
    try:
        build(args.split, args.dry_run, args.limit)
    except RuntimeError as exc:
        parser.exit(1, f"{exc}\n")


if __name__ == "__main__":
    main()
