from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime
import json
import os
from pathlib import Path
from typing import Any
import uuid
from collections.abc import Iterable, Mapping

from mediapipeline.core.diagnostics.autonomy_evaluators import (
    category_evaluation_error as autonomy_category_evaluation_error,
    evaluate_category as autonomy_evaluate_category,
)
from mediapipeline.core.diagnostics.autonomy_growth import (
    acquire_growth_snapshot_lock,
    bounded_snapshot_limit,
    growth_snapshot_write_result,
    minimum_present,
    release_growth_snapshot_lock,
)
from mediapipeline.core.diagnostics.autonomy_policy import AutonomyPolicy, autonomy_policy_from_resolved
from mediapipeline.core.diagnostics.autonomy_recovery import (
    journal_archive_action,
    pending_publish_drain_action,
    pending_publish_recovery_plan_action,
)
from mediapipeline.core.diagnostics.autonomy_scan import (
    directory_size_scan,
    limited_iter_files,
    unique_observed_bytes,
)
from mediapipeline.core.diagnostics.autonomy_types import (
    category as autonomy_category,
    issue as autonomy_issue,
    issue_status as autonomy_issue_status,
    overall_status as autonomy_overall_status,
    status_state as autonomy_status_state,
)
from mediapipeline.core.kernel.contracts.pending_publish import PENDING_PUSH_RETRY_LIMIT
from mediapipeline.core.status.runtime_health import runtime_reliability_counters

from mediapipeline.core.diagnostics.autonomy_health_constants import *  # noqa: F403



def _row_age_seconds(row: Mapping[str, Any], now: datetime) -> int | None:
    text = _first_text(row, "parked_at", "recorded_at", "last_update", "modified_at")
    path = _path_or_none(row.get("manifest_path") or row.get("path"))
    return _age_seconds(text, path, now)


def _age_seconds(text: str, path: Path | None, now: datetime) -> int | None:
    parsed = _parse_datetime(text)
    if parsed is None and path is not None:
        try:
            parsed = datetime.fromtimestamp(path.stat().st_mtime, UTC)
        except OSError:
            return None
    if parsed is None:
        return None
    return max(0, int((now - parsed.astimezone(UTC)).total_seconds()))


def _parse_datetime(value: Any) -> datetime | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def _first_text(mapping: Mapping[str, Any], *keys: str) -> str:
    for key in keys:
        value = mapping.get(key)
        text = str(value or "").strip()
        if text:
            return text
    return ""


def _path_or_none(value: Any) -> Path | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        return Path(text)
    except TypeError:
        return None


def _safe_int(*values: Any) -> int:
    for value in values:
        try:
            if value in (None, ""):
                continue
            return int(value)
        except (TypeError, ValueError):
            continue
    return 0


def _safe_float(*values: Any) -> float | None:
    for value in values:
        try:
            if value in (None, ""):
                continue
            return float(value)
        except (TypeError, ValueError):
            continue
    return None


def _iter_files(root: Path, pattern: str = "*", *, limit: int = AUTONOMY_SCAN_LIMIT) -> list[Path]:
    return _limited_iter_files(root, pattern, limit=limit)[0]


def _limited_iter_files(root: Path, pattern: str = "*", *, limit: int = AUTONOMY_SCAN_LIMIT) -> tuple[list[Path], bool]:
    scan = limited_iter_files(root, pattern, limit=limit)
    return scan.paths, scan.truncated


def _directory_size(root: Path | None, *, limit: int = AUTONOMY_SCAN_LIMIT) -> int:
    return int(_directory_size_scan(root, limit=limit)["size_bytes"])


def _directory_size_scan(root: Path | None, *, limit: int = AUTONOMY_SCAN_LIMIT) -> dict[str, Any]:
    return directory_size_scan(root, limit=limit)


def _journal_paths(resolved: Any) -> list[Path | None]:
    return [
        resolved.event_file,
        resolved.completed_manifest_path,
        resolved.queue_snapshot_path,
        resolved.progress_file,
        resolved.log_file,
    ]


def _read_json_mapping(path: Path) -> Mapping[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
    except Exception:
        return {"_read_error": str(path)}
    return payload if isinstance(payload, Mapping) else {"_json_root": type(payload).__name__}


def _queue_runnable_count(path: Path | None) -> int:
    if path is None or not path.exists() or not path.is_file():
        return 0
    payload = _read_json_mapping(path)
    for key in ("runnable_count", "RunnableCount"):
        if key in payload:
            return _safe_int(payload.get(key))
    items = payload.get("items")
    if isinstance(items, list):
        return len(items)
    rows = payload.get("rows")
    if isinstance(rows, list):
        return len(rows)
    return 0


def _active_job_definitely_dead(payload: Mapping[str, Any], psutil_module: Any) -> bool:
    pid = payload.get("pid")
    try:
        process = psutil_module.Process(int(pid))
        return not (bool(process.is_running()) and process.status() != psutil_module.STATUS_ZOMBIE)
    except psutil_module.NoSuchProcess:
        return True
    except Exception:
        return False


__all__ = [
    "_active_job_definitely_dead",
    "_age_seconds",
    "_directory_size",
    "_directory_size_scan",
    "_first_text",
    "_iter_files",
    "_journal_paths",
    "_limited_iter_files",
    "_parse_datetime",
    "_path_or_none",
    "_queue_runnable_count",
    "_read_json_mapping",
    "_row_age_seconds",
    "_safe_float",
    "_safe_int",
]
