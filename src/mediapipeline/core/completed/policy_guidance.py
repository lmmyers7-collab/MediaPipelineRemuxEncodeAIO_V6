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

from mediapipeline.core.completed.policy_quality import *  # noqa: F403

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
    quality_outcome = str(row.get("quality_outcome") or "").strip().casefold()
    quality_blocked = bool(row.get("quality_blocked"))
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
    if quality_outcome == "fail":
        flags.append("quality_below_floor")
        if quality_blocked:
            severity = "error"
        elif severity != "error":
            severity = "warning"
    elif quality_outcome == "warn":
        flags.append("quality_review")
        if severity == "ok":
            severity = "warning"
    elif quality_outcome == "pass":
        flags.append("quality_within_threshold")
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
    elif "quality_below_floor" in flags:
        label = "Quality below floor"
        guidance = "Completed history reports an encode that measured below the configured quality floor. Inspect the recorded score, metric, and thresholds before trusting or re-running this output."
    elif "quality_review" in flags:
        label = "Quality review"
        guidance = "Output published but its quality score fell below the warn threshold. Compare the score against the source before accepting it."
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
    quality_line = completed_row_quality_line(row)
    if quality_line:
        lines.append(quality_line)
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
    if bool(row.get("pending_publish")) and not str(row.get("output_health") or "").strip():
        health = "parked pending publish"
    else:
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
__all__ = (
    "completed_row_route_evidence_lines",
    "completed_row_operator_guidance",
    "completed_row_trust_fields",
    "completed_row_route_decision_summary",
)
