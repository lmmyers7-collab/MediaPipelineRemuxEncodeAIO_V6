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



def _completed_preview_dto(**fields: Any) -> CompletedPreviewDto:
    from mediapipeline.core.kernel.dto_inventory import CompletedPreviewDto

    return CompletedPreviewDto(**fields)

def _completed_at_text(value: datetime | None) -> str:
    if not value:
        return "Unknown"
    day = str(value.day)
    hour = value.strftime("%I").lstrip("0") or "12"
    return value.strftime(f"%b {day} {hour}:%M %p")

def _completed_at_sort_key(value: datetime | None) -> str:
    if not value:
        return ""
    return value.isoformat(timespec="seconds")

def bounded_completed_limit(value: Any, *, default: int = 100, minimum: int = 1, maximum: int = 500) -> int:
    try:
        limit = int(value or default)
    except (TypeError, ValueError):
        limit = default
    return min(maximum, max(minimum, limit))

def completed_preview_limit(value: Any, *, default: int = 100) -> int | None:
    if str(value or "").strip().casefold() == COMPLETED_HISTORY_ALL_LIMIT:
        return None
    return bounded_completed_limit(value, default=default)

def completed_inventory_progress_payload(
    *,
    rows_loaded: int,
    source: str = "",
    status: str = "complete",
    detail: str = "",
) -> dict[str, Any]:
    loaded = max(0, int(rows_loaded or 0))
    updated_at = datetime.now().isoformat(timespec="seconds")
    progress_detail = detail or f"Completed inventory loaded {loaded} row(s) from backend manifest preview."
    bar = {
        "id": "completed_inventory",
        "label": "Completed inventory",
        "mode": "determinate",
        "percent": 100.0 if status == "complete" else 0.0,
        "status": status,
        "detail": progress_detail,
        "source": source or "completed.preview",
        "updated_at": updated_at,
        "stale": False,
    }
    return {
        "schema_version": COMPLETED_INVENTORY_PROGRESS_SCHEMA_VERSION,
        "status": status,
        "rows_scanned": loaded,
        "rows_loaded": loaded,
        "source": source,
        "detail": progress_detail,
        "updated_at": updated_at,
        "progress_bars": [bar],
    }

def format_bytes_compact(raw_bytes: int) -> str:
    value = max(0.0, float(raw_bytes or 0))
    if value >= 1024 ** 3:
        return f"{value / (1024 ** 3):.2f} GB"
    if value >= 1024 ** 2:
        return f"{value / (1024 ** 2):.1f} MB"
    if value >= 1024:
        return f"{value / 1024:.1f} KB"
    return f"{int(value)} B"

def completed_record_key(record: CompletedJobRecord) -> str:
    seed = json.dumps(
        {
            "source_path": record.source_path_text,
            "output_path": str(record.output_path),
            "sidecar_path": str(record.sidecar_path),
            "encoded_at": str(record.payload.get("encoded_at", "") or ""),
            "route": record.route,
        },
        ensure_ascii=False,
        sort_keys=True,
    )
    return hashlib.sha256(seed.encode("utf-8", errors="replace")).hexdigest()[:24]

def completed_decision_value(value: Any, *keys: str) -> str:
    if not isinstance(value, dict):
        return ""
    for key in keys:
        raw = value.get(key, "")
        text = "" if raw is None else str(raw).strip()
        if text:
            return text
    return ""

def completed_decision_detail_rows(decisions: Iterable[dict[str, Any]], *, kind: str) -> list[dict[str, str]]:
    prefix = "s" if kind == "subtitle" else "a"
    ordinal_key = "subtitle_ordinal" if kind == "subtitle" else "audio_ordinal"
    rows: list[dict[str, str]] = []
    for item in list(decisions):
        ordinal = completed_decision_value(item, ordinal_key, "stream_index", "index") or "?"
        language = completed_decision_value(item, "language", "lang") or "und"
        source_codec = completed_decision_value(item, "source_codec", "codec") or "unknown"
        action = completed_decision_value(item, "action", "decision") or "unknown"
        reason = completed_decision_value(item, "reason", "route_reason")
        suffix = f" ({reason})" if reason else ""
        track_label = f"{prefix}:{ordinal}"
        rows.append(
            {
                "kind": "subtitle" if kind == "subtitle" else "audio",
                "track_label": track_label,
                "language": language,
                "source_codec": source_codec,
                "action": action,
                "reason": reason,
                "summary": f"{track_label} {language} {source_codec} -> {action}{suffix}",
            }
        )
    return rows

