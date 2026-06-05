from __future__ import annotations

import logging

from .json_policy import loads_strict_json


_log = logging.getLogger(__name__)


def _safe_repr(value: object) -> str:
    try:
        return repr(value)
    except Exception as exc:
        return f"<unrepresentable {type(value).__name__}: {exc}>"


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
            prefix = str(key).replace("/", "\\").rstrip("\\")
            replacement = str(value).replace("/", "\\").rstrip("\\")
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
    normalized = path.replace("/", "\\")
    normalized_lower = normalized.lower()
    for prefix, replacement in mappings:
        prefix_lower = prefix.lower()
        if normalized_lower == prefix_lower or normalized_lower.startswith(prefix_lower + "\\"):
            tail = normalized[len(prefix) :]
            return replacement + tail
    return path
