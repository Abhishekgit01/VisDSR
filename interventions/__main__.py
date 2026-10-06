"""Verify, collect, score, export, or restore the fixed improvement comparison."""
from __future__ import annotations

import argparse
import os
import subprocess
import zipfile
from pathlib import Path

from interventions.protocol import load_protocol


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("check")
    commands.add_parser("decoder-check")
    commands.add_parser("score")
    overnight = commands.add_parser("overnight")
    overnight.add_argument("--output-dir", type=Path, required=True)
    overnight.add_argument("--sequential", action="store_true")
    worker = commands.add_parser("worker", help="internal subprocess; use overnight")
    worker.add_argument("--model", choices=("model1", "model2"), required=True)
    worker.add_argument("--output-dir", type=Path, required=True)
    restore = commands.add_parser("restore")
    restore.add_argument("--input", type=Path, required=True)
    export = commands.add_parser("export")
    export.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        load_protocol()
        if args.command == "check":
            print("Verified separate intervention freeze: 96 controls + 96 improvement calls; no task simplification")
        elif args.command == "decoder-check":
            from interventions.provider import decoder_check
            decoder_check()
        elif args.command == "overnight":
            from interventions.overnight import run_job
            run_job(args.output_dir, not args.sequential)
        elif args.command == "worker":
            if os.environ.get("VISDSR_IMPROVEMENT_WORKER") != "1":
                raise RuntimeError("workers require the overnight parent and its cache locks")
            from interventions.run import collect
            collect(args.model, args.output_dir)
        elif args.command == "restore":
            from interventions.transfer import restore_backup
            restore_backup(args.input)
        else:
            from interventions.report import score
            summary = score()
            print(f"Saved {summary['saved']}/192; complete={summary['complete']}")
            if args.command == "export":
                from interventions.transfer import export_backup
                export_backup(args.output)
    except (OSError, RuntimeError, ValueError, KeyError, zipfile.BadZipFile, subprocess.CalledProcessError) as exc:
        parser.exit(1, f"Improvement comparison stopped: {exc}\n")


if __name__ == "__main__":
    main()
