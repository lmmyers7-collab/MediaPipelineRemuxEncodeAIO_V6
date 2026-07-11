"""Backend-owned CSV rerun result scanning, open, and promote helpers."""

from __future__ import annotations

import hashlib
import json
import shutil
from collections import Counter
from copy import deepcopy
from datetime import datetime, UTC
from pathlib import Path, PureWindowsPath
from typing import Any
from collections.abc import Mapping

from mediapipeline.core.final_library.promotion_parts.planning import PromotionFileTarget
from mediapipeline.core.final_library.promotion_parts.transfer import (
    companion_sidecars,
    copy_files_transactionally,
    sha256_file,
)
from mediapipeline.core.kernel.contracts.pending_publish import PendingPushManifest
from mediapipeline.core.kernel.dto_commands import CommandResult
from mediapipeline.core.paths.contracts import ResolvedPaths
from mediapipeline.core.processes.file_io import atomic_write_text
from mediapipeline.core.processes.rerun_preview import recent_rerun_csv_candidates
from mediapipeline.core.processes.rerun_policy import (
    rerun_effective_output_root_for_source,
    rerun_final_output_root_violation,
    rerun_path_resolves_under_root,
    rerun_paths_resolve_same,
)
from mediapipeline.core.processes.rerun_rules import (
    RERUN_RULE_DECISION_SCHEMA_VERSION,
    rerun_rule_decision_from_mapping,
)


RERUN_RESULTS_SCHEMA_VERSION = "desktop_rerun_results.v1"
RERUN_QUEUE_STATE_SCHEMA_VERSION = "desktop_rerun_queue_state.v1"
RERUN_QUEUE_STATE_ROW_SCHEMA_VERSION = "desktop_rerun_queue_state_row.v1"
RERUN_PROMOTE_DRY_RUN_SCHEMA_VERSION = "desktop_rerun_promote_dry_run.v1"
RERUN_PROMOTE_PIPELINE_VERSION = "1.0"
NETWORK_RERUN_DESTINATION_POLICY_RESULT_SCHEMA_VERSION = "desktop_rerun_network_destination_policy_result.v1"
PENDING_MANIFEST_ARRAY_FIELDS = (
    "tx3g_srt_tracks",
    "tx3g_srt_failures",
    "bdpgs_srt_failures",
    "vobsub_srt_failures",
    "converted_srt_sidecar_candidates",
    "subtitle_output_reduction",
    "tx3g_embedded_srt_tracks",
    "bdpgs_embedded_srt_tracks",
    "vobsub_embedded_srt_tracks",
)
PENDING_MANIFEST_BOOL_FIELDS = (
    "tx3g_srt_conversion_enabled",
    "tx3g_external_srt_sidecars_enabled",
    "drop_tx3g_after_conversion",
    "bdpgs_srt_conversion_enabled",
    "drop_bdpgs_after_conversion",
    "vobsub_srt_conversion_enabled",
    "drop_vobsub_after_conversion",
)
PENDING_MANIFEST_OPTIONAL_EVIDENCE_FIELDS = (
    "folder_policy",
    "route_plan",
    "route_explanation",
    "library_profile",
    "dynamic_hdr",
    "quality_verification",
    "audio_decisions",
    "subtitle_decisions",
    "encode_selected_attempt",
    "encode_selected_encoder",
    "encode_selected_encoder_kind",
    "encode_selected_gpu_device",
)



from mediapipeline.core.processes.rerun_results_support import *  # noqa: F403

