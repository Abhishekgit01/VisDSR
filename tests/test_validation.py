"""Focused tests for response validation, scoring, statistics, and rendering."""
from __future__ import annotations

import json
import unittest

from analysis.pilot2 import diagnostic, diagnostic_transcription
from analysis.stats import holm, mcnemar_exact, paired_bootstrap
from eval.prompts import CONDITIONS, prompt
from eval.run import request_key
from eval.score import score
from eval.validate import FormatError, parse
from gen.render import diagram_image, text_image, wrap_canonical
from tests.naive import simulate
from visdsr import canonical


class ValidationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.operations = [{"kind": "union", "a": "A", "b": "B"},
                           {"kind": "find", "a": "B"}]
        truth = simulate(3, [], self.operations)
        self.task = {"id": "test_1", "split": "pilot", "structure": "dsu",
                     "size": "small", "initial": truth["initial"],
                     "operations": self.operations, "steps": truth["steps"]}
        self.answer = {"steps": [{"op": i, **step}
                                 for i, step in enumerate(truth["steps"], 1)]}

    def test_all_five_prompts_and_exact_answer(self) -> None:
        for condition in CONDITIONS:
            answer = dict(self.answer)
            if condition.endswith("str"):
                answer["transcription"] = self.task["initial"]
            raw = json.dumps(answer)
            self.assertEqual(parse(raw, self.task, condition), answer)
            result = score(self.task, condition, raw)
            self.assertEqual(result["final_correct"], 1)
            self.assertEqual(result["full_sequence_correct"], 1)
            self.assertIn("union(a,b)", prompt(self.task, condition))

    def test_format_error_counts_as_wrong(self) -> None:
        answer = dict(self.answer)
        answer["steps"] = [dict(step) for step in answer["steps"]]
        del answer["steps"][1]["find_result"]
        raw = json.dumps(answer)
        with self.assertRaises(FormatError):
            parse(raw, self.task, "T-dir")
        scored = score(self.task, "T-dir", raw)
        self.assertEqual((scored["format_error"], scored["final_correct"]), (1, 0))

    def test_non_string_parent_is_a_format_error(self) -> None:
        answer = dict(self.answer)
        answer["steps"] = [dict(step) for step in answer["steps"]]
        answer["steps"][0]["state"] = dict(answer["steps"][0]["state"], A=[])
        scored = score(self.task, "T-dir", json.dumps(answer))
        self.assertEqual(scored["failure_type"], "format_error")

    def test_fence_allowed_and_wrong_transcription_split(self) -> None:
        answer = dict(self.answer, transcription={"A": "B", "B": "B", "C": "C"})
        raw = "```json\n" + json.dumps(answer) + "\n```"
        self.assertEqual(score(self.task, "G-str", raw)["failure_type"],
                         "wrong_transcription_final_correct")

    def test_pilot2_diagnostic_does_not_change_strict_scoring(self) -> None:
        answer = {"steps": [dict(step) for step in self.answer["steps"]],
                  "transcription": self.task["initial"]}
        answer["steps"][0]["find_result"] = "A"
        raw = json.dumps(answer)
        self.assertEqual(score(self.task, "T-str", raw)["format_error"], 1)
        changes, repaired = diagnostic(self.task, "T-str", raw)
        self.assertEqual(changes, ["removed union find_result"])
        self.assertEqual(repaired["final_correct"], 1)

        answer["steps"][0].pop("find_result")
        answer["transcription"] = json.dumps(self.task["initial"])
        raw = json.dumps(answer)
        self.assertEqual(score(self.task, "G-str", raw)["format_error"], 1)
        changes, repaired = diagnostic(self.task, "G-str", raw)
        self.assertEqual(changes, ["parsed JSON-string transcription"])
        self.assertEqual(repaired["transcription_correct"], 1)
        self.assertEqual(repaired["final_correct"], 1)
        self.assertEqual(diagnostic_transcription(self.task, raw), 1)

        answer["transcription"] = "A->A, B->B, C->C"
        changes, repaired = diagnostic(self.task, "G-str", json.dumps(answer))
        self.assertEqual(changes, [])
        self.assertIsNone(repaired)
        self.assertIsNone(diagnostic_transcription(self.task, json.dumps(answer)))

    def test_cache_key_changes_with_every_input(self) -> None:
        model = {"id": "example", "temperature": 0}
        key = request_key(model, "prompt", None, "task1", "T-dir")[0]
        self.assertNotEqual(key, request_key(model, "prompt changed", None, "task1", "T-dir")[0])
        self.assertNotEqual(key, request_key(model, "prompt", b"image", "task1", "T-dir")[0])
        self.assertNotEqual(key, request_key(dict(model, temperature=1), "prompt", None, "task1", "T-dir")[0])
        self.assertNotEqual(key, request_key(dict(model, id="other"), "prompt", None, "task1", "T-dir")[0])
        self.assertNotEqual(key, request_key(model, "prompt", None, "task2", "T-dir")[0])
        self.assertNotEqual(key, request_key(model, "prompt", None, "task1", "G-dir")[0])

    def test_statistics(self) -> None:
        self.assertEqual(mcnemar_exact([1, 1, 0], [0, 0, 0]), (2, 0, 0.5))
        self.assertEqual(holm([0.04, 0.01]), [0.04, 0.02])
        self.assertEqual(paired_bootstrap([1, 1, 1], 50), (1.0, 1.0, 1.0))

    def test_render(self) -> None:
        state = {"A": "A", "B": "A", "C": "A", "D": "C",
                 "E": "E", "F": "E", "G": "G", "H": "G"}
        self.assertEqual(diagram_image(state, 1024).size, (1024, 1024))
        value = canonical(state)
        lines = wrap_canonical(value)
        self.assertEqual("".join(lines), value)
        self.assertTrue(all(line.endswith(",") for line in lines[:-1]))
        self.assertEqual(text_image(value, 1024).mode, "RGB")


if __name__ == "__main__":
    unittest.main()
