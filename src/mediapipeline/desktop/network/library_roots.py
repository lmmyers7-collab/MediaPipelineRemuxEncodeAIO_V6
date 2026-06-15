"""Library-root payload and worker auto-map helpers for network mode."""
from __future__ import annotations

import ntpath
from collections.abc import Iterable, Mapping
from pathlib import Path
from typing import Any

from mediapipeline.core.config.library_profiles import library_profiles_from_config


NETWORK_LIBRARIES_SCHEMA_VERSION = "desktop_network_libraries.v1"


def _text(value: Any) -> str:
    return str(value or "").strip()


def _path_key(value: Any) -> str:
    return _text(value).replace("/", "\\").rstrip("\\").casefold()


def _path_within_root(path: Any, root: Any) -> bool:
    left = _path_key(path)
    right = _path_key(root)
    return bool(left and right and (left == right or left.startswith(right + "\\")))


def _safe_relative_path(value: Any) -> str:
    text = _text(value).replace("/", "\\")
    if not text or ntpath.isabs(text) or ntpath.splitdrive(text)[0]:
        return ""
    parts = [part for part in text.split("\\") if part not in ("", ".")]
    if not parts or any(part == ".." for part in parts):
        return ""
    return ntpath.join(*parts)


def _relative_under_root(path: Any, root: Any) -> str:
    try:
        relative = ntpath.relpath(_text(path), _text(root))
    except ValueError:
        return ""
    return _safe_relative_path(relative)


def _enabled(profile: Mapping[str, Any]) -> bool:
    return profile.get("enabled", True) is not False


def library_roots_from_config(config: Mapping[str, Any] | None) -> list[dict[str, str]]:
    """Return enabled library roots from resolved config in wire-safe shape."""
    try:
        profiles = library_profiles_from_config(dict(config or {}))
    except Exception:
        profiles = []
    rows: list[dict[str, str]] = []
    seen: set[str] = set()
    for profile in profiles:
        if not isinstance(profile, Mapping) or not _enabled(profile):
            continue
        library_id = _text(profile.get("id") or profile.get("library_id"))
        source_root = _text(profile.get("effective_source_root") or profile.get("source_path"))
        if not library_id or not source_root:
            continue
        key = library_id.casefold()
        if key in seen:
            continue
        seen.add(key)
        rows.append({
            "library_id": library_id,
            "name": _text(profile.get("name")) or library_id,
            "designation": _text(profile.get("designation")) or "auto",
            "source_root": source_root,
            "output_root": _text(profile.get("effective_output_root") or profile.get("output_path")),
        })
    return rows


def libraries_response_from_config(config: Mapping[str, Any] | None) -> dict[str, Any]:
    rows = library_roots_from_config(config)
    return {
        "schema_version": NETWORK_LIBRARIES_SCHEMA_VERSION,
        "libraries": rows,
        "library_count": len(rows),
        "read_only": True,
    }


def accessible_library_ids_from_config(config: Mapping[str, Any] | None) -> list[str]:
    """Return enabled library IDs whose worker-side source root is reachable."""
    ids: list[str] = []
    seen: set[str] = set()
    for library in library_roots_from_config(config):
        library_id = _text(library.get("library_id"))
        source_root = _text(library.get("source_root"))
        key = library_id.casefold()
        if not library_id or key in seen or not source_root:
            continue
        try:
            reachable = Path(source_root).is_dir()
        except OSError:
            reachable = False
        if not reachable:
            continue
        seen.add(key)
        ids.append(library_id)
    return ids


def _rows_by_library_id(rows: Iterable[Mapping[str, Any]]) -> dict[str, Mapping[str, Any]]:
    by_id: dict[str, Mapping[str, Any]] = {}
    for row in rows:
        library_id = _text(row.get("library_id") or row.get("id"))
        if not library_id:
            continue
        by_id.setdefault(library_id.casefold(), row)
    return by_id


