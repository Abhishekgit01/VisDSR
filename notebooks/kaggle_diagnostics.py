"""Resume the bounded diagnostic run without depending on notebook globals."""
from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path


def command(root: Path, *parts: str) -> None:
    subprocess.run(parts, cwd=root, check=True)


def check_gpu() -> None:
    os.environ["USE_TF"] = "0"
    os.environ["USE_TORCH"] = "1"
    import torch
    if not torch.cuda.is_available():
        raise RuntimeError("Enable a free GPU in Kaggle Session options before running diagnostics")
    for index in range(torch.cuda.device_count()):
        print(f"GPU {index}: {torch.cuda.get_device_name(index)}", flush=True)


def run(root: Path, inputs: Path, export: Path, model: str) -> None:
    if not (root / "configs/experiment.yaml").exists():
        raise RuntimeError("VisDSR v2 project files are missing; clone study-v2 before running this script")
    command(root, sys.executable, "-m", "pip", "install", "-q",
            "--upgrade-strategy", "only-if-needed",
            "-r", str(root / "environment/requirements.txt"),
            "-r", str(root / "environment/requirements-inference.txt"))
    check_gpu()
    tasks = root / "data/pilot2/tasks.jsonl"
    if not tasks.exists() or not list((root / "results/cache").glob("*.json")):
        print("Restoring the saved v2 smoke; attach visdsr_v2_results.zip as a private Dataset", flush=True)
        command(root, sys.executable, "-m", "study_transfer", "--restore-auto", str(inputs), "--require-backup")
    else:
        print("Using this session's existing smoke cache", flush=True)
    # Score-only checks the three exact smoke requests and never loads a model.
    command(root, sys.executable, "-m", "eval.run", "--split", "pilot2",
            "--model", model, "--smoke", "--score-only")
    command(root, "make", "build")
    try:
        command(root, sys.executable, "-m", "eval.diagnose", "--model", model,
                "--max-new-calls", "8", "--export", str(export))
    finally:
        command(root, sys.executable, "-m", "manifest")
        command(root, sys.executable, "-m", "study_transfer", "--export", str(export))
        print(f"BACKUP READY: {export}; download it from Output before ending the session", flush=True)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", choices=("model1", "model2"), default="model1")
    parser.add_argument("--root", type=Path, default=Path("/kaggle/working/VisDSR_v2"))
    parser.add_argument("--input", type=Path, default=Path("/kaggle/input"))
    parser.add_argument("--export", type=Path, default=Path("/kaggle/working/visdsr_v2_results.zip"))
    args = parser.parse_args()
    if not Path("/kaggle/working").exists():
        parser.error("run this recovery script inside a free Kaggle GPU session")
    try:
        run(args.root, args.input, args.export, args.model)
    except (OSError, RuntimeError, subprocess.CalledProcessError) as exc:
        parser.exit(1, f"{exc}\n")


if __name__ == "__main__":
    main()