def rerun_manifest_queue_rows(manifest_path: Path, data: Mapping[str, Any]) -> list[dict[str, Any]]:
    batch_id = str(data.get("batch_id") or manifest_path.stem)
    manifest_status = _clean_text(data.get("status"))
    rows: list[dict[str, Any]] = []
    for index, raw_row in enumerate(data.get("rows") or []):
        if not isinstance(raw_row, Mapping):
            continue
        verified_output = _first_text(raw_row, "verified_output_path", "planned_output_path")
        final_output = _first_text(raw_row, "final_output_path", "server_out", "published_path")
        stage_path = _clean_text(raw_row.get("stage_path"))
        planned_output_path = _clean_text(raw_row.get("planned_output_path"))
        status = _clean_text(raw_row.get("status"))
        status_model = _queue_status_for_row(raw_row, manifest_status=manifest_status)
        try:
            row_index = int(raw_row.get("row_index"))
        except (TypeError, ValueError):
            row_index = index
        key = _row_key(manifest_path, batch_id, index, raw_row)
        issue_codes = _string_list(raw_row.get("audit_issue_codes"))
        auto_issues = _string_list(raw_row.get("auto_destination_issues"))
        failure_code = _clean_text(raw_row.get("failure_code"))
        operator_message = _clean_text(raw_row.get("operator_message"))
        rule_decision = rerun_rule_decision_from_mapping(raw_row)
        rule_mapping = rule_decision.to_mapping()
        can_promote = _status_key(status) in {
            "complete",
            "completed",
            "done",
            "succeeded",
            "success",
            "review_workspace",
            "awaiting_review",
            "review",
        } and _path_exists(verified_output)
        row = {
            "schema_version": RERUN_QUEUE_STATE_ROW_SCHEMA_VERSION,
            "row_key": key,
            "row_index": row_index,
            "queue_source": "csv_rerun",
            "queue_kind": "csv_rerun_row",
            "uses_pipeline_start": False,
            "status": status,
            "queue_status": status_model["status_key"],
            "queue_status_label": status_model["label"],
            "operator_status": f"CSV rerun {status_model['label']}",
            "operator_status_state": status_model["status_key"],
            "operator_severity": status_model["severity"],
            "operator_guidance": operator_message or status_model["reason"] or status_model["warning_reason"] or status_model["blocking_reason"],
            "is_terminal": bool(status_model["terminal"]),
            "rule_schema_version": RERUN_RULE_DECISION_SCHEMA_VERSION,
            "rerun_rule_id": rule_decision.rule_id,
            "rerun_rule_label": rule_decision.label,
            "rerun_rule_status": rule_decision.status,
            "rerun_rule_reason": rule_decision.reason,
            "rerun_rule_destination_behavior": rule_decision.destination_behavior,
            "rerun_rule_replacement_eligible": rule_decision.replacement_eligible,
            "rerun_rule_required_confirmations": list(rule_decision.required_confirmations),
            "rerun_rule_runtime_options": dict(rule_decision.runtime_options),
            "rerun_rule_evidence": dict(rule_decision.evidence),
            "rule_decision": rule_mapping,
            "source_path": _clean_text(raw_row.get("source_path")),
            "original_source_path": _clean_text(raw_row.get("source_path")),
            "stage_path": stage_path,
            "planned_output_path": planned_output_path,
            "verified_output_path": verified_output,
            "review_output_path": verified_output,
            "output_path": _first_text(raw_row, "published_path", "pending_publish_payload_path", "verified_output_path", "planned_output_path"),
            "final_output_path": final_output,
            "final_output_source": _clean_text(raw_row.get("final_output_source")),
            "final_output_source_field": _clean_text(raw_row.get("final_output_source_field")),
            "destination_path": final_output,
            "pending_publish_manifest_path": _clean_text(raw_row.get("pending_publish_manifest_path")),
            "pending_publish_payload_path": _clean_text(raw_row.get("pending_publish_payload_path")),
            "published_path": _clean_text(raw_row.get("published_path")),
            "replaced_final_hold_path": _clean_text(raw_row.get("replaced_final_hold_path")),
            "pipeline_sidecar_path": _clean_text(raw_row.get("pipeline_sidecar_path")),
            "published_sidecar_paths": _string_list(raw_row.get("published_sidecar_paths")),
            "replaced_sidecar_hold_paths": _string_list(raw_row.get("replaced_sidecar_hold_paths")),
            "completed_manifest_path": _clean_text(raw_row.get("completed_manifest_path")),
            "completed_manifest_append": _clean_text(raw_row.get("completed_manifest_append")),
            "source_size": raw_row.get("source_size"),
            "source_mtime_utc": _clean_text(raw_row.get("source_mtime_utc")),
            "source_identity_v2": _clean_text(raw_row.get("source_identity_v2")),
            "source_identity_v2_algorithm": _clean_text(raw_row.get("source_identity_v2_algorithm")),
            "reason": status_model["reason"],
            "failure_code": failure_code,
            "operator_message": operator_message,
            "blocking_reason": status_model["blocking_reason"],
            "warning_reason": status_model["warning_reason"],
            "audit_issue_codes": ", ".join(issue_codes),
            "audit_issue_code_list": issue_codes,
            "media_kind": _clean_text(raw_row.get("media_kind")),
            "can_open_output": _path_exists(verified_output),
            "can_promote_to_pending_publish": can_promote,
            "manifest_key": _hash_text(str(manifest_path)),
            "manifest_path": str(manifest_path),
            "batch_id": batch_id,
            "manifest_status": manifest_status,
            "created_at": _clean_text(data.get("created_at")),
            "completed_at": _clean_text(data.get("completed_at") or raw_row.get("completed_at")),
            "stopped_at": _clean_text(data.get("stopped_at")),
            "destination_state": {
                "destination_mode": _clean_text(data.get("destination_mode")),
                "collision_policy": _clean_text(data.get("collision_policy")),
                "rerun_rule_id": rule_decision.rule_id,
                "rerun_rule_destination_behavior": rule_decision.destination_behavior,
                "rerun_rule_replacement_eligible": rule_decision.replacement_eligible,
                "auto_destination_policy": _clean_text(raw_row.get("auto_destination_policy")),
                "auto_destination_decision": _clean_text(raw_row.get("auto_destination_decision")),
                "auto_destination_issue_count": raw_row.get("auto_destination_issue_count", 0),
                "auto_destination_issues": auto_issues,
                "pending_publish_manifest_path": _clean_text(raw_row.get("pending_publish_manifest_path")),
                "pending_publish_payload_path": _clean_text(raw_row.get("pending_publish_payload_path")),
                "published_path": _clean_text(raw_row.get("published_path")),
                "replaced_final_hold_path": _clean_text(raw_row.get("replaced_final_hold_path")),
                "final_output_source": _clean_text(raw_row.get("final_output_source")),
                "final_output_source_field": _clean_text(raw_row.get("final_output_source_field")),
                "completed_manifest_path": _clean_text(raw_row.get("completed_manifest_path")),
                "completed_manifest_append": _clean_text(raw_row.get("completed_manifest_append")),
            },
            "attempt_evidence": {
                "row_index": row_index,
                "manifest_path": str(manifest_path),
                "rule_decision": rule_mapping,
                "current_chunk": data.get("current_chunk"),
                "stage_mode": _clean_text(raw_row.get("stage_mode")),
                "original_mode": _clean_text(raw_row.get("original_mode")),
                "return_mode": _clean_text(raw_row.get("return_mode")),
                "original_action": _clean_text(raw_row.get("original_action")),
                "source_overwrite_confirmed": raw_row.get("source_overwrite_confirmed") is True,
                "staged_input_cleanup": _clean_text(raw_row.get("staged_input_cleanup")),
                "failure_code": failure_code,
                "operator_message": operator_message,
                "pipeline_sidecar_publish": _clean_text(raw_row.get("pipeline_sidecar_publish")),
                "completed_manifest_append": _clean_text(raw_row.get("completed_manifest_append")),
            },
        }
        row["available_actions"] = _available_actions(row)
        rows.append(row)
    return rows


