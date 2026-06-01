from __future__ import annotations

from pathlib import Path

from app.files.constants import MEDIA_FILE_SUFFIXES
from app.rename.utils import natural_sort_key


def discover_rename_media_files(folder: Path, *, recursive: bool = False) -> list[Path]:
    """Return media files eligible for the standalone rename planner."""
    if not folder.exists():
        raise FileNotFoundError(f"Folder does not exist: {folder}")
    if not folder.is_dir():
        raise NotADirectoryError(f"Not a folder: {folder}")
    iterator = folder.rglob("*") if recursive else folder.glob("*")
    return sorted(
        [path for path in iterator if path.is_file() and path.suffix.lower() in MEDIA_FILE_SUFFIXES],
        key=natural_sort_key,
    )
