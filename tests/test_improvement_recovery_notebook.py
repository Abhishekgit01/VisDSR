"""Prevent the recovery notebook from launching costly interactive collection."""
from __future__ import annotations

import contextlib
import io
import json
import os
import unittest
from unittest.mock import patch

from visdsr import ROOT


class ImprovementRecoveryNotebookTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.path = ROOT / "notebooks/visdsr_improvements_recovery.ipynb"
        cls.notebook = json.loads(cls.path.read_text())

    def test_configuration_rejects_interactive_and_unknown_run_modes(self):
        code = "".join(self.notebook["cells"][1]["source"])
        for mode in ("Interactive", ""):
            with self.subTest(mode=mode), \
                    patch.dict(os.environ, {"KAGGLE_KERNEL_RUN_TYPE": mode}), \
                    contextlib.redirect_stdout(io.StringIO()):
                with self.assertRaisesRegex(RuntimeError, "Save Version > Save & Run All"):
                    exec(code, {})

    def test_saved_configuration_has_fixed_source_and_no_time_cutoff(self):
        namespace = {}
        with patch.dict(os.environ, {"KAGGLE_KERNEL_RUN_TYPE": "Batch"}), \
                contextlib.redirect_stdout(io.StringIO()):
            exec("".join(self.notebook["cells"][1]["source"]), namespace)
        self.assertEqual(namespace["SOURCE_COMMIT"], "9b4d02bb189b66daf2ec99790270f0f481301247")
        self.assertTrue(namespace["PARALLEL_MODELS"])
        self.assertEqual(namespace["BACKUP_INPUT"], "auto")
        self.assertNotIn("COLLECTION_TIME_LIMIT_HOURS", namespace)

    def test_collection_rejects_interactive_even_if_configuration_was_skipped(self):
        code = "".join(self.notebook["cells"][5]["source"])
        with patch.dict(os.environ, {"KAGGLE_KERNEL_RUN_TYPE": "Interactive"}), \
                patch("subprocess.run") as command, contextlib.redirect_stdout(io.StringIO()):
            with self.assertRaisesRegex(RuntimeError, "Save Version > Save & Run All"):
                exec(code, {"PARALLEL_MODELS": True})
        command.assert_not_called()

    def test_setup_rejects_interactive_before_installing_or_cloning(self):
        code = "".join(self.notebook["cells"][3]["source"])
        for mode in ("Interactive", ""):
            with self.subTest(mode=mode), \
                    patch.dict(os.environ, {"KAGGLE_KERNEL_RUN_TYPE": mode}), \
                    patch("subprocess.run") as command, contextlib.redirect_stdout(io.StringIO()):
                with self.assertRaisesRegex(RuntimeError, "Save Version > Save & Run All"):
                    exec(code, {})
                command.assert_not_called()

    def test_saved_setup_reports_missing_configuration_before_running_commands(self):
        code = "".join(self.notebook["cells"][3]["source"])
        with patch.dict(os.environ, {"KAGGLE_KERNEL_RUN_TYPE": "Batch"}), \
                patch("pathlib.Path.is_dir", return_value=True), \
                patch("subprocess.run") as command, contextlib.redirect_stdout(io.StringIO()):
            with self.assertRaisesRegex(RuntimeError, "check its Log for the first error"):
                exec(code, {})
        command.assert_not_called()

    def test_export_reports_missing_collection_without_writing_or_exporting(self):
        code = "".join(self.notebook["cells"][7]["source"])
        with patch("pathlib.Path.is_file", return_value=False), \
                patch("pathlib.Path.read_text") as read, \
                patch("pathlib.Path.write_text") as write, patch("subprocess.run") as command:
            with self.assertRaisesRegex(RuntimeError, "No collection status is available to export"):
                exec(code, {})
        read.assert_not_called()
        write.assert_not_called()
        command.assert_not_called()

    def test_saved_collection_launches_existing_protocol_with_parallel_defaults(self):
        with patch.dict(os.environ, {"KAGGLE_KERNEL_RUN_TYPE": "Batch"}), \
                patch("subprocess.run") as command, contextlib.redirect_stdout(io.StringIO()):
            exec("".join(self.notebook["cells"][5]["source"]), {"PARALLEL_MODELS": True})
        command.assert_called_once()
        self.assertIn("interventions", command.call_args.args[0])
        self.assertIn("overnight", command.call_args.args[0])
        self.assertNotIn("--sequential", command.call_args.args[0])
        self.assertEqual(str(command.call_args.kwargs["cwd"]), "/kaggle/working/VisDSR_improvements_recovery")

    def test_notebook_cells_have_clean_outputs_and_valid_python(self):
        for cell in self.notebook["cells"]:
            if cell["cell_type"] == "code":
                self.assertEqual(cell["outputs"], [])
                self.assertIsNone(cell["execution_count"])
                compile("".join(cell["source"]), str(self.path), "exec")


if __name__ == "__main__":
    unittest.main()
