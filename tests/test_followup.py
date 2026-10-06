"""Verify diagnostic truth, strict scoring, bounded inference, and backup recovery."""
from __future__ import annotations

import contextlib
import io
import json
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

from diagnostics import overnight, protocol, run, transfer
from diagnostics.prepare import generate_panel, validate_tasks
from diagnostics.report import summarize
from visdsr import ROOT, canonical, digest


class FollowupTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.frozen, cls.tasks, cls.cases = protocol.load_panel()
        cls.by_id = {task["id"]: task for task in cls.tasks}

    def expected(self, case):
        task = self.by_id[case["task_id"]]
        if case["control"].startswith("extract_"):
            return {"transcription": task["initial"]}
        return protocol.solution(task)

    def fake_provider(self, calls, invalid_case=None, interrupt_after=None):
        answers = {}
        for case in self.cases:
            image = (protocol.PILOT / case["image"]).read_bytes() if case["image"] else None
            raw = "not JSON" if case["case_id"] == invalid_case else canonical(self.expected(case))
            answers[(case["user_prompt"], image)] = raw

        class FakeModel:
            def __init__(self, settings):
                self.settings = settings

            def call_model(self, text, image, settings):
                if interrupt_after is not None and len(calls) == interrupt_after:
                    raise KeyboardInterrupt()
                calls.append((settings["name"], text, image))
                return {"raw_text": answers[(text, image)], "model_id": settings["id"],
                        "revision": settings["revision"], "output_tokens": 100,
                        "hit_output_cap": False, "latency_s": 1.0,
                        "effective_generation_parameters": {"do_sample": False, "num_beams": 1,
                                                            "max_new_tokens": 2048},
                        "input_tensor_shapes": {}, "settings": settings,
                        "gpus": [{"name": "TEST STUB: no GPU inference"}], "gpu_peaks_bytes": [0]}
        return FakeModel

    def test_panel_is_seeded_balanced_fresh_and_independently_verified(self):
        validate_tasks(self.tasks, self.frozen["reference"])
        self.assertEqual(generate_panel(self.frozen["reference"]), self.tasks)
        self.assertEqual(len(self.cases), 48)
        self.assertEqual({case["system_prompt"] for case in self.cases}, {protocol.SYSTEM})
        for case in self.cases:
            if case["control"].startswith("extract_"):
                self.assertNotIn("Operations:", case["user_prompt"])
                self.assertNotIn("Solution to copy:", case["user_prompt"])
            if case["control"] == "copy_solution":
                self.assertIn(canonical(self.expected(case)), case["user_prompt"])
                self.assertIsNone(case["image"])

    def test_correct_answers_and_format_failures_are_distinguished(self):
        for case in self.cases:
            raw = canonical(self.expected(case))
            result = protocol.evaluate(self.by_id[case["task_id"]], case, raw)
            self.assertTrue(result["valid"])
            self.assertTrue(result["correct"])
            for wrapped in ("```json\n" + raw + "\n```", "<think>text</think>" + raw):
                self.assertFalse(protocol.evaluate(self.by_id[case["task_id"]], case, wrapped)["valid"])
        extraction = next(case for case in self.cases if case["control"] == "extract_text")
        raw = canonical(self.expected(extraction))
        duplicated = '{"transcription":{},' + raw[1:]
        self.assertFalse(protocol.evaluate(self.by_id[extraction["task_id"]], extraction, duplicated)["valid"])

    def test_final_map_and_find_result_have_separate_outcomes(self):
        case = next(case for case in self.cases
                    if case["control"] == "update_text" and self.by_id[case["task_id"]]["operations"] == [{"kind": "find", "a": "F"}])
        task = self.by_id[case["task_id"]]
        answer = self.expected(case)
        answer["steps"][0]["find_result"] = "A"
        result = protocol.evaluate(task, case, canonical(answer))
        self.assertTrue(result["final_correct"])
        self.assertFalse(result["full_sequence_correct"])
        self.assertTrue(result["correct"])
        copy_case = {**case, "control": "copy_solution"}
        self.assertFalse(protocol.evaluate(task, copy_case, canonical(answer))["correct"])
        answer["steps"][0]["state"] = task["initial"]
        result = protocol.evaluate(task, case, canonical(answer))
        self.assertTrue(result["valid"])
        self.assertFalse(result["final_correct"])
        self.assertEqual(result["changed_parent_accuracy"], 0)

    def test_resume_budget_and_invalid_answer_retention(self):
        invalid = next(case["case_id"] for case in self.cases if case["control"] == "update_diagram")
        calls = []
        with tempfile.TemporaryDirectory() as directory:
            results = Path(directory) / "results"
            with patch.object(run, "LocalModel", self.fake_provider(calls, invalid)), contextlib.redirect_stdout(io.StringIO()):
                first = run.run("model1", 12, results=results)
                self.assertEqual(first["scored"], 12)
                self.assertEqual(first["gate"], "incomplete")
                run.run("model1", 48, results=results)
                run.run("model2", 48, results=results)
                self.assertEqual(len(calls), 96)
                with patch.object(run, "LocalModel", side_effect=AssertionError("loaded model during scoring")):
                    summary = run.run("model1", score_only=True, results=results)
                self.assertEqual(len(calls), 96)
                self.assertEqual(summary["scored"], 96)
                self.assertEqual(summary["gate"], "pass")
            record = json.loads((results / "cache/model1" / f"{invalid}.json").read_text())
            self.assertEqual(record["response"]["raw_text"], "not JSON")
            score_rows = run.rows_from_records(run.prepared_records(self.frozen, self.tasks, self.cases, protocol.PILOT, results))
            bad = [row for row in score_rows if row["control"] == "update_diagram" and not row["valid"]]
            self.assertEqual(len(bad), 2)
            self.assertFalse((results.parent / "scores_model1.csv").exists())

    def test_corrupted_later_cache_stops_before_filling_an_earlier_gap(self):
        calls = []
        with tempfile.TemporaryDirectory() as directory:
            results = Path(directory) / "results"
            with patch.object(run, "LocalModel", self.fake_provider(calls)), contextlib.redirect_stdout(io.StringIO()):
                run.run("model1", 2, results=results)
                first, second = self.cases[:2]
                (results / "cache/model1" / f"{first['case_id']}.json").unlink()
                path = results / "cache/model1" / f"{second['case_id']}.json"
                record = json.loads(path.read_text())
                record["response"]["raw_text"] = "changed response"
                path.write_text(canonical(record))
                with self.assertRaisesRegex(RuntimeError, "response hash mismatch"):
                    run.run("model1", 2, results=results)
                self.assertEqual(len(calls), 2)

    def test_interruption_exports_completed_responses_and_restore_resumes(self):
        calls = []
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory)
            results = folder / "results"
            backup = folder / "backup.zip"
            with patch.object(run, "LocalModel", self.fake_provider(calls, interrupt_after=1)), contextlib.redirect_stdout(io.StringIO()):
                with self.assertRaises(KeyboardInterrupt):
                    run.run("model1", 12, export=backup, results=results)
            self.assertTrue(backup.is_file())
            restored = folder / "restored"
            self.assertEqual(transfer.restore_backup(backup, results=restored), 1)
            self.assertEqual(transfer.restore_backup(backup, results=restored), 0)
            with patch.object(run, "LocalModel", self.fake_provider(calls)), contextlib.redirect_stdout(io.StringIO()):
                summary = run.run("model1", 1, results=restored)
            self.assertEqual(summary["scored"], 2)
            self.assertEqual(len(calls), 2)
            extracted = folder / "dataset"
            with zipfile.ZipFile(backup) as archive:
                self.assertTrue(all(not item.is_dir() for item in archive.infolist()))
                archive.extractall(extracted)
            self.assertEqual(transfer.restore_backup(extracted, results=folder / "from_dataset"), 1)

    def test_restore_checks_all_conflicts_before_writing(self):
        calls = []
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory)
            source, target = folder / "source", folder / "target"
            backup = folder / "backup.zip"
            with patch.object(run, "LocalModel", self.fake_provider(calls)), contextlib.redirect_stdout(io.StringIO()):
                run.run("model1", 2, export=backup, results=source)
            self.assertEqual(transfer.restore_backup(backup, results=target), 2)
            paths = sorted((target / "cache/model1").glob("*.json"))
            paths[0].unlink()
            paths[1].write_text("conflicting existing response")
            with self.assertRaisesRegex(RuntimeError, "different response already exists"):
                transfer.restore_backup(backup, results=target)
            self.assertFalse(paths[0].exists())

    def test_backup_rejects_traversal_and_corrupted_payloads(self):
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory)
            bad = folder / "bad.zip"
            with zipfile.ZipFile(bad, "w") as archive:
                archive.writestr("../escape", b"payload")
            with self.assertRaisesRegex(RuntimeError, "unsafe"):
                transfer.read_backup(bad)
            with zipfile.ZipFile(bad, "w") as archive:
                archive.writestr("MANIFEST.json", canonical({"protocol_id": protocol.PROTOCOL_ID,
                                                            "files": {"pilot/file": digest(b"correct")}}))
                archive.writestr("pilot/file", b"corrupted")
            with self.assertRaisesRegex(RuntimeError, "checksum"):
                transfer.read_backup(bad)

    def test_gate_cannot_pass_from_success_in_only_easy_cells(self):
        rows = []
        for model in ("model1", "model2"):
            for case in self.cases:
                task = self.by_id[case["task_id"]]
                valid = protocol.evaluate(task, case, canonical(self.expected(case)))
                rows.append({"model": model, "task_id": task["id"], "control": case["control"],
                             "elements": task["n"], "operations": len(task["operations"]),
                             "cap_hit": False, **valid})
        self.assertEqual(summarize(rows)["gate"], "pass")
        for row in rows:
            if row["model"] == "model1" and row["control"] == "update_text" and row["elements"] == 16 and row["operations"] == 4:
                row["correct"] = row["final_correct"] = False
        summary = summarize(rows)
        self.assertEqual(summary["gate"], "fail")
        self.assertEqual(summary["models"]["model1"]["controls"]["update_text"]["correct"], 6)

    def test_concurrent_collection_is_blocked(self):
        with tempfile.TemporaryDirectory() as directory:
            results = Path(directory)
            with run.collection_lock(results), self.assertRaisesRegex(RuntimeError, "another diagnostic batch"):
                run.run("model1", results=results)

    def test_notebook_is_clean_and_missing_configuration_is_actionable(self):
        path = ROOT / "notebooks/dsu_diagnostics_kaggle.ipynb"
        notebook = json.loads(path.read_text())
        for cell in notebook["cells"]:
            if cell["cell_type"] == "code":
                self.assertEqual(cell["outputs"], [])
                self.assertIsNone(cell["execution_count"])
                compile("".join(cell["source"]), str(path), "exec")
        namespace = {}
        with contextlib.redirect_stdout(io.StringIO()):
            exec("".join(notebook["cells"][1]["source"]), namespace)
        self.assertEqual(namespace["COLLECTION_TIME_LIMIT_HOURS"], 7)
        with self.assertRaisesRegex(RuntimeError, "Run Configuration"):
            exec("".join(notebook["cells"][7]["source"]), {})

    def test_overnight_fills_both_panels_and_resume_does_not_load_models(self):
        calls = []
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory)
            results, output = folder / "results", folder / "output"

            def execute(command, **kwargs):
                self.assertEqual(kwargs["cwd"], ROOT)
                self.assertTrue(kwargs["check"])
                self.assertGreater(kwargs["timeout"], 0)
                model = command[command.index("--model") + 1]
                budget = int(command[command.index("--max-new-calls") + 1])
                self.assertEqual(budget, 48)
                export = Path(command[command.index("--export") + 1])
                run.run(model, budget, export=export, results=results)

            with patch.object(overnight, "RESULTS", results), \
                    patch.object(overnight, "score_saved", side_effect=lambda: run.score_saved(results=results)), \
                    patch.object(overnight, "export_backup", side_effect=lambda target: transfer.export_backup(target, results=results)), \
                    patch.object(overnight.subprocess, "run", side_effect=execute) as processes, \
                    patch.object(run, "LocalModel", self.fake_provider(calls)), contextlib.redirect_stdout(io.StringIO()):
                summary = overnight.run_overnight(output)
                self.assertEqual(summary["scored"], 96)
                self.assertEqual(summary["run_status"]["status"], "complete")
                self.assertEqual(processes.call_count, 2)
                self.assertEqual([name for name, _, _ in calls], ["model1"] * 48 + ["model2"] * 48)
                before = len(calls)
                overnight.run_overnight(output)
                self.assertEqual(len(calls), before)
                self.assertEqual(processes.call_count, 2)
            for name in ("qwen_48", "internvl_48", "complete", "backup"):
                self.assertTrue((output / f"visdsr_diagnostics_{name}.zip").is_file())
            restored = folder / "restored"
            self.assertEqual(transfer.restore_backup(output / "visdsr_diagnostics_complete.zip", results=restored), 96)
            self.assertIn("96/96", (restored / "REPORT.md").read_text())
            self.assertIn("copy_solution", (output / "visdsr_diagnostics_report.md").read_text())

    def test_overnight_process_failure_preserves_partial_answers_and_tries_other_model(self):
        calls = []
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory)
            results, output = folder / "results", folder / "output"

            def execute(command, **kwargs):
                model = command[command.index("--model") + 1]
                if model == "model1":
                    run.run(model, 1, results=results)
                    raise overnight.subprocess.CalledProcessError(1, command)
                run.run(model, 48, results=results)

            with patch.object(overnight, "RESULTS", results), \
                    patch.object(overnight, "score_saved", side_effect=lambda: run.score_saved(results=results)), \
                    patch.object(overnight, "export_backup", side_effect=lambda target: transfer.export_backup(target, results=results)), \
                    patch.object(overnight.subprocess, "run", side_effect=execute), \
                    patch.object(run, "LocalModel", self.fake_provider(calls)), contextlib.redirect_stdout(io.StringIO()):
                summary = overnight.run_overnight(output)
            self.assertEqual(summary["scored"], 49)
            self.assertEqual(summary["gate"], "incomplete")
            self.assertEqual(summary["run_status"]["status"], "partial")
            self.assertEqual(len(summary["run_status"]["errors"]), 1)
            self.assertFalse((output / "visdsr_diagnostics_complete.zip").exists())
            self.assertEqual(transfer.restore_backup(output / "visdsr_diagnostics_backup.zip", results=folder / "restored"), 49)

    def test_overnight_timeout_finishes_with_resumable_output(self):
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory)
            results, output = folder / "results", folder / "output"
            with patch.object(overnight, "RESULTS", results), \
                    patch.object(overnight, "score_saved", side_effect=lambda: run.score_saved(results=results)), \
                    patch.object(overnight, "export_backup", side_effect=lambda target: transfer.export_backup(target, results=results)), \
                    patch.object(overnight.subprocess, "run", side_effect=overnight.subprocess.TimeoutExpired("test", 1)), \
                    patch.object(overnight.time, "monotonic", side_effect=(0, 0, 0, 25201, 25201, 25201)), \
                    contextlib.redirect_stdout(io.StringIO()):
                summary = overnight.run_overnight(output)
            self.assertEqual(summary["run_status"]["status"], "partial")
            self.assertEqual(summary["scored"], 0)
            self.assertTrue((output / "visdsr_diagnostics_backup.zip").is_file())
            self.assertFalse((output / "visdsr_diagnostics_complete.zip").exists())


if __name__ == "__main__":
    unittest.main()