def _remaining_pending_count(data: Mapping[str, Any], row_counts: Mapping[str, int]) -> int:
    value = data.get("remaining_pending_count")
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        parsed = int(row_counts.get("pending", 0) or 0)
    return max(0, parsed)


def _manifest_entries(resolved: ResolvedPaths, *, limit: int = 24) -> list[dict[str, Any]]:
    root = _manifest_root(resolved)
    if root is None or not root.exists():
        return []
    try:
        paths = sorted(root.glob("*.json"), key=lambda item: item.stat().st_mtime, reverse=True)
    except OSError:
        return []
    manifests: list[dict[str, Any]] = []
    for path in paths[:limit]:
        data = _read_json(path)
        if not isinstance(data, dict):
            continue
        rows = rerun_manifest_queue_rows(path, data)
        batch_id = str(data.get("batch_id") or path.stem)
        row_counts = _row_status_counts(rows)
        queue_status_counts = _row_queue_status_counts(rows)
        destination_summary = _destination_summary(rows)
        remaining_pending_count = _remaining_pending_count(data, row_counts)
        status = str(data.get("status") or "")
        manifests.append(
            {
                "manifest_key": _hash_text(str(path)),
                "manifest_path": str(path),
                "batch_id": batch_id,
                "status": status,
                "created_at": str(data.get("created_at") or ""),
                "completed_at": str(data.get("completed_at") or ""),
                "stopped_at": str(data.get("stopped_at") or ""),
                "current_chunk": data.get("current_chunk"),
                "execution_mode": str(data.get("execution_mode") or ""),
                "destination_mode": str(data.get("destination_mode") or ""),
                "original_policy": str(data.get("original_policy") or ""),
                "collision_policy": str(data.get("collision_policy") or ""),
                "window_size": data.get("window_size"),
                "output_root": str(data.get("output_root") or ""),
                "pending_publish_root": str(data.get("pending_publish_root") or ""),
                "completed_jobs_manifest": str(data.get("completed_jobs_manifest") or ""),
                "row_status_counts": row_counts,
                "queue_status_counts": queue_status_counts,
                "destination_summary": destination_summary,
                "remaining_pending_count": remaining_pending_count,
                "can_continue_pending": status == "stopped_after_current" and remaining_pending_count > 0,
                "stop_request_id": str(data.get("stop_request_id") or ""),
                "stop_requested_at": str(data.get("stop_requested_at") or ""),
                "stop_request_marker_path": str(data.get("stop_request_marker_path") or ""),
                "safe_next_action": str(data.get("safe_next_action") or ""),
                "rows": rows,
                "row_count": len(rows),
            }
        )
    return manifests