def completed_audio_decision_preview(decisions: Iterable[dict[str, Any]], *, limit: int = 5) -> list[str]:
    lines: list[str] = []
    for item in completed_decision_detail_rows(decisions, kind="audio")[:limit]:
        lines.append(item["summary"])
    return lines

def completed_subtitle_decision_preview(decisions: Iterable[dict[str, Any]], *, limit: int = 5) -> list[str]:
    lines: list[str] = []
    for item in completed_decision_detail_rows(decisions, kind="subtitle")[:limit]:
        lines.append(item["summary"])
    return lines

def _record_output_proof(record: CompletedJobRecord) -> str:
    return str(record.payload.get("_diagnostics_output_proof") or "").strip().casefold()

def _output_proof_deferred(record: CompletedJobRecord) -> bool:
    return _record_output_proof(record) == OUTPUT_PROOF_DEFERRED

def _payload_output_size(record: CompletedJobRecord) -> int | None:
    raw = record.payload.get("output_size")
    try:
        return int(raw) if raw is not None else None
    except (TypeError, ValueError):
        return None

def completed_size_reduction_text(source_size: int | None, output_size: int | None) -> str:
    if not source_size or not output_size or source_size <= 0:
        return ""
    pct = (1.0 - float(output_size) / float(source_size)) * 100.0
    src_gb = float(source_size) / (1024 ** 3)
    out_gb = float(output_size) / (1024 ** 3)
    return f"{pct:+.1f}%  ({src_gb:.2f} → {out_gb:.2f} GB)"

def _completed_payload_path_value(payload: dict[str, Any], *path: str) -> Any:
    current: Any = payload
    for key in path:
        if not isinstance(current, dict):
            return None
        current = current.get(key)
    return current

def _completed_route_category(value: Any) -> str:
    normalized = str(value or "").strip().casefold().replace("_", "-")
    if normalized == "remux-fallback":
        return "remux-fallback"
    if "remux" in normalized:
        return "remux"
    if "encode" in normalized or "transcode" in normalized:
        return "encode"
    if "skip" in normalized:
        return "skip"
    if "review" in normalized or "blocked" in normalized:
        return "review"
    if normalized == "copy":
        return "remux"
    if normalized.startswith("encode-"):
        return "encode"
    return ""

def _completed_first_route_category(payload: dict[str, Any], paths: Iterable[tuple[str, ...]]) -> str:
    for path in paths:
        category = _completed_route_category(_completed_payload_path_value(payload, *path))
        if category:
            return category
    return ""

def _completed_used_remux_fallback(payload: dict[str, Any]) -> bool:
    evidence = " ".join(
        str(value or "")
        for value in (
            payload.get("route_reason_code"),
            payload.get("route_reason"),
            _completed_payload_path_value(payload, "size_policy", "route_reason_code"),
            _completed_payload_path_value(payload, "route_explanation", "remux_fallback", "blocked_reason_code"),
            _completed_payload_path_value(payload, "route_explanation", "remux_fallback", "blocked_reason"),
        )
    ).casefold()
    if "oversized_encode_remux_fallback" in evidence:
        return True
    if "remux fallback" in evidence and "oversized encode" in evidence:
        return True
    return any(
        _completed_first_bool(payload, (path,)) is True
        for path in (
            ("route_explanation", "remux_fallback", "attempted"),
            ("route_explanation", "remux_fallback", "accepted"),
            ("route_explanation", "size_guard", "should_fallback_remux"),
        )
    )

