"""Audit launch policy helpers for process routes."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from mediapipeline.core.kernel.config_keys import KEY_OUTSOURCE

if TYPE_CHECKING:
    from mediapipeline.desktop.application.dto_commands import CommandResult


AUDIT_START_COMMAND = "audit.start"
AUDIT_STOP_COMMAND = "audit.stop"
AUDIT_LIBRARY_ROOT_ERROR = "Audit library root is unavailable."
AUDIT_STOP_CONFIRM_ERROR = "Audit stop requires confirm_stop=true."


def _command_result(**kwargs: Any) -> "CommandResult":
    from mediapipeline.desktop.application.dto_commands import CommandResult

    return CommandResult(**kwargs)


def _clean_library_root(value: Any) -> str:
    return str(value or "").strip()


def resolve_audit_library_roots(request: dict[str, Any], config_data: dict[str, Any]) -> list[str]:
    roots: list[str] = []
    seen: set[str] = set()
    raw_roots = request.get("library_roots")
    values = raw_roots if isinstance(raw_roots, list) else []
    if not values:
        values = [request.get("library_root")]
    for value in values:
        root = _clean_library_root(value)
        key = root.replace("/", "\\").rstrip("\\").casefold()
        if not root or key in seen:
            continue
        seen.add(key)
        roots.append(root)
    if roots:
        return roots
    fallback = _clean_library_root(config_data.get(KEY_OUTSOURCE))
    return [fallback] if fallback else []


def resolve_audit_library_root(request: dict[str, Any], config_data: dict[str, Any]) -> str:
    roots = resolve_audit_library_roots(request, config_data)
    return roots[0] if roots else ""


def audit_start_success_message(pid: int) -> str:
    return f"Started audit via PID {pid}."


def audit_start_success_data(
    *,
    library_root: str,
    library_roots: list[str] | None = None,
    include_sidecars: bool,
    pid: int,
    launch_prep_messages: list[str],
    launch_logs: str,
) -> dict[str, Any]:
    roots = list(library_roots or ([library_root] if library_root else []))
    return {
        "library_root": library_root,
        "library_roots": roots,
        "library_root_count": len(roots),
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


def audit_start_config_blocked_result(message: str, data: dict[str, Any]) -> "CommandResult":
    return _command_result(
        command=AUDIT_START_COMMAND,
        ok=False,
        message=message,
        severity="error",
        errors=[message],
        refresh_hint="settings",
        data=data,
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
    library_roots: list[str] | None = None,
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
            library_roots=library_roots,
            include_sidecars=include_sidecars,
            pid=pid,
            launch_prep_messages=launch_prep_messages,
            launch_logs=launch_logs,
        ),
    )


def audit_stop_confirm_required_result() -> "CommandResult":
    return _command_result(
        command=AUDIT_STOP_COMMAND,
        ok=False,
        message=AUDIT_STOP_CONFIRM_ERROR,
        severity="error",
        errors=[AUDIT_STOP_CONFIRM_ERROR],
    )


def audit_stop_active_work_result(block_message: str) -> "CommandResult":
    return _command_result(
        command=AUDIT_STOP_COMMAND,
        ok=False,
        message=block_message,
        severity="warning",
        warnings=[block_message],
        refresh_hint="snapshot",
    )


def audit_stop_exception_result(exc: Exception) -> "CommandResult":
    return _command_result(
        command=AUDIT_STOP_COMMAND,
        ok=False,
        message=f"Audit stop failed: {exc}",
        severity="error",
        errors=[str(exc)],
        refresh_hint="snapshot",
    )


def audit_stop_success_result(
    *,
    messages: list[str],
    progress_reset: str,
    reason: str,
) -> "CommandResult":
    summary = "; ".join(messages) if messages else "No active audit process tree was found."
    return _command_result(
        command=AUDIT_STOP_COMMAND,
        ok=True,
        message=f"Audit stop recorded. {summary}",
        severity="info",
        refresh_hint="snapshot",
        data={
            "schema_version": "desktop_audit_stop_result.v1",
            "requested_scope": "audit",
            "job_kinds": ["audit"],
            "stopped_process_tree_count": len(messages),
            "cleanup_messages": messages,
            "progress_reset": progress_reset,
            "audit_progress_status": "stopped",
            "reason": reason,
        },
    )


__all__ = [
    "AUDIT_START_COMMAND",
    "AUDIT_STOP_COMMAND",
    "AUDIT_LIBRARY_ROOT_ERROR",
    "AUDIT_STOP_CONFIRM_ERROR",
    "resolve_audit_library_roots",
    "resolve_audit_library_root",
    "audit_start_success_message",
    "audit_start_success_data",
    "audit_missing_library_root_result",
    "audit_start_active_work_result",
    "audit_start_config_blocked_result",
    "audit_start_exception_result",
    "audit_start_success_result",
    "audit_stop_confirm_required_result",
    "audit_stop_active_work_result",
    "audit_stop_exception_result",
    "audit_stop_success_result",
]
