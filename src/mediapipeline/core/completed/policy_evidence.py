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

def _mapping_text(mapping: Mapping[str, Any], *keys: str) -> str:
    for key in keys:
        value = str(mapping.get(key) or "").strip()
        if value:
            return value
    return ""

def _pending_publish_completed_payload(row: Mapping[str, Any]) -> dict[str, Any] | None:
    pending_state = _mapping_text(row, "state").casefold()
    if pending_state not in COMPLETED_PENDING_PUBLISH_ROW_STATES:
        return None
    manifest_path = _mapping_text(row, "manifest_path")
    local_file = _mapping_text(row, "local_file")
    server_out = _mapping_text(row, "server_out")
    if not manifest_path or not local_file or not server_out:
        return None
    if row.get("local_exists") is False:
        return None
    payload = {
        "source_path": _mapping_text(row, "source_path"),
        "output_path": server_out,
        "output_file": Path(server_out).name,
        "route": _mapping_text(row, "route"),
        "encoded_at": _mapping_text(row, "parked_at"),
        "output_size": row.get("output_size"),
        "publish_state": "parked",
        "publish_mode": _mapping_text(row, "publish_mode") or "deferred",
        "_diagnostics_output_proof": OUTPUT_PROOF_DEFERRED,
        "_diagnostics_pending_publish": True,
        "_diagnostics_pending_publish_manifest_path": manifest_path,
        "_diagnostics_pending_publish_local_file": local_file,
        "_diagnostics_pending_publish_state": pending_state,
    }
    for key in (
        "route_plan",
        "route_explanation",
        "route_actions",
        "encode_selected_attempt",
        "runtime_outcome_route",
        "size_policy",
    ):
        value = row.get(key)
        if isinstance(value, dict):
            payload[key] = value
        elif isinstance(value, str) and value.strip():
            payload[key] = value
    return payload

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

__all__ = (
    "_mapping_text",
    "_pending_publish_completed_payload",
    "completed_row_available_open_targets",
    "completed_row_operator_status_state",
    "completed_path_exists",
    "completed_path_mtime",
    "completed_size_bucket",
    "completed_row_consistency",
)
