"""Seeded, cached, independent model requests and exact scoring."""
from __future__ import annotations

import argparse
import csv
import datetime
import json
import random
import zipfile

from eval.prompts import CONDITIONS, SYSTEM, prompt
from eval.score import score
from visdsr import ROOT, SPLITS, canonical, config, digest, read_tasks, verify_freeze


def order(split: str, tasks: list[dict]) -> list[tuple[str, str]]:
    cfg = config()
    path = ROOT / "data" / split / "run_order.csv"
    pairs = [(task["id"], condition) for task in tasks for condition in CONDITIONS]
    seed = cfg["pilot2_run_order_seed"] if split == "pilot2" else cfg["run_order_seed"]
    random.Random(seed).shuffle(pairs)
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


def request_key(model: dict, text: str, image: bytes | None,
                task_id: str, condition: str) -> tuple[str, str, str]:
    full_prompt = SYSTEM + "\n" + text
    prompt_hash = digest(full_prompt.encode())
    image_hash = digest(image if image is not None else b"")
    key = digest(canonical({"model_id": model["id"], "settings": model,
                            "task_id": task_id, "condition": condition,
                            "prompt": full_prompt, "image_sha256": image_hash}).encode())
    return key, prompt_hash, image_hash


def snapshot_cache(folder) -> None:
    """Keep a complete cache archive after every successful inference."""
    target = folder.parent / "cache_snapshot.zip"
    temporary = target.with_suffix(".tmp")
    with zipfile.ZipFile(temporary, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(folder.glob("*.json")):
            archive.write(path, path.relative_to(ROOT))
    temporary.replace(target)


def run(split: str, model_name: str, dry_run: bool, limit: int | None,
        score_only: bool, smoke: bool, after_smoke_review: bool,
        max_new_calls: int | None = None) -> None:
    tasks = read_tasks(split)
    by_id = {task["id"]: task for task in tasks}
    if len(by_id) != len(tasks):
        raise ValueError("duplicate task IDs")
    cfg = config()
    models = {item["name"]: item for item in cfg["models"]}
    mock = model_name == "mock"
    if split == "main" and cfg.get("protocol_version") == 2 and not mock:
        verify_freeze()
    if not mock and model_name not in models:
        raise ValueError(f"model must be one of {', '.join(models)} or mock")
    model = {"name": "mock", "id": "mock-oracle", "provider": "mock",
             "do_sample": False, "max_output_tokens": 4096} if mock else models[model_name]
    pairs = order(split, tasks)
    if smoke:
        if split not in ("pilot", "pilot2") or mock:
            raise ValueError("smoke requires pilot or pilot2 split and a local model")
        smoke_task = tasks[0]
        if cfg.get("protocol_version") == 2:
            smoke_task = next((task for task in tasks if len(task["operations"]) == 4), tasks[0])
        pairs = [(smoke_task["id"], condition) for condition in ("T-dir", "R-dir", "G-dir")]
    elif limit is not None:
        pairs = pairs[:limit]
    if not mock and not (dry_run or score_only or smoke or after_smoke_review):
        raise RuntimeError("review the three-call model smoke report before a full evaluation; then pass --after-smoke-review")
    local = None
    mapping = image_mapping(split)
    cache_folder = ROOT / "results/cache"
    rows = []
    raw_records = []
    new_calls = 0
    cache_hits = 0
    deferred = 0
    for position, (task_id, condition) in enumerate(pairs, 1):
        task = by_id[task_id]
        text = prompt(task, condition)
        image = None
        if condition.startswith(("R", "G")):
            column = "text_image" if condition.startswith("R") else "diagram_image"
            path = ROOT / "data" / split / "img" / mapping[task_id][column]
            image = path.read_bytes()
            expected = mapping[task_id]["text_sha256" if column == "text_image" else "diagram_sha256"]
            if digest(image) != expected:
                raise RuntimeError(f"image hash mismatch: {path}")
        key, prompt_hash, image_hash = request_key(model, text, image, task_id, condition)
        cache_path = cache_folder / f"{key}.json"
        if dry_run:
            cache_hits += cache_path.exists()
            continue
        if cache_path.exists():
            from_cache = True
            record = json.loads(cache_path.read_text())
            expected_record = {"cache_key": key, "task_id": task_id, "split": split,
                               "condition": condition, "model_id": model["id"],
                               "prompt_hash": prompt_hash, "image_hash": image_hash}
            if cfg.get("protocol_version") == 2:
                expected_record.update(protocol_id=cfg["protocol_id"],
                                       task_sha256=digest(canonical(task).encode()),
                                       system_prompt=SYSTEM, user_prompt=text)
            if any(record.get(name) != value for name, value in expected_record.items()):
                raise RuntimeError(f"cache key collision or stale metadata: {cache_path}")
            cache_hits += 1
        elif score_only:
            raise RuntimeError(f"missing cache for {task_id}/{condition}")
        else:
            if max_new_calls is not None and new_calls >= max_new_calls:
                deferred += 1
                continue
            from_cache = False
            if mock:
                answer = {"steps": [{"op": i, **step} for i, step in enumerate(task["steps"], 1)]}
                if condition.endswith("str"):
                    answer["transcription"] = task["initial"]
                result = {"raw_text": canonical(answer), "usage": {}, "latency_s": 0.0}
            else:
                if local is None:
                    print(f"Loading {model['id']} on CUDA...", flush=True)
                    from eval.providers.local import LocalModel
                    local = LocalModel(model)
                    print("Model ready; starting requests", flush=True)
                result = local.call_model(text, image, model)
            record = {"cache_key": key, "task_id": task_id, "split": split, "condition": condition,
                      "model_id": model["id"], "settings": model,
                      "prompt_hash": prompt_hash, "image_hash": image_hash,
                      "protocol_id": cfg.get("protocol_id", "visdsr-dsu-v1"),
                      "task_sha256": digest(canonical(task).encode()),
                      "system_prompt": SYSTEM, "user_prompt": text,
                      "timestamp_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
                      **result}
            cache_folder.mkdir(parents=True, exist_ok=True)
            temporary = cache_path.with_suffix(".tmp")
            temporary.write_text(json.dumps(record, indent=2) + "\n")
            temporary.replace(cache_path)
            snapshot_cache(cache_folder)
            new_calls += 1
        print(f"{position}/{len(pairs)} {task_id}/{condition}: "
              f"{'cached' if from_cache else 'saved'}", flush=True)
        raw_records.append(record)
        rows.append({"model": model_name, "model_id": model["id"],
                     **score(task, condition, record["raw_text"])})
    if dry_run:
        print(f"{len(pairs)} requests planned, {cache_hits} cache entries already present")
        return
    if not rows:
        print(f"No responses scored; {deferred} requests deferred")
        return
    smoke_tag = "smoke" if split == "pilot" else "pilot2_smoke"
    filename = (f"scores_{smoke_tag}_{model_name}.csv" if smoke else
                f"scores_{model_name}.csv" if split == "main" else f"scores_{split}_{model_name}.csv")
    output = ROOT / "results" / filename
    output.parent.mkdir(parents=True, exist_ok=True)
    raw_path = ROOT / "results/raw" / f"{smoke_tag if smoke else split}_{model_name}.jsonl"
    raw_path.parent.mkdir(parents=True, exist_ok=True)
    raw_path.write_text("".join(canonical(record) + "\n" for record in raw_records))
    with output.open("w", newline="") as target:
        writer = csv.DictWriter(target, fieldnames=list(rows[0]) if rows else [])
        writer.writeheader()
        writer.writerows(rows)
    print(f"scored {len(rows)}/{len(pairs)} requests: {cache_hits} cached, "
          f"{new_calls} new, {deferred} deferred; {output}")
    if smoke and len(raw_records) == len(pairs):
        print_smoke(model, by_id, raw_records)


def print_smoke(model: dict, tasks: dict, records: list[dict]) -> None:
    from eval.validate import FormatError, parse
    print("VISDSR THREE-CALL SMOKE TEST")
    print(f"Model: {model['id']}")
    print(f"Revision: {model['revision']}")
    print("Hardware:", records[0].get("gpus", "not recorded"))
    print("Quantization:", model["quantization"])
    print(f"Generation settings: do_sample=False, num_beams=1, max_new_tokens={model['max_output_tokens']}")
    findings = []
    for record in records:
        try:
            parse(record["raw_text"], tasks[record["task_id"]], record["condition"])
            parsed = True
        except FormatError as exc:
            parsed = False
            findings.append(f"{record['condition']}: {exc}")
        if record.get("hit_output_cap"):
            findings.append(f"{record['condition']}: reached output-token cap")
        result = score(tasks[record["task_id"]], record["condition"], record["raw_text"])
        print(f"{record['condition']} task={record['task_id']}: parse={parsed}, "
              f"correct={bool(result['final_correct'])}, latency_s={record['latency_s']:.2f}, "
              f"peak_VRAM_GiB={record['gpu_peak_bytes'] / 2**30:.2f}")
        print("Input/output tokens:", record.get("input_tokens"), record.get("output_tokens"))
        print("response:", record["raw_text"])
    average = sum(record["latency_s"] for record in records) / len(records)
    print(f"Average latency: {average:.2f} s")
    print(f"Peak VRAM: {max(record['gpu_peak_bytes'] for record in records) / 2**30:.2f} GiB")
    print(f"Rough 60-call extrapolation: {average:.2f} min, excluding loading")
    print(f"Rough 400-call extrapolation: {average * 400 / 60:.2f} min, excluding loading")
    print("These extrapolations omit measured structured-condition latency; refine them after calibration.")
    print("Problems:", "; ".join(findings) if findings else "no format or output-cap problems observed")
    print("STOP: review and export this smoke before enabling calibration.")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--split", choices=SPLITS, required=True)
    parser.add_argument("--structure", choices=["dsu"], default="dsu")
    parser.add_argument("--model", required=True)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--limit", type=int)
    parser.add_argument("--max-new-calls", type=int,
                        help="cache at most this many new responses; score existing cached responses too")
    parser.add_argument("--score-only", action="store_true")
    parser.add_argument("--smoke", action="store_true", help="run one task in T-dir, R-dir, and G-dir only")
    parser.add_argument("--after-smoke-review", action="store_true")
    args = parser.parse_args()
    if args.limit is not None and args.limit <= 0:
        parser.error("--limit must be positive")
    if args.max_new_calls is not None and args.max_new_calls <= 0:
        parser.error("--max-new-calls must be positive")
    if args.max_new_calls is not None and (args.score_only or args.dry_run):
        parser.error("--max-new-calls is only for inference runs")
    run(args.split, args.model, args.dry_run, args.limit, args.score_only,
        args.smoke, args.after_smoke_review, args.max_new_calls)


if __name__ == "__main__":
    main()
