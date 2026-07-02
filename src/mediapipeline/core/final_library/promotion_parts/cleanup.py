from __future__ import annotations

from pathlib import Path
from typing import Any
from collections.abc import Iterable, Mapping

from .planning import normalized_path_key, path_within_root


def _delete_verified_source_file(source_path: Path, publish_root: Path, publish_root_key: str) -> dict[str, Any]:
    if not path_within_root(source_path, publish_root):
        return {"deleted": False, "path": str(source_path), "reason": "outside_publish_root"}
    if normalized_path_key(source_path) == publish_root_key:
        return {"deleted": False, "path": str(source_path), "reason": "publish_root_never_deleted"}
    try:
        if source_path.exists():
            source_path.unlink()
            return {"deleted": True, "path": str(source_path)}
        return {"deleted": False, "path": str(source_path), "reason": "already_missing"}
    except OSError as exc:
        return {"deleted": False, "path": str(source_path), "error": str(exc)}


def _remove_empty_parent_folders(start_path: Path, publish_root: Path, publish_root_key: str) -> tuple[list[str], list[dict[str, str]]]:
    removed: list[str] = []
    errors: list[dict[str, str]] = []
    current = start_path.parent
    while path_within_root(current, publish_root) and normalized_path_key(current) != publish_root_key:
        try:
            current.rmdir()
            removed.append(str(current))
        except OSError:
            break
        current = current.parent
    return removed, errors


def cleanup_verified_files(copied_files: Iterable[Mapping[str, Any]], publish_root: Path) -> dict[str, Any]:
    cleanup: dict[str, Any] = {
        "completed": False,
        "deleted_files": [],
        "skipped_files": [],
        "removed_empty_folders": [],
        "errors": [],
    }
    publish_root_key = normalized_path_key(publish_root)
    deleted_sources: list[Path] = []
    for copied in copied_files:
        source_path = Path(str(copied.get("source_path") or ""))
        result = _delete_verified_source_file(source_path, publish_root, publish_root_key)
        if result.get("deleted"):
            cleanup["deleted_files"].append(str(source_path))
            deleted_sources.append(source_path)
        elif result.get("error"):
            cleanup["errors"].append({"path": str(source_path), "error": str(result.get("error") or "")})
        else:
            cleanup["skipped_files"].append({"path": str(source_path), "reason": str(result.get("reason") or "skipped")})

    for source_path in deleted_sources:
        removed, errors = _remove_empty_parent_folders(source_path, publish_root, publish_root_key)
        cleanup["removed_empty_folders"].extend(removed)
        cleanup["errors"].extend(errors)

    cleanup["completed"] = not cleanup["errors"]
    return cleanup


__all__ = ["cleanup_verified_files"]
