"""Resume diagnostics or reviewed calibration without notebook globals."""
from __future__ import annotations

import argparse
import os
import shutil
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
        raise RuntimeError("Enable a free GPU in Kaggle Session options before running inference")
    for index in range(torch.cuda.device_count()):
        print(f"GPU {index}: {torch.cuda.get_device_name(index)}", flush=True)


def validate_calibration(root: Path) -> None:
    fonts = [Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
             Path("/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf")]
    if shutil.which("dot") is None or not all(path.exists() for path in fonts):
        command(root, "apt-get", "update", "-qq")
        command(root, "apt-get", "install", "-y", "-qq", "graphviz", "fonts-dejavu-core")
    command(root, sys.executable, "-m", "gen.validate", "--split", "pilot2")


def run(root: Path, inputs: Path, export: Path, model: str,
        calibration: bool = False) -> None:
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
        if calibration:
            validate_calibration(root)
            command(root, sys.executable, "-m", "eval.run", "--split", "pilot2",
                    "--model", model, "--after-smoke-review", "--max-new-calls", "20")
            print("STOP: calibration chunk finished; download the refreshed backup before continuing", flush=True)
        else:
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
    parser.add_argument("--calibration", action="store_true",
                        help="resume one reviewed calibration chunk, with at most 20 new calls")
    args = parser.parse_args()
    if not Path("/kaggle/working").exists():
        parser.error("run this recovery script inside a free Kaggle GPU session")
    try:
        run(args.root, args.input, args.export, args.model, args.calibration)
    except (OSError, RuntimeError, subprocess.CalledProcessError) as exc:
        parser.exit(1, f"{exc}\n")


if __name__ == "__main__":
    main()
