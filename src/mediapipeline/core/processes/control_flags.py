from __future__ import annotations

from collections.abc import Callable
from datetime import datetime
import json
import os
from pathlib import Path
import time
from typing import Any, Protocol
import uuid

from mediapipeline.core.kernel.contracts import ContractError, ControlFlagRecord
from mediapipeline.core.processes.constants import CONTROL_FLAG_SCHEMA_VERSION
from mediapipeline.core.processes.file_io import atomic_write_text, read_json_file


class WarningLogger(Protocol):
    def warning(self, message: object, *args: object, **kwargs: object) -> None: ...


def new_control_flag_payload(
    label: str,
    *,
    action: str = "",
    run_id: str = "",
    target_pid: int | None = None,
    target_launch_id: str = "",
) -> dict[str, Any]:
    normalized_action = action.strip().casefold() or label.strip().lower().replace(" ", "_")
    payload = {
        "schema_version": CONTROL_FLAG_SCHEMA_VERSION,
        "action": normalized_action,
        "label": label,
        "request_id": uuid.uuid4().hex,
        "created_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "app_pid": os.getpid(),
        "run_id": str(run_id or "").strip(),
        "target_pid": target_pid,
        "target_launch_id": str(target_launch_id or "").strip(),
    }
    return ControlFlagRecord.from_mapping(payload).to_mapping()


def write_control_flag(flag_path: Path, label: str) -> dict[str, Any]:
    payload = new_control_flag_payload(label)
    flag_path.parent.mkdir(parents=True, exist_ok=True)
    atomic_write_text(flag_path, json.dumps(payload, indent=2, sort_keys=True) + "\n")
    if not flag_path.exists():
        raise RuntimeError(f"{label} flag write did not create {flag_path}.")
    try:
        round_trip = read_json_file(flag_path, retries=1)
    except Exception as exc:
        raise RuntimeError(f"{label} flag was written but could not be read back: {exc}") from exc
    try:
        verified = ControlFlagRecord.from_mapping(round_trip)
    except ContractError as exc:
        raise RuntimeError(f"{label} flag verification failed for {flag_path}: {exc}") from exc
    if verified.request_id != payload["request_id"]:
        raise RuntimeError(f"{label} flag verification failed for {flag_path}.")
    return payload


def write_stop_after_current_flag(
    flag_path: Path,
    *,
    run_id: str = "",
    target_pid: int | None = None,
    target_launch_id: str = "",
) -> dict[str, Any]:
    payload = new_control_flag_payload(
        "Stop After Current",
        action="stop_after_current",
        run_id=run_id,
        target_pid=target_pid,
        target_launch_id=target_launch_id,
    )
    flag_path.parent.mkdir(parents=True, exist_ok=True)
    atomic_write_text(flag_path, json.dumps(payload, indent=2, sort_keys=True) + "\n")
    try:
        verified = ControlFlagRecord.from_mapping(read_json_file(flag_path, retries=1))
    except (ContractError, OSError, ValueError, TypeError) as exc:
        raise RuntimeError(f"Stop After Current flag verification failed for {flag_path}: {exc}") from exc
    if verified.request_id != payload["request_id"]:
        raise RuntimeError(f"Stop After Current flag verification failed for {flag_path}.")
    return payload


def remove_control_flag(flag_path: Path, label: str) -> None:
    flag_path.unlink(missing_ok=True)
    if flag_path.exists():
        raise RuntimeError(f"{label} flag could not be removed from {flag_path}.")


def read_control_flag_payload(flag_path: Path, logger: WarningLogger | None = None) -> dict[str, Any] | None:
    try:
        payload = read_json_file(flag_path, retries=1)
    except Exception as exc:
        if logger is not None:
            logger.warning("Control flag unreadable for %s: %s", flag_path, exc)
        return None
    if not isinstance(payload, dict):
        return None
    if str(payload.get("schema_version") or "").strip():
        try:
            return ControlFlagRecord.from_mapping(payload).to_mapping()
        except ContractError as exc:
            if logger is not None:
                logger.warning("Control flag contract invalid for %s: %s", flag_path, exc)
    return payload


def control_flag_age_seconds(
    flag_path: Path,
    payload: dict[str, Any] | None,
    *,
    parse_datetime: Callable[[str], datetime | None],
) -> float | None:
    created_at = str((payload or {}).get("created_at", "") or "").strip()
    parsed = parse_datetime(created_at)
    if parsed is not None:
        now = datetime.now(parsed.tzinfo) if parsed.tzinfo is not None else datetime.now()
        return max(0.0, (now - parsed).total_seconds())
    try:
        return max(0.0, time.time() - flag_path.stat().st_mtime)
    except OSError:
        return None
