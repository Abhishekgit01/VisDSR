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

from PIL import Image

from eval import run as runner
from eval.providers import local
from eval.prompts import SYSTEM
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
    def test_message_content_is_processor_compatible(self):
        image_file = io.BytesIO()
        Image.new("RGB", (2, 2), "white").save(image_file, format="PNG")
        for image in (None, image_file.getvalue()):
            with self.subTest(has_image=image is not None):
                messages = local.model_messages("task prompt", image)
                visuals = [part for message in messages for part in message["content"]
                           if part["type"] in ("image", "video")]
                self.assertEqual(messages[0]["content"], [{"type": "text", "text": SYSTEM}])
                self.assertEqual(messages[1]["content"][-1],
                                 {"type": "text", "text": "task prompt"})
                self.assertEqual(len(visuals), int(image is not None))

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
                with patch.object(local, "LocalModel", side_effect=AssertionError("cached run loaded a model")):
                    with contextlib.redirect_stdout(io.StringIO()):
                        runner.run("pilot", "model1", False, None, False, True, False)
                self.assertEqual(len(FakeModel.calls), 3)
                records = [json.loads(path.read_text()) for path in
                           (root / "results/cache").glob("*.json")]
                self.assertEqual({record["condition"] for record in records},
                                 {"T-dir", "R-dir", "G-dir"})
                second = dict(task, id="pilot2_test", split="pilot2")
                second_dir = root / "data/pilot2"
                (second_dir / "img").mkdir(parents=True)
                for name in ("text.png", "diagram.png"):
                    (second_dir / "img" / name).write_bytes(image)
                second_manifest = dict(manifest, task_id=second["id"])
                with (second_dir / "manifest.csv").open("w", newline="") as stream:
                    writer = csv.DictWriter(stream, fieldnames=list(second_manifest))
                    writer.writeheader()
                    writer.writerow(second_manifest)
                with patch.object(runner, "read_tasks", return_value=[second]):
                    with contextlib.redirect_stdout(io.StringIO()):
                        runner.run("pilot2", "model1", False, None, False, True, False)
                self.assertEqual(len(FakeModel.calls), 6)
                self.assertTrue((root / "results/scores_smoke_model1.csv").exists())
                self.assertTrue((root / "results/scores_pilot2_smoke_model1.csv").exists())
                with patch.object(runner, "read_tasks", return_value=[second]):
                    with contextlib.redirect_stdout(io.StringIO()):
                        runner.run("pilot2", "model2", False, None, False, True, False)
                self.assertEqual(len(FakeModel.calls), 9)
                self.assertTrue((root / "results/scores_pilot2_smoke_model2.csv").exists())
                self.assertEqual(len(list((root / "results/cache").glob("*.json"))), 9)
                with patch.object(runner, "read_tasks", return_value=[second]):
                    for expected_calls, expected_rows in ((10, 4), (11, 5)):
                        with contextlib.redirect_stdout(io.StringIO()):
                            runner.run("pilot2", "model1", False, None, False, False, True,
                                       max_new_calls=1)
                        self.assertEqual(len(FakeModel.calls), expected_calls)
                        with (root / "results/scores_pilot2_model1.csv").open(newline="") as source:
                            self.assertEqual(len(list(csv.DictReader(source))), expected_rows)
                    with patch.object(local, "LocalModel", side_effect=AssertionError("scoring loaded a model")):
                        with contextlib.redirect_stdout(io.StringIO()):
                            runner.run("pilot2", "model1", False, None, True, False, False)
                    output = io.StringIO()
                    with contextlib.redirect_stdout(output):
                        runner.run("pilot2", "model1", True, None, False, False, False)
                    self.assertIn("5 cache entries already present", output.getvalue())

    def test_full_run_requires_smoke_review(self):
        with patch.object(runner, "read_tasks", return_value=[{"id": "pilot_test"}]), \
                patch.object(runner, "order", return_value=[]):
            with self.assertRaisesRegex(RuntimeError, "review the three-call"):
                runner.run("pilot", "model1", False, None, False, False, False)


if __name__ == "__main__":
    unittest.main()