def completed_route_display_fields(payload: dict[str, Any]) -> dict[str, str]:
    if not isinstance(payload, dict):
        payload = {}
    category = _completed_route_category(payload.get("route"))
    if category == "remux" and _completed_used_remux_fallback(payload):
        category = "remux-fallback"
    if str(payload.get("route") or "").strip().casefold() == "csv_rerun":
        nested_category = _completed_first_route_category(
            payload,
            (
                ("route_plan", "route"),
                ("route_explanation", "route"),
                ("encode_selected_attempt", "route"),
                ("runtime_outcome_route",),
                ("route_actions", "video"),
            ),
        )
        if nested_category:
            category = nested_category
        if category == "remux" and _completed_used_remux_fallback(payload):
            category = "remux-fallback"
    final_route = "remux" if category == "remux-fallback" else category
    final_route_label = {
        "remux": "REMUX",
        "encode": "ENCODE",
        "skip": "SKIP",
        "review": "REVIEW",
    }.get(final_route, final_route.upper() if final_route else "")
    return {
        "route_display_category": category,
        "route_display_final_route": final_route,
        "route_display_final_route_label": final_route_label,
    }

def _completed_first_positive_number(
    payload: dict[str, Any],
    paths: Iterable[tuple[str, ...]],
) -> tuple[float | None, tuple[str, ...] | None]:
    for path in paths:
        value = _completed_payload_path_value(payload, *path)
        try:
            number = float(value)
        except (TypeError, ValueError):
            continue
        if number > 0:
            return number, path
    return None, None

def _completed_first_bool(payload: dict[str, Any], paths: Iterable[tuple[str, ...]]) -> bool | None:
    for path in paths:
        value = _completed_payload_path_value(payload, *path)
        if isinstance(value, bool):
            return value
        text = str(value or "").strip().casefold()
        if text in {"true", "yes", "1"}:
            return True
        if text in {"false", "no", "0"}:
            return False
    return None

def completed_bitrate_display(value: float | None) -> str:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return ""
    if number <= 0:
        return ""
    precision = 1 if number >= 1.0 else 2
    text = f"{number:.{precision}f}".rstrip("0").rstrip(".")
    return f"{text} Mbps"

def _completed_bitrate_basis(path: tuple[str, ...] | None, fallback: str = "") -> str:
    if not path:
        return fallback
    if path[0] == "route_plan":
        return "route_plan"
    if path[0] == "source_media_profile":
        return "source_media_profile"
    return "manifest"

def _completed_derived_bitrate_mbps(size_bytes: int | None, duration_seconds: float | None) -> float | None:
    if not size_bytes or not duration_seconds or size_bytes <= 0 or duration_seconds <= 0:
        return None
    return (float(size_bytes) * 8.0) / float(duration_seconds) / 1_000_000.0

