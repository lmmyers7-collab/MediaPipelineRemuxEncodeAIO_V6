"""Completed-job preview DTO policy."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Iterable, Mapping
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

from mediapipeline.core.completed.manifest import OUTPUT_PROOF_DEFERRED, OUTPUT_PROOF_LIVE
from mediapipeline.core.completed.trust_fields import build_completed_row_trust_fields
from mediapipeline.core.completed.validation_state import validation_state_for_completed_row, validation_state_payload
from mediapipeline.core.files.constants import MEDIA_FILE_SUFFIXES
from mediapipeline.core.observability.artifact_freshness import file_freshness_fields
from mediapipeline.core.observability.runtime_outcomes import (
    RUNTIME_OUTCOME_EVENT_LIMIT as COMPLETED_RUNTIME_OUTCOME_EVENT_LIMIT,
    runtime_outcome_index,
    source_identity_key,
)
from mediapipeline.core.subtitles.qa import build_completed_subtitle_qa
from mediapipeline.core.completed.contracts import CompletedJobRecord

if TYPE_CHECKING:
    from mediapipeline.core.kernel.dto_inventory import CompletedPreviewDto


COMPLETED_HISTORY_SERVICE_UNAVAILABLE_MESSAGE = "Completed history service is not available."
COMPLETED_HISTORY_EMPTY_MESSAGE = "No completed jobs are available from the local manifest."
COMPLETED_MANIFEST_STALE_AFTER_SECONDS = 604800
COMPLETED_INVENTORY_PROGRESS_SCHEMA_VERSION = "desktop_completed_inventory_progress.v1"
COMPLETED_HISTORY_ALL_LIMIT = "all"
COMPLETED_NEUTRAL_SIZE_DELTA_PERCENT = 1.0
COMPLETED_PENDING_PUBLISH_ROW_STATES = {
    "parked",
    "parked_recovered",
    "pending_move",
}
COMPLETED_RUNTIME_FAILURE_STATUSES = {
    "failed",
    "skipped",
    "stopped",
    "transient_failure",
    "permanent_failure",
    "operator_required_failure",
    "failure_recorded",
}
COMPLETED_BENIGN_RUNTIME_ERROR_CODES = {"already_processed"}



from mediapipeline.core.completed.policy_projection import *  # noqa: F403

from mediapipeline.core.completed.policy_evidence import *  # noqa: F403

def completed_runtime_outcome_indices(events: Iterable[Any]) -> tuple[dict[str, dict[str, Any]], dict[str, dict[str, Any]]]:
    source_index = runtime_outcome_index(events)
    output_index: dict[str, dict[str, Any]] = {}
    for outcome in source_index.values():
        output_key = source_identity_key(outcome.get("runtime_outcome_output_path"))
        if output_key:
            output_index[output_key] = outcome
    return source_index, output_index

def completed_size_delta_percent(source_size: int | None, output_size: int | None) -> float | None:
    if not source_size or not output_size or source_size <= 0:
        return None
    return round(((float(output_size) - float(source_size)) / float(source_size)) * 100.0, 2)

def completed_size_delta_label(value: float | None) -> str:
    if value is None:
        return ""
    return f"{value:+.1f}%"

def completed_size_policy_fields(payload: dict[str, Any], *, size_delta_percent: float | None = None) -> dict[str, Any]:
    raw = payload.get("size_policy") if isinstance(payload, dict) else None
    if not isinstance(raw, dict):
        return {
            "size_policy_available": False,
            "size_policy_status": "unavailable",
            "size_policy_message": "",
            "size_policy_mode": "",
            "size_policy_routing_profile": "",
            "size_policy_route_reason_code": "",
            "size_policy_max_growth_percent": None,
            "size_policy_limit_ratio": None,
            "size_policy_ratio": None,
            "size_policy_exceeded": False,
            "size_policy_enforced": False,
            "size_policy_limit_label": "",
            "size_policy_delta_vs_limit_percent": None,
        }

    def _text(key: str) -> str:
        return str(raw.get(key, "") or "").strip()

    def _number(key: str) -> float | None:
        value = raw.get(key)
        try:
            return float(value)
        except (TypeError, ValueError):
            return None

    max_growth = _number("max_growth_percent")
    limit_ratio = _number("limit_ratio")
    ratio = _number("ratio")
    exceeded = bool(raw.get("exceeded"))
    enforced = bool(raw.get("enforced"))
    if exceeded and enforced:
        status = "blocked"
    elif exceeded:
        status = "review"
    elif max_growth is not None:
        status = "within_policy"
    else:
        status = "available"
    delta_vs_limit = None
    if isinstance(size_delta_percent, (int, float)) and max_growth is not None:
        delta_vs_limit = round(float(size_delta_percent) - float(max_growth), 2)
    limit_label = f"+{max_growth:g}%" if max_growth is not None else ""
    if limit_label and limit_ratio is not None:
        limit_label = f"{limit_label} ({limit_ratio:.2f}x)"
    return {
        "size_policy_available": True,
        "size_policy_status": status,
        "size_policy_message": _text("message"),
        "size_policy_mode": _text("mode"),
        "size_policy_routing_profile": _text("routing_profile"),
        "size_policy_route_reason_code": _text("route_reason_code"),
        "size_policy_max_growth_percent": max_growth,
        "size_policy_limit_ratio": limit_ratio,
        "size_policy_ratio": ratio,
        "size_policy_exceeded": exceeded,
        "size_policy_enforced": enforced,
        "size_policy_limit_label": limit_label,
        "size_policy_delta_vs_limit_percent": delta_vs_limit,
    }

def completed_quality_fields(payload: dict[str, Any]) -> dict[str, Any]:
    raw = payload.get("quality_verification") if isinstance(payload, dict) else None
    if not isinstance(raw, dict):
        return {
            "quality_available": False,
            "quality_metric": "",
            "quality_score": None,
            "quality_outcome": "",
            "quality_min_window_score": None,
            "quality_sample_mode": "",
            "quality_warn_threshold": None,
            "quality_fail_threshold": None,
            "quality_blocked": False,
        }

    def _text(key: str) -> str:
        return str(raw.get(key, "") or "").strip()

    def _number(key: str) -> float | None:
        value = raw.get(key)
        try:
            return float(value)
        except (TypeError, ValueError):
            return None

    outcome = _text("outcome").casefold()
    fail_action = _text("fail_action").casefold()
    return {
        "quality_available": True,
        "quality_metric": _text("metric"),
        "quality_score": _number("score"),
        "quality_outcome": outcome,
        "quality_min_window_score": _number("min_window_score"),
        "quality_sample_mode": _text("sample_mode"),
        "quality_warn_threshold": _number("warn_threshold"),
        "quality_fail_threshold": _number("fail_threshold"),
        "quality_blocked": outcome == "fail" and fail_action == "block_review",
    }

def completed_quality_number_label(value: Any) -> str:
    if not isinstance(value, (int, float)):
        return ""
    return f"{float(value):g}"

def completed_row_quality_line(row: dict[str, Any]) -> str:
    if not row.get("quality_available"):
        return ""
    metric = str(row.get("quality_metric") or "quality").strip() or "quality"
    score = completed_quality_number_label(row.get("quality_score")) or "unknown"
    warn_threshold = completed_quality_number_label(row.get("quality_warn_threshold"))
    fail_threshold = completed_quality_number_label(row.get("quality_fail_threshold"))
    outcome = str(row.get("quality_outcome") or "").strip()
    thresholds: list[str] = []
    if warn_threshold:
        thresholds.append(f"warn < {warn_threshold}")
    if fail_threshold:
        thresholds.append(f"fail < {fail_threshold}")
    line = f"Quality: {metric} {score}"
    if thresholds:
        line = f"{line} ({'; '.join(thresholds)})"
    if outcome:
        line = f"{line}; outcome={outcome}"
    return line

def completed_row_size_policy_line(row: dict[str, Any]) -> str:
    if not row.get("size_policy_available"):
        return ""
    mode = str(row.get("size_policy_mode") or "unknown").strip() or "unknown"
    profile = str(row.get("size_policy_routing_profile") or "").strip()
    limit = str(row.get("size_policy_limit_label") or "").strip()
    status = str(row.get("size_policy_status") or "available").strip()
    message = str(row.get("size_policy_message") or "").strip()
    parts = [f"Size policy: {mode}"]
    if profile:
        parts.append(f"profile={profile}")
    if limit:
        parts.append(f"limit={limit}")
    parts.append(f"status={status}")
    if message:
        parts.append(message)
    return "; ".join(parts)

def count_by_key(rows: Iterable[dict[str, Any]], key: str, *, default: str = "unknown") -> dict[str, int]:
    counts: dict[str, int] = {}
    for row in rows:
        value = str(row.get(key) or default).strip() or default
        counts[value] = counts.get(value, 0) + 1
    return dict(sorted(counts.items()))

def count_list_values(rows: Iterable[dict[str, Any]], key: str) -> dict[str, int]:
    counts: dict[str, int] = {}
    for row in rows:
        values = row.get(key)
        if not isinstance(values, list):
            continue
        for value in values:
            text = str(value or "").strip()
            if text:
                counts[text] = counts.get(text, 0) + 1
    return dict(sorted(counts.items()))

__all__ = (
    "completed_runtime_outcome_indices",
    "completed_size_delta_percent",
    "completed_size_delta_label",
    "completed_size_policy_fields",
    "completed_quality_fields",
    "completed_quality_number_label",
    "completed_row_quality_line",
    "completed_row_size_policy_line",
    "count_by_key",
    "count_list_values",
)