def _network_row_key(batch_id: str, row_key: str, state_path: Path) -> str:
    raw = str(row_key or "").strip()
    if raw:
        return f"network:{batch_id}:{raw}"
    return f"network:{batch_id}:{_hash_text(str(state_path))}"


def _network_reducer_result(row: Mapping[str, Any]) -> dict[str, Any]:
    raw = row.get("reducer_result")
    return deepcopy(raw) if isinstance(raw, Mapping) else {}


def _network_worker_result(row: Mapping[str, Any]) -> dict[str, Any]:
    raw = row.get("worker_result")
    return deepcopy(raw) if isinstance(raw, Mapping) else {}


def _network_verified_output(row: Mapping[str, Any], worker_result: Mapping[str, Any], reducer_result: Mapping[str, Any]) -> str:
    text = _first_text(row, "verified_output_path", "review_output_path")
    if text:
        return text
    output = reducer_result.get("output_artifact") if isinstance(reducer_result, Mapping) else None
    if isinstance(output, Mapping):
        text = _clean_text(output.get("path"))
        if text:
            return text
    return _clean_text(worker_result.get("output_path"))


def _network_batch_queue_rows(state_path: Path, data: Mapping[str, Any]) -> list[dict[str, Any]]:
    batch_id = str(data.get("batch_id") or state_path.stem)
    manifest_status = _clean_text(data.get("status"))
    rows: list[dict[str, Any]] = []
    for index, raw_row in enumerate(data.get("rows") or []):
        if not isinstance(raw_row, Mapping):
            continue
        raw_row_key = _clean_text(raw_row.get("row_key"))
        status = _clean_text(raw_row.get("status"))
        status_model = _queue_status_for_row(raw_row, manifest_status=manifest_status)
        try:
            row_index = int(raw_row.get("row_index"))
        except (TypeError, ValueError):
            row_index = index
        reducer_result = _network_reducer_result(raw_row)
        worker_result = _network_worker_result(raw_row)
        raw_destination_result = raw_row.get("destination_policy_result")
        destination_result = deepcopy(raw_destination_result) if isinstance(raw_destination_result, Mapping) else {}
        destination_applied = raw_row.get("destination_policy_applied") is True or destination_result.get("ok") is True
        destination_terminal = destination_result.get("terminal") is True
        pending_destination_policy = (
            reducer_result.get("pending_destination_policy") is True
            and not destination_applied
            and not destination_terminal
        )
        verified_output = _network_verified_output(raw_row, worker_result, reducer_result)
        output_artifact = reducer_result.get("output_artifact") if isinstance(reducer_result, Mapping) else {}
        destination_policy = raw_row.get("destination_policy")
        pending_manifest_path = (
            _clean_text(raw_row.get("pending_publish_manifest_path"))
            or _clean_text(destination_result.get("pending_publish_manifest_path"))
        )
        pending_payload_path = (
            _clean_text(raw_row.get("pending_publish_payload_path"))
            or _clean_text(destination_result.get("pending_publish_payload_path"))
        )
        published_path = _clean_text(raw_row.get("published_path")) or _clean_text(destination_result.get("published_path"))
        row = {
            "schema_version": RERUN_QUEUE_STATE_ROW_SCHEMA_VERSION,
            "row_key": _network_row_key(batch_id, raw_row_key, state_path),
            "network_rerun_row_key": raw_row_key,
            "row_index": row_index,
            "queue_source": "network_csv_rerun",
            "queue_kind": "network_csv_rerun_row",
            "uses_pipeline_start": False,
            "status": status,
            "queue_status": status_model["status_key"],
            "queue_status_label": status_model["label"],
            "operator_status": f"Network CSV rerun {status_model['label']}",
            "operator_status_state": status_model["status_key"],
            "operator_severity": status_model["severity"],
            "operator_guidance": (
                status_model["reason"]
                or status_model["warning_reason"]
                or status_model["blocking_reason"]
                or _clean_text(reducer_result.get("reason"))
            ),
            "is_terminal": bool(status_model["terminal"]),
            "source_path": _clean_text(raw_row.get("source_path")),
            "original_source_path": _clean_text(raw_row.get("source_path")),
            "stage_path": "",
            "planned_output_path": _clean_text(raw_row.get("planned_output_path")),
            "verified_output_path": verified_output,
            "review_output_path": verified_output,
            "output_path": verified_output,
            "final_output_path": _first_text(raw_row, "final_output_path", "server_out", "published_path"),
            "destination_path": _first_text(raw_row, "final_output_path", "server_out", "published_path"),
            "pending_publish_manifest_path": pending_manifest_path,
            "pending_publish_payload_path": pending_payload_path,
            "published_path": published_path,
            "source_size": raw_row.get("source_size"),
            "source_mtime_utc": _clean_text(raw_row.get("source_mtime_utc")),
            "source_identity_v2": _clean_text(raw_row.get("source_identity_v2")),
            "source_identity_v2_algorithm": _clean_text(raw_row.get("source_identity_v2_algorithm")),
            "reason": status_model["reason"] or _clean_text(reducer_result.get("reason")),
            "blocking_reason": status_model["blocking_reason"],
            "warning_reason": status_model["warning_reason"] or _clean_text(reducer_result.get("reason")),
            "audit_issue_codes": _clean_text(raw_row.get("audit_issue_codes")),
            "audit_issue_code_list": _string_list(raw_row.get("audit_issue_codes")),
            "media_kind": _clean_text(raw_row.get("media_kind")),
            "can_open_output": _path_exists(verified_output),
            "can_promote_to_pending_publish": False,
            "manifest_key": _hash_text(str(state_path)),
            "manifest_path": str(state_path),
            "batch_id": batch_id,
            "manifest_status": manifest_status,
            "created_at": _clean_text(data.get("created_at_utc") or data.get("created_at")),
            "completed_at": _clean_text(raw_row.get("completed_at")),
            "stopped_at": _clean_text(data.get("stopped_at")),
            "claim_status": _clean_text(raw_row.get("claim_status")),
            "claimable": raw_row.get("claimable") is True,
            "active_claim": deepcopy(raw_row.get("active_claim")) if isinstance(raw_row.get("active_claim"), Mapping) else {},
            "network_reducer_result": reducer_result,
            "network_worker_result": worker_result,
            "network_output_artifact": deepcopy(output_artifact) if isinstance(output_artifact, Mapping) else {},
            "network_destination_policy": deepcopy(destination_policy) if isinstance(destination_policy, Mapping) else {},
            "network_destination_policy_result": destination_result,
            "destination_state": {
                "destination_mode": _clean_text(data.get("destination_mode")),
                "collision_policy": _clean_text(data.get("collision_policy")),
                "pending_destination_policy": pending_destination_policy,
                "destination_policy_applied": destination_applied,
                "destination_policy_terminal": destination_terminal,
                "destination_policy_status": _clean_text(destination_result.get("status")),
                "destination_policy_action": _clean_text(destination_result.get("action")),
                "destination_policy_result": destination_result,
                "pending_publish_manifest_path": pending_manifest_path,
                "pending_publish_payload_path": pending_payload_path,
                "published_path": published_path,
                "reducer_classification": _clean_text(reducer_result.get("classification")),
                "reducer_accepted": reducer_result.get("accepted") is True,
                "final_output_source": _clean_text(raw_row.get("final_output_source")),
                "final_output_source_field": _clean_text(raw_row.get("final_output_source_field")),
            },
            "attempt_evidence": {
                "row_index": row_index,
                "manifest_path": str(state_path),
                "network_batch_state": True,
                "claim_status": _clean_text(raw_row.get("claim_status")),
                "reducer_result": reducer_result,
                "worker_result": worker_result,
                "destination_policy_result": destination_result,
            },
            "available_actions": [],
        }
        rows.append(row)
    return rows