def auto_source_path_map_from_libraries(
    coordinator_libraries: Iterable[Mapping[str, Any]],
    worker_config: Mapping[str, Any] | None,
) -> list[tuple[str, str]]:
    """Build coordinator-source to worker-source mappings by matching library IDs."""
    worker_libraries = library_roots_from_config(worker_config)
    worker_by_id = _rows_by_library_id(worker_libraries)
    mappings: list[tuple[str, str]] = []
    seen_sources: set[str] = set()
    for coord in coordinator_libraries:
        if not isinstance(coord, Mapping):
            continue
        library_id = _text(coord.get("library_id") or coord.get("id"))
        worker = worker_by_id.get(library_id.casefold())
        if worker is None:
            continue
        coordinator_root = _text(coord.get("source_root") or coord.get("source_path"))
        worker_root = _text(worker.get("source_root") or worker.get("source_path"))
        source_key = _path_key(coordinator_root)
        if not source_key or not worker_root or source_key in seen_sources:
            continue
        seen_sources.add(source_key)
        mappings.append((coordinator_root.replace("/", "\\").rstrip("\\"), worker_root.replace("/", "\\").rstrip("\\")))
    return mappings


def claim_library_fields_for_record(
    record: object,
    config: Mapping[str, Any] | None,
) -> tuple[str, str]:
    """Return additive claim ``library_id`` and safe ``relative_path`` fields."""
    source_path = _text(getattr(record, "source_path", ""))
    explicit_library_id = _text(getattr(record, "library_id", ""))
    explicit_relative = _safe_relative_path(getattr(record, "relative_path", ""))

    matched_library: Mapping[str, Any] | None = None
    best_root_len = -1
    for library in library_roots_from_config(config):
        if explicit_library_id and library["library_id"].casefold() != explicit_library_id.casefold():
            continue
        root = library.get("source_root", "")
        if _path_within_root(source_path, root):
            root_len = len(_path_key(root))
            if root_len > best_root_len:
                matched_library = library
                best_root_len = root_len

    library_id = explicit_library_id
    if not library_id and matched_library is not None:
        library_id = _text(matched_library.get("library_id"))

    relative_path = explicit_relative
    if not relative_path and matched_library is not None:
        relative_path = _relative_under_root(source_path, matched_library.get("source_root"))

    return library_id, relative_path


def resolve_worker_library_relative_path(
    worker_config: Mapping[str, Any] | None,
    library_id: Any,
    relative_path: Any,
) -> str:
    """Resolve a claim's library-relative path against the worker's roots."""
    safe_relative = _safe_relative_path(relative_path)
    library_key = _text(library_id).casefold()
    if not library_key or not safe_relative:
        return ""
    for library in library_roots_from_config(worker_config):
        if library["library_id"].casefold() != library_key:
            continue
        source_root = _text(library.get("source_root"))
        if not source_root:
            return ""
        return ntpath.join(source_root.rstrip("\\/"), safe_relative)
    return ""


def merge_manual_and_auto_path_maps(
    manual_mappings: Iterable[tuple[str, str]],
    auto_mappings: Iterable[tuple[str, str]],
) -> list[tuple[str, str]]:
    """Return effective mappings with manual entries taking precedence."""
    merged: list[tuple[str, str]] = []
    manual_keys: set[str] = set()
    for source, target in manual_mappings:
        source_text = _text(source).replace("/", "\\").rstrip("\\")
        target_text = _text(target).replace("/", "\\").rstrip("\\")
        if not source_text or not target_text:
            continue
        merged.append((source_text, target_text))
        manual_keys.add(_path_key(source_text))
    seen_auto: set[str] = set()
    for source, target in auto_mappings:
        source_text = _text(source).replace("/", "\\").rstrip("\\")
        target_text = _text(target).replace("/", "\\").rstrip("\\")
        source_key = _path_key(source_text)
        if not source_key or not target_text or source_key in manual_keys or source_key in seen_auto:
            continue
        seen_auto.add(source_key)
        merged.append((source_text, target_text))
    return merged


__all__ = [
    "NETWORK_LIBRARIES_SCHEMA_VERSION",
    "accessible_library_ids_from_config",
    "auto_source_path_map_from_libraries",
    "claim_library_fields_for_record",
    "libraries_response_from_config",
    "library_roots_from_config",
    "merge_manual_and_auto_path_maps",
    "resolve_worker_library_relative_path",
]
