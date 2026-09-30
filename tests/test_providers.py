"""Network-free checks for the smoke gate and response cache."""
from __future__ import annotations

import csv
import contextlib
import io
import json
import tempfile
import unittest
import zipfile
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from eval import run as runner
from eval.providers import local
from visdsr import config, digest


class FakeModel:
    calls = []

    def __init__(self, settings):
        self.settings = settings
        self.torch = SimpleNamespace(cuda=SimpleNamespace(
            get_device_name=lambda _: "test GPU",
            get_device_properties=lambda _: SimpleNamespace(total_memory=16 * 2**30),
        ))

    def call_model(self, text, image, settings):
        self.calls.append((text, image))
        return {"raw_text": "{}", "latency_s": 1.0,
                "gpu_peak_bytes": 2 * 2**30, "revision": settings["revision"]}


class ProviderTests(unittest.TestCase):
    def test_smoke_caches_three_conditions_and_resumes(self):
        task = {"id": "pilot_test", "split": "pilot", "structure": "dsu", "size": 1,
                "initial": {"A": "A"}, "operations": [{"kind": "find", "a": "A"}],
                "steps": [{"state": {"A": "A"}, "find_result": "A"}]}
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            destination = root / "data/pilot"
            (destination / "img").mkdir(parents=True)
            image = b"placeholder image bytes for the fake model"
            manifest = {"task_id": task["id"], "text_image": "text.png",
                        "diagram_image": "diagram.png", "text_sha256": digest(image),
                        "diagram_sha256": digest(image)}
            for name in ("text.png", "diagram.png"):
                (destination / "img" / name).write_bytes(image)
            with (destination / "manifest.csv").open("w", newline="") as stream:
                writer = csv.DictWriter(stream, fieldnames=list(manifest))
                writer.writeheader()
                writer.writerow(manifest)
            FakeModel.calls = []
            with patch.object(runner, "ROOT", root), \
                    patch.object(runner, "read_tasks", return_value=[task]), \
                    patch.object(runner, "config", side_effect=config), \
                    patch.object(local, "LocalModel", FakeModel):
                with contextlib.redirect_stdout(io.StringIO()):
                    runner.run("pilot", "model1", False, None, False, True, False)
                self.assertEqual(len(FakeModel.calls), 3)
                self.assertIsNone(FakeModel.calls[0][1])
                self.assertIsNotNone(FakeModel.calls[1][1])
                self.assertIsNotNone(FakeModel.calls[2][1])
                archive = root / "results/cache_snapshot.zip"
                with zipfile.ZipFile(archive) as stream:
                    self.assertEqual(len(stream.namelist()), 3)
                with contextlib.redirect_stdout(io.StringIO()):
                    runner.run("pilot", "model1", False, None, False, True, False)
                self.assertEqual(len(FakeModel.calls), 3)
                records = [json.loads(path.read_text()) for path in
                           (root / "results/cache").glob("*.json")]
                self.assertEqual({record["condition"] for record in records},
                                 {"T-dir", "R-dir", "G-dir"})

    def test_full_run_requires_smoke_review(self):
        with patch.object(runner, "read_tasks", return_value=[{"id": "pilot_test"}]), \
                patch.object(runner, "order", return_value=[]):
            with self.assertRaisesRegex(RuntimeError, "review the three-call"):
                runner.run("pilot", "model1", False, None, False, False, False)


if __name__ == "__main__":
    unittest.main()
