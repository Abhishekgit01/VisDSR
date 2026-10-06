"""Verify matched interventions, predicted-forest execution, and combined recovery."""
from __future__ import annotations

import contextlib
import importlib.util
import io
import json
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

import diagnostics.protocol as diagnostic
import diagnostics.run as diagnostic_run
import diagnostics.transfer as diagnostic_transfer
from interventions import executor, overnight, protocol, provider, report, run, transfer
from tests.naive import simulate
from visdsr import ROOT, canonical


class InterventionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.frozen, cls.tasks, cls.cases = protocol.load_protocol()

    @contextlib.contextmanager
    def isolated(self, directory):
        result = Path(directory) / "results"
        baseline = Path(directory) / "diagnostics"
        with contextlib.ExitStack() as stack:
            for module in (run, report, transfer, overnight):
                stack.enter_context(patch.object(module, "RESULTS", result))
            for module in (run, overnight):
                stack.enter_context(patch.object(module, "DIAGNOSTIC_RESULTS", baseline))
            stack.enter_context(patch.object(transfer, "export_diagnostics",
                                             side_effect=lambda path: diagnostic_transfer.export_backup(path, results=baseline)))
            stack.enter_context(patch.object(transfer, "restore_diagnostics",
                                             side_effect=lambda path: diagnostic_transfer.restore_backup(path, results=baseline)))
            stack.enter_context(patch.object(overnight, "score_saved",
                                             side_effect=lambda: diagnostic_run.score_saved(results=baseline)))
            yield result, baseline

    def fake_provider(self, calls, loads, bad_procedure=False):
        class FakeModel:
            def __init__(self, settings):
                loads.append(settings["name"])

            def answer(self, case, task, image, settings):
                calls.append((settings["name"], case["case_id"]))
                if case["control"].startswith("extract_"):
                    answer = {"transcription": task["initial"]}
                else:
                    answer = diagnostic.solution(task)
                raw = canonical(answer)
                if bad_procedure and case.get("arm") == "procedure":
                    raw = "TEST STUB: invalid answer retained"
                return {"raw_text": raw, "model_id": settings["id"], "revision": settings["revision"],
                        "output_tokens": 100, "hit_output_cap": False, "latency_s": 1.0,
                        "effective_generation_parameters": {"do_sample": False, "num_beams": 1, "max_new_tokens": 2048},
                        "input_tensor_shapes": {}, "settings": settings,
                        "gpus": [{"name": "TEST STUB: no inference"}], "gpu_peaks_bytes": [0],
                        "grammar_version": "0.2.8" if case.get("grammar") else None}
        return FakeModel

    def test_matched_prompts_and_original_panel_are_preserved(self):
        _, original_tasks, original_cases = diagnostic.load_panel()
        self.assertEqual(self.tasks, original_tasks)
        self.assertEqual(len(self.cases), 48)
        by_id = {case["case_id"]: case for case in original_cases}
        for case in self.cases:
            original = by_id[case["case_id"].rsplit("__", 1)[0]]
            self.assertEqual(case["image"], original["image"])
            self.assertEqual(case["system_prompt"], original["system_prompt"])
            if case["arm"] == "grammar":
                self.assertEqual(case["user_prompt"], original["user_prompt"])
            else:
                self.assertEqual(case["user_prompt"], original["user_prompt"] + "\n\n" + protocol.PROCEDURE)
        self.assertEqual({case["arm"] for case in self.cases}, {"grammar", "procedure", "combined"})

    def test_executor_matches_independent_truth_and_rejects_cycles(self):
        for task in self.tasks:
            expected = simulate(task["n"], task["prelude"], task["operations"])
            answer = executor.execute(task["initial"], list(task["initial"]), task["operations"])
            self.assertEqual(answer, diagnostic.solution({"steps": expected["steps"]}))
        with self.assertRaisesRegex(ValueError, "cycle"):
            executor.execute({"A": "B", "B": "A"}, ["A", "B"], [{"kind": "find", "a": "A"}])
        with self.assertRaisesRegex(ValueError, "labels"):
            executor.execute({"A": "Z"}, ["A"], [{"kind": "find", "a": "A"}])
        predicted = {"A": "A", "B": "B", "C": "C"}
        answer = executor.execute(predicted, list(predicted), [{"kind": "union", "a": "B", "b": "C"}])
        self.assertEqual(answer["steps"][0]["state"], {"A": "A", "B": "B", "C": "B"})
        self.assertEqual(predicted, {"A": "A", "B": "B", "C": "C"})

    def test_one_load_per_model_resume_pairing_and_assisted_outputs(self):
        calls, loads = [], []
        with tempfile.TemporaryDirectory() as directory, self.isolated(directory), \
                patch.object(provider, "InterventionModel", self.fake_provider(calls, loads, bad_procedure=True)), \
                contextlib.redirect_stdout(io.StringIO()):
            output = Path(directory) / "output"
            run.collect("model1", output)
            run.collect("model2", output)
            summary = report.score()
            self.assertEqual(len(calls), 192)
            self.assertEqual(loads, ["model1", "model2"])
            self.assertEqual(summary["saved"], 192)
            self.assertTrue(summary["complete"])
            for row in summary["comparisons"]:
                self.assertEqual(row["paired"], 8)
                self.assertEqual(row["lost"], 8 if row["arm"] == "procedure" else 0)
            self.assertTrue(all(row["final_correct"] == 8 for row in summary["assisted"]))
            run.collect("model1", output)
            self.assertEqual(len(calls), 192)
            self.assertEqual(len(loads), 2)

    def test_combined_backup_round_trip_conflicts_and_extracted_kaggle_folder(self):
        calls, loads = [], []
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            backup = root / "backup.zip"
            with self.isolated(root / "source"), \
                    patch.object(provider, "InterventionModel", self.fake_provider(calls, loads)), \
                    patch.object(transfer, "export_backup"), contextlib.redirect_stdout(io.StringIO()):
                run.collect("model1", root / "output")
            with self.isolated(root / "source"):
                transfer.export_backup(backup)
            extracted = root / "dataset"
            with zipfile.ZipFile(backup) as archive:
                self.assertTrue(all(not item.is_dir() for item in archive.infolist()))
                archive.extractall(extracted)
            with self.isolated(root / "target") as (results, baseline):
                transfer.restore_backup(extracted)
                self.assertEqual(len(list((results / "cache/model1").glob("*.json"))), 48)
                self.assertEqual(len(list((baseline / "cache/model1").glob("*.json"))), 48)
                paths = sorted((results / "cache/model1").glob("*.json"))
                paths[0].unlink()
                record = json.loads(paths[1].read_text())
                record["timestamp_utc"] = "different saved response record"
                paths[1].write_text(canonical(record))
                with self.assertRaisesRegex(RuntimeError, "conflicting"):
                    transfer.restore_backup(backup)
                self.assertFalse(paths[0].exists())

    def test_backup_rejects_path_traversal(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "bad.zip"
            with zipfile.ZipFile(path, "w") as archive:
                archive.writestr("../outside", b"payload")
            with self.assertRaisesRegex(RuntimeError, "unsafe"):
                transfer.payloads(path)

    def test_parallel_orchestration_starts_both_devices_before_waiting(self):
        events = []

        class FakeProcess:
            def __init__(self, command, **kwargs):
                self.model = command[command.index("--model") + 1]
                self.device = kwargs["env"]["CUDA_VISIBLE_DEVICES"]
                self.finished = False
                events.append(("start", self.model, self.device))

            def wait(self):
                events.append(("wait", self.model))
                self.finished = True
                return 1 if self.model == "model1" else 0

            def poll(self):
                return 0 if self.finished else None

            def kill(self):
                self.finished = True

        with tempfile.TemporaryDirectory() as directory, self.isolated(directory), \
                patch.object(overnight.subprocess, "run", return_value=type("Query", (), {"stdout": "2"})()), \
                patch.object(overnight.subprocess, "Popen", FakeProcess), contextlib.redirect_stdout(io.StringIO()):
            result = overnight.run_job(Path(directory) / "output")
            self.assertFalse(result["complete"])
            self.assertEqual(events[:2], [("start", "model1", "0"), ("start", "model2", "1")])
            status = json.loads((overnight.RESULTS / "run_status.json").read_text())
            self.assertEqual(len(status["errors"]), 1)
            self.assertEqual(status["status"], "partial")
            self.assertTrue((Path(directory) / "output/visdsr_improvements_backup.zip").exists())

    def test_notebook_is_clean_and_has_no_time_cutoff(self):
        path = ROOT / "notebooks/dsu_improvements_overnight.ipynb"
        notebook = json.loads(path.read_text())
        namespace = {}
        for cell in notebook["cells"]:
            if cell["cell_type"] == "code":
                self.assertEqual(cell["outputs"], [])
                self.assertIsNone(cell["execution_count"])
                compile("".join(cell["source"]), str(path), "exec")
        with contextlib.redirect_stdout(io.StringIO()):
            exec("".join(notebook["cells"][1]["source"]), namespace)
        self.assertTrue(namespace["PARALLEL_MODELS"])
        self.assertNotIn("COLLECTION_TIME_LIMIT_HOURS", namespace)
        self.assertNotIn("FINISH_BY_8AM_IST", namespace)

    @unittest.skipUnless(importlib.util.find_spec("xgrammar"), "optional pinned decoder environment required")
    def test_real_grammar_and_hf_adapter_allow_wrong_values_and_block_bad_structure(self):
        import torch
        import xgrammar as xgr
        from xgrammar.contrib.hf import LogitsProcessor
        chars = [chr(value) for value in range(32, 127)]
        info = xgr.TokenizerInfo(["<eos>", *chars], stop_token_ids=[0])
        compiler = xgr.GrammarCompiler(info, max_threads=2)
        for task in self.tasks:
            compiled = compiler.compile_grammar(xgr.Grammar.from_ebnf(protocol.grammar(task)))
            answer = {"steps": []}
            for number, operation in enumerate(task["operations"], 1):
                step = {"op": number, "state": {name: "A" for name in task["initial"]}}
                if operation["kind"] == "find":
                    step["find_result"] = "A"
                answer["steps"].append(step)
            raw = json.dumps(answer, separators=(",", ":"))
            self.assertTrue(xgr.GrammarMatcher(compiled).accept_string(raw))
            self.assertFalse(xgr.GrammarMatcher(compiled).accept_string(raw.replace('"A":"A"', '"A":"Z"', 1)))
            self.assertFalse(xgr.GrammarMatcher(compiled).accept_string(raw.replace('"op":1', '"op":2', 1)))
            self.assertFalse(xgr.GrammarMatcher(compiled).accept_string('{"steps":[]}'))
            processor = LogitsProcessor(compiled)
            ids = torch.tensor([[0]])
            for char in raw:
                token = chars.index(char) + 1
                scores = torch.zeros((1, info.vocab_size))
                scores[0, token] = 10
                selected = processor(ids, scores).argmax(-1)
                self.assertEqual(selected.item(), token)
                ids = torch.cat((ids, selected[:, None]), dim=1)
            scores = processor(ids, torch.zeros((1, info.vocab_size)))
            self.assertEqual(scores.argmax(-1).item(), 0)


if __name__ == "__main__":
    unittest.main()
