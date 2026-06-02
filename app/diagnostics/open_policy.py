"""Diagnostics open command policy and result helpers."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any

from mediapipeline_desktop_app.models import ResolvedPaths

if TYPE_CHECKING:
    from mediapipeline_desktop_app.application.dto_commands import CommandResult


DIAGNOSTICS_OPEN_TARGETS = {
    "run_logs": "Run logs folder",
    "cluster_log": "cluster log file",
    "config": "active config file",
    "config_folder": "config folder",
    "workspace": "workspace folder",
    "state": "state folder",
    "pending_publish": "pending publish folder",
    "failed_reports": "failed reports folder",
    "failed_markers": "failure markers folder",
    "audit_reports": "audit reports folder",
    "queue_snapshot": "queue snapshot file",
    "active_jobs": "ActiveJobs folder",
    "completed_manifest": "completed manifest file",
    "latest_failure_report": "latest failure report",
    "latest_failure_json": "latest failure JSON",
    "latest_audit_csv": "latest audit CSV",
    "latest_priority_csv": "latest priority CSV",
    "last_stdout_log": "latest launch stdout log",
    "last_stderr_log": "latest launch stderr log",
    "sample_validation_log": "sample validation log",
}
DIAGNOSTICS_OPEN_COMMAND = "diagnostics.open"
DIAGNOSTICS_REFRESH_HINT = "diagnostics"


def _command_result(**kwargs: Any) -> "CommandResult":
    from mediapipeline_desktop_app.application.dto_commands import CommandResult

    return CommandResult(**kwargs)


def normalize_diagnostics_open_target(value: Any) -> str:
    return str(value or "").strip().casefold()


def diagnostics_open_target_label(target: str) -> str | None:
    return DIAGNOSTICS_OPEN_TARGETS.get(target)


def diagnostics_allowed_targets_error() -> str:
    return f"Allowed targets: {', '.join(sorted(DIAGNOSTICS_OPEN_TARGETS))}"


def optional_diagnostics_path(value: Any) -> Path | None:
    if value is None:
        return None
    if isinstance(value, str):
        text = value.strip()
        if "\x00" in text:
            return None
        return Path(text) if text else None
    try:
        path = Path(value)
    except (TypeError, ValueError):
        return None
    text = str(path).strip()
    return path if text and "\x00" not in text else None


def diagnostics_open_path(
    resolved: ResolvedPaths,
    target: str,
    *,
    latest_failure_report: Any = None,
    latest_failure_json: Any = None,
    latest_audit_csv: Any = None,
    latest_priority_csv: Any = None,
    last_stdout_log: Any = None,
    last_stderr_log: Any = None,
) -> Path | None:
    target_paths: dict[str, Path | None] = {
        "run_logs": Path(resolved.app_root) / "RunLogs",
        "cluster_log": Path(resolved.app_root) / "cluster.log",
        "config": resolved.config_path,
        "config_folder": resolved.config_path.parent if resolved.config_path else None,
        "workspace": resolved.workspace_root,
        "state": resolved.state_root,
        "pending_publish": resolved.pending_push_path,
        "failed_reports": resolved.failed_reports_path,
        "failed_markers": resolved.failed_markers_path,
        "audit_reports": resolved.audit_reports_path,
        "queue_snapshot": resolved.queue_snapshot_path,
        "active_jobs": resolved.active_jobs_path,
        "completed_manifest": resolved.completed_manifest_path,
        "latest_failure_report": optional_diagnostics_path(latest_failure_report),
        "latest_failure_json": optional_diagnostics_path(latest_failure_json),
        "latest_audit_csv": optional_diagnostics_path(latest_audit_csv),
        "latest_priority_csv": optional_diagnostics_path(latest_priority_csv),
        "last_stdout_log": optional_diagnostics_path(last_stdout_log),
        "last_stderr_log": optional_diagnostics_path(last_stderr_log),
        "sample_validation_log": Path(resolved.state_root or (Path(resolved.app_root) / "State"))
        / "Validation"
        / "sample_validation_log.jsonl",
    }
    return target_paths.get(target)


def diagnostics_open_success_message(target: str) -> str:
    return f"Opened {DIAGNOSTICS_OPEN_TARGETS[target]}."


def diagnostics_open_failure_message(target: str, error: Exception) -> str:
    return f"Could not open {DIAGNOSTICS_OPEN_TARGETS[target]}: {error}"


def diagnostics_open_missing_message(target: str) -> str:
    return f"No path is configured for {DIAGNOSTICS_OPEN_TARGETS[target]}."


def diagnostics_open_missing_warning(target: str) -> str:
    return f"No path is configured for target '{target}'."


def diagnostics_open_data(target: str, path: Path) -> dict[str, str]:
    return {"target": target, "path": str(path)}


def diagnostics_open_disallowed_target_result() -> CommandResult:
    return _command_result(
        command=DIAGNOSTICS_OPEN_COMMAND,
        ok=False,
        message="Diagnostics open target is not allowed.",
        severity="error",
        errors=[diagnostics_allowed_targets_error()],
        refresh_hint=DIAGNOSTICS_REFRESH_HINT,
    )


def diagnostics_open_missing_result(target: str) -> CommandResult:
    return _command_result(
        command=DIAGNOSTICS_OPEN_COMMAND,
        ok=False,
        message=diagnostics_open_missing_message(target),
        severity="warning",
        warnings=[diagnostics_open_missing_warning(target)],
        refresh_hint=DIAGNOSTICS_REFRESH_HINT,
    )


def diagnostics_open_service_unavailable_result(target: str, path: Path) -> CommandResult:
    return _command_result(
        command=DIAGNOSTICS_OPEN_COMMAND,
        ok=False,
        message="Path open service is not available.",
        severity="error",
        errors=["Path open service is not available."],
        data=diagnostics_open_data(target, path),
        refresh_hint=DIAGNOSTICS_REFRESH_HINT,
    )


def diagnostics_open_exception_result(target: str, path: Path, exc: Exception) -> CommandResult:
    return _command_result(
        command=DIAGNOSTICS_OPEN_COMMAND,
        ok=False,
        message=diagnostics_open_failure_message(target, exc),
        severity="error",
        errors=[str(exc)],
        data=diagnostics_open_data(target, path),
        refresh_hint=DIAGNOSTICS_REFRESH_HINT,
    )


def diagnostics_open_success_result(target: str, path: Path) -> CommandResult:
    return _command_result(
        command=DIAGNOSTICS_OPEN_COMMAND,
        ok=True,
        message=diagnostics_open_success_message(target),
        severity="info",
        data=diagnostics_open_data(target, path),
        refresh_hint=DIAGNOSTICS_REFRESH_HINT,
    )


__all__ = [
    "DIAGNOSTICS_OPEN_TARGETS",
    "DIAGNOSTICS_OPEN_COMMAND",
    "DIAGNOSTICS_REFRESH_HINT",
    "normalize_diagnostics_open_target",
    "diagnostics_open_target_label",
    "diagnostics_allowed_targets_error",
    "optional_diagnostics_path",
    "diagnostics_open_path",
    "diagnostics_open_success_message",
    "diagnostics_open_failure_message",
    "diagnostics_open_missing_message",
    "diagnostics_open_missing_warning",
    "diagnostics_open_data",
    "diagnostics_open_disallowed_target_result",
    "diagnostics_open_missing_result",
    "diagnostics_open_service_unavailable_result",
    "diagnostics_open_exception_result",
    "diagnostics_open_success_result",
]
