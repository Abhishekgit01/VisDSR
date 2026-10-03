"""Shared paths, configuration, and stable serialization."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent
SPLITS = ("pilot", "pilot2", "main")
STUDY_SOURCE_FILES = (
    "configs/experiment.yaml", "configs/v2_tasks.json", "sim/dsu.cpp", "STUDY_V2.md",
    "environment/requirements.txt", "environment/requirements-inference.txt",
    "visdsr.py", "gen/generate.py", "gen/render.py", "gen/visual_checks.py",
    "gen/validate.py", "gen/freeze.py", "study_transfer.py", "manifest.py",
    "eval/prompts.py", "eval/providers/local.py",
    "eval/run.py", "eval/score.py", "eval/validate.py",
    "analysis/stats.py", "analysis/analyze.py",
)


def config() -> dict:
    return yaml.safe_load((ROOT / "configs/experiment.yaml").read_text())


def canonical(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def protocol_hashes() -> dict[str, str]:
    return {name: digest((ROOT / name).read_bytes()) for name in STUDY_SOURCE_FILES}


def verify_freeze() -> dict:
    path = ROOT / "FREEZE.json"
    if not path.exists():
        raise RuntimeError("freeze the reviewed calibration before any main run")
    record = json.loads(path.read_text())
    if record.get("protocol_id") != config().get("protocol_id"):
        raise RuntimeError("freeze belongs to a different protocol")
    if record.get("source_hashes") != protocol_hashes():
        raise RuntimeError("study source changed after freeze")
    tasks = ROOT / "data/pilot2/tasks.jsonl"
    if not tasks.exists() or record.get("pilot2_tasks_sha256") != digest(tasks.read_bytes()):
        raise RuntimeError("calibration tasks changed after freeze")
    return record


def read_tasks(split: str) -> list[dict]:
    if split not in SPLITS:
        raise ValueError(f"split must be one of {', '.join(SPLITS)}")
    path = ROOT / "data" / split / "tasks.jsonl"
    contents = path.read_bytes()
    if config().get("protocol_version") == 2:
        expected = json.loads((ROOT / "configs/v2_tasks.json").read_text()).get(split)
        if expected is not None and digest(contents) != expected:
            raise ValueError(f"{split} tasks do not match the v2 seed; do not reuse an older export")
    return [json.loads(line) for line in contents.decode().splitlines() if line.strip()]
