"""Check fresh-session restoration and the diagnostic recovery call sequence."""
from __future__ import annotations

import contextlib
import io
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from notebooks import kaggle_diagnostics as recovery


class KaggleRecoveryTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        config = self.root / "configs/experiment.yaml"
        config.parent.mkdir()
        config.write_text("fixture")
        self.inputs = self.root / "input"
        self.export = self.root / "backup.zip"

    def populate_smoke(self):
        tasks = self.root / "data/pilot2/tasks.jsonl"
        tasks.parent.mkdir(parents=True)
        tasks.write_text("fixture")
        cache = self.root / "results/cache/smoke.json"
        cache.parent.mkdir(parents=True)
        cache.write_text("fixture")

    def test_fresh_session_requires_backup_and_checks_smoke_before_inference(self):
        calls = []

        def command(root, *parts):
            calls.append(parts)
            if "--restore-auto" in parts:
                self.populate_smoke()

        with patch.object(recovery, "command", side_effect=command), \
                patch.object(recovery, "check_gpu"), contextlib.redirect_stdout(io.StringIO()):
            recovery.run(self.root, self.inputs, self.export, "model1")
        restore = next(i for i, parts in enumerate(calls) if "--restore-auto" in parts)
        score = next(i for i, parts in enumerate(calls) if "eval.run" in parts)
        inference = next(i for i, parts in enumerate(calls) if "eval.diagnose" in parts)
        self.assertLess(restore, score)
        self.assertLess(score, inference)
        self.assertIn("--require-backup", calls[restore])
        self.assertIn("--score-only", calls[score])
        self.assertIn("--max-new-calls", calls[inference])
        self.assertIn("8", calls[inference])
        self.assertFalse(any("gen.generate" in parts or "gen.render" in parts for parts in calls))

    def test_existing_session_uses_cache_without_overwriting_from_backup(self):
        self.populate_smoke()
        with patch.object(recovery, "command") as command, \
                patch.object(recovery, "check_gpu"), contextlib.redirect_stdout(io.StringIO()):
            recovery.run(self.root, self.inputs, self.export, "model1")
        calls = [call.args[1:] for call in command.call_args_list]
        self.assertFalse(any("--restore-auto" in parts for parts in calls))
        self.assertEqual(sum("eval.diagnose" in parts for parts in calls), 1)

    def test_missing_backup_stops_before_model_call(self):
        calls = []

        def command(root, *parts):
            calls.append(parts)
            if "--restore-auto" in parts:
                raise subprocess.CalledProcessError(1, parts)

        with patch.object(recovery, "command", side_effect=command), \
                patch.object(recovery, "check_gpu"), contextlib.redirect_stdout(io.StringIO()):
            with self.assertRaises(subprocess.CalledProcessError):
                recovery.run(self.root, self.inputs, self.export, "model1")
        self.assertFalse(any("eval.diagnose" in parts for parts in calls))

    def test_interrupted_inference_still_exports_progress(self):
        self.populate_smoke()
        for calibration in (False, True):
            calls = []

            def command(root, *parts):
                calls.append(parts)
                if "eval.diagnose" in parts or "--after-smoke-review" in parts:
                    raise KeyboardInterrupt()

            with self.subTest(calibration=calibration), \
                    patch.object(recovery, "command", side_effect=command), \
                    patch.object(recovery, "check_gpu"), contextlib.redirect_stdout(io.StringIO()):
                with self.assertRaises(KeyboardInterrupt):
                    recovery.run(self.root, self.inputs, self.export, "model1", calibration)
            self.assertIn("manifest", calls[-2])
            self.assertIn("--export", calls[-1])

    def test_calibration_checks_inputs_before_one_bounded_chunk(self):
        self.populate_smoke()
        with patch.object(recovery, "command") as command, \
                patch.object(recovery, "check_gpu"), contextlib.redirect_stdout(io.StringIO()):
            recovery.run(self.root, self.inputs, self.export, "model2", calibration=True)
        calls = [call.args[1:] for call in command.call_args_list]
        score = next(i for i, parts in enumerate(calls) if "--score-only" in parts)
        validation = next(i for i, parts in enumerate(calls) if "gen.validate" in parts)
        inference = next(i for i, parts in enumerate(calls) if "--after-smoke-review" in parts)
        self.assertLess(score, validation)
        self.assertLess(validation, inference)
        self.assertIn("model2", calls[inference])
        self.assertEqual(calls[inference][-2:], ("--max-new-calls", "20"))
        self.assertEqual(calls[inference][calls[inference].index("--split") + 1], "pilot2")
        self.assertEqual(sum("--after-smoke-review" in parts for parts in calls), 1)
        self.assertFalse(any("eval.diagnose" in parts or "gen.generate" in parts or "gen.render" in parts
                             for parts in calls))
        self.assertFalse(any("--restore-auto" in parts for parts in calls))
        self.assertIn("--export", calls[-1])

    def test_calibration_with_missing_smoke_stops_before_inference(self):
        self.populate_smoke()
        calls = []

        def command(root, *parts):
            calls.append(parts)
            if "--score-only" in parts:
                raise subprocess.CalledProcessError(1, parts)

        with patch.object(recovery, "command", side_effect=command), \
                patch.object(recovery, "check_gpu"), contextlib.redirect_stdout(io.StringIO()):
            with self.assertRaises(subprocess.CalledProcessError):
                recovery.run(self.root, self.inputs, self.export, "model2", calibration=True)
        self.assertFalse(any("--after-smoke-review" in parts for parts in calls))

    def test_failed_calibration_validation_exports_without_new_calls(self):
        self.populate_smoke()
        calls = []

        def command(root, *parts):
            calls.append(parts)
            if "gen.validate" in parts:
                raise subprocess.CalledProcessError(1, parts)

        with patch.object(recovery, "command", side_effect=command), \
                patch.object(recovery, "check_gpu"), contextlib.redirect_stdout(io.StringIO()):
            with self.assertRaises(subprocess.CalledProcessError):
                recovery.run(self.root, self.inputs, self.export, "model2", calibration=True)
        self.assertFalse(any("--after-smoke-review" in parts for parts in calls))
        self.assertIn("manifest", calls[-2])
        self.assertIn("--export", calls[-1])


if __name__ == "__main__":
    unittest.main()
