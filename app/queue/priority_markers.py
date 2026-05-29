from __future__ import annotations

import os
import time
from pathlib import Path

from mediapipeline_desktop_app.priority_markers import remove_priority_markers_from_name, starts_with_priority_marker


def path_is_unc(path: Path) -> bool:
    text = str(path)
    return text.startswith("\\\\") or text.startswith("//")


def safe_mtime(path: Path, cache: dict[Path, float] | None = None) -> float:
    if cache is not None and path in cache:
        return cache[path]
    try:
        value = path.stat().st_mtime
    except OSError:
        value = 0.0
    if cache is not None:
        cache[path] = value
    return value


def get_source_priority_info(
    source_path: Path,
    markers: list[str],
    stat_cache: dict[Path, float] | None = None,
) -> tuple[bool, list[str], float]:
    reasons: list[str] = []
    priority_rank = 0.0
    if starts_with_priority_marker(source_path.name, markers):
        reasons.append("file")
        priority_rank = max(priority_rank, safe_mtime(source_path, stat_cache))

    current = source_path.parent
    source_mtime = stat_cache.get(source_path, 0.0) if stat_cache is not None else 0.0
    for _ in range(4):
        leaf = current.name
        if leaf and starts_with_priority_marker(leaf, markers):
            reasons.append(f"folder:{leaf}")
            if stat_cache is not None and path_is_unc(current) and current not in stat_cache:
                priority_rank = max(priority_rank, source_mtime)
            else:
                priority_rank = max(priority_rank, safe_mtime(current, stat_cache))
        if current.parent == current:
            break
        current = current.parent

    return (len(reasons) > 0, reasons, priority_rank)


def format_priority_leaf_name(marker: str, leaf: str, markers: list[str]) -> str:
    cleaned = remove_priority_markers_from_name(leaf, markers)
    if not cleaned:
        return leaf
    return f"{marker} {cleaned}"


def priority_marker_destination(target_path: Path, markers: list[str], marker: str, remove_only: bool = False) -> Path:
    leaf = target_path.name
    if target_path.is_file():
        new_stem = (
            remove_priority_markers_from_name(target_path.stem, markers)
            if remove_only
            else format_priority_leaf_name(marker, target_path.stem, markers)
        )
        new_name = f"{new_stem}{target_path.suffix}"
    else:
        new_name = (
            remove_priority_markers_from_name(leaf, markers)
            if remove_only
            else format_priority_leaf_name(marker, leaf, markers)
        )
    return target_path.with_name(new_name)


def touch_priority_target(target_path: Path) -> None:
    timestamp = time.time()
    try:
        os.utime(target_path, (timestamp, timestamp))
    except OSError:
        return


def apply_priority_marker(target_path: Path, markers: list[str], marker: str, remove_only: bool = False) -> Path:
    if not target_path.exists():
        raise FileNotFoundError(f"Target does not exist: {target_path}")

    destination = priority_marker_destination(target_path, markers, marker, remove_only=remove_only)
    if destination.name == target_path.name:
        return target_path
    if destination.exists():
        raise FileExistsError(f"Cannot rename because the destination already exists: {destination}")

    renamed = target_path.rename(destination)
    if not remove_only:
        touch_priority_target(renamed)
    return renamed
