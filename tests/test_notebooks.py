"""Check Kaggle notebook stage guards and backup behavior without GPU inference."""
from __future__ import annotations

import contextlib
import io
import json
import unittest

import visdsr


class NotebookTests(unittest.TestCase):
    def notebooks(self):
        return [visdsr.ROOT / "notebooks" / name for name in
                ("qwen3_vl_v2_kaggle.ipynb", "internvl35_v2_kaggle.ipynb")]

    def test_defaults_execute_only_smoke_and_export(self):
        for path in self.notebooks():
            with self.subTest(notebook=path.name):
                notebook = json.loads(path.read_text())
                for cell in notebook["cells"]:
                    if cell["cell_type"] == "code":
                        self.assertEqual(cell["outputs"], [])
                        self.assertIsNone(cell["execution_count"])
                        compile("".join(cell["source"]), str(path), "exec")
                namespace = {}
                with contextlib.redirect_stdout(io.StringIO()):
                    exec("".join(notebook["cells"][1]["source"]), namespace)
                self.assertEqual(namespace["STAGE"], "smoke")
                self.assertFalse(namespace["SMOKE_REVIEWED"])
                self.assertFalse(namespace["MAIN_APPROVED"])
                calls = []
                exports = []
                namespace.update(run_command=lambda *args: calls.append(args),
                                 export_results=lambda: exports.append(True),
                                 sys=__import__("sys"))
                with contextlib.redirect_stdout(io.StringIO()):
                    exec("".join(notebook["cells"][9]["source"]), namespace)
                self.assertEqual(len(calls), 1)
                self.assertIn("--smoke", calls[0])
                self.assertNotIn("--after-smoke-review", calls[0])
                self.assertEqual(exports, [True])

    def test_unreviewed_calibration_stops_in_configuration(self):
        for path in self.notebooks():
            notebook = json.loads(path.read_text())
            source = "".join(notebook["cells"][1]["source"])
            source = source.replace('STAGE = "smoke"', 'STAGE = "calibration"')
            with self.subTest(notebook=path.name), self.assertRaisesRegex(RuntimeError, "Review"):
                exec(source, {})

    def test_interruption_still_attempts_export(self):
        for path in self.notebooks():
            notebook = json.loads(path.read_text())
            namespace = {}
            with contextlib.redirect_stdout(io.StringIO()):
                exec("".join(notebook["cells"][1]["source"]), namespace)
            exports = []

            def interrupt(*args):
                raise KeyboardInterrupt()

            namespace.update(run_command=interrupt, export_results=lambda: exports.append(True),
                             sys=__import__("sys"))
            with self.subTest(notebook=path.name), contextlib.redirect_stdout(io.StringIO()):
                with self.assertRaises(KeyboardInterrupt):
                    exec("".join(notebook["cells"][9]["source"]), namespace)
                self.assertEqual(exports, [True])


if __name__ == "__main__":
    unittest.main()
