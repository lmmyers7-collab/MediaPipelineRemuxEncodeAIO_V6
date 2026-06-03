"""Pipeline launch request and result policy helpers."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import asdict, is_dataclass
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from mediapipeline_desktop_app.application.dto_commands import CommandResult

PIPELINE_START_COMMAND = "pipeline.start"
PIPELINE_START_MODES = frozenset({"continuous", "once", "validate", "drain_pending_pushes"})
PIPELINE_START_MODE_ERROR = "Mode must be continuous, once, validate, or drain_pending_pushes."
PIPELINE_SLEEP_SECONDS_ERROR = "Sleep seconds must be a whole number."
PIPELINE_EXTRA_ARGS_ERROR = "Extra pipeline arguments are not accepted by the Local API pipeline.start command."


def _command_result(**kwargs: Any) -> "CommandResult":
    from mediapipeline_desktop_app.application.dto_commands import CommandResult

    return CommandResult(**kwargs)


def _json_safe(value: Any) -> Any:
    if is_dataclass(value):
        return _json_safe(asdict(value))
    if isinstance(value, datetime):
        return value.astimezone().isoformat() if value.tzinfo else value.isoformat()
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, Mapping):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, tuple | list):
        return [_json_safe(item) for item in value]
    if isinstance(value, set):
        return [_json_safe(item) for item in sorted(value, key=str)]
    return value


def normalize_pipeline_start_mode(value: Any) -> str:
    return str(value or "once").strip().casefold()


def is_supported_pipeline_start_mode(mode: str) -> bool:
    return mode in PIPELINE_START_MODES


def parse_pipeline_sleep_seconds(value: Any) -> tuple[int | None, str | None]:
    try:
        return max(1, int(value or 30)), None
    except (TypeError, ValueError):
        return None, PIPELINE_SLEEP_SECONDS_ERROR


def normalize_pipeline_extra_args(value: Any) -> str:
    return str(value or "").strip()


def pipeline_extra_args_error(extra_args: str, allow_extra_args: bool) -> str | None:
    if extra_args and not allow_extra_args:
        return PIPELINE_EXTRA_ARGS_ERROR
    return None


def pipeline_start_success_message(actual_mode: str, pid: int) -> str:
    return f"Started pipeline ({actual_mode}) via PID {pid}."


def pipeline_start_success_data(
    *,
    actual_mode: str,
    requested_mode: str,
    schedule_data: Any,
    pid: int,
    launch_prep_messages: list[str],
    launch_logs: str,
) -> dict[str, Any]:
    return {
        "mode": actual_mode,
        "requested_mode": requested_mode,
        "schedule": schedule_data,
        "pid": pid,
        "launch_prep": launch_prep_messages,
        "logs": launch_logs,
    }


def pipeline_start_unsupported_mode_result() -> "CommandResult":
    return _command_result(
        command=PIPELINE_START_COMMAND,
        ok=False,
        message="Unsupported pipeline start mode.",
        severity="error",
        errors=[PIPELINE_START_MODE_ERROR],
    )


def pipeline_start_sleep_error_result() -> "CommandResult":
    return _command_result(
        command=PIPELINE_START_COMMAND,
        ok=False,
        message=PIPELINE_SLEEP_SECONDS_ERROR,
        severity="error",
        errors=[PIPELINE_SLEEP_SECONDS_ERROR],
    )


def pipeline_start_extra_args_error_result() -> "CommandResult":
    return _command_result(
        command=PIPELINE_START_COMMAND,
        ok=False,
        message="Extra pipeline arguments are disabled for the local API start command.",
        severity="error",
        errors=[PIPELINE_EXTRA_ARGS_ERROR],
    )


def pipeline_start_schedule_gate_result(schedule_gate: dict[str, Any]) -> "CommandResult":
    message = str(schedule_gate["message"])
    return _command_result(
        command=PIPELINE_START_COMMAND,
        ok=False,
        message=message,
        severity=str(schedule_gate.get("severity") or "warning"),
        warnings=[message],
        refresh_hint="schedule",
        data={"schedule": _json_safe(schedule_gate.get("data") or {})},
    )


def pipeline_start_active_work_result(block_message: str) -> "CommandResult":
    return _command_result(
        command=PIPELINE_START_COMMAND,
        ok=False,
        message=block_message,
        severity="warning",
        warnings=[block_message],
        refresh_hint="snapshot",
    )


def pipeline_start_config_blocked_result(message: str, data: dict[str, Any]) -> "CommandResult":
    return _command_result(
        command=PIPELINE_START_COMMAND,
        ok=False,
        message=message,
        severity="error",
        errors=[message],
        refresh_hint="settings",
        data=data,
    )


def pipeline_start_exception_result(exc: Exception) -> "CommandResult":
    return _command_result(
        command=PIPELINE_START_COMMAND,
        ok=False,
        message=f"Pipeline start failed: {exc}",
        severity="error",
        errors=[str(exc)],
        refresh_hint="snapshot",
    )


def pipeline_start_success_result(
    *,
    actual_mode: str,
    requested_mode: str,
    schedule_data: Any,
    pid: int,
    launch_prep_messages: list[str],
    launch_logs: str,
) -> "CommandResult":
    return _command_result(
        command=PIPELINE_START_COMMAND,
        ok=True,
        message=pipeline_start_success_message(actual_mode, pid),
        severity="info",
        refresh_hint="snapshot",
        data=pipeline_start_success_data(
            actual_mode=actual_mode,
            requested_mode=requested_mode,
            schedule_data=_json_safe(schedule_data or {}),
            pid=pid,
            launch_prep_messages=launch_prep_messages,
            launch_logs=launch_logs,
        ),
    )

__all__ = [
    "PIPELINE_START_COMMAND",
    "PIPELINE_START_MODES",
    "PIPELINE_START_MODE_ERROR",
    "PIPELINE_SLEEP_SECONDS_ERROR",
    "PIPELINE_EXTRA_ARGS_ERROR",
    "normalize_pipeline_start_mode",
    "is_supported_pipeline_start_mode",
    "parse_pipeline_sleep_seconds",
    "normalize_pipeline_extra_args",
    "pipeline_extra_args_error",
    "pipeline_start_success_message",
    "pipeline_start_success_data",
    "pipeline_start_unsupported_mode_result",
    "pipeline_start_sleep_error_result",
    "pipeline_start_extra_args_error_result",
    "pipeline_start_schedule_gate_result",
    "pipeline_start_active_work_result",
    "pipeline_start_config_blocked_result",
    "pipeline_start_exception_result",
    "pipeline_start_success_result",
]
