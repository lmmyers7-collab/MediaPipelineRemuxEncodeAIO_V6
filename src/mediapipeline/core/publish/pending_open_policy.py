from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any, Mapping

from .pending_results import (
    PENDING_PUBLISH_OPEN_COMMAND,
    PENDING_PUBLISH_OPEN_TARGETS,
    PENDING_PUBLISH_SERVICE_UNAVAILABLE_MESSAGE,
    _command_result,
)

if TYPE_CHECKING:
    from mediapipeline.desktop.application.dto_commands import CommandResult

def normalize_pending_publish_open_target(value: Any) -> str:
    return str(value or "").strip().casefold()


def pending_publish_open_target_label(target: str) -> str | None:
    return PENDING_PUBLISH_OPEN_TARGETS.get(target)


def normalize_pending_publish_row_key(value: Any) -> str:
    return str(value or "").strip(" \t\r\n").casefold()


def pending_publish_open_allowed_targets_text() -> str:
    return f"Allowed targets: {', '.join(sorted(PENDING_PUBLISH_OPEN_TARGETS))}"


def optional_pending_publish_path(value: Any) -> Path | None:
    text = str(value or "").strip()
    return Path(text) if text else None


def pending_publish_open_path(row: Mapping[str, Any], target: str) -> Path | None:
    if target in {"play_local_file", "local_file"}:
        return optional_pending_publish_path(row.get("local_file"))
    if target == "manifest":
        return optional_pending_publish_path(row.get("manifest_path"))
    if target == "destination_folder":
        destination = optional_pending_publish_path(row.get("server_out"))
        return destination.parent if destination else None
    if target == "source_folder":
        source = optional_pending_publish_path(row.get("source_path"))
        return source.parent if source else None
    return None


def pending_publish_open_result_data(target: str, row_key: str, path: Path | None = None) -> dict[str, str]:
    data = {"target": target, "row_key": row_key}
    if path is not None:
        data["path"] = str(path)
    return data


def pending_publish_open_disallowed_target_result() -> CommandResult:
    return _command_result(
        command=PENDING_PUBLISH_OPEN_COMMAND,
        ok=False,
        message="Pending publish open target is not allowed.",
        severity="error",
        errors=[pending_publish_open_allowed_targets_text()],
        refresh_hint="pending_publish",
    )


def pending_publish_open_missing_row_result(row_key: str) -> CommandResult:
    return _command_result(
        command=PENDING_PUBLISH_OPEN_COMMAND,
        ok=False,
        message="Pending publish row was not found in the current backend scan.",
        severity="warning",
        warnings=["Refresh pending publish and select the row again."],
        data={"row_key": row_key},
        refresh_hint="pending_publish",
    )


def pending_publish_open_scan_exception_result(row_key: str, exc: Exception) -> CommandResult:
    return _command_result(
        command=PENDING_PUBLISH_OPEN_COMMAND,
        ok=False,
        message=f"Pending publish scan failed before open: {exc}",
        severity="error",
        errors=[str(exc)],
        data={"row_key": row_key},
        refresh_hint="pending_publish",
    )


def pending_publish_open_scan_service_unavailable_result(row_key: str) -> CommandResult:
    return _command_result(
        command=PENDING_PUBLISH_OPEN_COMMAND,
        ok=False,
        message=PENDING_PUBLISH_SERVICE_UNAVAILABLE_MESSAGE,
        severity="error",
        errors=[PENDING_PUBLISH_SERVICE_UNAVAILABLE_MESSAGE],
        data={"row_key": row_key},
        refresh_hint="pending_publish",
    )


def pending_publish_open_missing_path_result(target: str, row_key: str) -> CommandResult:
    label = PENDING_PUBLISH_OPEN_TARGETS.get(target, target)
    return _command_result(
        command=PENDING_PUBLISH_OPEN_COMMAND,
        ok=False,
        message=f"No path is available for {label}.",
        severity="warning",
        warnings=[f"No path is available for target '{target}'."],
        data=pending_publish_open_result_data(target, row_key),
        refresh_hint="pending_publish",
    )


def pending_publish_open_service_unavailable_result(target: str, row_key: str, path: Path) -> CommandResult:
    return _command_result(
        command=PENDING_PUBLISH_OPEN_COMMAND,
        ok=False,
        message="Path open service is not available.",
        severity="error",
        errors=["Path open service is not available."],
        data=pending_publish_open_result_data(target, row_key, path),
        refresh_hint="pending_publish",
    )


def pending_publish_open_exception_result(target: str, row_key: str, path: Path, exc: Exception) -> CommandResult:
    label = PENDING_PUBLISH_OPEN_TARGETS.get(target, target)
    return _command_result(
        command=PENDING_PUBLISH_OPEN_COMMAND,
        ok=False,
        message=f"Could not open {label}: {exc}",
        severity="error",
        errors=[str(exc)],
        data=pending_publish_open_result_data(target, row_key, path),
        refresh_hint="pending_publish",
    )


def pending_publish_open_success_result(target: str, row_key: str, path: Path) -> CommandResult:
    label = PENDING_PUBLISH_OPEN_TARGETS.get(target, target)
    message = (
        "Opened parked output playback with the default app."
        if target == "play_local_file"
        else f"Opened {label}."
    )
    return _command_result(
        command=PENDING_PUBLISH_OPEN_COMMAND,
        ok=True,
        message=message,
        severity="info",
        data=pending_publish_open_result_data(target, row_key, path),
        refresh_hint="pending_publish",
    )


__all__ = [
    "normalize_pending_publish_open_target",
    "pending_publish_open_target_label",
    "normalize_pending_publish_row_key",
    "pending_publish_open_allowed_targets_text",
    "optional_pending_publish_path",
    "pending_publish_open_path",
    "pending_publish_open_result_data",
    "pending_publish_open_disallowed_target_result",
    "pending_publish_open_missing_row_result",
    "pending_publish_open_scan_exception_result",
    "pending_publish_open_scan_service_unavailable_result",
    "pending_publish_open_missing_path_result",
    "pending_publish_open_service_unavailable_result",
    "pending_publish_open_exception_result",
    "pending_publish_open_success_result",
]
