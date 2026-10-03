"""Regenerate the reproducibility manifest from local artifacts."""
from __future__ import annotations

import argparse
import datetime
import importlib.metadata
import json
import platform
import subprocess

from visdsr import ROOT, config, digest, protocol_hashes


def command_version(arguments: list[str]) -> str | None:
    try:
        result = subprocess.run(arguments, text=True, capture_output=True, timeout=10, check=True)
        return (result.stdout or result.stderr).splitlines()[0]
    except (FileNotFoundError, subprocess.CalledProcessError, subprocess.TimeoutExpired):
        return None


def git_commit() -> str | None:
    try:
        root = subprocess.check_output(["git", "-C", str(ROOT), "rev-parse", "--show-toplevel"],
                                       text=True, stderr=subprocess.DEVNULL).strip()
        if root != str(ROOT):
            return None
        return subprocess.check_output(["git", "-C", str(ROOT), "rev-parse", "HEAD"],
                                       text=True, stderr=subprocess.DEVNULL).strip()
    except (FileNotFoundError, subprocess.CalledProcessError):
        return None


def build() -> dict:
    main = ROOT / "data/main"
    pilot2 = ROOT / "data/pilot2"
    task_file = main / "tasks.jsonl"
    versions = {}
    for package in ("PyYAML", "Pillow", "matplotlib", "pycodestyle", "torch",
                    "transformers", "accelerate", "bitsandbytes", "huggingface_hub"):
        try:
            versions[package] = importlib.metadata.version(package)
        except importlib.metadata.PackageNotFoundError:
            versions[package] = None
    dates = []
    for path in (ROOT / "results/cache").glob("*.json"):
        try:
            record = json.loads(path.read_text())
            dates.append(record["timestamp_utc"])
        except (ValueError, KeyError):
            continue
    return {
        "generated_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "git_commit": git_commit(),
        "protocol_id": config().get("protocol_id", "visdsr-dsu-v1"),
        "prompt_sha256": digest((ROOT / "eval/prompts.py").read_bytes()),
        "source_hashes": protocol_hashes() if config().get("protocol_version") == 2 else None,
        "config_sha256": digest((ROOT / "configs/experiment.yaml").read_bytes()),
        "model_ids": [model["id"] for model in config()["models"]],
        "run_dates_utc": {"first": min(dates) if dates else None,
                          "last": max(dates) if dates else None},
        "main_tasks_sha256": digest(task_file.read_bytes()) if task_file.exists() else None,
        "pilot2_tasks_sha256": digest((pilot2 / "tasks.jsonl").read_bytes()) if (pilot2 / "tasks.jsonl").exists() else None,
        "pilot2_image_sha256": {path.name: digest(path.read_bytes()) for path in sorted((pilot2 / "img").glob("*.png"))},
        "main_image_sha256": {path.name: digest(path.read_bytes()) for path in sorted((main / "img").glob("*.png"))},
        "run_order_sha256": {split: digest(path.read_bytes()) if path.exists() else None
                             for split in ("pilot", "pilot2", "main")
                             for path in [ROOT / "data" / split / "run_order.csv"]},
        "python_version": platform.python_version(),
        "package_versions": versions,
        "gpp_version": command_version(["g++", "--version"]),
        "graphviz_version": command_version(["dot", "-V"]),
        "freeze_sha256": digest((ROOT / "FREEZE.json").read_bytes()) if (ROOT / "FREEZE.json").exists() else None,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    result = build()
    if args.dry_run:
        print(json.dumps(result, indent=2))
    else:
        target = ROOT / "MANIFEST.json"
        target.write_text(json.dumps(result, indent=2) + "\n")
        print(target)


if __name__ == "__main__":
    main()
