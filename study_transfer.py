"""Export and restore private v2 study data with protocol and file checks."""
from __future__ import annotations

import argparse
import json
import zipfile
from pathlib import Path

from visdsr import ROOT, config, digest, protocol_hashes

MARKER = "VISDSR_EXPORT.json"
MAX_FILE_BYTES = 100 * 2**20
MAX_TOTAL_BYTES = 2 * 2**30
MAX_FILES = 5000


def protocol() -> dict:
    if config().get("protocol_version") != 2:
        raise ValueError("this transfer tool requires protocol version 2")
    return {
        "version": 2,
        "source_hashes": protocol_hashes(),
        "config_sha256": digest((ROOT / "configs/experiment.yaml").read_bytes()),
        "prompt_sha256": digest((ROOT / "eval/prompts.py").read_bytes()),
        "task_hashes_sha256": digest((ROOT / "configs/v2_tasks.json").read_bytes()),
    }


def expected_tasks() -> dict[str, str]:
    return json.loads((ROOT / "configs/v2_tasks.json").read_text())


def study_files() -> list[Path]:
    files = []
    for folder in ("data", "results"):
        if not (ROOT / folder).exists():
            continue
        for path in sorted((ROOT / folder).rglob("*")):
            if path.is_symlink():
                raise ValueError(f"symlink in study data: {path}")
            if path.is_file() and path.name != "cache_snapshot.zip" and not path.name.startswith("."):
                files.append(path)
    for split, checksum in expected_tasks().items():
        task_file = ROOT / "data" / split / "tasks.jsonl"
        if task_file.exists() and digest(task_file.read_bytes()) != checksum:
            raise ValueError(f"{split} tasks do not match the v2 seed")
    return files


def export_archive(destination: Path) -> None:
    files = study_files()
    if not (ROOT / "data/pilot2/tasks.jsonl").exists():
        raise ValueError("generate and validate v2 pilot2 before export")
    if not files:
        raise ValueError("no study data to export")
    checksums = {path.relative_to(ROOT).as_posix(): digest(path.read_bytes()) for path in files}
    metadata = {**protocol(), "files": checksums}
    manifest = ROOT / "MANIFEST.json"
    if manifest.exists():
        metadata["run_manifest"] = json.loads(manifest.read_text())
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_suffix(destination.suffix + ".tmp")
    with zipfile.ZipFile(temporary, "w", compression=zipfile.ZIP_DEFLATED) as output:
        output.writestr(MARKER, json.dumps(metadata, sort_keys=True, indent=2) + "\n")
        for path in files:
            output.write(path, path.relative_to(ROOT).as_posix())
    temporary.replace(destination)
    print(f"Exported {len(files)} files: {destination}")


def check_metadata(metadata: dict) -> dict[str, str]:
    if not isinstance(metadata, dict):
        raise ValueError("backup metadata must be an object")
    expected = protocol()
    if any(metadata.get(key) != value for key, value in expected.items()):
        raise ValueError("backup belongs to a different VisDSR protocol or code revision")
    files = metadata.get("files")
    if not isinstance(files, dict) or not files or len(files) > MAX_FILES:
        raise ValueError("invalid backup file manifest")
    for name, checksum in files.items():
        if not isinstance(name, str):
            raise ValueError("backup path must be a string")
        path = Path(name)
        if len(path.parts) < 2:
            raise ValueError(f"invalid backup entry: {name}")
        invalid_path = any((path.is_absolute(), ".." in path.parts, "\\" in name,
                            path.as_posix() != name, path.parts[0] not in ("data", "results"),
                            name == "results/cache_snapshot.zip"))
        invalid_checksum = not isinstance(checksum, str) or len(checksum) != 64
        if not invalid_checksum:
            invalid_checksum = any(char not in "0123456789abcdef" for char in checksum)
        if invalid_path or invalid_checksum:
            raise ValueError(f"invalid backup entry: {name}")
    if "data/pilot2/tasks.jsonl" not in files:
        raise ValueError("backup is missing v2 pilot2 tasks")
    for split, checksum in expected_tasks().items():
        name = f"data/{split}/tasks.jsonl"
        if name in files and files[name] != checksum:
            raise ValueError(f"{split} tasks do not match the v2 seed")
    return files


