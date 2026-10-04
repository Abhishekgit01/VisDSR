"""Run one frozen main-study chunk without notebook configuration variables."""
from __future__ import annotations

import argparse
import csv
import subprocess
import sys
from pathlib import Path

from notebooks.kaggle_diagnostics import check_gpu, command, validate_calibration


def audit_freeze(root: Path) -> None:
    program = """
from gen.freeze import audit_calibration
from eval.run import image_mapping
from visdsr import ROOT, config, digest, read_tasks, verify_freeze

frozen = verify_freeze()
if (ROOT / "MAIN_DECISION.md").read_text() != frozen["calibration_note"]:
    raise RuntimeError("main decision differs from the reviewed freeze")
for name, checksum in frozen["calibration_files_sha256"].items():
    if digest((ROOT / name).read_bytes()) != checksum:
        raise RuntimeError(f"reviewed calibration payload changed: {name}")
tasks = read_tasks("pilot2")
mapping = image_mapping("pilot2")
summaries = [audit_calibration(model, tasks, mapping) for model in config()["models"]]
if summaries != frozen["calibration_summaries"]:
    raise RuntimeError("calibration differs from the reviewed freeze")
print("Verified frozen sources and both complete calibrations", flush=True)
"""
    command(root, sys.executable, "-c", program)


def run(root: Path, inputs: Path, export: Path, model: str, max_new_calls: int) -> None:
    if type(max_new_calls) is not int or not 1 <= max_new_calls <= 100:
        raise ValueError("choose between 1 and 100 new calls per execution")
    if model not in ("model1", "model2"):
        raise ValueError("model must be model1 or model2")
    if not (root / "FREEZE.json").is_file():
        raise RuntimeError("Pull main to obtain the reviewed FREEZE.json before main execution")
    command(root, sys.executable, "-m", "pip", "install", "-q",
            "--upgrade-strategy", "only-if-needed",
            "-r", str(root / "environment/requirements.txt"),
            "-r", str(root / "environment/requirements-inference.txt"))
    if not (root / "data/pilot2/tasks.jsonl").exists() or not list((root / "results/cache").glob("*.json")):
        command(root, sys.executable, "-m", "study_transfer", "--restore-auto", str(inputs),
                "--require-backup")
    audit_freeze(root)
    try:
        check_gpu()
        command(root, "make", "build")
        validate_calibration(root)
        if not (root / "data/main/tasks.jsonl").exists():
            command(root, sys.executable, "-m", "gen.generate", "--split", "main")
        if not (root / "data/main/manifest.csv").exists():
            command(root, sys.executable, "-m", "gen.render", "--split", "main")
        command(root, sys.executable, "-m", "gen.validate", "--split", "main")
        command(root, sys.executable, "-m", "eval.run", "--split", "main", "--model", model,
                "--dry-run")
        command(root, sys.executable, "-m", "eval.run", "--split", "main", "--model", model,
                "--after-smoke-review", "--max-new-calls", str(max_new_calls))
        with (root / "results" / f"scores_{model}.csv").open(newline="") as source:
            count = len(list(csv.DictReader(source)))
        print(f"MAIN PROGRESS: {count}/400 cached and scored responses for {model}", flush=True)
        if count == 400:
            command(root, sys.executable, "-m", "analysis.analyze", "--split", "main",
                    "--models", model)
        else:
            print("Download this backup before running the next chunk", flush=True)
    finally:
        command(root, sys.executable, "-m", "manifest")
        command(root, sys.executable, "-m", "study_transfer", "--export", str(export))
        print(f"BACKUP READY: {export}; download it from Output", flush=True)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", choices=("model1", "model2"), default="model1")
    parser.add_argument("--max-new-calls", type=int, default=100)
    parser.add_argument("--root", type=Path, default=Path("/kaggle/working/VisDSR_v2"))
    parser.add_argument("--input", type=Path, default=Path("/kaggle/input"))
    parser.add_argument("--export", type=Path, default=Path("/kaggle/working/visdsr_v2_results.zip"))
    args = parser.parse_args()
    if not Path("/kaggle/working").exists():
        parser.error("run this module inside a free Kaggle GPU session")
    try:
        run(args.root, args.input, args.export, args.model, args.max_new_calls)
    except (OSError, ValueError, RuntimeError, subprocess.CalledProcessError) as exc:
        parser.exit(1, f"{exc}\n")


if __name__ == "__main__":
    main()