def completed_bitrate_fields(
    payload: dict[str, Any],
    *,
    source_size: int | None,
    output_size: int | None,
) -> dict[str, Any]:
    if not isinstance(payload, dict):
        payload = {}
    duration_seconds, duration_path = _completed_first_positive_number(
        payload,
        (
            ("duration_seconds",),
            ("media_duration_seconds",),
            ("source_media_profile", "duration_seconds"),
            ("route_plan", "source_media_profile", "duration_seconds"),
            ("route_plan", "duration_seconds"),
        ),
    )
    source_bitrate_mbps, source_bitrate_path = _completed_first_positive_number(
        payload,
        (
            ("source_bitrate_mbps",),
            ("source_estimated_bitrate_mbps",),
            ("estimated_bitrate_mbps",),
            ("source_media_profile", "bitrate_mbps"),
            ("source_media_profile", "estimated_bitrate_mbps"),
            ("route_plan", "source_bitrate_mbps"),
            ("route_plan", "estimated_bitrate_mbps"),
            ("route_plan", "source_media_profile", "bitrate_mbps"),
            ("route_plan", "source_media_profile", "estimated_bitrate_mbps"),
        ),
    )
    source_bitrate_basis = _completed_bitrate_basis(source_bitrate_path)
    if source_bitrate_mbps is None:
        source_bitrate_mbps = _completed_derived_bitrate_mbps(source_size, duration_seconds)
        source_bitrate_basis = "source_size_duration" if source_bitrate_mbps is not None else ""

    output_bitrate_mbps, output_bitrate_path = _completed_first_positive_number(
        payload,
        (
            ("output_bitrate_mbps",),
            ("output_estimated_bitrate_mbps",),
            ("route_plan", "output_bitrate_mbps"),
            ("route_plan", "output_estimated_bitrate_mbps"),
        ),
    )
    output_bitrate_basis = _completed_bitrate_basis(output_bitrate_path)
    if output_bitrate_mbps is None:
        output_bitrate_mbps = _completed_derived_bitrate_mbps(output_size, duration_seconds)
        output_bitrate_basis = "output_size_duration" if output_bitrate_mbps is not None else ""

    threshold_mbps, _ = _completed_first_positive_number(
        payload,
        (
            ("bitrate_threshold_mbps",),
            ("route_bitrate_threshold_mbps",),
            ("route_plan", "bitrate_threshold_mbps"),
        ),
    )
    over_threshold = _completed_first_bool(
        payload,
        (
            ("bitrate_over_threshold",),
            ("route_plan", "bitrate_over_threshold"),
        ),
    )
    primary_bitrate = output_bitrate_mbps if output_bitrate_mbps is not None else source_bitrate_mbps
    primary_basis = output_bitrate_basis if output_bitrate_mbps is not None else source_bitrate_basis
    return {
        "duration_seconds": duration_seconds,
        "duration_basis": _completed_bitrate_basis(duration_path),
        "source_bitrate_mbps": round(source_bitrate_mbps, 3) if source_bitrate_mbps is not None else None,
        "source_bitrate_text": completed_bitrate_display(source_bitrate_mbps),
        "source_bitrate_basis": source_bitrate_basis,
        "output_bitrate_mbps": round(output_bitrate_mbps, 3) if output_bitrate_mbps is not None else None,
        "output_bitrate_text": completed_bitrate_display(output_bitrate_mbps),
        "output_bitrate_basis": output_bitrate_basis,
        "bitrate_mbps": round(primary_bitrate, 3) if primary_bitrate is not None else None,
        "bitrate_text": completed_bitrate_display(primary_bitrate),
        "bitrate_basis": primary_basis,
        "bitrate_threshold_mbps": threshold_mbps,
        "bitrate_threshold_text": completed_bitrate_display(threshold_mbps),
        "bitrate_over_threshold": over_threshold,
    }

__all__ = (
    "COMPLETED_RUNTIME_OUTCOME_EVENT_LIMIT",
    "COMPLETED_HISTORY_SERVICE_UNAVAILABLE_MESSAGE",
    "COMPLETED_HISTORY_EMPTY_MESSAGE",
    "COMPLETED_MANIFEST_STALE_AFTER_SECONDS",
    "COMPLETED_INVENTORY_PROGRESS_SCHEMA_VERSION",
    "COMPLETED_HISTORY_ALL_LIMIT",
    "COMPLETED_NEUTRAL_SIZE_DELTA_PERCENT",
    "COMPLETED_PENDING_PUBLISH_ROW_STATES",
    "COMPLETED_RUNTIME_FAILURE_STATUSES",
    "COMPLETED_BENIGN_RUNTIME_ERROR_CODES",
    "_completed_preview_dto",
    "_completed_at_text",
    "_completed_at_sort_key",
    "bounded_completed_limit",
    "completed_preview_limit",
    "completed_inventory_progress_payload",
    "format_bytes_compact",
    "completed_record_key",
    "completed_decision_value",
    "completed_decision_detail_rows",
    "completed_audio_decision_preview",
    "completed_subtitle_decision_preview",
    "_record_output_proof",
    "_output_proof_deferred",
    "_payload_output_size",
    "completed_size_reduction_text",
    "_completed_payload_path_value",
    "_completed_route_category",
    "_completed_first_route_category",
    "_completed_used_remux_fallback",
    "completed_route_display_fields",
    "_completed_first_positive_number",
    "_completed_first_bool",
    "completed_bitrate_display",
    "_completed_bitrate_basis",
    "_completed_derived_bitrate_mbps",
    "completed_bitrate_fields",
)