def _network_manifest_entries(resolved: ResolvedPaths, *, limit: int = 24) -> list[dict[str, Any]]:
    root = _network_manifest_root(resolved)
    if root is None or not root.exists():
        return []
    try:
        paths = sorted(root.glob("*.json"), key=lambda item: item.stat().st_mtime, reverse=True)
    except OSError:
        return []
    manifests: list[dict[str, Any]] = []
    for path in paths[:limit]:
        data = _read_json(path)
        if not isinstance(data, dict):
            continue
        if str(data.get("schema_version") or "") != "desktop_rerun_network_batch.v1":
            continue
        rows = _network_batch_queue_rows(path, data)
        batch_id = str(data.get("batch_id") or path.stem)
        manifests.append(
            {
                "manifest_key": _hash_text(str(path)),
                "manifest_path": str(path),
                "batch_id": batch_id,
                "status": str(data.get("status") or ""),
                "schema_version": str(data.get("schema_version") or ""),
                "phase": str(data.get("phase") or ""),
                "created_at": str(data.get("created_at_utc") or data.get("created_at") or ""),
                "updated_at": str(data.get("updated_at_utc") or ""),
                "queue_source": "network_csv_rerun",
                "uses_pipeline_start": False,
                "claim_provider_enabled": data.get("claim_provider_enabled") is True,
                "worker_execution_enabled": data.get("worker_execution_enabled") is True,
                "rows_claimable": data.get("rows_claimable") is True,
                "row_status_counts": _row_status_counts(rows),
                "queue_status_counts": _row_queue_status_counts(rows),
                "row_count": len(rows),
                "rows": rows,
            }
        )
    return manifests


