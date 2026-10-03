"""Check diagnostic controls, bounded calls, and isolation from study scores."""
from __future__ import annotations

import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from eval import diagnose
from tests.naive import simulate
from visdsr import canonical, config, digest


class DiagnosticTests(unittest.TestCase):
    def setUp(self):
        self.task = {"id": "pilot2_test", "split": "pilot2", "structure": "dsu", "size": "small", "n": 8,
                     "prelude": [{"kind": "union", "a": a, "b": b}
                                 for a, b in (("C", "F"), ("D", "E"), ("C", "D"),
                                              ("B", "A"), ("H", "G"), ("B", "H"))],
                     "operations": [{"kind": "find", "a": "E"},
                                    {"kind": "union", "a": "G", "b": "F"},
                                    {"kind": "find", "a": "H"},
                                    {"kind": "union", "a": "D", "b": "C"}]}
        self.task.update(simulate(self.task["n"], self.task["prelude"], self.task["operations"]))
        self.images = {"R-dir": b"text pixels", "G-dir": b"diagram pixels"}
        with patch.object(diagnose, "run_sim", side_effect=simulate):
            self.cases = diagnose.build_cases(self.task, self.images)

    def test_cases_keep_the_forest_and_isolate_state_changes(self):
        self.assertEqual(len(self.cases), 8)
        self.assertEqual(len({case["id"] for case in self.cases}), 8)
        by_id = {case["id"]: case for case in self.cases}
        self.assertEqual(by_id["roots_sizes_T-dir"]["expected"]["sizes"], {"B": 4, "C": 4})
        self.assertEqual(by_id["roots_sizes_T-dir"]["expected"]["roots"]["E"], "C")
        for case in self.cases:
            self.assertEqual(case["task"]["initial"], self.task["initial"])
            self.assertEqual(case["image"], self.images.get(case["condition"]))
            self.assertTrue(diagnose.evaluate(case, canonical(case["expected"]))["diagnostic_correct"])
        find = by_id["find_T-dir"]["expected"]["steps"][0]
        self.assertEqual(find["state"]["E"], "C")
        self.assertEqual(find["find_result"], "C")
        union = by_id["union_T-dir"]["expected"]["steps"][0]
        self.assertEqual(union["state"]["E"], "D")
        self.assertEqual(union["state"]["C"], "B")
        self.assertEqual(union["state"]["G"], "B")

    def test_wrong_content_and_reasoning_preambles_remain_failures(self):
        case = next(case for case in self.cases if case["id"] == "find_T-dir")
        answer = {"steps": [{"op": 1, "state": self.task["initial"], "find_result": "C"}]}
        result = diagnose.evaluate(case, canonical(answer))
        self.assertTrue(result["parse_success"])
        self.assertFalse(result["diagnostic_correct"])
        for raw in ('<think>analysis</think>' + canonical(case["expected"]),
                    '```json\n' + canonical(case["expected"]) + '\n```'):
            self.assertFalse(diagnose.evaluate(case, raw)["parse_success"])

    def test_bounded_resume_preserves_raw_cache_and_never_writes_study_scores(self):
        answers = {(case["prompt"], case["image"]): canonical(case["expected"]) for case in self.cases}
        calls = []

        class FakeModel:
            def __init__(self, settings):
                self.settings = settings

            def call_model(self, text, image, settings):
                calls.append((text, image))
                return {"raw_text": answers[(text, image)], "latency_s": 1.0,
                        "hit_output_cap": False, "model_id": settings["id"],
                        "revision": settings["revision"]}

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            folder = root / "data/pilot2/img"
            folder.mkdir(parents=True)
            mapping = {}
            for condition, column, checksum in (("R-dir", "text_image", "text_sha256"),
                                                ("G-dir", "diagram_image", "diagram_sha256")):
                name = condition + ".png"
                (folder / name).write_bytes(self.images[condition])
                mapping[column] = name
                mapping[checksum] = digest(self.images[condition])
            with patch.object(diagnose, "ROOT", root), \
                    patch.object(diagnose, "config", return_value=config()), \
                    patch.object(diagnose, "read_tasks", return_value=[self.task]), \
                    patch.object(diagnose, "image_mapping", return_value={self.task["id"]: mapping}), \
                    patch.object(diagnose, "run_sim", side_effect=simulate), \
                    patch.object(diagnose, "LocalModel", FakeModel), \
                    patch.object(diagnose, "export_archive") as export, \
                    contextlib.redirect_stdout(io.StringIO()):
                rows = diagnose.run("model1", max_new_calls=2, export=root / "backup.zip")
                self.assertEqual(len(calls), 2)
                self.assertEqual(len(rows), 2)
                self.assertEqual(export.call_count, 3)
                rows = diagnose.run("model1")
                self.assertEqual(len(calls), 8)
                self.assertEqual(len(rows), 8)
                with patch.object(diagnose, "LocalModel", side_effect=AssertionError("scoring loaded a model")):
                    self.assertEqual(len(diagnose.run("model1", score_only=True)), 8)
                record_path = root / "results/diagnostics/model1/find_G-dir.json"
                record = json.loads(record_path.read_text())
                record["user_prompt"] = "changed request"
                record_path.write_text(canonical(record))
                (root / "results/diagnostics/model1/extract_T-dir.json").unlink()
                with self.assertRaisesRegex(RuntimeError, "existing diagnostic request differs"):
                    diagnose.run("model1")
                self.assertEqual(len(calls), 8)
            self.assertFalse((root / "results/cache").exists())
            self.assertEqual(list((root / "results").glob("scores*.csv")), [])
            records = list((root / "results/diagnostics/model1").glob("*.json"))
            self.assertEqual(len(records), 8)


if __name__ == "__main__":
    unittest.main()
