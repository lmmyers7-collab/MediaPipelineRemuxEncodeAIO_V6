from __future__ import annotations

from pathlib import Path
from typing import Any

from .models import ResolvedPaths
from .service_process_control_flags import (
    control_flag_age_seconds,
    new_control_flag_payload,
    read_control_flag_payload,
    remove_control_flag,
    write_control_flag,
)
from .service_process_launch_cleanup import prepare_control_flags_for_launch as prepare_control_flags_for_launch_helper
from .service_runner_protocols import (
    ProcessControlFlagAgeServiceProtocol,
    ProcessControlLaunchServiceProtocol,
    ProcessControlPayloadReadServiceProtocol,
    ProcessControlWriteServiceProtocol,
)


def new_control_flag_payload_for_service(_service: object, label: str) -> dict[str, Any]:
    return new_control_flag_payload(label)


def write_control_flag_for_service(_service: object, flag_path: Path, label: str) -> dict[str, Any]:
    return write_control_flag(flag_path, label)


def remove_control_flag_for_service(_service: object, flag_path: Path, label: str) -> None:
    remove_control_flag(flag_path, label)


def read_control_flag_payload_for_service(
    service: ProcessControlPayloadReadServiceProtocol,
    flag_path: Path,
) -> dict[str, Any] | None:
    return read_control_flag_payload(flag_path, logger=service.logger)


def control_flag_age_seconds_for_service(
    service: ProcessControlFlagAgeServiceProtocol,
    flag_path: Path,
    payload: dict[str, Any] | None,
) -> float | None:
    return control_flag_age_seconds(flag_path, payload, parse_datetime=service._parse_progress_datetime)


def prepare_pipeline_control_flags_for_service(
    service: ProcessControlLaunchServiceProtocol,
    resolved: ResolvedPaths,
    *,
    stale_after_seconds: float,
) -> list[str]:
    specs = (
        ("Pause", resolved.pause_flag, False),
        ("Stop", resolved.stop_flag, True),
        ("Rescan", resolved.rescan_flag, False),
    )
    return prepare_control_flags_for_launch_helper(
        specs,
        stale_after_seconds=stale_after_seconds,
        read_payload=service._read_control_flag_payload,
        age_seconds=service._control_flag_age_seconds,
        remove_flag=service._remove_control_flag,
        logger=service.logger,
    )


def toggle_pause_flag_for_service(service: ProcessControlWriteServiceProtocol, resolved: ResolvedPaths) -> str:
    if not resolved.pause_flag:
        raise RuntimeError("Pause flag is unavailable because LocalBase is not resolved.")
    if resolved.pause_flag.exists():
        service._remove_control_flag(resolved.pause_flag, "Pause")
        return "Pause flag cleared."
    service._write_control_flag(resolved.pause_flag, "Pause")
    return "Pause requested."


def write_flag_for_service(service: ProcessControlWriteServiceProtocol, flag_path: Path | None, label: str) -> str:
    if not flag_path:
        raise RuntimeError(f"{label} flag is unavailable because LocalBase is not resolved.")
    service._write_control_flag(flag_path, label)
    return f"{label} requested."
