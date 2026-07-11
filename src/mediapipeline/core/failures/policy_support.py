"""Failure preview policy and result helpers."""

from __future__ import annotations

import os
from pathlib import Path
from typing import TYPE_CHECKING, Any

from mediapipeline.core.failures.retry_state import retry_state_for_failure_row, retry_state_payload
from mediapipeline.core.failures.contracts import FailureRecord

if TYPE_CHECKING:
    from mediapipeline.core.kernel.dto_inventory import FailurePreviewDto


FAILURE_MARKER_SERVICE_UNAVAILABLE_MESSAGE = "Failure marker service is not available."
FAILURE_MARKERS_EMPTY_MESSAGE = "No failure markers are available from the state store."
FAILURE_REPORT_SERVICE_UNAVAILABLE_MESSAGE = "Failure report service is not available."
FAILURE_NO_JSON_REPORT_MESSAGE = "No failure JSON report is available yet."
FAILURE_LOADER_UNAVAILABLE_MESSAGE = "Failure report loader is not available."
FAILURE_JSON_EMPTY_MESSAGE = "Latest failure JSON contains no rows."


FAILURE_RESOLUTION_SCHEMA_VERSION = "desktop_failure_resolution.v1"
FAILURE_RESOLUTION_GROUP_SCHEMA_VERSION = "desktop_failure_resolution_group.v1"
FAILURE_EVIDENCE_DETAILS_SCHEMA_VERSION = "desktop_failure_evidence_details.v1"
FAILURE_EVIDENCE_MAX_LINES = 10
FAILURE_EVIDENCE_MAX_STREAM_ROWS = 16
FAILURE_EVIDENCE_MAX_PROOF_FIELDS = 16
FAILURE_OPEN_TARGETS = {
    "artifact": "failure artifact",
    "repro": "reproduction file",
    "record_file": "failure record file",
    "record_folder": "failure record folder",
}
FAILURE_RESOLUTION_OWNER_PAGES = {
    "Pending Publish": "pending",
    "Queue": "queue",
    "Settings": "settings",
    "Completed": "completed",
    "Diagnostics": "diagnostics",
    "Manual review": "diagnostics",
    "Backend retry": "",
}
FAILURE_LIFECYCLE_LABELS = {
    "new": "New",
    "acknowledged": "Acknowledged",
    "working": "Working",
    "waiting_backend": "Waiting retry",
    "ready_to_clear": "Ready to clear",
    "resolved": "Resolved",
    "reopened": "Reopened",
}
FAILURE_LIFECYCLE_TRANSITION_LABELS = {
    "acknowledge": "Acknowledge",
    "start_work": "Start work",
    "complete_step": "Complete step",
    "waive_step": "Waive step",
    "mark_resolved": "Mark resolved",
    "reopen": "Reopen",
}



def _failure_preview_dto(**kwargs: Any) -> FailurePreviewDto:
    from mediapipeline.core.kernel.dto_inventory import FailurePreviewDto

    return FailurePreviewDto(**kwargs)


def normalize_failure_source_kind(value: Any) -> str:
    return str(value or "latest_json").strip().casefold()


def bounded_failure_limit(value: Any, *, default: int = 100, minimum: int = 1, maximum: int = 500) -> int:
    try:
        limit = int(value or default)
    except (TypeError, ValueError):
        limit = default
    return min(maximum, max(minimum, limit))


def normalize_failure_open_target(value: Any) -> str:
    return str(value or "").strip().casefold()


def failure_open_target_label(target: str) -> str:
    return FAILURE_OPEN_TARGETS.get(target, "failure evidence")


def allowed_failure_open_targets_text() -> str:
    return ", ".join(sorted(FAILURE_OPEN_TARGETS))


def _failure_open_path_text(row: dict[str, object], *keys: str) -> str:
    for key in keys:
        text = _failure_text(row.get(key))
        if text:
            return text
    return ""


def _failure_open_allowed_roots(resolved: object, *, include_artifacts: bool) -> list[Path]:
    roots: list[Path] = []
    if not include_artifacts:
        for attr in ("failed_reports_path", "failed_markers_path"):
            value = getattr(resolved, attr, None)
            if value:
                roots.append(Path(value))
    else:
        state_root = getattr(resolved, "state_root", None)
        local_base = getattr(resolved, "local_base", None)
        if state_root:
            roots.append(Path(state_root) / "Failures" / "Artifacts")
        elif local_base:
            roots.append(Path(local_base) / "State" / "Failures" / "Artifacts")
        if local_base:
            roots.append(Path(local_base) / "Failed" / "Artifacts")

    unique: list[Path] = []
    seen: set[str] = set()
    for root in roots:
        key = os.path.normcase(os.path.abspath(str(root)))
        if key in seen:
            continue
        seen.add(key)
        unique.append(root)
    return unique


def _failure_path_is_under(path: Path, roots: list[Path]) -> bool:
    try:
        path_key = os.path.normcase(os.path.abspath(str(path)))
    except (TypeError, ValueError):
        return False
    for root in roots:
        try:
            root_key = os.path.normcase(os.path.abspath(str(root)))
            if os.path.commonpath([path_key, root_key]) == root_key:
                return True
        except (TypeError, ValueError):
            continue
    return False


