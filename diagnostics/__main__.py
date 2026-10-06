"""Prepare, verify, collect, score, export, or restore the diagnostic pilot."""
from __future__ import annotations

import argparse
import json
import subprocess
import zipfile
from pathlib import Path

from diagnostics.protocol import PILOT, RESULTS, load_panel


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    prepare = commands.add_parser("prepare", help="maintainer: prepare a new empty input directory")
    prepare.add_argument("--reference-root", type=Path, required=True)
    prepare.add_argument("--folder", type=Path, default=PILOT)
    prepare.add_argument("--font", type=Path)
    prepare.add_argument("--mono", type=Path)
    commands.add_parser("check", help="verify frozen sources, inputs, visual review, and simulator truth")
    run = commands.add_parser("run", help="run a bounded batch using the original pinned checkpoint")
    run.add_argument("--model", choices=("model1", "model2"), required=True)
    run.add_argument("--max-new-calls", type=int, default=12)
    run.add_argument("--score-only", action="store_true")
    run.add_argument("--export", type=Path, required=True)
    overnight = commands.add_parser("overnight", help="collect both models sequentially and export complete or partial output")
    overnight.add_argument("--output-dir", type=Path, required=True)
    overnight.add_argument("--time-limit-hours", type=float, default=7)
    commands.add_parser("score", help="score available caches without loading a model")
    export = commands.add_parser("export", help="create a fresh checksummed diagnostic backup")
    export.add_argument("--output", type=Path, required=True)
    restore = commands.add_parser("restore", help="restore compatible raw caches, preserving existing responses")
    restore.add_argument("--input", type=Path, required=True)
    args = parser.parse_args()
    try:
        if args.command == "prepare":
            from diagnostics.prepare import prepare as build
            result = build(args.reference_root, args.folder, args.font, args.mono)
            print(f"Prepared {result['tasks']} forests and {result['total_requests']} requests; visual review required")
        elif args.command == "check":
            from diagnostics.prepare import validate_tasks
            frozen, tasks, cases = load_panel()
            validate_tasks(tasks, frozen["reference"])
            print(f"Verified diagnostic freeze, 8 independent truths, 16 RGB images, {len(cases)} requests/model, and visual review")
        elif args.command == "run":
            from diagnostics.run import run as collect
            collect(args.model, args.max_new_calls, args.score_only, args.export)
        elif args.command == "overnight":
            from diagnostics.overnight import run_overnight
            run_overnight(args.output_dir, args.time_limit_hours)
        elif args.command == "score":
            from diagnostics.run import score_saved
            summary = score_saved()
            print(f"Scored {summary['scored']}/96 cached responses; gate={summary['gate']}")
            print(summary["next_step"])
        elif args.command == "export":
            from diagnostics.run import score_saved
            from diagnostics.transfer import export_backup
            score_saved()
            export_backup(args.output)
            print(f"BACKUP READY: {args.output}")
        else:
            from diagnostics.transfer import restore_backup
            count = restore_backup(args.input)
            print(f"Restored {count} new cache files; compatible existing responses retained")
    except (OSError, ValueError, RuntimeError, KeyError, zipfile.BadZipFile, subprocess.CalledProcessError) as exc:
        parser.exit(1, f"Diagnostic pilot stopped: {exc}\n")


if __name__ == "__main__":
    main()
