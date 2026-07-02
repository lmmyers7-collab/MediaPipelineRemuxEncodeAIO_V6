"""Bounded read-only filesystem scanning for autonomy diagnostics."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class LimitedFileScan:
    paths: list[Path]
    truncated: bool
    limit: int
    total_candidate_count: int
    stat_error_count: int
    read_error: str = ""


def limited_iter_files(root: Path, pattern: str = "*", *, limit: int = 500) -> LimitedFileScan:
    try:
        candidates = list(root.glob(pattern))
    except OSError as exc:
        return LimitedFileScan([], False, limit, 0, 0, str(exc))
    rows: list[tuple[float, Path]] = []
    stat_error_count = 0
    for path in candidates:
        try:
            modified = path.stat().st_mtime
        except OSError:
            stat_error_count += 1
            modified = 0.0
        rows.append((modified, path))
    rows.sort(key=lambda item: item[0], reverse=True)
    return LimitedFileScan(
        paths=[path for _, path in rows[:limit]],
        truncated=len(rows) > limit,
        limit=limit,
        total_candidate_count=len(rows),
        stat_error_count=stat_error_count,
    )


def directory_size_scan(root: Path | None, *, limit: int = 500) -> dict[str, Any]:
    if root is None or not root.exists() or not root.is_dir():
        return {
            "size_bytes": 0,
            "scanned_file_count": 0,
            "truncated": False,
            "limit": limit,
            "stat_error_count": 0,
            "read_error": "",
        }
    total = 0
    scanned = 0
    truncated = False
    stat_error_count = 0
    read_error = ""
    try:
        iterator = root.rglob("*")
        for path in iterator:
            try:
                is_file = path.is_file()
            except OSError:
                stat_error_count += 1
                continue
            if not is_file:
                continue
            if scanned >= limit:
                truncated = True
                break
            scanned += 1
            try:
                total += int(path.stat().st_size)
            except OSError:
                stat_error_count += 1
                continue
    except OSError as exc:
        read_error = str(exc)
    return {
        "size_bytes": total,
        "scanned_file_count": scanned,
        "truncated": truncated,
        "limit": limit,
        "stat_error_count": stat_error_count,
        "read_error": read_error,
    }


def unique_observed_bytes(rows: list[tuple[Path | None, int]]) -> int:
    normalized: list[tuple[Path, int]] = []
    for path, size in rows:
        if path is None:
            continue
        try:
            normalized.append((Path(path).resolve(), max(0, int(size))))
        except (OSError, RuntimeError, ValueError):
            normalized.append((Path(path), max(0, int(size))))
    total = 0
    for path, size in sorted(normalized, key=lambda item: len(str(item[0]))):
        if any(_is_relative_to(path, parent) for parent, _ in normalized if parent != path and len(str(parent)) < len(str(path))):
            continue
        total += size
    return total


def _is_relative_to(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
    except ValueError:
        return False
    return True


__all__ = [
    "LimitedFileScan",
    "directory_size_scan",
    "limited_iter_files",
    "unique_observed_bytes",
]
