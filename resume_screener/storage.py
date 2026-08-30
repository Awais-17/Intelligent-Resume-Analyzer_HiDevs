"""JSON persistence for parsed resumes and match results."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any


class StorageError(Exception):
    """Raised when data cannot be saved to or loaded from disk."""


def save_json(data: Any, file_path: str | Path) -> str:
    """Serialize `data` to JSON at `file_path`, returning the path."""
    path = Path(file_path)
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8") as handle:
            json.dump(data, handle, indent=2, ensure_ascii=False)
        return str(path)
    except (OSError, TypeError) as exc:
        raise StorageError(f"Failed to save {path}: {exc}") from exc


def load_json(file_path: str | Path) -> Any:
    """Load and deserialize JSON from `file_path`."""
    path = Path(file_path)
    if not path.is_file():
        raise StorageError(f"File not found: {path}")
    try:
        with path.open("r", encoding="utf-8") as handle:
            return json.load(handle)
    except (OSError, json.JSONDecodeError) as exc:
        raise StorageError(f"Failed to load {path}: {exc}") from exc


def append_to_results(record: dict, results_path: str | Path) -> None:
    """Append a match record to a growing results list."""
    path = Path(results_path)
    try:
        if path.is_file():
            existing = load_json(path)
            if not isinstance(existing, list):
                raise StorageError(
                    f"{path}: expected a JSON list of results, got "
                    f"{type(existing).__name__}"
                )
        else:
            existing = []
        existing.append(record)
        save_json(existing, path)
    except StorageError:
        raise


def file_exists(file_path: str | Path) -> bool:
    return Path(file_path).is_file()


def ensure_directory(directory: str | Path) -> Path:
    path = Path(directory)
    path.mkdir(parents=True, exist_ok=True)
    return path


def base_name_of(file_path: str | Path) -> str:
    """Stem of a file plus the folder it lives in (for unique keys)."""
    path = Path(file_path)
    parent = "root" if path.parent.name == "" else path.parent.name
    return f"{parent}__{path.stem}"


def unique_path(output_dir: str | Path, base_dir: str | Path,
                stem: str, extension: str) -> Path:
    """Return a collision-free path in `output_dir`."""
    out = Path(output_dir)
    slug = (Path(base_dir).name + "__" + Path(stem).stem) \
        .replace(" ", "_").replace("/", "_")
    candidate = out / f"{slug}{extension}"
    counter = 1
    while candidate.exists():
        candidate = out / f"{slug}_{counter}{extension}"
        counter += 1
    return candidate


def atomic_rename(source: Path, destination: Path) -> None:
    """Move a temp file into place; creates parent dirs as needed."""
    destination.parent.mkdir(parents=True, exist_ok=True)
    try:
        os.replace(source, destination)
    except OSError:
        # Windows may refuse os.replace across some locked/temp scenarios.
        if destination.exists():
            destination.unlink()
        os.replace(source, destination)