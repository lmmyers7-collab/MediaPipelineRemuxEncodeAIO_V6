from __future__ import annotations

import logging
import ntpath

from .json_policy import loads_strict_json


_log = logging.getLogger(__name__)


def _safe_repr(value: object) -> str:
    try:
        return repr(value)
    except Exception as exc:
        return f"<unrepresentable {type(value).__name__}: {exc}>"


def _has_parent_segment(value: str) -> bool:
    _drive, tail = ntpath.splitdrive(value.replace("/", "\\"))
    return any(part == ".." for part in tail.split("\\") if part)


def _is_full_absolute_windows_path(value: str) -> bool:
    drive, tail = ntpath.splitdrive(value)
    if drive.startswith("\\\\"):
        return True
    if drive:
        return tail.startswith("\\")
    return False


def _normalize_root(value: object, field_name: str) -> str:
    text = str(value or "").strip().replace("/", "\\")
    if not text:
        raise ValueError(f"{field_name} must be non-empty.")
    if _has_parent_segment(text):
        raise ValueError(f"{field_name} must not contain parent traversal.")
    normalized = ntpath.normpath(text)
    if not _is_full_absolute_windows_path(normalized):
        raise ValueError(f"{field_name} must be a full absolute Windows path.")
    return normalized


def _path_key(value: object) -> str:
    return ntpath.normcase(ntpath.normpath(str(value or "").replace("/", "\\"))).rstrip("\\")


def _match_key(value: object) -> str:
    return ntpath.normcase(str(value or "").replace("/", "\\")).rstrip("\\")


def _path_within_root(path: str, root: str) -> bool:
    path_key = _path_key(path)
    root_key = _path_key(root)
    if not path_key or not root_key:
        return False
    root_prefix = root_key if root_key.endswith("\\") else root_key + "\\"
    return path_key == root_key or path_key.startswith(root_prefix)


def parse_source_path_map(raw: str) -> list[tuple[str, str]]:
    """Parse WorkerSourcePathMap JSON into ordered prefix replacements."""
    if not raw:
        return []
    try:
        payload = loads_strict_json(raw)
    except Exception as exc:
        _log.warning("WorkerSourcePathMap is not valid JSON: %s", exc)
        return []
    if not isinstance(payload, dict):
        _log.warning("WorkerSourcePathMap must be a JSON object {prefix: replacement}.")
        return []

    mappings: list[tuple[str, str]] = []
    for key, value in payload.items():
        try:
            prefix = _normalize_root(key, "WorkerSourcePathMap prefix")
            replacement = _normalize_root(value, "WorkerSourcePathMap replacement")
        except Exception as exc:
            _log.warning(
                "WorkerSourcePathMap entry could not be parsed for key %s: %s",
                _safe_repr(key),
                exc,
            )
            continue
        if prefix and replacement:
            mappings.append((prefix, replacement))
    return mappings


def apply_source_path_map(path: str, mappings: list[tuple[str, str]]) -> str:
    """Apply the first matching Windows-style path prefix rewrite."""
    if not mappings or not path:
        return path
    normalized = str(path).strip().replace("/", "\\")
    normalized_key = _match_key(normalized)
    for prefix, replacement in mappings:
        try:
            safe_prefix = _normalize_root(prefix, "WorkerSourcePathMap prefix")
            safe_replacement = _normalize_root(replacement, "WorkerSourcePathMap replacement")
        except ValueError:
            continue
        prefix_key = _match_key(safe_prefix)
        prefix_boundary = prefix_key if prefix_key.endswith("\\") else prefix_key + "\\"
        if normalized_key == prefix_key or normalized_key.startswith(prefix_boundary):
            tail = normalized[len(safe_prefix) :]
            if _has_parent_segment(tail):
                raise ValueError("WorkerSourcePathMap mapped tail contains parent traversal.")
            mapped = ntpath.normpath(safe_replacement + tail)
            if not _path_within_root(mapped, safe_replacement):
                raise ValueError("WorkerSourcePathMap mapped path escapes replacement root.")
            return mapped
    return path
