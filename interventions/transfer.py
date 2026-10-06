"""Checksummed combined backups, retaining the original diagnostic archive."""
from __future__ import annotations

import json
import stat
import tempfile
import zipfile
from pathlib import Path, PurePosixPath

from diagnostics.protocol import write_json
from diagnostics.run import check_record
from diagnostics.transfer import export_backup as export_diagnostics
from diagnostics.transfer import restore_backup as restore_diagnostics
from interventions.protocol import FOLDER, PROTOCOL_ID, RESULTS, load_protocol
from interventions.run import records
from visdsr import ROOT, canonical, digest


def export_backup(target: Path) -> None:
    frozen, _, _ = load_protocol()
    records()
    target.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=target.parent) as directory:
        diagnostic = Path(directory) / "diagnostics.zip"
        export_diagnostics(diagnostic)
        files = {"diagnostics.zip": diagnostic, "FREEZE.json": FOLDER / "FREEZE.json",
                 "requests.json": FOLDER / "requests.json"}
        files.update({"sources/" + name: ROOT / name for name in frozen["source_hashes"]})
        files.update({"results/" + str(path.relative_to(RESULTS)): path
                      for path in (RESULTS / "cache").glob("*/*.json")})
        for name in ("scores.csv", "summary.json", "REPORT.md", "assisted.json", "run_status.json"):
            if (RESULTS / name).exists():
                files["results/" + name] = RESULTS / name
        manifest = {"protocol_id": PROTOCOL_ID,
                    "files": {name: digest(path.read_bytes()) for name, path in files.items()}}
        temporary = target.with_suffix(".zip.tmp")
        with zipfile.ZipFile(temporary, "w", zipfile.ZIP_DEFLATED) as archive:
            for name, path in sorted(files.items()):
                archive.write(path, name)
            archive.writestr("MANIFEST.json", canonical(manifest) + "\n")
        temporary.replace(target)


def payloads(path: Path) -> dict[str, bytes]:
    if path.is_dir():
        manifest = json.loads((path / "MANIFEST.json").read_text())
        names = list(manifest["files"])
        contents = {}
        for name in names:
            safe_name(name)
            target = path / name
            if target.is_symlink() or any(parent.is_symlink() for parent in target.parents):
                raise RuntimeError("backup contains a symlink")
            if target.stat().st_size > 32 * 1024 * 1024:
                raise RuntimeError("backup payload exceeds its size limit")
            contents[name] = target.read_bytes()
    else:
        with zipfile.ZipFile(path) as archive:
            infos = archive.infolist()
            if len(infos) > 250 or sum(item.file_size for item in infos) > 32 * 1024 * 1024:
                raise RuntimeError("backup exceeds its size limit")
            names = [item.filename for item in infos]
            for name in names:
                safe_name(name)
            if len(set(names)) != len(names) or any(item.is_dir() or stat.S_ISLNK(item.external_attr >> 16) for item in infos):
                raise RuntimeError("backup contains duplicate entries, directories, or symlinks")
            manifest = json.loads(archive.read("MANIFEST.json"))
            if set(manifest["files"]) != set(names) - {"MANIFEST.json"}:
                raise RuntimeError("backup manifest differs from its payloads")
            contents = {name: archive.read(name) for name in manifest["files"]}
    if manifest["protocol_id"] != PROTOCOL_ID or len(contents) > 250:
        raise RuntimeError("this is not an improvement backup")
    if sum(len(content) for content in contents.values()) > 32 * 1024 * 1024:
        raise RuntimeError("backup exceeds its size limit")
    for name, content in contents.items():
        relative = PurePosixPath(name)
        if relative.is_absolute() or ".." in relative.parts or "\\" in name:
            raise RuntimeError("unsafe backup path")
        if digest(content) != manifest["files"][name]:
            raise RuntimeError("backup checksum failed: " + name)
    return contents


def safe_name(name: str) -> None:
    relative = PurePosixPath(name)
    if relative.is_absolute() or ".." in relative.parts or "\\" in name:
        raise RuntimeError("unsafe backup path")


def restore_backup(path: Path) -> None:
    frozen, _, _ = load_protocol()
    files = payloads(path)
    expected = {"FREEZE.json": (FOLDER / "FREEZE.json").read_bytes(),
                "requests.json": (FOLDER / "requests.json").read_bytes()}
    expected.update({"sources/" + name: (ROOT / name).read_bytes() for name in frozen["source_hashes"]})
    if any(files.get(name) != content for name, content in expected.items()):
        raise RuntimeError("backup belongs to a different intervention freeze")
    _, added = records()
    requests = {"results/" + str(item["path"].relative_to(RESULTS)): item for item in added}
    reports = {"results/" + name for name in ("scores.csv", "summary.json", "REPORT.md", "assisted.json", "run_status.json")}
    if set(files) - (set(expected) | set(requests) | reports | {"diagnostics.zip"}):
        raise RuntimeError("unexpected backup payloads")
    pending = []
    for name, item in requests.items():
        if name not in files:
            continue
        record = json.loads(files[name])
        check_record(record, item["request"])
        if item["case"]["grammar"] and record["response"].get("grammar_version") != "0.2.8":
            raise RuntimeError("cached constrained response lacks the pinned grammar provenance")
        if item["path"].exists() and item["path"].read_bytes() != files[name]:
            raise RuntimeError("conflicting intervention answer; no responses replaced")
        if item["path"].is_symlink() or any(parent.is_symlink() for parent in item["path"].parents):
            raise RuntimeError("cache restore target contains a symlink")
        pending.append((item["path"], record))
    with tempfile.TemporaryDirectory() as directory:
        diagnostic = Path(directory) / "diagnostics.zip"
        diagnostic.write_bytes(files["diagnostics.zip"])
        restore_diagnostics(diagnostic)
    for target, record in pending:
        if not target.exists():
            write_json(target, record)
    from interventions.report import score
    score()
