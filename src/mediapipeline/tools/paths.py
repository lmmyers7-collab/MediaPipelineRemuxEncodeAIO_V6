"""Path helpers for source-checkout tooling."""

from __future__ import annotations

from pathlib import Path, PurePosixPath

__all__ = ["Path", "PurePosixPath", "find_repo_root"]


def find_repo_root(start: Path | str) -> Path:
    path = Path(start).resolve()
    if path.is_file():
        path = path.parent
    for candidate in (path, *path.parents):
        if (candidate / "pyproject.toml").is_file() and (candidate / "src" / "mediapipeline").is_dir():
            return candidate
    raise RuntimeError(f"Could not find MediaPipeline repository root from {start}")
