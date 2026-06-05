"""Queue row identity, scalar coercion, and open-target helpers."""

from __future__ import annotations

from typing import Any, Mapping

LIBRARY_EFFECTIVE_SETTINGS_SCOPE = "library_only"
RUNTIME_EVIDENCE_NOTE = "resolved during job processing"
OVERRIDE_LAYERS_PENDING = ["show", "folder", "file"]

def queue_row_key(row: dict[str, Any]) -> str:
    return "\x1f".join(
        [
            str(row.get("source_path") or ""),
            str(row.get("global_order") or ""),
            str(row.get("queue_index") or ""),
            str(row.get("route_name") or ""),
        ]
    ).casefold()

def _json_mapping(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}

def _json_list(value: Any) -> list[str]:
    return [str(item) for item in value if str(item).strip()] if isinstance(value, list) else []

def _text_value(value: Any) -> str:
    return str(value or "").strip()

def _float_value(value: Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0

def _bool_value(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if value in (None, ""):
        return False
    return str(value).strip().casefold() in {"1", "true", "yes", "y", "on"}

def _queue_normalized_path_key(value: Any) -> str:
    return str(value or "").replace("\\", "/").strip().casefold()

def queue_row_available_open_targets(row: dict[str, Any]) -> list[str]:
    targets: list[str] = []
    if str(row.get("source_path") or "").strip():
        targets.extend(["source_file", "source_folder"])
    if str(row.get("source_root") or "").strip():
        targets.append("source_root")
    return targets
