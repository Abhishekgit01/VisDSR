"""Offline checks for v2 backup integrity and freeze provenance."""
from __future__ import annotations

import contextlib
import csv
import io
import json
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

import study_transfer as transfer
import visdsr
from eval.prompts import CONDITIONS, SYSTEM, prompt
from eval.run import request_key
from eval.score import score
from gen.freeze import audit_calibration
from visdsr import canonical, config, digest


class TransferTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.folder = Path(self.temporary.name)
        self.source = self.folder / "source"
        self.destination = self.folder / "destination"
        for name in visdsr.STUDY_SOURCE_FILES:
            for root in (self.source, self.destination):
                path = root / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text("fixture")
        tasks = b'{"id":"pilot2_test"}\n'
        for root in (self.source, self.destination):
            (root / "configs/experiment.yaml").write_text(
                canonical({"protocol_version": 2, "protocol_id": "visdsr-dsu-v2"}))
            (root / "configs/v2_tasks.json").write_text(canonical({"pilot2": digest(tasks)}))
        path = self.source / "data/pilot2/tasks.jsonl"
        path.parent.mkdir(parents=True)
        path.write_bytes(tasks)
        cache = self.source / "results/cache/response.json"
        cache.parent.mkdir(parents=True)
        cache.write_text('{"raw_text":"{}"}\n')
        (self.source / "results/cache_snapshot.zip").write_bytes(b"excluded nested backup")
        self.archive = self.folder / "backup.zip"
        with self.at_root(self.source), contextlib.redirect_stdout(io.StringIO()):
            transfer.export_archive(self.archive)

    @contextlib.contextmanager
    def at_root(self, root):
        with patch.object(visdsr, "ROOT", root), patch.object(transfer, "ROOT", root):
            yield

    def rewrite(self, mutate):
        with zipfile.ZipFile(self.archive) as source:
            files = {name: source.read(name) for name in source.namelist()}
        mutate(files)
        corrupted = self.folder / "changed.zip"
        with zipfile.ZipFile(corrupted, "w") as output:
            for name, contents in files.items():
                output.writestr(name, contents)
        return corrupted

    def test_archive_and_kaggle_extracted_directory_roundtrip(self):
        with zipfile.ZipFile(self.archive) as source:
            self.assertNotIn("results/cache_snapshot.zip", source.namelist())
        with self.at_root(self.destination), contextlib.redirect_stdout(io.StringIO()):
            transfer.restore_archive(self.archive)
            transfer.restore_archive(self.archive)
        self.assertEqual((self.destination / "data/pilot2/tasks.jsonl").read_bytes(),
                         (self.source / "data/pilot2/tasks.jsonl").read_bytes())
        extracted = self.folder / "kaggle-input"
        with zipfile.ZipFile(self.archive) as source:
            source.extractall(extracted / "dataset")
        with self.at_root(self.destination), contextlib.redirect_stdout(io.StringIO()):
            transfer.restore_auto(extracted, required=True)

    def test_corrupt_payload_is_rejected_before_any_write(self):
        archive = self.rewrite(lambda files: files.update({"results/cache/response.json": b"changed"}))
        with self.at_root(self.destination):
            with self.assertRaisesRegex(ValueError, "checksum mismatch"):
                transfer.restore_archive(archive)
        self.assertFalse((self.destination / "data").exists())

    def test_old_protocol_is_rejected_before_any_write(self):
        def change(files):
            metadata = json.loads(files[transfer.MARKER])
            metadata["version"] = 1
            files[transfer.MARKER] = canonical(metadata).encode()
        with self.at_root(self.destination):
            with self.assertRaisesRegex(ValueError, "different VisDSR protocol"):
                transfer.restore_archive(self.rewrite(change))
        self.assertFalse((self.destination / "data").exists())

    def test_v1_task_content_cannot_be_given_a_v2_marker(self):
        def change(files):
            old_tasks = b'{"id":"old_task"}\n'
            metadata = json.loads(files[transfer.MARKER])
            metadata["files"]["data/pilot2/tasks.jsonl"] = digest(old_tasks)
            files["data/pilot2/tasks.jsonl"] = old_tasks
            files[transfer.MARKER] = canonical(metadata).encode()
        with self.at_root(self.destination):
            with self.assertRaisesRegex(ValueError, "do not match the v2 seed"):
                transfer.restore_archive(self.rewrite(change))
        self.assertFalse((self.destination / "data").exists())

    def test_unsafe_paths_and_destination_conflicts_are_rejected(self):
        with self.at_root(self.destination):
            metadata = transfer.protocol()
            for name in ("../escape", "", "results", "data//x", "data/../x", "/data/x"):
                with self.subTest(name=name), self.assertRaises(ValueError):
                    transfer.check_metadata(dict(metadata, files={name: "a" * 64}))
            path = self.destination / "results/cache/response.json"
            path.parent.mkdir(parents=True)
            path.write_text("newer local result")
            with self.assertRaisesRegex(ValueError, "existing file differs"):
                transfer.restore_archive(self.archive)
        self.assertFalse((self.destination / "data").exists())
        self.assertEqual(path.read_text(), "newer local result")


class FreezeAuditTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.model = config()["models"][0]
        self.task = {"id": "pilot2_test", "split": "pilot2", "structure": "dsu", "size": "small",
                     "initial": {"A": "A", "B": "B"},
                     "operations": [{"kind": "union", "a": "A", "b": "B"}],
                     "steps": [{"state": {"A": "A", "B": "A"}}]}
        image = b"fixture image bytes"
        self.mapping = {"pilot2_test": {
            "text_image": "text.png", "diagram_image": "diagram.png",
            "text_sha256": digest(image), "diagram_sha256": digest(image),
        }}
        folder = self.root / "data/pilot2/img"
        folder.mkdir(parents=True)
        for name in ("text.png", "diagram.png"):
            (folder / name).write_bytes(image)
        cache = self.root / "results/cache"
        cache.mkdir(parents=True)
        rows = []
        self.cache_files = []
        for condition in CONDITIONS:
            text = prompt(self.task, condition)
            payload = image if condition.startswith(("R", "G")) else None
            key, prompt_hash, image_hash = request_key(self.model, text, payload,
                                                       self.task["id"], condition)
            answer = {"steps": [{"op": 1, "state": {"A": "A", "B": "A"}}]}
            if condition.endswith("str"):
                answer["transcription"] = self.task["initial"]
            raw = canonical(answer)
            record = {"cache_key": key, "task_id": self.task["id"], "split": "pilot2",
                      "condition": condition, "model_id": self.model["id"],
                      "revision": self.model["revision"], "protocol_id": "visdsr-dsu-v2",
                      "task_sha256": digest(canonical(self.task).encode()),
                      "prompt_hash": prompt_hash, "image_hash": image_hash,
                      "system_prompt": SYSTEM, "user_prompt": text,
                      "effective_generation_parameters": {"do_sample": False, "num_beams": 1,
                                                          "max_new_tokens": 2048},
                      "latency_s": 1.0, "raw_text": raw}
            path = cache / f"{key}.json"
            path.write_text(canonical(record))
            self.cache_files.append(path)
            rows.append({"model": self.model["name"], "model_id": self.model["id"],
                         **score(self.task, condition, raw)})
        with (self.root / "results/scores_pilot2_model1.csv").open("w", newline="") as target:
            writer = csv.DictWriter(target, fieldnames=list(rows[0]))
            writer.writeheader()
            writer.writerows(rows)

    def audit(self):
        from gen import freeze
        with patch.object(freeze, "ROOT", self.root):
            return audit_calibration(self.model, [self.task], self.mapping)

    def test_matching_cache_recomputes_all_five_scores(self):
        result = self.audit()
        self.assertEqual(result["responses"], 5)
        self.assertTrue(all(value["final_correct"] == 1 for value in result["by_condition"].values()))

    def test_complete_csv_cannot_freeze_without_matching_raw_cache(self):
        self.cache_files[0].unlink()
        with self.assertRaisesRegex(RuntimeError, "missing matching raw cache"):
            self.audit()

    def test_changed_request_metadata_is_rejected(self):
        record = json.loads(self.cache_files[0].read_text())
        record["user_prompt"] = "different request"
        self.cache_files[0].write_text(canonical(record))
        with self.assertRaisesRegex(RuntimeError, "provenance differs"):
            self.audit()


if __name__ == "__main__":
    unittest.main()
