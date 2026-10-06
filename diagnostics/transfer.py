"""Checksummed diagnostic backups with safe, conflict-aware cache restoration."""
from __future__ import annotations

import json
import stat
import zipfile
from pathlib import Path, PurePosixPath

from diagnostics.protocol import PILOT, PROTOCOL_ID, RESULTS, load_panel
from visdsr import ROOT, canonical, digest

MAX_FILES = 250
MAX_BYTES = 32 * 1024 * 1024


def export_backup(target: Path, pilot: Path = PILOT, results: Path = RESULTS) -> None:
    frozen, _, _ = load_panel(pilot)
    files = {f"pilot/{name}": pilot / name for name in frozen["input_hashes"]}
    files.update({f"pilot/{name}": pilot / name for name in ("FREEZE.json", "REVIEW.json")})
    files.update({f"sources/{name}": ROOT / name for name in frozen["source_hashes"]})
    for path in sorted((results / "cache").glob("*/*.json")):
        files["results/" + str(path.relative_to(results))] = path
    for name in ("scores.csv", "summary.json", "REPORT.md", "run_status.json"):
        if (results / name).exists():
            files[f"results/{name}"] = results / name
    manifest = {"protocol_id": PROTOCOL_ID,
                "files": {name: digest(path.read_bytes()) for name, path in files.items()}}
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_suffix(target.suffix + ".tmp")
    with zipfile.ZipFile(temporary, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        # File entries only: no repeated directory records for Kaggle uploads.
        for name, path in sorted(files.items()):
            archive.write(path, name)
        archive.writestr("MANIFEST.json", canonical(manifest) + "\n")
    temporary.replace(target)


def read_backup(path: Path) -> dict[str, bytes]:
    if path.is_dir():
        manifest = json.loads((path / "MANIFEST.json").read_text())
        if manifest["protocol_id"] != PROTOCOL_ID or len(manifest["files"]) > MAX_FILES:
            raise RuntimeError("this directory is not a compatible diagnostic backup")
        files = {}
        total_bytes = 0
        for name, checksum in manifest["files"].items():
            relative = PurePosixPath(name)
            target = path / name
            unsafe = any((relative.is_absolute(), ".." in relative.parts, "\\" in name,
                          target.is_symlink(), any(parent.is_symlink() for parent in target.parents)))
            if unsafe:
                raise RuntimeError("unsafe diagnostic backup path")
            total_bytes += target.stat().st_size
            if total_bytes > MAX_BYTES:
                raise RuntimeError("diagnostic backup exceeds its size limit")
            content = target.read_bytes()
            if digest(content) != checksum:
                raise RuntimeError(f"diagnostic backup checksum failed: {name}")
            files[name] = content
        return files
    with zipfile.ZipFile(path) as archive:
        infos = archive.infolist()
        names = [info.filename for info in infos]
        oversized = sum(info.file_size for info in infos) > MAX_BYTES
        if len(names) > MAX_FILES or len(set(names)) != len(names) or oversized:
            raise RuntimeError("diagnostic backup has duplicate entries or exceeds its size limit")
        for info in infos:
            name = PurePosixPath(info.filename)
            mode = info.external_attr >> 16
            unsafe = any((name.is_absolute(), ".." in name.parts, "\\" in info.filename,
                          info.is_dir(), stat.S_ISLNK(mode)))
            if unsafe:
                raise RuntimeError("unsafe diagnostic backup entry")
        if "MANIFEST.json" not in names:
            raise RuntimeError("this is not a diagnostic backup")
        manifest = json.loads(archive.read("MANIFEST.json"))
        if manifest["protocol_id"] != PROTOCOL_ID or set(manifest["files"]) != set(names) - {"MANIFEST.json"}:
            raise RuntimeError("diagnostic backup manifest differs from its payloads")
        files = {name: archive.read(name) for name in manifest["files"]}
        for name, content in files.items():
            if digest(content) != manifest["files"][name]:
                raise RuntimeError(f"diagnostic backup checksum failed: {name}")
    return files


def restore_backup(path: Path, pilot: Path = PILOT, results: Path = RESULTS) -> int:
    frozen, tasks, cases = load_panel(pilot)
    files = read_backup(path)
    expected = {f"pilot/{name}": (pilot / name).read_bytes() for name in frozen["input_hashes"]}
    expected.update({f"pilot/{name}": (pilot / name).read_bytes() for name in ("FREEZE.json", "REVIEW.json")})
    expected.update({f"sources/{name}": (ROOT / name).read_bytes() for name in frozen["source_hashes"]})
    if any(files.get(name) != content for name, content in expected.items()):
        raise RuntimeError("backup belongs to different frozen sources or pilot inputs")
    by_id = {task["id"]: task for task in tasks}
    requests = {}
    from diagnostics.protocol import request_provenance
    from diagnostics.run import check_record, score_saved
    for model in frozen["models"]:
        for case in cases:
            name = f"results/cache/{model['name']}/{case['case_id']}.json"
            requests[name] = request_provenance(frozen, by_id[case["task_id"]], case, model, pilot)
    derived = {f"results/{name}" for name in ("scores.csv", "summary.json", "REPORT.md", "run_status.json")}
    allowed = set(expected) | set(requests) | derived
    if set(files) - allowed:
        raise RuntimeError("unexpected backup payloads")
    pending = []
    for name, content in files.items():
        if name not in requests:
            continue
        check_record(json.loads(content), requests[name])
        target = results / name.removeprefix("results/")
        if target.is_symlink() or any(parent.is_symlink() for parent in target.parents):
            raise RuntimeError("cache restore target contains a symlink")
        if target.exists() and target.read_bytes() != content:
            raise RuntimeError("a different response already exists for this request; no files replaced")
        if not target.exists():
            pending.append((target, content))
    # Check all incoming records and conflicts before writing any cache.
    for target, content in pending:
        target.parent.mkdir(parents=True, exist_ok=True)
        temporary = target.with_suffix(".json.tmp")
        temporary.write_bytes(content)
        temporary.replace(target)
    score_saved(pilot, results)
    return len(pending)
