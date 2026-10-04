"""Exercise main-study gates and interruption exports without inference."""
from __future__ import annotations

import contextlib
import io
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from notebooks import kaggle_main


class KaggleMainTests(unittest.TestCase):
    def test_missing_freeze_stops_before_installation(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            with patch.object(kaggle_main, "command") as command:
                with self.assertRaisesRegex(RuntimeError, "FREEZE.json"):
                    kaggle_main.run(root, root / "input", root / "backup.zip", "model1", 100)
                command.assert_not_called()

    def test_invalid_chunk_limit_stops_before_installation(self):
        with patch.object(kaggle_main, "command") as command:
            for limit in (0, 101, True):
                with self.subTest(limit=limit), self.assertRaises(ValueError):
                    kaggle_main.run(Path("unused"), Path("unused"), Path("unused"), "model1", limit)
            command.assert_not_called()

    def test_failed_calibration_audit_prevents_gpu_and_main_calls(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / "FREEZE.json").write_text("{}")
            with patch.object(kaggle_main, "command") as command, \
                    patch.object(kaggle_main, "check_gpu") as gpu, \
                    patch.object(kaggle_main, "audit_freeze", side_effect=RuntimeError("stale cache")):
                with self.assertRaisesRegex(RuntimeError, "stale cache"):
                    kaggle_main.run(root, root / "input", root / "backup.zip", "model1", 100)
                gpu.assert_not_called()
                self.assertFalse(any("eval.run" in call.args for call in command.call_args_list))

    def test_interrupted_main_chunk_still_exports(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / "FREEZE.json").write_text("{}")
            calls = []

            def command(project, *parts):
                calls.append(parts)
                if "--after-smoke-review" in parts:
                    raise KeyboardInterrupt()

            with patch.object(kaggle_main, "command", side_effect=command), \
                    patch.object(kaggle_main, "check_gpu"), \
                    patch.object(kaggle_main, "validate_calibration"), \
                    patch.object(kaggle_main, "audit_freeze"), \
                    contextlib.redirect_stdout(io.StringIO()):
                with self.assertRaises(KeyboardInterrupt):
                    kaggle_main.run(root, root / "input", root / "backup.zip", "model1", 100)
            self.assertTrue(any("manifest" in parts for parts in calls))
            self.assertIn((kaggle_main.sys.executable, "-m", "study_transfer", "--export",
                           str(root / "backup.zip")), calls)


if __name__ == "__main__":
    unittest.main()
