from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any, Protocol

from .control_flags import (
    control_flag_age_seconds,
    new_control_flag_payload,
    read_control_flag_payload,
    remove_control_flag,
    write_control_flag,
)
from .launch_cleanup import prepare_control_flags_for_launch as prepare_control_flags_for_launch_helper


class WarningLogger(Protocol):
    def warning(self, message: object, *args: object, **kwargs: object) -> None: ...


class ControlFlagPaths(Protocol):
    pause_flag: Path | None
    stop_flag: Path | None
    rescan_flag: Path | None


class ProcessControlPayloadReadService(Protocol):
    logger: WarningLogger


class ProcessControlFlagAgeService(Protocol):
    def _parse_progress_datetime(self, raw: str) -> datetime | None: ...


class ProcessControlLaunchService(ProcessControlPayloadReadService, ProcessControlFlagAgeService, Protocol):
    def _read_control_flag_payload(self, flag_path: Path) -> dict[str, Any] | None: ...

    def _control_flag_age_seconds(self, flag_path: Path, payload: dict[str, Any] | None) -> float | None: ...

    def _remove_control_flag(self, flag_path: Path, label: str) -> None: ...


class ProcessControlWriteService(Protocol):
    def _write_control_flag(self, flag_path: Path, label: str) -> dict[str, Any]: ...

    def _remove_control_flag(self, flag_path: Path, label: str) -> None: ...


def new_control_flag_payload_for_service(_service: object, label: str) -> dict[str, Any]:
    return new_control_flag_payload(label)


def write_control_flag_for_service(_service: object, flag_path: Path, label: str) -> dict[str, Any]:
    return write_control_flag(flag_path, label)


def remove_control_flag_for_service(_service: object, flag_path: Path, label: str) -> None:
    remove_control_flag(flag_path, label)


def read_control_flag_payload_for_service(
    service: ProcessControlPayloadReadService,
    flag_path: Path,
) -> dict[str, Any] | None:
    return read_control_flag_payload(flag_path, logger=service.logger)


def control_flag_age_seconds_for_service(
    service: ProcessControlFlagAgeService,
    flag_path: Path,
    payload: dict[str, Any] | None,
) -> float | None:
    return control_flag_age_seconds(flag_path, payload, parse_datetime=service._parse_progress_datetime)


def prepare_pipeline_control_flags_for_service(
    service: ProcessControlLaunchService,
    resolved: ControlFlagPaths,
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


def toggle_pause_flag_for_service(service: ProcessControlWriteService, resolved: ControlFlagPaths) -> str:
    if not resolved.pause_flag:
        raise RuntimeError("Pause flag is unavailable because LocalBase is not resolved.")
    if resolved.pause_flag.exists():
        service._remove_control_flag(resolved.pause_flag, "Pause")
        return "Pause flag cleared."
    service._write_control_flag(resolved.pause_flag, "Pause")
    return "Pause requested."


def write_flag_for_service(service: ProcessControlWriteService, flag_path: Path | None, label: str) -> str:
    if not flag_path:
        raise RuntimeError(f"{label} flag is unavailable because LocalBase is not resolved.")
    service._write_control_flag(flag_path, label)
    return f"{label} requested."
