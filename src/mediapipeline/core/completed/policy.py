"""Completed-job preview DTO policy."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any, Iterable

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
from mediapipeline.desktop.models import CompletedJobRecord

if TYPE_CHECKING:
    from mediapipeline.desktop.application.dto_inventory import CompletedPreviewDto


COMPLETED_HISTORY_SERVICE_UNAVAILABLE_MESSAGE = "Completed history service is not available."
COMPLETED_HISTORY_EMPTY_MESSAGE = "No completed jobs are available from the local manifest."
COMPLETED_MANIFEST_STALE_AFTER_SECONDS = 604800
COMPLETED_INVENTORY_PROGRESS_SCHEMA_VERSION = "desktop_completed_inventory_progress.v1"
COMPLETED_HISTORY_ALL_LIMIT = "all"
COMPLETED_NEUTRAL_SIZE_DELTA_PERCENT = 1.0
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


def _completed_preview_dto(**fields: Any) -> "CompletedPreviewDto":
    from mediapipeline.desktop.application.dto_inventory import CompletedPreviewDto

    return CompletedPreviewDto(**fields)


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


def completed_audio_decision_preview(decisions: Iterable[dict[str, Any]], *, limit: int = 5) -> list[str]:
    lines: list[str] = []
    for item in list(decisions)[:limit]:
        ordinal = completed_decision_value(item, "audio_ordinal", "stream_index", "index") or "?"
        language = completed_decision_value(item, "language", "lang") or "und"
        source_codec = completed_decision_value(item, "source_codec", "codec") or "unknown"
        action = completed_decision_value(item, "action", "decision") or "unknown"
        reason = completed_decision_value(item, "reason", "route_reason")
        suffix = f" ({reason})" if reason else ""
        lines.append(f"a:{ordinal} {language} {source_codec} -> {action}{suffix}")
    return lines


def completed_subtitle_decision_preview(decisions: Iterable[dict[str, Any]], *, limit: int = 5) -> list[str]:
    lines: list[str] = []
    for item in list(decisions)[:limit]:
        ordinal = completed_decision_value(item, "subtitle_ordinal", "stream_index", "index") or "?"
        language = completed_decision_value(item, "language", "lang") or "und"
        source_codec = completed_decision_value(item, "source_codec", "codec") or "unknown"
        action = completed_decision_value(item, "action", "decision") or "unknown"
        reason = completed_decision_value(item, "reason", "route_reason")
        suffix = f" ({reason})" if reason else ""
        lines.append(f"s:{ordinal} {language} {source_codec} -> {action}{suffix}")
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

    threshold_mbps, _threshold_path = _completed_first_positive_number(
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


def completed_record_to_row(record: CompletedJobRecord) -> dict[str, Any]:
    deferred = _output_proof_deferred(record)
    # Deferred rows must not touch the filesystem: take output size from the
    # manifest payload only (skip the stat() fallback in output_size_bytes).
    output_size = _payload_output_size(record) if deferred else record.output_size_bytes
    source_size = record.source_size_bytes
    size_delta_percent = completed_size_delta_percent(source_size, output_size)
    size_policy_fields = completed_size_policy_fields(record.payload, size_delta_percent=size_delta_percent)
    bitrate_fields = completed_bitrate_fields(record.payload, source_size=source_size, output_size=output_size)
    route_reason = str(record.payload.get("route_reason", "") or "").strip()
    route_reason_code = str(record.payload.get("route_reason_code", "") or "").strip()
    audio_decisions = record.audio_decisions
    subtitle_decisions = record.subtitle_decisions
    row = {
        "row_key": completed_record_key(record),
        "completed_at": record.completed_at_text,
        "route": record.route,
        "route_label": record.route_label,
        "route_reason": route_reason,
        "route_reason_code": route_reason_code,
        "elapsed": record.elapsed_text,
        "publish": record.publish_label,
        "publish_state": record.publish_state,
        "publish_mode": record.publish_mode,
        "media_type": record.media_type,
        "library_id": str(record.payload.get("library_id", "") or "").strip(),
        "library_name": str(record.payload.get("library_name", "") or "").strip(),
        "library_designation": str(record.payload.get("library_designation", "") or "").strip(),
        "library_source_root": str(record.payload.get("library_source_root", "") or "").strip(),
        "library_output_root": str(record.payload.get("library_output_root", "") or "").strip(),
        "lookup_title": record.lookup_title,
        "relative_path": record.relative_path,
        "output_file": record.output_file,
        "output_path": str(record.output_path),
        "output_exists": (None if deferred else bool(record.output_exists)),
        "output_proof": (OUTPUT_PROOF_DEFERRED if deferred else OUTPUT_PROOF_LIVE),
        "output_health": ("" if deferred else record.output_health),
        "source_path": record.source_path_text,
        "manifest_output_path": str(record.payload.get("output_path", "") or "").strip(),
        "manifest_output_file": str(record.payload.get("output_file", "") or "").strip(),
        "sidecar_path": str(record.sidecar_path),
        "source_size_bytes": record.source_size_bytes,
        "output_size_bytes": output_size,
        "output_size_text": format_bytes_compact(output_size or 0),
        "size_reduction_text": completed_size_reduction_text(source_size, output_size),
        "size_delta_percent": size_delta_percent,
        "size_delta_label": completed_size_delta_label(size_delta_percent),
        "size_growth_over_5": bool(size_delta_percent is not None and size_delta_percent > 5.0),
        **size_policy_fields,
        **bitrate_fields,
        "encoder": record.encode_selected_encoder,
        "encoder_kind": record.encode_selected_encoder_kind,
        "gpu_device": record.encode_selected_gpu_device,
        "audio_decision_count": len(audio_decisions),
        "audio_decision_preview": completed_audio_decision_preview(audio_decisions),
        "subtitle_decision_count": len(subtitle_decisions),
        "subtitle_decision_preview": completed_subtitle_decision_preview(subtitle_decisions),
        "ready_for_promotion": False,
        "no_destination_rule": False,
        "destination_offline": False,
        "promoting": False,
        "paused": False,
        "promotion_failed": False,
        "promoted": False,
        "promoted_cleaned": False,
        "final_library_promotion_status": "not_evaluated",
        "final_library_promotion_status_label": "Not Evaluated",
        "final_library_destination_path": "",
        "final_library_destination_root": "",
        "final_library_rule_id": "",
        "final_library_rule_label": "",
        "last_promotion_run_id": "",
        "last_promotion_completed_at": "",
        "promotion_error": "",
        "promotion_warnings": [],
    }
    row.update(completed_row_consistency(record, row))
    row["available_open_targets"] = completed_row_available_open_targets(row)
    row.update(completed_row_operator_guidance(row))
    validation_state = validation_state_for_completed_row(row)
    row.update(
        {
            "validation_status_state": validation_state["validation_status_state"],
            "validation_failure_reason": validation_state["failure_reason"],
            "validation_probe_ok": validation_state["probe_ok"],
            "validation_hash_ok": validation_state["hash_ok"],
            "validation_playback_required": validation_state["playback_required"],
            "validation_unavailable_reasons": validation_state["unavailable_reasons"],
            "validation_safe_next_action": validation_state["safe_next_action"],
        }
    )
    row.update(completed_row_trust_fields(row))
    row["subtitle_qa"] = build_completed_subtitle_qa(
        row,
        subtitle_decisions=subtitle_decisions,
        record_payload=record.payload,
    )
    return row


def completed_row_available_open_targets(row: dict[str, Any]) -> list[str]:
    targets: list[str] = []
    output_path = str(row.get("output_path") or "").strip()
    if output_path:
        if row.get("output_exists") is not False:
            if Path(output_path).suffix.lower() in MEDIA_FILE_SUFFIXES:
                targets.append("play_output_file")
            targets.append("output_file")
        targets.append("output_folder")
    if str(row.get("sidecar_path") or "").strip():
        targets.append("sidecar")
    if str(row.get("source_path") or "").strip():
        targets.append("source_folder")
    return targets


def completed_row_operator_status_state(
    row: dict[str, Any],
    *,
    severity: str = "",
    review_flags: Iterable[str] | None = None,
) -> str:
    operator_severity = str(severity or row.get("operator_severity") or "").strip().casefold()
    flags = {str(flag or "").strip().casefold() for flag in (review_flags or row.get("review_flags") or []) if str(flag or "").strip()}
    runtime_status = str(row.get("runtime_outcome_status") or "").strip().casefold()
    runtime_freshness = str(row.get("runtime_outcome_freshness_status") or "").strip().casefold()
    runtime_success = row.get("runtime_outcome_success")
    runtime_success_text = str(runtime_success).casefold() if runtime_success is not None else ""
    runtime_recent = bool(runtime_status) and runtime_freshness != "stale"
    if operator_severity in {"error", "critical"} or row.get("output_exists") is False:
        return "blocked"
    warning_flags = flags - {"encoded", "remuxed", "size_policy_within_limit"}
    if runtime_recent and (
        runtime_success is False
        or runtime_success_text == "false"
        or runtime_status in COMPLETED_RUNTIME_FAILURE_STATUSES
    ):
        return "warning"
    if operator_severity == "warning" or warning_flags:
        return "warning"
    if row.get("output_exists") is None:
        # Output-existence proof was deferred (bounded/summary proof budget),
        # so existence is unproven. Do not present an unverified row as the
        # all-clear "match"; surface a distinct "unverified" state instead.
        return "unverified"
    return "match"


def completed_path_exists(path: Path | None) -> bool:
    if path is None:
        return False
    try:
        return path.exists()
    except OSError:
        return False


def completed_path_mtime(path: Path | None) -> float | None:
    if path is None:
        return None
    try:
        return path.stat().st_mtime
    except OSError:
        return None


def completed_size_bucket(row: dict[str, Any]) -> str:
    value = row.get("size_delta_percent")
    if not isinstance(value, (int, float)):
        return "unknown"
    if float(value) > 5.0:
        return "growth_over_5"
    if float(value) > 0.0:
        return "growth_0_to_5"
    return "shrink_or_equal"


def completed_row_consistency(record: CompletedJobRecord, row: dict[str, Any]) -> dict[str, Any]:
    output_path = record.output_path
    expected_sidecar = output_path.with_suffix(".pipeline.json")
    sidecar_path = record.sidecar_path
    if row.get("output_proof") == OUTPUT_PROOF_DEFERRED or _output_proof_deferred(record):
        # Output/sidecar existence proof is deferred under the bounded/summary
        # proof budget: do not stat the filesystem and do not claim
        # missing_output. Report the row as unverified so the UI surfaces the
        # deferred state explicitly (output_proof + validation_status_state).
        issues: list[str] = []
        severity = "ok"
        if not str(row.get("manifest_output_path") or "").strip() and not str(
            row.get("manifest_output_file") or ""
        ).strip():
            issues.append("manifest_missing_output_path")
            severity = "warning"
        if sidecar_path != expected_sidecar:
            issues.append("output_sidecar_mismatch")
            if severity != "error":
                severity = "warning"
        return {
            "expected_sidecar_path": str(expected_sidecar),
            "sidecar_exists": None,
            "sidecar_matches_output": sidecar_path == expected_sidecar,
            "output_mtime": None,
            "sidecar_mtime": None,
            "size_bucket": completed_size_bucket(row),
            "consistency_status": "Unverified",
            "consistency_severity": severity,
            "consistency_issues": issues,
            "consistency_guidance": (
                "Output existence proof is deferred for this row. Open the row, request "
                "live proof, or use Completed Manifest and Run Logs before treating it as "
                "proof of output."
            ),
        }

    output_exists = bool(row.get("output_exists"))
    sidecar_exists = completed_path_exists(sidecar_path)
    manifest_output_path = str(row.get("manifest_output_path") or "").strip()
    manifest_output_file = str(row.get("manifest_output_file") or "").strip()
    issues: list[str] = []
    severity = "ok"

    if not manifest_output_path and not manifest_output_file:
        issues.append("manifest_missing_output_path")
        severity = "warning"
    if not output_exists:
        issues.append("missing_output")
        severity = "error"
    if sidecar_path != expected_sidecar:
        issues.append("output_sidecar_mismatch")
        if severity != "error":
            severity = "warning"
    if not sidecar_exists:
        issues.append("missing_sidecar")
        if severity != "error":
            severity = "warning"
    output_mtime = completed_path_mtime(output_path) if output_exists else None
    sidecar_mtime = completed_path_mtime(sidecar_path) if sidecar_exists else None
    if output_mtime is not None and sidecar_mtime is not None and output_mtime - sidecar_mtime > 60.0:
        issues.append("sidecar_older_than_output")
        if severity != "error":
            severity = "warning"

    if severity == "error":
        status = "Broken"
        guidance = "Do not treat this completed row as safe proof of output. Inspect output, sidecar, and run logs before rerun or cleanup."
    elif issues:
        status = "Review"
        guidance = "Completed manifest row is usable for triage but has sidecar/output consistency issues. Inspect backend-selected locations before rerun."
    else:
        status = "Consistent"
        guidance = "Output and expected sidecar are present for this loaded completed row."
    return {
        "expected_sidecar_path": str(expected_sidecar),
        "sidecar_exists": sidecar_exists,
        "sidecar_matches_output": sidecar_path == expected_sidecar,
        "output_mtime": output_mtime,
        "sidecar_mtime": sidecar_mtime,
        "size_bucket": completed_size_bucket(row),
        "consistency_status": status,
        "consistency_severity": severity,
        "consistency_issues": issues,
        "consistency_guidance": guidance,
    }


def completed_row_operator_guidance(row: dict[str, Any]) -> dict[str, Any]:
    flags: list[str] = []
    severity = "ok"
    health = str(row.get("output_health") or "").strip().casefold()
    publish_state = str(row.get("publish_state") or "").strip().casefold()
    route = str(row.get("route") or "").strip().casefold()
    size_delta = row.get("size_delta_percent")
    size_policy_available = bool(row.get("size_policy_available"))
    size_policy_exceeded = bool(row.get("size_policy_exceeded"))
    size_policy_enforced = bool(row.get("size_policy_enforced"))
    runtime_outcome_status = str(row.get("runtime_outcome_status") or "").strip()
    runtime_outcome_freshness = str(row.get("runtime_outcome_freshness_status") or "").strip().casefold()
    runtime_error_code = str(row.get("runtime_outcome_error_code") or "").strip()
    runtime_success = row.get("runtime_outcome_success")
    runtime_success_text = str(runtime_success).casefold() if runtime_success is not None else ""
    runtime_recent = bool(runtime_outcome_status) and runtime_outcome_freshness != "stale"
    consistency_issues = [
        str(issue or "").strip()
        for issue in (row.get("consistency_issues") or [])
        if str(issue or "").strip()
    ]
    consistency_issue_set = {issue.casefold() for issue in consistency_issues}
    consistency_severity = str(row.get("consistency_severity") or "").strip().casefold()
    runtime_failed = (
        runtime_success is False
        or runtime_success_text == "false"
        or runtime_outcome_status.casefold() in COMPLETED_RUNTIME_FAILURE_STATUSES
    )
    runtime_successful = runtime_success is True or runtime_success_text == "true" or runtime_outcome_status.casefold() in {
        "ok",
        "success",
        "succeeded",
        "completed",
        "published",
    }
    runtime_error_review = bool(runtime_error_code) and not (
        runtime_successful and runtime_error_code.casefold() in COMPLETED_BENIGN_RUNTIME_ERROR_CODES
    )

    if row.get("output_exists") is False:
        flags.append("missing_output")
        severity = "error"
    if health and health not in {"ok", "present", "healthy"}:
        flags.append(f"health_{health}")
        severity = "error"
    if size_policy_available:
        if size_policy_exceeded:
            flags.append("size_policy_exceeded")
            if size_policy_enforced:
                flags.append("size_policy_enforced")
                severity = "error"
            elif severity != "error":
                severity = "warning"
        elif isinstance(size_delta, (int, float)) and float(size_delta) > 0.0:
            flags.append("size_policy_within_limit")
    else:
        if bool(row.get("size_growth_over_5")):
            flags.append("size_growth_over_5")
            if severity != "error":
                severity = "warning"
        elif (
            isinstance(size_delta, (int, float))
            and float(size_delta) > COMPLETED_NEUTRAL_SIZE_DELTA_PERCENT
        ):
            flags.append("size_growth")
            if severity == "ok":
                severity = "warning"
    if size_delta is None:
        flags.append("size_unknown")
        if severity == "ok":
            severity = "info"
    if publish_state and publish_state not in {"published", "complete", "completed", "ok"}:
        flags.append(f"publish_{publish_state}")
        if severity == "ok":
            severity = "warning"
    for issue in consistency_issues:
        if issue not in flags:
            flags.append(issue)
    if consistency_issue_set:
        if consistency_severity == "error" and severity != "error":
            severity = "error"
        elif severity == "ok":
            severity = "warning"
    if route.startswith("encode"):
        flags.append("encoded")
    elif route == "remux":
        flags.append("remuxed")
    if runtime_outcome_status and (runtime_failed or runtime_error_review):
        flags.append("runtime_outcome")
        flags.append(f"runtime_outcome:{runtime_outcome_status.casefold()}")
        if runtime_error_code:
            flags.append(f"runtime_error:{runtime_error_code}")
        if runtime_outcome_freshness == "stale":
            flags.append("runtime_outcome_stale")
        elif runtime_failed and severity != "error":
            severity = "warning"

    if "missing_output" in flags:
        label = "Missing output"
        guidance = "Open the output folder and completed manifest from backend-selected actions before rerunning or deleting any sidecars."
    elif any(flag.startswith("health_") for flag in flags):
        label = "Output health review"
        guidance = "Inspect output health, sidecar, and run logs before trusting this completed row."
    elif runtime_recent and runtime_failed:
        label = "Recent runtime conflict"
        guidance = "This completed row exists, but the latest backend runtime event for the same source/output failed or skipped. Inspect runtime history, pending publish, and logs before treating this manifest row as current."
    elif "size_policy_enforced" in flags:
        label = "Size policy blocked"
        guidance = "Completed history reports an output that exceeded a strict Output Size Check. Inspect route metadata, Run Logs, and sidecar size_policy before trusting this row."
    elif "size_policy_exceeded" in flags:
        label = "Review size policy"
        guidance = "Output exceeded the recorded size policy but the guard was advisory. Confirm this was an intentional compatibility encode before accepting the result."
    elif "size_policy_within_limit" in flags:
        label = "Size policy allowed"
        guidance = "Output grew, but the recorded backend size_policy says it stayed within the applicable growth limit. Review route reason if the growth is surprising."
    elif "size_growth_over_5" in flags:
        label = "Review size growth"
        guidance = "Output is more than 5% larger than source and no recorded size_policy was available. Confirm this was an intentional compatibility encode before accepting the result."
    elif "size_growth" in flags:
        label = "Output grew"
        guidance = "Output is larger than source. Review route reason and encoder choice if size was expected to shrink."
    elif "size_unknown" in flags:
        label = "Size comparison unavailable"
        guidance = "Source or output size was unavailable. Use output-integrity or open the sidecar before treating this as proof of success."
    elif publish_state and publish_state not in {"published", "complete", "completed", "ok"}:
        label = "Publish state review"
        guidance = "Review pending publish state before assuming the final output is available in the Plex destination."
    elif consistency_issue_set:
        label = "Sidecar proof review"
        guidance = "Completed manifest row has sidecar/output consistency issues. Inspect the backend-selected output and sidecar before acceptance, rerun, or cleanup."
    else:
        label = "Healthy"
        guidance = "Output is present and the loaded manifest row has no review flags."
    return {
        "operator_status": label,
        "operator_status_state": completed_row_operator_status_state(row, severity=severity, review_flags=flags),
        "operator_severity": severity,
        "operator_guidance": guidance,
        "review_flags": flags,
        "route_decision_summary": completed_row_route_decision_summary(row),
        "route_evidence_lines": completed_row_route_evidence_lines(row),
    }


def completed_row_trust_fields(row: dict[str, Any]) -> dict[str, Any]:
    return build_completed_row_trust_fields(row)


def completed_row_route_decision_summary(row: dict[str, Any]) -> str:
    route_label = str(row.get("route_label") or row.get("route") or "").strip()
    route_reason_code = str(row.get("route_reason_code") or "").strip()
    route_reason = str(row.get("route_reason") or "").strip()
    if route_label and route_reason_code:
        return f"{route_label} ({route_reason_code})"
    if route_label and route_reason:
        return f"{route_label} ({route_reason})"
    if route_label:
        return route_label
    return "Route not reported"


def completed_row_route_evidence_lines(row: dict[str, Any]) -> list[str]:
    lines: list[str] = []
    route_label = str(row.get("route_label") or row.get("route") or "").strip()
    route_reason_code = str(row.get("route_reason_code") or "").strip()
    route_reason = str(row.get("route_reason") or "").strip()
    if route_label:
        lines.append(f"Route: {route_label}")
    if route_reason_code:
        lines.append(f"Reason code: {route_reason_code}")
    if route_reason:
        lines.append(f"Reason: {route_reason}")
    encoder = str(row.get("encoder") or row.get("encoder_kind") or "").strip()
    gpu_device = str(row.get("gpu_device") or "").strip()
    if encoder or gpu_device:
        lines.append(f"Encoder: {encoder or 'unknown'}{f' on {gpu_device}' if gpu_device else ''}")
    source_size = row.get("source_size_bytes")
    output_size = row.get("output_size_bytes")
    size_delta = row.get("size_delta_label") or "unknown"
    if source_size or output_size:
        lines.append(f"Size: source={format_bytes_compact(int(source_size or 0))}; output={format_bytes_compact(int(output_size or 0))}; delta={size_delta}")
    size_policy_line = completed_row_size_policy_line(row)
    if size_policy_line:
        lines.append(size_policy_line)
    bitrate_parts: list[str] = []
    output_bitrate = str(row.get("output_bitrate_text") or "").strip()
    source_bitrate = str(row.get("source_bitrate_text") or "").strip()
    primary_bitrate = str(row.get("bitrate_text") or "").strip()
    if output_bitrate:
        bitrate_parts.append(f"output={output_bitrate}")
    if source_bitrate and source_bitrate != output_bitrate:
        bitrate_parts.append(f"source={source_bitrate}")
    elif primary_bitrate and not bitrate_parts:
        bitrate_parts.append(f"value={primary_bitrate}")
    threshold_bitrate = str(row.get("bitrate_threshold_text") or "").strip()
    if threshold_bitrate:
        bitrate_parts.append(f"threshold={threshold_bitrate}")
    over_threshold = row.get("bitrate_over_threshold")
    if over_threshold is not None:
        bitrate_parts.append(f"over threshold={'yes' if bool(over_threshold) else 'no'}")
    if bitrate_parts:
        lines.append("Bitrate: " + "; ".join(bitrate_parts))
    publish = str(row.get("publish") or row.get("publish_state") or "").strip()
    if publish:
        lines.append(f"Publish: {publish}")
    health = str(row.get("output_health") or ("missing output" if row.get("output_exists") is False else "ok")).strip()
    if health:
        lines.append(f"Output health: {health}")
    audio_preview = row.get("audio_decision_preview")
    if isinstance(audio_preview, list) and audio_preview:
        lines.append("Audio: " + " | ".join(str(item) for item in audio_preview[:3]))
    subtitle_preview = row.get("subtitle_decision_preview")
    if isinstance(subtitle_preview, list) and subtitle_preview:
        lines.append("Subtitles: " + " | ".join(str(item) for item in subtitle_preview[:3]))
    runtime_status = str(row.get("runtime_outcome_status") or "").strip()
    if runtime_status:
        runtime_at = str(row.get("runtime_outcome_at") or "").strip()
        runtime_event = str(row.get("runtime_outcome_event_type") or "").strip()
        runtime_freshness = str(row.get("runtime_outcome_freshness_status") or "").strip()
        runtime_age = str(row.get("runtime_outcome_age_text") or "").strip()
        runtime_error = str(row.get("runtime_outcome_error_code") or "").strip()
        runtime_reason = str(row.get("runtime_outcome_reason") or "").strip()
        runtime_match = str(row.get("runtime_outcome_match") or "").strip()
        lines.append(
            "Last runtime outcome: "
            f"{runtime_status}"
            f"{f' via {runtime_event}' if runtime_event else ''}"
            f"{f' at {runtime_at}' if runtime_at else ''}"
            f"{f' ({runtime_age}; {runtime_freshness})' if runtime_age or runtime_freshness else ''}"
        )
        if runtime_match:
            lines.append(f"Runtime match: {runtime_match}")
        if runtime_error:
            lines.append(f"Runtime error code: {runtime_error}")
        if runtime_reason:
            lines.append(f"Runtime reason: {runtime_reason}")
    return lines


def completed_runtime_outcome_indices(events: Iterable[Any]) -> tuple[dict[str, dict[str, Any]], dict[str, dict[str, Any]]]:
    source_index = runtime_outcome_index(events)
    output_index: dict[str, dict[str, Any]] = {}
    for outcome in source_index.values():
        output_key = source_identity_key(outcome.get("runtime_outcome_output_path"))
        if output_key:
            output_index[output_key] = outcome
    return source_index, output_index


def completed_apply_runtime_outcomes(rows: list[dict[str, Any]], events: Iterable[Any]) -> list[dict[str, Any]]:
    source_index, output_index = completed_runtime_outcome_indices(events)
    if not source_index and not output_index:
        return rows
    for row in rows:
        outcome = None
        match = ""
        source_key = source_identity_key(row.get("source_path"))
        if source_key:
            outcome = source_index.get(source_key)
            if outcome is not None:
                match = "exact_source_path"
        if outcome is None:
            output_key = source_identity_key(row.get("output_path"))
            if output_key:
                outcome = output_index.get(output_key)
                if outcome is not None:
                    match = "exact_output_path"
        if outcome is None:
            continue
        patched = dict(outcome)
        if match:
            patched["runtime_outcome_match"] = match
        row.update(patched)
        row.update(completed_row_operator_guidance(row))
        row.update(completed_row_trust_fields(row))
    return rows


def completed_preview_rows(records: Iterable[object]) -> list[dict[str, Any]]:
    return [completed_record_to_row(record) for record in records if isinstance(record, CompletedJobRecord)]


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


def completed_preview_fields(
    rows: list[dict[str, Any]],
    *,
    source: str,
    manifest_path: Path | None = None,
    runtime_event_count: int = 0,
    runtime_outcome_source: str = "",
    runtime_outcome_warning: str = "",
) -> dict[str, Any]:
    output_sizes = [int(row.get("output_size_bytes") or 0) for row in rows]
    total_output_bytes = sum(output_sizes)
    size_unknown_count = sum(1 for row in rows if row.get("size_delta_percent") is None)
    audio_decision_total = sum(int(row.get("audio_decision_count") or 0) for row in rows)
    subtitle_decision_total = sum(int(row.get("subtitle_decision_count") or 0) for row in rows)
    runtime_outcome_rows = [row for row in rows if str(row.get("runtime_outcome_status") or "").strip()]
    inventory_progress = completed_inventory_progress_payload(rows_loaded=len(rows), source=source)
    fields = {
        "rows": rows,
        "source": source,
        "count": len(rows),
        "missing_output_count": sum(1 for row in rows if row.get("output_exists") is False),
        "encode_count": sum(1 for row in rows if str(row.get("route") or "").startswith("encode")),
        "remux_count": sum(1 for row in rows if str(row.get("route") or "") == "remux"),
        "route_counts": count_by_key(rows, "route"),
        "publish_counts": count_by_key(rows, "publish_state"),
        "health_counts": count_by_key(rows, "output_health", default="ok"),
        "operator_status_counts": count_by_key(rows, "operator_status"),
        "operator_status_state_counts": count_by_key(rows, "operator_status_state"),
        "operator_severity_counts": count_by_key(rows, "operator_severity"),
        "operator_trust_state_counts": count_by_key(rows, "operator_trust_state"),
        "consistency_status_counts": count_by_key(rows, "consistency_status"),
        "consistency_severity_counts": count_by_key(rows, "consistency_severity"),
        "validation_status_state_counts": count_by_key(rows, "validation_status_state"),
        "size_bucket_counts": count_by_key(rows, "size_bucket"),
        "media_type_counts": count_by_key(rows, "media_type"),
        "decision_totals": {
            "audio": audio_decision_total,
            "subtitle": subtitle_decision_total,
        },
        "runtime_outcome_source": runtime_outcome_source,
        "runtime_outcome_event_count": max(0, int(runtime_event_count or 0)),
        "runtime_outcome_match_count": len(runtime_outcome_rows),
        "runtime_outcome_warning": runtime_outcome_warning,
        "runtime_outcome_status_counts": count_by_key(runtime_outcome_rows, "runtime_outcome_status"),
        "runtime_outcome_event_type_counts": count_by_key(runtime_outcome_rows, "runtime_outcome_event_type"),
        "runtime_outcome_error_code_counts": count_by_key(runtime_outcome_rows, "runtime_outcome_error_code"),
        "runtime_outcome_freshness_counts": count_by_key(runtime_outcome_rows, "runtime_outcome_freshness_status"),
        "available_open_target_counts": count_list_values(rows, "available_open_targets"),
        "size_growth_count": sum(1 for row in rows if isinstance(row.get("size_delta_percent"), (int, float)) and float(row["size_delta_percent"]) > 0.0),
        "size_growth_over_5_count": sum(1 for row in rows if bool(row.get("size_growth_over_5"))),
        "size_policy_available_count": sum(1 for row in rows if bool(row.get("size_policy_available"))),
        "size_policy_exceeded_count": sum(1 for row in rows if bool(row.get("size_policy_exceeded"))),
        "size_policy_blocked_count": sum(1 for row in rows if bool(row.get("size_policy_exceeded")) and bool(row.get("size_policy_enforced"))),
        "size_policy_within_limit_count": sum(1 for row in rows if bool(row.get("size_policy_available")) and not bool(row.get("size_policy_exceeded"))),
        "size_policy_status_counts": count_by_key(rows, "size_policy_status"),
        "size_policy_mode_counts": count_by_key(rows, "size_policy_mode"),
        "size_unknown_count": size_unknown_count,
        "missing_sidecar_count": sum(1 for row in rows if "missing_sidecar" in (row.get("consistency_issues") or [])),
        "output_sidecar_mismatch_count": sum(1 for row in rows if "output_sidecar_mismatch" in (row.get("consistency_issues") or [])),
        "stale_sidecar_count": sum(1 for row in rows if "sidecar_older_than_output" in (row.get("consistency_issues") or [])),
        "missing_manifest_output_path_count": sum(1 for row in rows if "manifest_missing_output_path" in (row.get("consistency_issues") or [])),
        "total_output_bytes": total_output_bytes,
        "total_output_size_text": format_bytes_compact(total_output_bytes),
        "inventory_progress": inventory_progress,
        "progress_bars": inventory_progress["progress_bars"],
        "validation_state": validation_state_payload(rows, source=source),
        "warnings": [] if rows else [COMPLETED_HISTORY_EMPTY_MESSAGE],
    }
    fields.update(
        file_freshness_fields(
            manifest_path,
            prefix="manifest",
            stale_after_seconds=COMPLETED_MANIFEST_STALE_AFTER_SECONDS,
        )
    )
    return fields


def completed_history_service_unavailable_result() -> CompletedPreviewDto:
    progress = completed_inventory_progress_payload(
        rows_loaded=0,
        status="blocked",
        detail=COMPLETED_HISTORY_SERVICE_UNAVAILABLE_MESSAGE,
    )
    return _completed_preview_dto(
        inventory_progress=progress,
        progress_bars=progress["progress_bars"],
        warnings=[COMPLETED_HISTORY_SERVICE_UNAVAILABLE_MESSAGE],
    )


def completed_history_read_error_result(manifest_path: object, exc: Exception) -> CompletedPreviewDto:
    detail = f"Completed history could not be read: {exc}"
    progress = completed_inventory_progress_payload(
        rows_loaded=0,
        source=str(manifest_path or ""),
        status="blocked",
        detail=detail,
    )
    return _completed_preview_dto(
        source=str(manifest_path or ""),
        inventory_progress=progress,
        progress_bars=progress["progress_bars"],
        warnings=[detail],
    )


def completed_preview_from_records(
    records: Iterable[object],
    *,
    source: str,
    manifest_path: Path | None = None,
    runtime_events: Iterable[Any] = (),
    runtime_event_count: int = 0,
    runtime_outcome_source: str = "",
    runtime_outcome_warning: str = "",
) -> CompletedPreviewDto:
    rows = completed_preview_rows(records)
    rows = completed_apply_runtime_outcomes(rows, runtime_events)
    return _completed_preview_dto(
        **completed_preview_fields(
            rows,
            source=source,
            manifest_path=manifest_path,
            runtime_event_count=runtime_event_count,
            runtime_outcome_source=runtime_outcome_source,
            runtime_outcome_warning=runtime_outcome_warning,
        )
    )

__all__ = [
    "COMPLETED_HISTORY_SERVICE_UNAVAILABLE_MESSAGE",
    "COMPLETED_HISTORY_EMPTY_MESSAGE",
    "COMPLETED_MANIFEST_STALE_AFTER_SECONDS",
    "COMPLETED_INVENTORY_PROGRESS_SCHEMA_VERSION",
    "COMPLETED_HISTORY_ALL_LIMIT",
    "bounded_completed_limit",
    "completed_preview_limit",
    "completed_inventory_progress_payload",
    "format_bytes_compact",
    "completed_bitrate_display",
    "completed_bitrate_fields",
    "completed_record_key",
    "completed_decision_value",
    "completed_audio_decision_preview",
    "completed_subtitle_decision_preview",
    "completed_record_to_row",
    "completed_row_available_open_targets",
    "completed_row_operator_status_state",
    "completed_path_exists",
    "completed_path_mtime",
    "completed_size_bucket",
    "completed_row_consistency",
    "completed_row_operator_guidance",
    "completed_row_trust_fields",
    "completed_row_route_decision_summary",
    "completed_row_route_evidence_lines",
    "completed_runtime_outcome_indices",
    "completed_apply_runtime_outcomes",
    "completed_preview_rows",
    "completed_size_delta_percent",
    "completed_size_delta_label",
    "completed_size_policy_fields",
    "completed_row_size_policy_line",
    "count_by_key",
    "count_list_values",
    "completed_preview_fields",
    "completed_history_service_unavailable_result",
    "completed_history_read_error_result",
    "completed_preview_from_records",
]
