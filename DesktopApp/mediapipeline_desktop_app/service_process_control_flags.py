from __future__ import annotations

import json
import os
import time
import uuid
from collections.abc import Callable
from datetime import datetime
from pathlib import Path
from typing import Any

from .contracts import ContractError, ControlFlagRecord
from .service_constants import CONTROL_FLAG_SCHEMA_VERSION
from .service_runner_protocols import WarningLogger
from .service_utils import _atomic_write_text, _read_json_file


def new_control_flag_payload(label: str) -> dict[str, Any]:
    action = label.strip().lower().replace(" ", "_")
    payload = {
        "schema_version": CONTROL_FLAG_SCHEMA_VERSION,
        "action": action,
        "label": label,
        "request_id": uuid.uuid4().hex,
        "created_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "app_pid": os.getpid(),
    }
    return ControlFlagRecord.from_mapping(payload).to_mapping()


def write_control_flag(flag_path: Path, label: str) -> dict[str, Any]:
    payload = new_control_flag_payload(label)
    flag_path.parent.mkdir(parents=True, exist_ok=True)
    _atomic_write_text(flag_path, json.dumps(payload, indent=2, sort_keys=True) + "\n")
    if not flag_path.exists():
        raise RuntimeError(f"{label} flag write did not create {flag_path}.")
    try:
        round_trip = _read_json_file(flag_path, retries=1)
    except Exception as exc:
        raise RuntimeError(f"{label} flag was written but could not be read back: {exc}") from exc
    try:
        verified = ControlFlagRecord.from_mapping(round_trip)
    except ContractError as exc:
        raise RuntimeError(f"{label} flag verification failed for {flag_path}: {exc}") from exc
    if verified.request_id != payload["request_id"]:
        raise RuntimeError(f"{label} flag verification failed for {flag_path}.")
    return payload


def remove_control_flag(flag_path: Path, label: str) -> None:
    flag_path.unlink(missing_ok=True)
    if flag_path.exists():
        raise RuntimeError(f"{label} flag could not be removed from {flag_path}.")


def read_control_flag_payload(flag_path: Path, logger: WarningLogger | None = None) -> dict[str, Any] | None:
    try:
        payload = _read_json_file(flag_path, retries=1)
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