def failure_open_path(row: dict[str, object], target: str, resolved: object) -> Path | None:
    if target == "artifact":
        raw = _failure_open_path_text(row, "artifact_path", "ArtifactPath")
        candidate = Path(raw) if raw else None
        roots = _failure_open_allowed_roots(resolved, include_artifacts=True)
    elif target == "repro":
        raw = _failure_open_path_text(row, "repro_path", "ReproPath", "reproduction_path")
        candidate = Path(raw) if raw else None
        roots = _failure_open_allowed_roots(resolved, include_artifacts=True)
    else:
        raw = _failure_open_path_text(row, "source_json")
        candidate = Path(raw) if raw else None
        if target == "record_folder" and candidate is not None:
            candidate = candidate.parent
        roots = _failure_open_allowed_roots(resolved, include_artifacts=False)
    if target not in FAILURE_OPEN_TARGETS or candidate is None:
        return None
    return candidate if _failure_path_is_under(candidate, roots) else None


def _failure_text(value: Any) -> str:
    return str(value or "").strip()


def _failure_payload_value(payload: dict[str, Any], *keys: str) -> Any:
    for key in keys:
        if key not in payload:
            continue
        value = payload.get(key)
        if value is None:
            continue
        if isinstance(value, str) and not value.strip():
            continue
        return value
    return None


def _failure_mapping(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _failure_payload_mapping(payload: dict[str, Any], *keys: str) -> dict[str, Any]:
    return _failure_mapping(_failure_payload_value(payload, *keys))


def _failure_list(value: Any) -> list[Any]:
    if isinstance(value, list):
        return value
    if isinstance(value, tuple):
        return list(value)
    if value is None:
        return []
    return [value]


def _failure_evidence_value(mapping: dict[str, Any], *keys: str) -> Any:
    for key in keys:
        if key in mapping and mapping.get(key) is not None:
            return mapping.get(key)
    return None


def _failure_evidence_int(value: Any, default: int = 0) -> int:
    try:
        fallback = int(default)
    except (TypeError, ValueError):
        fallback = 0
    if value is None:
        return fallback
    try:
        return int(value)
    except (TypeError, ValueError):
        return fallback


def _failure_evidence_bool(value: Any, default: bool = False) -> bool:
    if isinstance(value, bool):
        return value
    text = _failure_text(value).casefold()
    if text in {"1", "true", "yes"}:
        return True
    if text in {"0", "false", "no"}:
        return False
    return default


def _failure_bounded_text(value: Any, limit: int = 240) -> str:
    text = _failure_text(value)
    if len(text) <= limit:
        return text
    return f"{text[: limit - 3].rstrip()}..."


def _failure_unique_lines(lines: list[str], *, limit: int = FAILURE_EVIDENCE_MAX_LINES) -> list[str]:
    unique: list[str] = []
    seen: set[str] = set()
    for line in lines:
        text = _failure_bounded_text(line)
        if not text:
            continue
        key = text.casefold()
        if key in seen:
            continue
        seen.add(key)
        unique.append(text)
        if len(unique) >= limit:
            break
    return unique

__all__ = (
    "FAILURE_MARKER_SERVICE_UNAVAILABLE_MESSAGE",
    "FAILURE_MARKERS_EMPTY_MESSAGE",
    "FAILURE_REPORT_SERVICE_UNAVAILABLE_MESSAGE",
    "FAILURE_NO_JSON_REPORT_MESSAGE",
    "FAILURE_LOADER_UNAVAILABLE_MESSAGE",
    "FAILURE_JSON_EMPTY_MESSAGE",
    "FAILURE_RESOLUTION_SCHEMA_VERSION",
    "FAILURE_RESOLUTION_GROUP_SCHEMA_VERSION",
    "FAILURE_EVIDENCE_DETAILS_SCHEMA_VERSION",
    "FAILURE_EVIDENCE_MAX_LINES",
    "FAILURE_EVIDENCE_MAX_STREAM_ROWS",
    "FAILURE_EVIDENCE_MAX_PROOF_FIELDS",
    "FAILURE_OPEN_TARGETS",
    "FAILURE_RESOLUTION_OWNER_PAGES",
    "FAILURE_LIFECYCLE_LABELS",
    "FAILURE_LIFECYCLE_TRANSITION_LABELS",
    "_failure_preview_dto",
    "normalize_failure_source_kind",
    "bounded_failure_limit",
    "normalize_failure_open_target",
    "failure_open_target_label",
    "allowed_failure_open_targets_text",
    "_failure_open_path_text",
    "_failure_open_allowed_roots",
    "_failure_path_is_under",
    "failure_open_path",
    "_failure_text",
    "_failure_payload_value",
    "_failure_mapping",
    "_failure_payload_mapping",
    "_failure_list",
    "_failure_evidence_value",
    "_failure_evidence_int",
    "_failure_evidence_bool",
    "_failure_bounded_text",
    "_failure_unique_lines",
)