def check_existing(files: dict[str, str]) -> None:
    for name, checksum in files.items():
        target = ROOT / name
        if not target.resolve().is_relative_to(ROOT.resolve()):
            raise ValueError(f"unsafe destination path: {name}")
        if target.exists() and (not target.is_file() or digest(target.read_bytes()) != checksum):
            raise ValueError(f"existing file differs from backup: {name}")


def restore_archive(source: Path) -> None:
    with zipfile.ZipFile(source) as archive:
        names = archive.namelist()
        if len(names) != len(set(names)) or MARKER not in names:
            raise ValueError("backup marker missing or duplicate archive entries")
        if archive.getinfo(MARKER).file_size > 2 * 2**20:
            raise ValueError("backup marker exceeds size limit")
        metadata = json.loads(archive.read(MARKER))
        files = check_metadata(metadata)
        if set(names) != set(files) | {MARKER}:
            raise ValueError("backup contents differ from file manifest")
        total = 0
        for name, checksum in files.items():
            info = archive.getinfo(name)
            total += info.file_size
            if info.file_size > MAX_FILE_BYTES or total > MAX_TOTAL_BYTES:
                raise ValueError("backup exceeds size limit")
            if digest(archive.read(name)) != checksum:
                raise ValueError(f"backup checksum mismatch: {name}")
        check_existing(files)
        for name in files:
            target = ROOT / name
            if not target.exists():
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(archive.read(name))
    print(f"Restored {len(files)} files: {source}")


def restore_directory(source: Path) -> None:
    metadata = json.loads((source / MARKER).read_text())
    files = check_metadata(metadata)
    total = 0
    for name, checksum in files.items():
        path = source / name
        unsafe = not path.resolve().is_relative_to(source.resolve())
        if not path.is_file() or path.is_symlink() or unsafe:
            raise ValueError(f"backup entry missing or unsafe: {name}")
        total += path.stat().st_size
        if path.stat().st_size > MAX_FILE_BYTES or total > MAX_TOTAL_BYTES:
            raise ValueError("backup exceeds size limit")
        if digest(path.read_bytes()) != checksum:
            raise ValueError(f"backup checksum mismatch: {name}")
    check_existing(files)
    for name in files:
        target = ROOT / name
        if not target.exists():
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes((source / name).read_bytes())
    print(f"Restored {len(files)} files: {source}")


def restore_auto(input_root: Path, required: bool = False) -> None:
    if not input_root.exists():
        if required:
            raise FileNotFoundError("attach a private v2 results Dataset")
        print("No prior v2 backup attached")
        return
    directories = [path.parent for path in input_root.rglob(MARKER)]
    if directories:
        if len(directories) != 1:
            raise ValueError("attach exactly one v2 results Dataset")
        restore_directory(directories[0])
        return
    archives = []
    for path in input_root.rglob("*.zip"):
        try:
            with zipfile.ZipFile(path) as source:
                if MARKER in source.namelist():
                    archives.append(path)
        except zipfile.BadZipFile:
            continue
    if len(archives) > 1:
        raise ValueError("attach exactly one v2 results archive")
    if archives:
        restore_archive(archives[0])
    elif required:
        raise FileNotFoundError("attach a private v2 results Dataset")
    else:
        print("No prior v2 backup attached")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument("--export", type=Path)
    action.add_argument("--restore", type=Path)
    action.add_argument("--restore-auto", type=Path)
    parser.add_argument("--require-backup", action="store_true")
    args = parser.parse_args()
    if args.export:
        export_archive(args.export)
    elif args.restore:
        if args.restore.is_dir():
            restore_directory(args.restore)
        else:
            restore_archive(args.restore)
    else:
        restore_auto(args.restore_auto, args.require_backup)


if __name__ == "__main__":
    main()
