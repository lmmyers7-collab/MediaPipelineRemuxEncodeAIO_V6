"""Rename apply command result payload builders."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any, Iterable, Mapping

from mediapipeline.core.rename.path_authority import OUTSIDE_CONFIGURED_ROOTS_MESSAGE, UNSCOPED_OPERATOR_PATHS_MESSAGE
from mediapipeline.core.rename.preview_policy import missing_rename_selection_warnings, rename_blocker_error_lines

if TYPE_CHECKING:
    from mediapipeline.core.kernel.dto_commands import CommandResult
    from mediapipeline.core.kernel.dto_base import JsonMap

RENAME_APPLY_COMMAND = "rename.apply"
RENAME_UNDO_COMMAND = "rename.undo"
RENAME_REFRESH_HINT = "rename"
CONFIRM_RENAME_APPLY_MESSAGE = "Rename apply requires explicit confirmation."
CONFIRM_RENAME_APPLY_WARNING = "confirm_apply must be true."
CONFIRM_RENAME_UNDO_MESSAGE = "Rename undo requires explicit confirmation."
CONFIRM_RENAME_UNDO_WARNING = "confirm_undo must be true."
NO_RENAME_UNDO_MANIFEST_MESSAGE = "Rename undo requires an undo manifest path."
NO_RENAME_SELECTION_MESSAGE = "Select one or more rename rows before applying."
NO_RENAME_SELECTION_WARNING = "No selected_sources were provided."
MISSING_RENAME_SELECTION_MESSAGE = "One or more selected rename rows are no longer in the current plan."
RENAME_APPLY_SERVICE_UNAVAILABLE_MESSAGE = "Rename apply service is not available."
RENAME_APPLY_BUSY_MESSAGE = "Rename apply blocked because another rename apply command is already in progress."


def _command_result(**fields: Any) -> "CommandResult":
    from mediapipeline.core.kernel.dto_commands import CommandResult

    return CommandResult(**fields)


def _json_safe(value: Any) -> "JsonMap":
    from mediapipeline.core.kernel.dto_base import json_safe

    return json_safe(value)


def rename_apply_confirmation_required_result() -> CommandResult:
    return _command_result(
        command=RENAME_APPLY_COMMAND,
        ok=False,
        message=CONFIRM_RENAME_APPLY_MESSAGE,
        severity="warning",
        warnings=[CONFIRM_RENAME_APPLY_WARNING],
        refresh_hint=RENAME_REFRESH_HINT,
    )


def rename_apply_no_selection_result() -> CommandResult:
    return _command_result(
        command=RENAME_APPLY_COMMAND,
        ok=False,
        message=NO_RENAME_SELECTION_MESSAGE,
        severity="warning",
        warnings=[NO_RENAME_SELECTION_WARNING],
        refresh_hint=RENAME_REFRESH_HINT,
    )


def rename_apply_service_unavailable_result() -> CommandResult:
    return _command_result(
        command=RENAME_APPLY_COMMAND,
        ok=False,
        message=RENAME_APPLY_SERVICE_UNAVAILABLE_MESSAGE,
        severity="error",
        errors=[RENAME_APPLY_SERVICE_UNAVAILABLE_MESSAGE],
        refresh_hint=RENAME_REFRESH_HINT,
    )


def rename_apply_busy_result(message: str = RENAME_APPLY_BUSY_MESSAGE) -> CommandResult:
    return _command_result(
        command=RENAME_APPLY_COMMAND,
        ok=False,
        message=message,
        severity="warning",
        warnings=[message],
        refresh_hint=RENAME_REFRESH_HINT,
    )


def rename_apply_active_work_result(message: str) -> CommandResult:
    return _command_result(
        command=RENAME_APPLY_COMMAND,
        ok=False,
        message=message,
        severity="error",
        errors=["active_work"],
        refresh_hint=RENAME_REFRESH_HINT,
    )


def rename_plan_build_exception_result(exc: Exception) -> CommandResult:
    return _command_result(
        command=RENAME_APPLY_COMMAND,
        ok=False,
        message=f"Rename plan could not be built: {exc}",
        severity="error",
        errors=[str(exc)],
        refresh_hint=RENAME_REFRESH_HINT,
    )


def rename_apply_missing_selection_result(missing: Iterable[str]) -> CommandResult:
    return _command_result(
        command=RENAME_APPLY_COMMAND,
        ok=False,
        message=MISSING_RENAME_SELECTION_MESSAGE,
        severity="warning",
        warnings=missing_rename_selection_warnings(missing),
        refresh_hint=RENAME_REFRESH_HINT,
    )


def rename_apply_blockers_result(blockers: Iterable[Mapping[str, Any]]) -> CommandResult:
    blocker_list = list(blockers)
    return _command_result(
        command=RENAME_APPLY_COMMAND,
        ok=False,
        message=f"Rename selection has {len(blocker_list)} blocked row(s).",
        severity="error",
        errors=rename_blocker_error_lines(blocker_list),
        refresh_hint=RENAME_REFRESH_HINT,
    )


def rename_apply_outside_configured_roots_result(rows: Iterable[Mapping[str, Any]]) -> CommandResult:
    row_list = list(rows)
    warnings = [OUTSIDE_CONFIGURED_ROOTS_MESSAGE]
    warnings.extend(
        f"Outside configured roots: {Path(str(row.get('source') or '')).name} ({row.get('source') or ''})"
        for row in row_list[:8]
    )
    if len(row_list) > 8:
        warnings.append(f"...and {len(row_list) - 8} more outside-root row(s).")
    warnings.append("Set allow_outside_configured_roots only after operator review of the exact source and destination paths.")
    return _command_result(
        command=RENAME_APPLY_COMMAND,
        ok=False,
        message=OUTSIDE_CONFIGURED_ROOTS_MESSAGE,
        severity="warning",
        warnings=warnings,
        refresh_hint=RENAME_REFRESH_HINT,
    )


def rename_apply_unscoped_operator_paths_result(rows: Iterable[Mapping[str, Any]]) -> CommandResult:
    row_list = list(rows)
    warnings = [UNSCOPED_OPERATOR_PATHS_MESSAGE]
    warnings.extend(
        f"Unscoped operator path: {Path(str(row.get('source') or '')).name} ({row.get('source') or ''})"
        for row in row_list[:8]
    )
    if len(row_list) > 8:
        warnings.append(f"...and {len(row_list) - 8} more unscoped row(s).")
    warnings.append("Configured media roots must be resolved by the backend before rename apply can mutate files.")
    return _command_result(
        command=RENAME_APPLY_COMMAND,
        ok=False,
        message=UNSCOPED_OPERATOR_PATHS_MESSAGE,
        severity="warning",
        warnings=warnings,
        refresh_hint=RENAME_REFRESH_HINT,
    )


def rename_apply_exception_result(exc: Exception) -> CommandResult:
    return _command_result(
        command=RENAME_APPLY_COMMAND,
        ok=False,
        message=f"Rename apply failed: {exc}",
        severity="error",
        errors=[str(exc)],
        refresh_hint=RENAME_REFRESH_HINT,
    )


def rename_apply_progress_payload(summary: Mapping[str, Any], *, renamed: int) -> dict[str, Any]:
    selected = int(summary.get("selected") or 0)
    unchanged = int(summary.get("unchanged") or 0)
    sidecars = int(summary.get("sidecars") or 0)
    media_operations = int(summary.get("media_operations") or 0)
    sidecar_operations = int(summary.get("sidecar_operations") or 0)
    percent = 100.0 if selected <= 0 else max(0.0, min(100.0, round((renamed / selected) * 100.0, 1)))
    detail = (
        f"{renamed} renamed / {selected} planned"
        f"; unchanged {unchanged}; media ops {media_operations}; sidecar ops {sidecar_operations}; sidecars {sidecars}"
    )
    updated_at = datetime.now().isoformat(timespec="seconds")
    bar = {
        "id": "rename_apply",
        "label": "Rename apply",
        "mode": "determinate",
        "percent": percent,
        "status": "complete",
        "detail": detail,
        "source": "rename.apply",
        "updated_at": updated_at,
        "stale": False,
    }
    return {
        "schema_version": "desktop_rename_apply_progress.v1",
        "status": "complete",
        "selected": selected,
        "renamed": renamed,
        "unchanged": unchanged,
        "sidecars": sidecars,
        "media_operations": media_operations,
        "sidecar_operations": sidecar_operations,
        "updated_at": updated_at,
        "progress_bars": [bar],
    }


def rename_apply_success_result(summary: Mapping[str, Any], *, renamed: int) -> CommandResult:
    rows = [_json_safe(dict(row)) for row in summary.get("rows") or [] if isinstance(row, dict)]
    progress = rename_apply_progress_payload(summary, renamed=renamed)
    return _command_result(
        command=RENAME_APPLY_COMMAND,
        ok=True,
        message=f"Rename applied: {renamed} file(s) renamed.",
        severity="info",
        refresh_hint=RENAME_REFRESH_HINT,
        data={
            "selected": int(summary.get("selected") or len(rows)),
            "renamed": renamed,
            "unchanged": int(summary.get("unchanged") or 0),
            "sidecars": int(summary.get("sidecars") or 0),
            "media_operations": int(summary.get("media_operations") or 0),
            "sidecar_operations": int(summary.get("sidecar_operations") or 0),
            "rows": rows,
            "undo_manifest": str(summary.get("undo_manifest") or ""),
            "applied_count": len(rows),
            "rename_progress": progress,
            "progress_bars": progress["progress_bars"],
        },
    )


def rename_undo_confirmation_required_result() -> CommandResult:
    return _command_result(
        command=RENAME_UNDO_COMMAND,
        ok=False,
        message=CONFIRM_RENAME_UNDO_MESSAGE,
        severity="warning",
        warnings=[CONFIRM_RENAME_UNDO_WARNING],
        refresh_hint=RENAME_REFRESH_HINT,
    )


def rename_undo_missing_manifest_result() -> CommandResult:
    return _command_result(
        command=RENAME_UNDO_COMMAND,
        ok=False,
        message=NO_RENAME_UNDO_MANIFEST_MESSAGE,
        severity="warning",
        warnings=[NO_RENAME_UNDO_MANIFEST_MESSAGE],
        refresh_hint=RENAME_REFRESH_HINT,
    )


def rename_undo_service_unavailable_result() -> CommandResult:
    message = "Rename undo service is not available."
    return _command_result(
        command=RENAME_UNDO_COMMAND,
        ok=False,
        message=message,
        severity="error",
        errors=[message],
        refresh_hint=RENAME_REFRESH_HINT,
    )


def rename_undo_busy_result(message: str = "Rename undo blocked because another rename command is already in progress.") -> CommandResult:
    return _command_result(
        command=RENAME_UNDO_COMMAND,
        ok=False,
        message=message,
        severity="warning",
        warnings=[message],
        refresh_hint=RENAME_REFRESH_HINT,
    )


def rename_undo_active_work_result(message: str) -> CommandResult:
    return _command_result(
        command=RENAME_UNDO_COMMAND,
        ok=False,
        message=message,
        severity="error",
        errors=["active_work"],
        refresh_hint=RENAME_REFRESH_HINT,
    )


def rename_undo_exception_result(exc: Exception) -> CommandResult:
    return _command_result(
        command=RENAME_UNDO_COMMAND,
        ok=False,
        message=f"Rename undo failed: {exc}",
        severity="error",
        errors=[str(exc)],
        refresh_hint=RENAME_REFRESH_HINT,
    )


def rename_undo_success_result(summary: Mapping[str, Any]) -> CommandResult:
    rows = [_json_safe(dict(row)) for row in summary.get("rows") or [] if isinstance(row, dict)]
    warnings = [str(item) for item in summary.get("warnings") or []]
    undone = int(summary.get("undone") or 0)
    return _command_result(
        command=RENAME_UNDO_COMMAND,
        ok=True,
        message=f"Rename undo applied: {undone} operation(s) restored.",
        severity="warning" if warnings else "info",
        warnings=warnings,
        refresh_hint=RENAME_REFRESH_HINT,
        data={
            "schema_version": "desktop_rename_undo_result.v1",
            "media_operations": int(summary.get("media_operations") or 0),
            "sidecar_operations": int(summary.get("sidecar_operations") or 0),
            "undone": undone,
            "skipped": int(summary.get("skipped") or 0),
            "failed": int(summary.get("failed") or 0),
            "undo_manifest": str(summary.get("undo_manifest") or ""),
            "rows": rows,
        },
    )


__all__ = [
    "RENAME_APPLY_COMMAND",
    "RENAME_UNDO_COMMAND",
    "RENAME_REFRESH_HINT",
    "CONFIRM_RENAME_APPLY_MESSAGE",
    "CONFIRM_RENAME_APPLY_WARNING",
    "CONFIRM_RENAME_UNDO_MESSAGE",
    "CONFIRM_RENAME_UNDO_WARNING",
    "NO_RENAME_UNDO_MANIFEST_MESSAGE",
    "NO_RENAME_SELECTION_MESSAGE",
    "NO_RENAME_SELECTION_WARNING",
    "MISSING_RENAME_SELECTION_MESSAGE",
    "RENAME_APPLY_SERVICE_UNAVAILABLE_MESSAGE",
    "RENAME_APPLY_BUSY_MESSAGE",
    "rename_apply_confirmation_required_result",
    "rename_apply_no_selection_result",
    "rename_apply_service_unavailable_result",
    "rename_apply_busy_result",
    "rename_apply_active_work_result",
    "rename_plan_build_exception_result",
    "rename_apply_missing_selection_result",
    "rename_apply_blockers_result",
    "rename_apply_outside_configured_roots_result",
    "rename_apply_unscoped_operator_paths_result",
    "rename_apply_exception_result",
    "rename_apply_progress_payload",
    "rename_apply_success_result",
    "rename_undo_confirmation_required_result",
    "rename_undo_missing_manifest_result",
    "rename_undo_service_unavailable_result",
    "rename_undo_busy_result",
    "rename_undo_active_work_result",
    "rename_undo_exception_result",
    "rename_undo_success_result",
]
