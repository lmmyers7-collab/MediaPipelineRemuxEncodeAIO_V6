"""Queue source-open validation and command-result policy."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any

from mediapipeline.core.queue.policy_parts.rules import QUEUE_OPEN_COMMAND, QUEUE_OPEN_SCOPES, QUEUE_OPEN_TARGETS, QUEUE_REFRESH_HINT

if TYPE_CHECKING:
    from mediapipeline.core.kernel.dto_commands import CommandResult


def _command_result(**fields: Any) -> CommandResult:
    from mediapipeline.core.kernel.dto_commands import CommandResult

    return CommandResult(**fields)


def normalize_queue_open_target(value: Any) -> str:
    return str(value or "").strip().casefold()


def normalize_queue_open_scope(value: Any) -> str:
    scope = str(value or "").strip().casefold()
    return scope or "runnable"


def allowed_queue_open_targets_text() -> str:
    return ", ".join(sorted(QUEUE_OPEN_TARGETS))


def allowed_queue_open_scopes_text() -> str:
    return ", ".join(sorted(QUEUE_OPEN_SCOPES))


def queue_open_target_label(target: str) -> str:
    return QUEUE_OPEN_TARGETS[target]


def queue_open_scope_label(scope: str) -> str:
    return QUEUE_OPEN_SCOPES[scope]


def queue_open_path(row: dict[str, Any], target: str) -> Path | None:
    source_text = str(row.get("source_path") or "").strip()
    source_root = str(row.get("source_root") or "").strip()
    if target == "source_file" and source_text:
        return Path(source_text)
    if target == "source_folder" and source_text:
        return Path(source_text).parent
    if target == "source_root" and source_root:
        return Path(source_root)
    return None


def queue_open_requires_row_result() -> CommandResult:
    return _command_result(
        command=QUEUE_OPEN_COMMAND,
        ok=False,
        message="Queue open requires a selected row.",
        severity="warning",
        warnings=["No queue row key was provided."],
        refresh_hint=QUEUE_REFRESH_HINT,
    )


def queue_open_disallowed_target_result() -> CommandResult:
    return _command_result(
        command=QUEUE_OPEN_COMMAND,
        ok=False,
        message="Queue open target is not allowed.",
        severity="error",
        errors=[f"Allowed targets: {allowed_queue_open_targets_text()}"],
        refresh_hint=QUEUE_REFRESH_HINT,
    )


def queue_open_disallowed_scope_result(scope: str) -> CommandResult:
    return _command_result(
        command=QUEUE_OPEN_COMMAND,
        ok=False,
        message="Queue open row scope is not allowed.",
        severity="error",
        errors=[f"Allowed row scopes: {allowed_queue_open_scopes_text()}"],
        data={"row_scope": scope},
        refresh_hint=QUEUE_REFRESH_HINT,
    )


def queue_open_row_missing_result(row_key: str = "") -> CommandResult:
    return _command_result(
        command=QUEUE_OPEN_COMMAND,
        ok=False,
        message="The selected queue row is no longer available.",
        severity="warning",
        warnings=["Refresh Queue and select the row again."],
        data={"row_key": row_key},
        refresh_hint=QUEUE_REFRESH_HINT,
    )


def queue_open_path_missing_result(target: str, row_key: str, row_scope: str = "runnable") -> CommandResult:
    return _command_result(
        command=QUEUE_OPEN_COMMAND,
        ok=False,
        message=f"No path is available for {queue_open_target_label(target)}.",
        severity="warning",
        warnings=[f"No path is available for target '{target}'."],
        data={"target": target, "row_key": row_key, "row_scope": row_scope},
        refresh_hint=QUEUE_REFRESH_HINT,
    )


def queue_open_path_service_unavailable_result(target: str, row_key: str, path: Path, row_scope: str = "runnable") -> CommandResult:
    return _command_result(
        command=QUEUE_OPEN_COMMAND,
        ok=False,
        message="Path open service is not available.",
        severity="error",
        errors=["Path open service is not available."],
        data=queue_open_result_data(target, row_key, path, row_scope=row_scope),
        refresh_hint=QUEUE_REFRESH_HINT,
    )


def queue_open_exception_result(target: str, row_key: str, path: Path, exc: Exception, row_scope: str = "runnable") -> CommandResult:
    return _command_result(
        command=QUEUE_OPEN_COMMAND,
        ok=False,
        message=f"Could not open {queue_open_target_label(target)}: {exc}",
        severity="error",
        errors=[str(exc)],
        data=queue_open_result_data(target, row_key, path, row_scope=row_scope),
        refresh_hint=QUEUE_REFRESH_HINT,
    )


def queue_open_success_result(target: str, row_key: str, path: Path, row_scope: str = "runnable") -> CommandResult:
    return _command_result(
        command=QUEUE_OPEN_COMMAND,
        ok=True,
        message=f"Opened {queue_open_target_label(target)} from {queue_open_scope_label(row_scope)}.",
        severity="info",
        data=queue_open_result_data(target, row_key, path, row_scope=row_scope),
        refresh_hint=QUEUE_REFRESH_HINT,
    )


def queue_open_result_data(target: str, row_key: str, path: Path, row_scope: str = "runnable") -> dict[str, str]:
    return {"target": target, "row_key": row_key, "row_scope": row_scope, "path": str(path)}


__all__ = [
    "normalize_queue_open_target",
    "normalize_queue_open_scope",
    "allowed_queue_open_targets_text",
    "allowed_queue_open_scopes_text",
    "queue_open_target_label",
    "queue_open_scope_label",
    "queue_open_path",
    "queue_open_requires_row_result",
    "queue_open_disallowed_target_result",
    "queue_open_disallowed_scope_result",
    "queue_open_row_missing_result",
    "queue_open_path_missing_result",
    "queue_open_path_service_unavailable_result",
    "queue_open_exception_result",
    "queue_open_success_result",
    "queue_open_result_data",
]
