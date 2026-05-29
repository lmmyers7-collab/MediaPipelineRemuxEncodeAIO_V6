"""Audit launch policy helpers for process routes."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from mediapipeline_desktop_app.config_keys import KEY_OUTSOURCE

if TYPE_CHECKING:
    from mediapipeline_desktop_app.application.dto_commands import CommandResult


AUDIT_START_COMMAND = "audit.start"
AUDIT_LIBRARY_ROOT_ERROR = "Audit library root is unavailable."


def _command_result(**kwargs: Any) -> "CommandResult":
    from mediapipeline_desktop_app.application.dto_commands import CommandResult

    return CommandResult(**kwargs)


def resolve_audit_library_root(request: dict[str, Any], config_data: dict[str, Any]) -> str:
    return str(request.get("library_root") or config_data.get(KEY_OUTSOURCE) or "").strip()


def audit_start_success_message(pid: int) -> str:
    return f"Started audit via PID {pid}."


def audit_start_success_data(
    *,
    library_root: str,
    include_sidecars: bool,
    pid: int,
    launch_prep_messages: list[str],
    launch_logs: str,
) -> dict[str, Any]:
    return {
        "library_root": library_root,
        "include_sidecars": include_sidecars,
        "pid": pid,
        "launch_prep": launch_prep_messages,
        "logs": launch_logs,
    }


def audit_missing_library_root_result() -> "CommandResult":
    return _command_result(
        command=AUDIT_START_COMMAND,
        ok=False,
        message="Audit start requires a library_root or configured Outsource path.",
        severity="error",
        errors=[AUDIT_LIBRARY_ROOT_ERROR],
    )


def audit_start_active_work_result(block_message: str) -> "CommandResult":
    return _command_result(
        command=AUDIT_START_COMMAND,
        ok=False,
        message=block_message,
        severity="warning",
        warnings=[block_message],
        refresh_hint="snapshot",
    )


def audit_start_exception_result(exc: Exception) -> "CommandResult":
    return _command_result(
        command=AUDIT_START_COMMAND,
        ok=False,
        message=f"Audit start failed: {exc}",
        severity="error",
        errors=[str(exc)],
        refresh_hint="snapshot",
    )


def audit_start_success_result(
    *,
    library_root: str,
    include_sidecars: bool,
    pid: int,
    launch_prep_messages: list[str],
    launch_logs: str,
) -> "CommandResult":
    return _command_result(
        command=AUDIT_START_COMMAND,
        ok=True,
        message=audit_start_success_message(pid),
        severity="info",
        refresh_hint="snapshot",
        data=audit_start_success_data(
            library_root=library_root,
            include_sidecars=include_sidecars,
            pid=pid,
            launch_prep_messages=launch_prep_messages,
            launch_logs=launch_logs,
        ),
    )


__all__ = [
    "AUDIT_START_COMMAND",
    "AUDIT_LIBRARY_ROOT_ERROR",
    "resolve_audit_library_root",
    "audit_start_success_message",
    "audit_start_success_data",
    "audit_missing_library_root_result",
    "audit_start_active_work_result",
    "audit_start_exception_result",
    "audit_start_success_result",
]
