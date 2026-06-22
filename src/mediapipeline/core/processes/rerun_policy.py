"""CSV rerun launch request and result policy helpers."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from mediapipeline.desktop.application.dto_commands import CommandResult

CSV_RERUN_START_COMMAND = "rerun.start"
CSV_RERUN_PATH_ERROR = "CSV path is required."
CSV_RERUN_MODE_ERROR = "stage_mode must be copy, original_mode must be keep, and return_mode must be park."
CSV_RERUN_PLAN_MODE_ERROR = "dry_run and plan_only cannot both be true."


def _command_result(**kwargs: Any) -> "CommandResult":
    from mediapipeline.desktop.application.dto_commands import CommandResult

    return CommandResult(**kwargs)


def normalize_rerun_csv_path(value: Any) -> str:
    return str(value or "").strip()


def rerun_csv_path_from_request(request: dict[str, Any]) -> Path | None:
    raw_csv_path = normalize_rerun_csv_path(request.get("csv_path"))
    if not raw_csv_path:
        return None
    return Path(raw_csv_path)


def normalize_rerun_mode(value: Any, default: str) -> str:
    return str(value or default).strip().casefold()


def rerun_modes_from_request(request: dict[str, Any]) -> tuple[str, str, str]:
    return (
        normalize_rerun_mode(request.get("stage_mode"), "copy"),
        normalize_rerun_mode(request.get("original_mode"), "keep"),
        normalize_rerun_mode(request.get("return_mode"), "park"),
    )


def rerun_modes_are_supported(stage_mode: str, original_mode: str, return_mode: str) -> bool:
    return stage_mode == "copy" and original_mode == "keep" and return_mode == "park"


def rerun_bool_from_request(request: dict[str, Any], key: str) -> bool:
    return request.get(key) is True


def rerun_dry_run_from_request(request: dict[str, Any]) -> bool:
    return rerun_bool_from_request(request, "dry_run")


def rerun_plan_only_from_request(request: dict[str, Any]) -> bool:
    return rerun_bool_from_request(request, "plan_only")


def rerun_plan_flags_are_supported(dry_run: bool, plan_only: bool) -> bool:
    return not (dry_run and plan_only)


def rerun_run_label(dry_run: bool, plan_only: bool = False) -> str:
    if plan_only:
        return "plan-only check"
    return "dry run" if dry_run else "run"


def rerun_start_success_message(pid: int, dry_run: bool, plan_only: bool = False) -> str:
    return f"Started CSV rerun {rerun_run_label(dry_run, plan_only)} via PID {pid}."


def rerun_start_success_data(
    *,
    csv_path: Path,
    dry_run: bool,
    plan_only: bool,
    stage_mode: str,
    original_mode: str,
    return_mode: str,
    pid: int,
    launch_logs: str,
) -> dict[str, Any]:
    return {
        "csv_path": str(csv_path),
        "dry_run": dry_run,
        "plan_only": plan_only,
        "stage_mode": stage_mode,
        "original_mode": original_mode,
        "return_mode": return_mode,
        "pid": pid,
        "logs": launch_logs,
    }


def rerun_csv_path_missing_result() -> "CommandResult":
    return _command_result(
        command=CSV_RERUN_START_COMMAND,
        ok=False,
        message="CSV rerun start requires csv_path.",
        severity="error",
        errors=[CSV_RERUN_PATH_ERROR],
    )


def rerun_mode_error_result() -> "CommandResult":
    return _command_result(
        command=CSV_RERUN_START_COMMAND,
        ok=False,
        message="CSV rerun API defaults are limited to copy/keep/park for this migration phase.",
        severity="error",
        errors=[CSV_RERUN_MODE_ERROR],
    )


def rerun_plan_mode_error_result() -> "CommandResult":
    return _command_result(
        command=CSV_RERUN_START_COMMAND,
        ok=False,
        message="CSV rerun accepts either dry_run or plan_only, not both.",
        severity="error",
        errors=[CSV_RERUN_PLAN_MODE_ERROR],
    )


def rerun_start_active_work_result(block_message: str) -> "CommandResult":
    return _command_result(
        command=CSV_RERUN_START_COMMAND,
        ok=False,
        message=block_message,
        severity="warning",
        warnings=[block_message],
        refresh_hint="snapshot",
    )


def rerun_start_config_blocked_result(message: str, data: dict[str, Any]) -> "CommandResult":
    return _command_result(
        command=CSV_RERUN_START_COMMAND,
        ok=False,
        message=message,
        severity="error",
        errors=[message],
        refresh_hint="settings",
        data=data,
    )


def rerun_start_exception_result(exc: Exception) -> "CommandResult":
    return _command_result(
        command=CSV_RERUN_START_COMMAND,
        ok=False,
        message=f"CSV rerun start failed: {exc}",
        severity="error",
        errors=[str(exc)],
        refresh_hint="snapshot",
    )


def rerun_start_success_result(
    *,
    csv_path: Path,
    dry_run: bool,
    plan_only: bool,
    stage_mode: str,
    original_mode: str,
    return_mode: str,
    pid: int,
    launch_logs: str,
) -> "CommandResult":
    return _command_result(
        command=CSV_RERUN_START_COMMAND,
        ok=True,
        message=rerun_start_success_message(pid, dry_run, plan_only),
        severity="info",
        refresh_hint="snapshot",
        data=rerun_start_success_data(
            csv_path=csv_path,
            dry_run=dry_run,
            plan_only=plan_only,
            stage_mode=stage_mode,
            original_mode=original_mode,
            return_mode=return_mode,
            pid=pid,
            launch_logs=launch_logs,
        ),
    )

__all__ = [
    "CSV_RERUN_START_COMMAND",
    "CSV_RERUN_PATH_ERROR",
    "CSV_RERUN_MODE_ERROR",
    "CSV_RERUN_PLAN_MODE_ERROR",
    "normalize_rerun_csv_path",
    "rerun_csv_path_from_request",
    "normalize_rerun_mode",
    "rerun_modes_from_request",
    "rerun_modes_are_supported",
    "rerun_bool_from_request",
    "rerun_dry_run_from_request",
    "rerun_plan_only_from_request",
    "rerun_plan_flags_are_supported",
    "rerun_run_label",
    "rerun_start_success_message",
    "rerun_start_success_data",
    "rerun_csv_path_missing_result",
    "rerun_mode_error_result",
    "rerun_plan_mode_error_result",
    "rerun_start_active_work_result",
    "rerun_start_config_blocked_result",
    "rerun_start_exception_result",
    "rerun_start_success_result",
]
