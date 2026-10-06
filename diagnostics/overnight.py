"""Collect both fixed panels in separate processes and preserve partial output."""
from __future__ import annotations

import datetime
import math
import subprocess
import sys
import time
from pathlib import Path

from diagnostics.protocol import RESULTS, write_json
from diagnostics.run import score_saved
from diagnostics.transfer import export_backup
from visdsr import ROOT


def run_overnight(output: Path, time_limit_hours: float = 7) -> dict:
    """A complete panel is successful collection even when its accuracy gate fails."""
    if not math.isfinite(time_limit_hours) or not 0 < time_limit_hours <= 8:
        raise ValueError("choose a collection time limit greater than 0 and at most 8 hours")
    output.mkdir(parents=True, exist_ok=True)
    backup = output / "visdsr_diagnostics_backup.zip"
    started = time.monotonic()
    deadline = started + time_limit_hours * 3600
    status = {"started_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
              "time_limit_hours": time_limit_hours, "errors": [], "status": "running"}
    summary = score_saved()

    def checkpoint() -> None:
        status["elapsed_seconds"] = round(time.monotonic() - started, 2)
        status["scored"] = summary["scored"]
        status["gate"] = summary["gate"]
        write_json(RESULTS / "run_status.json", status)
        for name, visible in (("REPORT.md", "visdsr_diagnostics_report.md"),
                              ("summary.json", "visdsr_diagnostics_summary.json"),
                              ("run_status.json", "visdsr_diagnostics_run_status.json")):
            temporary = output / (visible + ".tmp")
            temporary.write_bytes((RESULTS / name).read_bytes())
            temporary.replace(output / visible)
        export_backup(backup)

    checkpoint()
    try:
        for model, label in (("model1", "qwen"), ("model2", "internvl")):
            if not summary["models"][model]["complete"]:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    status["errors"].append("Collection time limit reached; resume from the backup.")
                    break
                print(f"OVERNIGHT: {label}, filling its 48-response panel", flush=True)
                command = [sys.executable, "-u", "-m", "diagnostics", "run", "--model", model,
                           "--max-new-calls", "48", "--export", str(backup)]
                try:
                    # Blocking subprocesses ensure only one checkpoint occupies GPU memory.
                    subprocess.run(command, cwd=ROOT, check=True, timeout=remaining)
                except subprocess.TimeoutExpired:
                    status["errors"].append(f"{label}: collection time limit reached; unfinished request stopped.")
                except (OSError, subprocess.CalledProcessError) as exc:
                    status["errors"].append(f"{label}: inference process failed: {exc}")
                    print(status["errors"][-1], flush=True)
            summary = score_saved()
            if summary["models"][model]["complete"]:
                target = output / f"visdsr_diagnostics_{label}_48.zip"
                export_backup(target)
                print(f"MODEL BACKUP READY: {target}", flush=True)
            checkpoint()
    finally:
        summary = score_saved()
        status["status"] = "complete" if summary["scored"] == 96 else "partial"
        status["finished_utc"] = datetime.datetime.now(datetime.timezone.utc).isoformat()
        checkpoint()
        if status["status"] == "complete":
            target = output / "visdsr_diagnostics_complete.zip"
            export_backup(target)
            print(f"COLLECTION COMPLETE: 96/96; accuracy gate={summary['gate']}", flush=True)
            print(f"FINAL BACKUP READY: {target}", flush=True)
        else:
            print(f"PARTIAL COLLECTION: {summary['scored']}/96; resume from {backup}", flush=True)
        for error in status["errors"]:
            print(f"RECORDED ERROR: {error}", flush=True)
        print(summary["next_step"], flush=True)
    return {**summary, "run_status": status}
