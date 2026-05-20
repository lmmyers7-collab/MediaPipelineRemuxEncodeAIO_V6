from __future__ import annotations

from collections.abc import Callable, Iterable
from pathlib import Path
from typing import Any

from ..models import CompletedJobRecord
from .dto import CommandResult


COMPLETED_OPEN_TARGETS = {
    "output_file": "completed output file",
    "output_folder": "completed output folder",
    "sidecar": "completed sidecar file",
    "source_folder": "completed source folder",
}
COMPLETED_OPEN_COMMAND = "completed.open"
COMPLETED_REFRESH_HINT = "completed"


def normalize_completed_open_target(value: Any) -> str:
    return str(value or "").strip().casefold()


def allowed_completed_open_targets_text() -> str:
    return ", ".join(sorted(COMPLETED_OPEN_TARGETS))


def completed_open_target_label(target: str) -> str:
    return COMPLETED_OPEN_TARGETS[target]


def find_completed_record_by_key(
    records: Iterable[Any],
    row_key: str,
    key_func: Callable[[CompletedJobRecord], str],
) -> CompletedJobRecord | None:
    for item in records:
        if isinstance(item, CompletedJobRecord) and key_func(item) == row_key:
            return item
    return None


def completed_open_path(record: CompletedJobRecord, target: str) -> Path | None:
    if target == "output_file":
        return record.output_path
    if target == "output_folder":
        return record.output_path.parent
    if target == "sidecar":
        return record.sidecar_path
    if target == "source_folder":
        source_path = record.source_path
        return source_path.parent if source_path is not None else None
    return None


def completed_open_requires_row_result() -> CommandResult:
    return CommandResult(
        command=COMPLETED_OPEN_COMMAND,
        ok=False,
        message="Completed open requires a selected row.",
        severity="warning",
        warnings=["No completed row key was provided."],
        refresh_hint=COMPLETED_REFRESH_HINT,
    )


def completed_open_disallowed_target_result() -> CommandResult:
    return CommandResult(
        command=COMPLETED_OPEN_COMMAND,
        ok=False,
        message="Completed open target is not allowed.",
        severity="error",
        errors=[f"Allowed targets: {allowed_completed_open_targets_text()}"],
        refresh_hint=COMPLETED_REFRESH_HINT,
    )


def completed_open_service_unavailable_result() -> CommandResult:
    return CommandResult(
        command=COMPLETED_OPEN_COMMAND,
        ok=False,
        message="Completed history service is not available.",
        severity="error",
        errors=["Completed history service is not available."],
        refresh_hint=COMPLETED_REFRESH_HINT,
    )


def completed_open_read_exception_result(exc: Exception) -> CommandResult:
    return CommandResult(
        command=COMPLETED_OPEN_COMMAND,
        ok=False,
        message=f"Completed history could not be read: {exc}",
        severity="error",
        errors=[str(exc)],
        refresh_hint=COMPLETED_REFRESH_HINT,
    )


def completed_open_row_missing_result() -> CommandResult:
    return CommandResult(
        command=COMPLETED_OPEN_COMMAND,
        ok=False,
        message="The selected completed row is no longer available.",
        severity="warning",
        warnings=["The selected completed row key was not found in the recent manifest window."],
        refresh_hint=COMPLETED_REFRESH_HINT,
    )


def completed_open_path_missing_result(target: str, row_key: str) -> CommandResult:
    return CommandResult(
        command=COMPLETED_OPEN_COMMAND,
        ok=False,
        message=f"No path is available for {completed_open_target_label(target)}.",
        severity="warning",
        warnings=[f"No path is available for target '{target}'."],
        data={"target": target, "row_key": row_key},
        refresh_hint=COMPLETED_REFRESH_HINT,
    )


def completed_open_path_service_unavailable_result(target: str, row_key: str, path: Path) -> CommandResult:
    return CommandResult(
        command=COMPLETED_OPEN_COMMAND,
        ok=False,
        message="Path open service is not available.",
        severity="error",
        errors=["Path open service is not available."],
        data=completed_open_result_data(target, row_key, path),
        refresh_hint=COMPLETED_REFRESH_HINT,
    )


def completed_open_exception_result(target: str, row_key: str, path: Path, exc: Exception) -> CommandResult:
    return CommandResult(
        command=COMPLETED_OPEN_COMMAND,
        ok=False,
        message=f"Could not open {completed_open_target_label(target)}: {exc}",
        severity="error",
        errors=[str(exc)],
        data=completed_open_result_data(target, row_key, path),
        refresh_hint=COMPLETED_REFRESH_HINT,
    )


def completed_open_success_result(target: str, row_key: str, path: Path) -> CommandResult:
    return CommandResult(
        command=COMPLETED_OPEN_COMMAND,
        ok=True,
        message=f"Opened {completed_open_target_label(target)}.",
        severity="info",
        data=completed_open_result_data(target, row_key, path),
        refresh_hint=COMPLETED_REFRESH_HINT,
    )


def completed_open_result_data(target: str, row_key: str, path: Path) -> dict[str, str]:
    return {"target": target, "row_key": row_key, "path": str(path)}

__all__ = [
    "COMPLETED_OPEN_TARGETS",
    "COMPLETED_OPEN_COMMAND",
    "COMPLETED_REFRESH_HINT",
    "normalize_completed_open_target",
    "allowed_completed_open_targets_text",
    "completed_open_target_label",
    "find_completed_record_by_key",
    "completed_open_path",
    "completed_open_requires_row_result",
    "completed_open_disallowed_target_result",
    "completed_open_service_unavailable_result",
    "completed_open_read_exception_result",
    "completed_open_row_missing_result",
    "completed_open_path_missing_result",
    "completed_open_path_service_unavailable_result",
    "completed_open_exception_result",
    "completed_open_success_result",
    "completed_open_result_data",
]