def rerun_results_payload(resolved: ResolvedPaths, *, service: Any | None = None, limit: int = 24) -> dict[str, Any]:
    manifests = _manifest_entries(resolved, limit=limit)
    network_manifests = _network_manifest_entries(resolved, limit=limit)
    csvs = recent_rerun_csv_candidates(resolved, service, limit=limit)
    for item in csvs:
        item["csv_key"] = _hash_text(str(item.get("path") or ""))
    local_row_count = sum(len(item.get("rows") or []) for item in manifests)
    network_row_count = sum(len(item.get("rows") or []) for item in network_manifests)
    row_count = local_row_count + network_row_count
    rows = [row for manifest in manifests for row in manifest.get("rows", [])]
    rows.extend(row for manifest in network_manifests for row in manifest.get("rows", []))
    queue_status_counts = _row_queue_status_counts(rows)
    return {
        "schema_version": RERUN_RESULTS_SCHEMA_VERSION,
        "manifest_root": str(_manifest_root(resolved) or ""),
        "network_manifest_root": str(_network_manifest_root(resolved) or ""),
        "manifests": manifests,
        "network_manifests": network_manifests,
        "rows": rows,
        "queue_state": {
            "schema_version": RERUN_QUEUE_STATE_SCHEMA_VERSION,
            "row_schema_version": RERUN_QUEUE_STATE_ROW_SCHEMA_VERSION,
            "queue_source": "csv_rerun",
            "contains_network_csv_rerun": bool(network_manifests),
            "uses_pipeline_start": False,
            "rows": rows,
            "row_count": row_count,
            "status_counts": queue_status_counts,
            "available_statuses": [
                {"key": "pending", "label": "Pending"},
                {"key": "active", "label": "Active"},
                {"key": "blocked", "label": "Blocked"},
                {"key": "warning", "label": "Warning"},
                {"key": "failed", "label": "Failed"},
                {"key": "stopped", "label": "Stopped"},
                {"key": "pending_reduction", "label": "Pending Reduction"},
                {"key": "completed", "label": "Completed"},
                {"key": "awaiting_review", "label": "Awaiting Review"},
                {"key": "pending_publish", "label": "Pending Publish"},
                {"key": "replaced_returned", "label": "Replaced / Returned"},
                {"key": "skipped", "label": "Skipped"},
            ],
        },
        "recent_csvs": csvs,
        "counts": {
            "manifest_count": len(manifests),
            "network_manifest_count": len(network_manifests),
            "row_count": row_count,
            "local_row_count": local_row_count,
            "network_row_count": network_row_count,
            "promotable_rows": sum(1 for manifest in manifests for row in manifest.get("rows", []) if row.get("can_promote_to_pending_publish")),
            "csv_candidate_count": len(csvs),
            "queue_status_counts": queue_status_counts,
        },
        "touches_media": False,
        "writes_queue": False,
        "writes_file_overrides": False,
    }

__all__ = (
    "rerun_manifest_queue_rows",
    "_remaining_pending_count",
    "_manifest_entries",
    "_network_row_key",
    "_network_reducer_result",
    "_network_worker_result",
    "_network_verified_output",
    "_network_batch_queue_rows",
    "_network_manifest_entries",
    "rerun_results_payload",
)
