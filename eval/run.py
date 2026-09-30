"""Seeded, cached, independent model requests and exact scoring."""
from __future__ import annotations

import argparse
import csv
import datetime
import json
import random
import time

from eval.prompts import CONDITIONS, prompt
from eval.providers.base import TransientProviderError
from eval.score import score
from visdsr import ROOT, canonical, config, digest, read_tasks


def order(split: str, tasks: list[dict]) -> list[tuple[str, str]]:
    cfg = config()
    path = ROOT / "data" / split / "run_order.csv"
    pairs = [(task["id"], condition) for task in tasks for condition in CONDITIONS]
    random.Random(cfg["run_order_seed"]).shuffle(pairs)
    if path.exists():
        with path.open(newline="") as source:
            recorded = [(row["task_id"], row["condition"]) for row in csv.DictReader(source)]
        if recorded != pairs:
            raise RuntimeError("existing run order differs from current tasks/config")
    else:
        with path.open("w", newline="") as target:
            writer = csv.writer(target)
            writer.writerow(["position", "task_id", "condition"])
            writer.writerows((i, task_id, condition) for i, (task_id, condition) in enumerate(pairs, 1))
    return pairs


def image_mapping(split: str) -> dict[str, dict]:
    with (ROOT / "data" / split / "manifest.csv").open(newline="") as source:
        return {row["task_id"]: row for row in csv.DictReader(source)}


def request_key(model: dict, text: str, image: bytes | None) -> tuple[str, str, str]:
    prompt_hash = digest(text.encode())
    image_hash = digest(image if image is not None else b"")
    key = digest(canonical({"model_id": model["id"], "settings": model,
                            "prompt": text, "image_sha256": image_hash}).encode())
    return key, prompt_hash, image_hash


def call_with_retries(provider: str, text: str, image: bytes | None, model: dict) -> dict:
    if provider == "openai":
        from eval.providers.provider1 import call_model
    elif provider == "anthropic":
        from eval.providers.provider2 import call_model
    else:
        raise ValueError(f"unsupported provider {provider}")
    for retry in range(4):
        try:
            return call_model(text, image, model)
        except TransientProviderError:
            if retry == 3:
                raise
            time.sleep(2 ** retry)
    raise AssertionError("unreachable")


def run(split: str, model_name: str, dry_run: bool, limit: int | None,
        score_only: bool, allow_paid_run: bool) -> None:
    tasks = read_tasks(split)
    by_id = {task["id"]: task for task in tasks}
    if len(by_id) != len(tasks):
        raise ValueError("duplicate task IDs")
    models = {item["name"]: item for item in config()["models"]}
    mock = model_name == "mock"
    if not mock and model_name not in models:
        raise ValueError(f"model must be one of {', '.join(models)} or mock")
    model = {"name": "mock", "id": "mock-oracle", "provider": "mock",
             "temperature": 0, "max_output_tokens": 4096} if mock else models[model_name]
    pairs = order(split, tasks)
    if limit is not None:
        pairs = pairs[:limit]
    if not mock and not model["id"] and not dry_run:
        raise RuntimeError("set an exact model ID in configs/experiment.yaml")
    if not mock and not (dry_run or score_only or allow_paid_run):
        raise RuntimeError("live API calls require --allow-paid-run after DSU validation and pilot calibration")
    mapping = {} if dry_run else image_mapping(split)
    cache_folder = ROOT / "results/cache"
    rows = []
    raw_records = []
    new_calls = 0
    cache_hits = 0
    for task_id, condition in pairs:
        task = by_id[task_id]
        text = prompt(task, condition)
        image = None
        if condition.startswith(("R", "G")) and not dry_run:
            column = "text_image" if condition.startswith("R") else "diagram_image"
            path = ROOT / "data" / split / "img" / mapping[task_id][column]
            image = path.read_bytes()
            expected = mapping[task_id]["text_sha256" if column == "text_image" else "diagram_sha256"]
            if digest(image) != expected:
                raise RuntimeError(f"image hash mismatch: {path}")
        key, prompt_hash, image_hash = request_key(model, text, image)
        cache_path = cache_folder / f"{key}.json"
        if dry_run:
            cache_hits += cache_path.exists()
            continue
        if cache_path.exists():
            record = json.loads(cache_path.read_text())
            if record["task_id"] != task_id or record["condition"] != condition:
                raise RuntimeError(f"cache key collision or stale metadata: {cache_path}")
            cache_hits += 1
        elif score_only:
            raise RuntimeError(f"missing cache for {task_id}/{condition}")
        else:
            if mock:
                answer = {"steps": [{"op": i, **step} for i, step in enumerate(task["steps"], 1)]}
                if condition.endswith("str"):
                    answer["transcription"] = task["initial"]
                result = {"raw_text": canonical(answer), "usage": {}, "latency_s": 0.0}
            else:
                result = call_with_retries(model["provider"], text, image, model)
            record = {"cache_key": key, "task_id": task_id, "split": split, "condition": condition,
                      "model_id": model["id"], "settings": model,
                      "prompt_hash": prompt_hash, "image_hash": image_hash,
                      "timestamp_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
                      **result}
            cache_folder.mkdir(parents=True, exist_ok=True)
            temporary = cache_path.with_suffix(".tmp")
            temporary.write_text(json.dumps(record, indent=2) + "\n")
            temporary.replace(cache_path)
            new_calls += 1
        raw_records.append(record)
        rows.append({"model": model_name, "model_id": model["id"],
                     **score(task, condition, record["raw_text"])})
    if dry_run:
        print(f"{len(pairs)} requests planned, {cache_hits} cache entries already present")
        return
    filename = f"scores_{model_name}.csv" if split == "main" else f"scores_{split}_{model_name}.csv"
    output = ROOT / "results" / filename
    output.parent.mkdir(parents=True, exist_ok=True)
    raw_path = ROOT / "results/raw" / f"{split}_{model_name}.jsonl"
    raw_path.parent.mkdir(parents=True, exist_ok=True)
    raw_path.write_text("".join(canonical(record) + "\n" for record in raw_records))
    with output.open("w", newline="") as target:
        writer = csv.DictWriter(target, fieldnames=list(rows[0]) if rows else [])
        writer.writeheader()
        writer.writerows(rows)
    print(f"scored {len(rows)} requests: {cache_hits} cached, {new_calls} new; {output}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--split", choices=["pilot", "main"], required=True)
    parser.add_argument("--structure", choices=["dsu"], default="dsu")
    parser.add_argument("--model", required=True)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--limit", type=int)
    parser.add_argument("--score-only", action="store_true")
    parser.add_argument("--allow-paid-run", action="store_true")
    args = parser.parse_args()
    if args.limit is not None and args.limit <= 0:
        parser.error("--limit must be positive")
    run(args.split, args.model, args.dry_run, args.limit, args.score_only, args.allow_paid_run)


if __name__ == "__main__":
    main()
