"""Run both checkpoints on separate T4s, with a sequential single-GPU fallback."""
from __future__ import annotations

import datetime
import os
import subprocess
import sys
import time
from pathlib import Path

from diagnostics.protocol import RESULTS as DIAGNOSTIC_RESULTS, write_json
from diagnostics.run import collection_lock, score_saved
from interventions.protocol import RESULTS
from interventions.report import score
from interventions.transfer import export_backup
from visdsr import ROOT


def run_job(output: Path, parallel: bool = True) -> dict:
    with collection_lock(RESULTS), collection_lock(DIAGNOSTIC_RESULTS):
        return collect_job(output, parallel)


def collect_job(output: Path, parallel: bool) -> dict:
    output.mkdir(parents=True, exist_ok=True)
    initial = score()
    started = time.monotonic()
    query = subprocess.run([sys.executable, "-c", "import torch; print(torch.cuda.device_count())"],
                           capture_output=True, text=True, check=True)
    count = int(query.stdout.strip())
    if count == 0 and not initial["complete"]:
        raise RuntimeError("enable a CUDA GPU")
    simultaneous = parallel and count >= 2
    status = {"started_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
              "stop_condition": "fixed 192-response panel completed", "parallel_models": simultaneous,
              "errors": [], "status": "running"}
    write_json(RESULTS / "run_status.json", status)
    processes = []

    def start(model: str, device: int) -> subprocess.Popen:
        env = {**os.environ, "CUDA_VISIBLE_DEVICES": str(device), "VISDSR_IMPROVEMENT_WORKER": "1",
               "USE_TF": "0", "USE_TORCH": "1"}
        command = [sys.executable, "-u", "-m", "interventions", "worker", "--model", model,
                   "--output-dir", str(output)]
        print(f"STARTING {model} on GPU {device}: 96 planned responses, one model load", flush=True)
        child = subprocess.Popen(command, cwd=ROOT, env=env)
        processes.append(child)
        return child

    def finish(child: subprocess.Popen, model: str) -> None:
        code = child.wait()
        if code:
            status["errors"].append(f"{model} exited with code {code}; completed answers retained.")

    try:
        if not initial["complete"]:
            if simultaneous:
                first = start("model1", 0)
                second = start("model2", 1)
                finish(first, "model1")
                finish(second, "model2")
            else:
                for model in ("model1", "model2"):
                    finish(start(model, 0), model)
    finally:
        for child in processes:
            if child.poll() is None:
                child.kill()
                child.wait()
        score_saved()
        summary = score()
        status.update({"status": "complete" if summary["complete"] else "partial",
                       "saved": summary["saved"], "elapsed_seconds": round(time.monotonic() - started, 2),
                       "finished_utc": datetime.datetime.now(datetime.timezone.utc).isoformat()})
        write_json(RESULTS / "run_status.json", status)
        backup = output / "visdsr_improvements_backup.zip"
        export_backup(backup)
        if summary["complete"]:
            export_backup(output / "visdsr_improvements_complete.zip")
        for name in ("REPORT.md", "summary.json", "run_status.json"):
            (output / ("visdsr_improvements_" + name)).write_bytes((RESULTS / name).read_bytes())
        print(f"FINAL STATUS: {status['status']}; {summary['saved']}/192 saved", flush=True)
        for error in status["errors"]:
            print("RECORDED ERROR: " + error, flush=True)
        print(f"BACKUP READY: {backup}; inspect the saved version's Output", flush=True)
    return summary
