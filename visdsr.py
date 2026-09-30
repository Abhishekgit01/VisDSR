"""Shared paths, configuration, and stable serialization."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent


def config() -> dict:
    return yaml.safe_load((ROOT / "configs/experiment.yaml").read_text())


def canonical(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def read_tasks(split: str) -> list[dict]:
    if split not in ("pilot", "main"):
        raise ValueError("split must be pilot or main")
    path = ROOT / "data" / split / "tasks.jsonl"
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]
