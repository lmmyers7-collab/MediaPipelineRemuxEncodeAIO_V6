"""Backend-owned CSV rerun result scanning, open, and promote helpers."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
from collections import Counter
from collections.abc import Mapping, Sequence
from datetime import datetime, UTC
from pathlib import Path, PureWindowsPath
from typing import Any, cast

try:
    import psutil
except ImportError:  # pragma: no cover - optional runtime dependency
    psutil = None

from mediapipeline.core.final_library.promotion_parts.planning import PromotionFileTarget
from mediapipeline.core.final_library.promotion_parts.transfer import (
    companion_sidecars,
    copy_files_transactionally,
    sha256_file,
)
from mediapipeline.core.kernel.contracts.pending_publish import PendingPushManifest
from mediapipeline.core.kernel.contracts import ActiveJobRecord, ContractError
from mediapipeline.core.kernel.dto_commands import CommandResult
from mediapipeline.core.network.facade_connectivity import _heartbeat_timeout_seconds, _runtime_state_dir
from mediapipeline.core.network.registry import InFlightRegistry
from mediapipeline.core.paths.contracts import ResolvedPaths
from mediapipeline.core.processes.active_jobs import active_job_pid_matches_record, active_jobs_dir_for_resolved
from mediapipeline.core.processes.file_io import atomic_write_text
from mediapipeline.core.processes.rerun_preview import recent_rerun_csv_candidates
from mediapipeline.core.processes.rerun_control import (
    COMPLETED_WITH_FAILURES_STATUSES,
    WAITING_RESTART_STATUSES,
    rerun_pending_recovery_posture,
    rerun_retry_exhausted_recovery_posture,
    rerun_waiting_restart_posture,
)
from mediapipeline.core.processes.rerun_lifecycle import (
    read_rerun_startup_reconciliation,
    rerun_correlation_evidence,
    rerun_execution_manifest_has_durable_exit_state,
    rerun_execution_manifest_root,
    rerun_lifecycle_counts,
    rerun_manifest_declared_path_matches_actual,
    rerun_manifest_matches_enrollment,
    rerun_manifest_path_matches_canonical_batch,
)
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
from mediapipeline.core.processes.rerun_results_network_projection import (
    _network_batch_queue_rows,
    _network_lifecycle_counts,
    _network_nonnegative_int,
    _network_output_probe,
    _network_reducer_result,
    _network_row_key,
    _network_verified_output,
    _network_worker_result,
)
from mediapipeline.core.rerun.evidence import exact_rerun_active_job_payload, read_rerun_enrollment, rerun_enrollment_root


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
RERUN_SCAN_WARNING_LIMIT = 20
NETWORK_RERUN_OPEN_STATUSES = frozenset(
    {"starting", "running", "active", "stopping", "stopped_after_current", "paused", "claim_disabled"}
)


def _scan_warning(source: str, code: str, path: Path | None, message: object) -> dict[str, str]:
    return {
        "source": source,
        "code": code,
        "path": str(path or ""),
        "message": str(message or "")[:500],
    }


def _safe_json_candidates(root: Path | None, *, source: str) -> tuple[list[Path], dict[str, Any]]:
    info: dict[str, Any] = {
        "source": source,
        "discovered_candidate_count": 0,
        "scannable_candidate_count": 0,
        "skipped_candidate_count": 0,
        "warning_count": 0,
        "scan_warnings": [],
    }
    if root is None or not root.exists():
        return [], info
    candidates: list[tuple[float, Path]] = []
    try:
        discovered = list(root.glob("*.json"))
    except OSError as exc:
        info["warning_count"] = 1
        info["scan_warnings"] = [_scan_warning(source, "manifest_root_scan_failed", root, exc)]
        return [], info
    info["discovered_candidate_count"] = len(discovered)
    for path in discovered:
        try:
            modified_at = path.stat().st_mtime
        except OSError as exc:
            info["skipped_candidate_count"] += 1
            info["warning_count"] += 1
            if len(info["scan_warnings"]) < RERUN_SCAN_WARNING_LIMIT:
                info["scan_warnings"].append(_scan_warning(source, "manifest_stat_failed", path, exc))
            continue
        candidates.append((modified_at, path))
    candidates.sort(key=lambda item: item[0], reverse=True)
    info["scannable_candidate_count"] = len(candidates)
    return [path for _modified_at, path in candidates], info


def _merge_scan_warning(info: dict[str, Any], warning: dict[str, str]) -> None:
    info["warning_count"] = int(info.get("warning_count") or 0) + 1
    warnings = info.setdefault("scan_warnings", [])
    if len(warnings) < RERUN_SCAN_WARNING_LIMIT:
        warnings.append(warning)


def _direct_live_local_jobs(resolved: ResolvedPaths) -> tuple[list[dict[str, Any]], list[dict[str, str]]]:
    root = active_jobs_dir_for_resolved(resolved)
    paths, scan = _safe_json_candidates(root, source="active_jobs")
    warnings = list(scan.get("scan_warnings") or [])
    live: list[dict[str, Any]] = []
    for path in paths:
        raw = _read_json(path)
        if not isinstance(raw, dict):
            warnings.append(_scan_warning("active_jobs", "active_job_unreadable", path, "ActiveJobs JSON is unreadable."))
            continue
        try:
            record = ActiveJobRecord.from_mapping(raw)
        except ContractError as exc:
            warnings.append(_scan_warning("active_jobs", "active_job_invalid", path, exc))
            continue
        if record.job_kind.casefold() != "rerun_csv" or record.status.casefold() not in {"launching", "active"}:
            continue
        if active_job_pid_matches_record(record, psutil) is not True:
            continue
        metadata = dict(raw.get("metadata") or {}) if isinstance(raw.get("metadata"), Mapping) else {}
        batch_id = _clean_text(metadata.get("batch_id"))
        launch_id = _clean_text(raw.get("launch_id"))
        if not batch_id or not launch_id:
            warnings.append(
                _scan_warning("active_jobs", "active_rerun_correlation_missing", path, "Live rerun lacks batch or launch identity.")
            )
            continue
        manifest_path = Path(
            _clean_text(metadata.get("manifest_path"))
            or str(rerun_execution_manifest_root(resolved) / f"{batch_id}.json")
        )
        enrollment_path = Path(
            _clean_text(metadata.get("enrollment_path"))
            or str(rerun_enrollment_root(resolved) / f"{batch_id}.json")
        )
        canonical_manifest_path = rerun_execution_manifest_root(resolved) / f"{batch_id}.json"
        if _path_key(manifest_path) != _path_key(canonical_manifest_path):
            warnings.append(
                _scan_warning("active_jobs", "active_rerun_manifest_noncanonical", manifest_path, "Live rerun manifest path is not canonical.")
            )
            continue
        if _path_key(enrollment_path.parent) != _path_key(rerun_enrollment_root(resolved)):
            warnings.append(
                _scan_warning("active_jobs", "active_rerun_enrollment_noncanonical", enrollment_path, "Live rerun enrollment path is not canonical.")
            )
            continue
        live.append(
            {
                "record_path": path,
                "record": raw,
                "metadata": metadata,
                "batch_id": batch_id,
                "launch_id": launch_id,
                "command_id": _clean_text(metadata.get("command_id")),
                "manifest_path": manifest_path,
                "enrollment_path": enrollment_path,
            }
        )
    return live, warnings


def _has_durable_row_index(row: Mapping[str, Any]) -> bool:
    try:
        return int(cast(Any, row.get("row_index"))) >= 0
    except (TypeError, ValueError):
        return False


def _recovery_row_selector(row: Mapping[str, Any]) -> tuple[int | None, str]:
    try:
        row_index = int(cast(Any, row.get("row_index")))
    except (TypeError, ValueError):
        row_index = None
    source_path = _clean_text(row.get("source_path")).replace("/", "\\").casefold()
    return row_index, source_path



from mediapipeline.core.processes.rerun_results_support import *  # noqa: F403

def rerun_manifest_queue_rows(
    resolved: ResolvedPaths,
    manifest_path: Path,
    data: Mapping[str, Any],
    *,
    retry_posture: Mapping[str, Any] | None = None,
    pending_posture: Mapping[str, Any] | None = None,
    recovery_actions_allowed: bool = True,
) -> list[dict[str, Any]]:
    batch_id = str(data.get("batch_id") or manifest_path.stem)
    manifest_status = _clean_text(data.get("status"))
    retry_exhausted_batch = (
        recovery_actions_allowed and manifest_status.casefold() in COMPLETED_WITH_FAILURES_STATUSES
    )
    effective_retry_posture = dict(
        retry_posture
        or (
            rerun_retry_exhausted_recovery_posture(resolved, data)
            if retry_exhausted_batch
            else {}
        )
    )
    recoverable_retry_exhausted_batch_count = int(effective_retry_posture.get("recoverable_count") or 0)
    recoverable_selectors = {
        _recovery_row_selector(row)
        for row in effective_retry_posture.get("recoverable_rows") or []
        if isinstance(row, Mapping)
    }
    blocked_by_selector = {
        _recovery_row_selector(row): dict(row)
        for row in effective_retry_posture.get("blocked_rows") or []
        if isinstance(row, Mapping)
    }
    pending_recovery_batch = recovery_actions_allowed and manifest_status.casefold() == "stopped_after_current"
    effective_pending_posture = dict(
        pending_posture
        or (
            rerun_pending_recovery_posture(resolved, data)
            if pending_recovery_batch
            else {}
        )
    )
    recoverable_pending_selectors = {
        _recovery_row_selector(row)
        for row in effective_pending_posture.get("recoverable_rows") or []
        if isinstance(row, Mapping)
    }
    blocked_pending_by_selector = {
        _recovery_row_selector(row): dict(row)
        for row in effective_pending_posture.get("blocked_rows") or []
        if isinstance(row, Mapping)
    }
    correlation = rerun_correlation_evidence(
        resolved,
        data,
        enrollment_path=str(data.get("enrollment_path") or ""),
        manifest_path=manifest_path,
    )
    rows: list[dict[str, Any]] = []
    for index, raw_row in enumerate(data.get("rows") or []):
        if not isinstance(raw_row, Mapping):
            continue
        verified_output = _first_text(raw_row, "verified_output_path", "planned_output_path")
        final_output = _first_text(raw_row, "final_output_path", "server_out", "published_path")
        stage_path = _clean_text(raw_row.get("stage_path"))
        planned_output_path = _clean_text(raw_row.get("planned_output_path"))
        status = _clean_text(raw_row.get("status"))
        lifecycle_state = _clean_text(raw_row.get("lifecycle_state") or status)
        timeline = [dict(item) for item in raw_row.get("timeline") or [] if isinstance(item, Mapping)]
        latest_timeline_what = next(
            (_clean_text(item.get("what")) for item in reversed(timeline) if _clean_text(item.get("what"))),
            "",
        )
        status_model = _queue_status_for_row(raw_row, manifest_status=manifest_status)
        try:
            row_index = int(cast(Any, raw_row.get("row_index")))
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
            "has_durable_row_index": _has_durable_row_index(raw_row),
            "queue_source": "csv_rerun",
            "queue_kind": "csv_rerun_row",
            "uses_pipeline_start": False,
            "status": status,
            "lifecycle_state": lifecycle_state,
            **correlation,
            "command_id": _clean_text(raw_row.get("command_id") or data.get("command_id")),
            "launch_id": _clean_text(raw_row.get("launch_id") or data.get("launch_id")),
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
            "source_identity_v2": _clean_text(
                raw_row.get("planned_source_identity_v2") or raw_row.get("source_identity_v2")
            ),
            "source_identity_v2_algorithm": _clean_text(raw_row.get("source_identity_v2_algorithm")),
            "source_content_sha256": _clean_text(raw_row.get("source_content_sha256")),
            "source_content_sha256_algorithm": _clean_text(
                raw_row.get("source_content_sha256_algorithm")
            ),
            "planned_source_content_sha256": _clean_text(
                raw_row.get("planned_source_content_sha256") or raw_row.get("source_content_sha256")
            ),
            "planned_source_content_sha256_algorithm": _clean_text(
                raw_row.get("planned_source_content_sha256_algorithm")
                or raw_row.get("source_content_sha256_algorithm")
            ),
            "staged_source_content_sha256": _clean_text(raw_row.get("staged_source_content_sha256")),
            "staged_source_content_sha256_algorithm": _clean_text(
                raw_row.get("staged_source_content_sha256_algorithm")
            ),
            "recovery_blocked_reason": "",
            "reason": status_model["reason"],
            "reason_code": _clean_text(raw_row.get("reason_code") or data.get("reason_code")),
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
            "started_at": _clean_text(data.get("started_at")),
            "last_transition_at": _clean_text(raw_row.get("last_transition_at") or data.get("last_transition_at")),
            "attempt_count": raw_row.get("attempt_count", 0),
            "max_attempts": raw_row.get("max_attempts", 0),
            "first_failure_at": _clean_text(raw_row.get("first_failure_at")),
            "last_failure_at": _clean_text(raw_row.get("last_failure_at")),
            "next_retry_at": _clean_text(raw_row.get("next_retry_at")),
            "last_error": _clean_text(raw_row.get("last_error")),
            "lifecycle_what": _clean_text(
                raw_row.get("lifecycle_what") or raw_row.get("what") or latest_timeline_what
            ),
            "automatic_next_action": _clean_text(raw_row.get("automatic_next_action")),
            "operator_action_required": raw_row.get("operator_action_required") is True,
            "available_operator_action": _clean_text(raw_row.get("available_operator_action")),
            "timeline": timeline,
            "evidence_links": {
                "manifest": str(manifest_path),
                "enrollment": correlation["enrollment_path"],
                "active_jobs": {
                    "key": correlation["active_jobs_key"],
                    "path": correlation["active_jobs_path"],
                },
                "command_journal": {"key": correlation["command_evidence_key"]},
                "stdout_log": correlation["stdout_log"],
                "stderr_log": correlation["stderr_log"],
            },
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
        pending_recovery_blocked = (
            lifecycle_state.casefold() == "pending"
            and pending_recovery_batch
            and _recovery_row_selector(raw_row) not in recoverable_pending_selectors
        )
        if pending_recovery_blocked:
            blocked = blocked_pending_by_selector.get(_recovery_row_selector(raw_row), {})
            row["queue_status_label"] = "Blocked"
            row["operator_status_state"] = "review"
            row["recovery_blocked_reason_code"] = _clean_text(blocked.get("reason_code"))
            row["recovery_blocked_reason"] = _clean_text(blocked.get("reason")) or (
                "This pending row lacks the durable strong-identity evidence required for safe continuation."
            )
        row["available_actions"] = _available_actions(row)
        if recovery_actions_allowed and lifecycle_state.casefold() in {
            "retry_exhausted",
            "retry_scheduled",
            "waiting_for_source",
        }:
            retry_exhausted_recoverable = (
                lifecycle_state.casefold() == "retry_exhausted"
                and retry_exhausted_batch
                and _recovery_row_selector(raw_row) in recoverable_selectors
            )
            retry_exhausted_blocked = (
                lifecycle_state.casefold() == "retry_exhausted"
                and retry_exhausted_batch
                and not retry_exhausted_recoverable
            )
            if retry_exhausted_blocked:
                blocked = blocked_by_selector.get(_recovery_row_selector(raw_row), {})
                row["queue_status"] = "blocked"
                row["queue_status_label"] = "Blocked"
                row["operator_status_state"] = "review"
                row["recovery_blocked_reason_code"] = _clean_text(blocked.get("reason_code"))
                row["recovery_blocked_reason"] = _clean_text(blocked.get("reason")) or (
                    "This exhausted row did not pass the backend's durable source-CSV and identity checks."
                )
                row["recovery_blocked_reason"] = (
                    "This exhausted row is not eligible for automatic recovery because its durable selector, "
                    "source identity, or enabled source-CSV row no longer qualifies."
                )
            row["available_actions"].append(
                {
                    "action": "retry",
                    "label": (
                        f"Retry Exhausted Rows ({recoverable_retry_exhausted_batch_count})"
                        if retry_exhausted_recoverable
                        else row["available_operator_action"] or "Retry"
                    ),
                    "route": "/api/rerun/continue" if retry_exhausted_recoverable else "",
                    "request": (
                        {"manifest_key": row["manifest_key"], "confirm_continue": True}
                        if retry_exhausted_recoverable
                        else {}
                    ),
                    "requires_confirmation": False,
                    "request_id_required": retry_exhausted_recoverable,
                    "confirmation_field": "confirm_continue" if retry_exhausted_recoverable else "",
                    "confirmation_prompt": (
                        "Retry only backend-qualified exhausted CSV rerun rows? Review rows stay untouched."
                        if retry_exhausted_recoverable
                        else ""
                    ),
                    "availability": (
                        "available"
                        if retry_exhausted_recoverable
                        else "blocked"
                        if retry_exhausted_blocked
                        else "operator_intent"
                    ),
                    "scope": "batch_retry_exhausted" if retry_exhausted_recoverable else "row_intent",
                    "selected_row_count": (
                        recoverable_retry_exhausted_batch_count if retry_exhausted_recoverable else 0
                    ),
                }
            )
        row["lifecycle_evidence"] = {
            "what": row["lifecycle_what"] or lifecycle_state,
            "why": row["reason"] or row["reason_code"] or row["last_error"],
            "when": row["last_transition_at"] or row["created_at"],
            "next": row["automatic_next_action"] or row["available_operator_action"],
            "attempt": {"count": row["attempt_count"], "max": row["max_attempts"], "next_retry_at": row["next_retry_at"]},
            "evidence_links": dict(row["evidence_links"]),
        }
        rows.append(row)
    return rows


def _apply_waiting_restart_actions(
    rows: list[dict[str, Any]],
    posture: Mapping[str, Any],
) -> tuple[int, str]:
    waiting_rows = [
        row
        for row in rows
        if str(row.get("lifecycle_state") or row.get("status") or "").strip().casefold()
        in WAITING_RESTART_STATUSES
    ]
    if not waiting_rows:
        return 0, ""
    manual_available = posture.get("manual_retry_available") is True
    state = str(posture.get("state") or "")
    source_posture = (
        dict(posture.get("source_recovery_posture") or {})
        if isinstance(posture.get("source_recovery_posture"), Mapping)
        else {}
    )
    recoverable_selectors = {
        _recovery_row_selector(row)
        for row in source_posture.get("recoverable_rows") or []
        if isinstance(row, Mapping)
    }
    blocked_by_selector = {
        _recovery_row_selector(row): dict(row)
        for row in source_posture.get("blocked_rows") or []
        if isinstance(row, Mapping)
    }
    recoverable_count = len(recoverable_selectors)
    if manual_available:
        label = f"Retry Waiting Rows ({recoverable_count})"
    elif state == "child_active":
        label = "Automatic Retry Owned by Active Child"
    else:
        label = "Reconcile Before Retry"
    for row in waiting_rows:
        selector = _recovery_row_selector(row)
        row_recoverable = selector in recoverable_selectors
        row["waiting_restart_evidence"] = dict(posture)
        for action in row.get("available_actions") or []:
            if not isinstance(action, dict) or action.get("action") != "retry":
                continue
            action.update(
                {
                    "label": label,
                    "route": "/api/rerun/continue" if manual_available and row_recoverable else "",
                    "request": (
                        {"manifest_key": row["manifest_key"], "confirm_continue": True}
                        if manual_available and row_recoverable
                        else {}
                    ),
                    "availability": "available" if manual_available and row_recoverable else state,
                    "scope": "batch_waiting_restart",
                    "selected_row_count": recoverable_count,
                    "requires_confirmation": False,
                    "request_id_required": manual_available and row_recoverable,
                    "evidence": dict(posture),
                }
            )
        if manual_available and row_recoverable:
            row["available_operator_action"] = label
            evidence = row.get("lifecycle_evidence")
            if isinstance(evidence, dict):
                evidence["next"] = label
        elif state == "source_identity_unqualified" or (manual_available and not row_recoverable):
            blocked = blocked_by_selector.get(selector, {})
            row["queue_status"] = "blocked"
            row["queue_status_label"] = "Blocked"
            row["operator_status_state"] = "review"
            row["recovery_blocked_reason_code"] = _clean_text(blocked.get("reason_code"))
            row["recovery_blocked_reason"] = _clean_text(blocked.get("reason")) or str(
                posture.get("reason") or "Waiting row lacks strong recovery evidence."
            )
    return len(waiting_rows), label


def _remaining_pending_count(data: Mapping[str, Any], row_counts: Mapping[str, int]) -> int:
    value = data.get("remaining_pending_count")
    try:
        parsed = int(cast(Any, value))
    except (TypeError, ValueError):
        parsed = int(row_counts.get("pending", 0) or 0)
    return max(0, parsed)


def _exact_live_rerun_activity(resolved: ResolvedPaths, payload: Mapping[str, Any]) -> bool:
    """Return true only for an exactly correlated, identity-matched live rerun process."""

    _record_path, raw_record = exact_rerun_active_job_payload(resolved, payload)
    if not isinstance(raw_record, Mapping):
        return False
    if _clean_text(raw_record.get("status")).casefold() not in {"launching", "active"}:
        return False
    try:
        record = ActiveJobRecord.from_mapping(raw_record)
    except ContractError:
        return False
    return active_job_pid_matches_record(record, psutil) is True


_TERMINAL_RERUN_BATCH_STATUSES = frozenset(
    {
        "cancelled",
        "complete",
        "completed",
        "completed_with_failed_rows",
        "completed_with_failures",
        "disabled",
        "done",
        "failed",
        "failed_before_manifest",
        "invalid",
        "missing",
        "parked",
        "pending_publish",
        "published_non_overlap",
        "published_replace_final",
        "replaced",
        "retry_exhausted",
        "review",
        "review_workspace",
        "returned",
        "skipped",
        "stopped_after_current",
        "succeeded",
        "success",
        "awaiting_review",
    }
)


def _manifest_has_nonterminal_work(manifest: Mapping[str, Any], *, network: bool = False) -> bool:
    if network and manifest.get("batch_terminal") is True:
        return False
    rows = [row for row in manifest.get("rows") or [] if isinstance(row, Mapping)]
    if rows:
        return any(row.get("is_terminal") is not True for row in rows)
    status = _clean_text(manifest.get("status")).casefold()
    return bool(status) and status not in _TERMINAL_RERUN_BATCH_STATUSES


def _empty_current_rerun(queue_source: str) -> dict[str, Any]:
    return {
        "queue_source": queue_source,
        "manifest_key": "",
        "manifest_path": "",
        "batch_id": "",
        "status": "",
        "selection_reason": "none",
        "activity_state": "none",
        "row_count": 0,
        "remaining_pending_count": 0,
        "queue_status_counts": {},
        "available_actions": [],
        "rows": [],
        "runtime_activity": {"status": "none", "evidence_source": "none"},
        "conflict_count": 0,
    }


def _current_rerun_summary(
    manifests: Sequence[Mapping[str, Any]],
    *,
    queue_source: str,
    network: bool = False,
) -> dict[str, Any]:
    selected: Mapping[str, Any] | None = None
    selection_reason = "none"
    activity_state = "none"
    live_manifests = [manifest for manifest in manifests if manifest.get("runtime_active") is True]
    live_conflict_count = len(live_manifests)
    if not network:
        live_conflict_count = sum(
            max(1, _network_nonnegative_int((manifest.get("runtime_activity") or {}).get("matched_count")))
            for manifest in live_manifests
        )
    if live_conflict_count > 1:
        conflict = _empty_current_rerun(queue_source)
        conflict.update(
            {
                "selection_reason": "ambiguous_live_process",
                "activity_state": "review",
                "status": "ambiguous_live_process",
                "conflict_count": live_conflict_count,
                "runtime_activity": {
                    "status": "ambiguous",
                    "evidence_source": "active_jobs" if not network else "coordinator_inflight",
                    "matched_count": live_conflict_count,
                },
            }
        )
        return conflict
    if live_manifests:
        selected = live_manifests[0]
        selection_reason = "exact_live_network_claim" if network else "exact_live_process"
        activity_state = "active"
    if selected is None:
        for manifest in manifests:
            if manifest.get("available_actions"):
                selected = manifest
                selection_reason = "recovery_actionable"
                activity_state = "recoverable"
                break
    if selected is None:
        for manifest in manifests:
            if _manifest_has_nonterminal_work(manifest, network=network):
                selected = manifest
                selection_reason = "newest_nonterminal"
                activity_state = "review"
                break
    if selected is None:
        return _empty_current_rerun(queue_source)
    runtime_activity = dict(selected.get("runtime_activity") or {})
    if network and activity_state == "review" and runtime_activity.get("status") in {"stale", "unverified"}:
        activity_state = "open_unverified"
    return {
        "queue_source": queue_source,
        "manifest_key": _clean_text(selected.get("manifest_key")),
        "manifest_path": _clean_text(selected.get("manifest_path")),
        "batch_id": _clean_text(selected.get("batch_id")),
        "status": _clean_text(selected.get("status")),
        "selection_reason": selection_reason,
        "activity_state": activity_state,
        "row_count": len(selected.get("rows") or []),
        "remaining_pending_count": _network_nonnegative_int(
            selected.get("remaining_pending_count")
        ),
        "queue_status_counts": dict(selected.get("queue_status_counts") or {}),
        "available_actions": [
            dict(action)
            for action in selected.get("available_actions") or []
            if isinstance(action, Mapping)
        ],
        "rows": [dict(row) for row in selected.get("rows") or [] if isinstance(row, Mapping)],
        "runtime_activity": runtime_activity or {"status": "none", "evidence_source": "none"},
        "conflict_count": 0,
    }


def _manifest_entries(
    resolved: ResolvedPaths,
    *,
    limit: int = 24,
    scan_info: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    root = _manifest_root(resolved)
    paths, manifest_scan = _safe_json_candidates(root, source="local_rerun_manifests")
    live_jobs, active_job_warnings = _direct_live_local_jobs(resolved)
    enrollment_paths, enrollment_scan = _safe_json_candidates(
        rerun_enrollment_root(resolved),
        source="local_rerun_enrollments",
    )
    enrollment_items: list[tuple[Path, dict[str, Any]]] = []
    for enrollment_path in enrollment_paths[: max(limit, 100)]:
        enrollment = read_rerun_enrollment(enrollment_path)
        if enrollment is None:
            _merge_scan_warning(
                manifest_scan,
                _scan_warning(
                    "local_rerun_enrollments",
                    "enrollment_unreadable",
                    enrollment_path,
                    "Rerun enrollment JSON is unreadable.",
                ),
            )
            continue
        enrollment_items.append((enrollment_path, enrollment))
    for warning in enrollment_scan.get("scan_warnings") or []:
        if isinstance(warning, dict):
            _merge_scan_warning(manifest_scan, warning)
    manifest_scan["skipped_candidate_count"] = int(manifest_scan.get("skipped_candidate_count") or 0) + int(
        enrollment_scan.get("skipped_candidate_count") or 0
    )
    manifest_scan["enrollment_discovered_candidate_count"] = int(
        enrollment_scan.get("discovered_candidate_count") or 0
    )
    manifest_scan["discovered_candidate_count"] = len(
        {path.stem.casefold() for path in paths} | {path.stem.casefold() for path in enrollment_paths}
    )
    known_enrollment_paths = {_path_key(path) for path, _data in enrollment_items}
    for live_job in live_jobs:
        enrollment_path = Path(live_job["enrollment_path"])
        if _path_key(enrollment_path) in known_enrollment_paths or not enrollment_path.is_file():
            continue
        enrollment = read_rerun_enrollment(enrollment_path)
        if enrollment is not None:
            enrollment_items.append((enrollment_path, enrollment))
            known_enrollment_paths.add(_path_key(enrollment_path))
    enrollment_by_batch = {
        str(data.get("batch_id") or path.stem): (path, data)
        for path, data in enrollment_items
    }
    enrollment_by_manifest_path = {
        _path_key(
            Path(
                str(
                    data.get("manifest_path")
                    or rerun_execution_manifest_root(resolved)
                    / f"{str(data.get('batch_id') or path.stem)}.json"
                )
            )
        ): (path, data)
        for path, data in enrollment_items
    }
    preferred_paths = [Path(item["manifest_path"]) for item in live_jobs]
    processing_paths = list(paths[: max(limit, 100)])
    processing_path_keys = {_path_key(path) for path in processing_paths}
    scannable_path_by_key = {_path_key(path): path for path in paths}
    for preferred_path in preferred_paths:
        preferred_key = _path_key(preferred_path)
        if preferred_key in processing_path_keys or preferred_key not in scannable_path_by_key:
            continue
        processing_paths.append(scannable_path_by_key[preferred_key])
        processing_path_keys.add(preferred_key)
    for warning in active_job_warnings:
        _merge_scan_warning(manifest_scan, warning)
    direct_live_count_by_manifest = Counter(_path_key(Path(item["manifest_path"])) for item in live_jobs)
    manifests: list[dict[str, Any]] = []
    represented_batches: set[str] = set()
    for path in processing_paths:
        data = _read_json(path)
        if not isinstance(data, dict):
            continue
        manifest_batch_id = str(data.get("batch_id") or path.stem)
        matched_enrollment_path, enrollment = enrollment_by_batch.get(
            manifest_batch_id,
            enrollment_by_manifest_path.get(_path_key(path), (None, {})),
        )
        batch_id = str(enrollment.get("batch_id") or manifest_batch_id)
        represented_batches.add(batch_id)
        manifest_correlation_degraded = (
            not rerun_manifest_declared_path_matches_actual(data, path)
            or not rerun_manifest_path_matches_canonical_batch(resolved, data, path)
            or bool(enrollment)
            and not rerun_manifest_matches_enrollment(
                data,
                enrollment,
                enrollment_path=matched_enrollment_path,
                manifest_path=path,
            )
        )
        enrollment_state = str(enrollment.get("lifecycle_state") or enrollment.get("status") or "").casefold()
        terminal_enrollment_overrides_skeleton = not manifest_correlation_degraded and bool(enrollment) and enrollment_state in {
            "failed",
            "failed_before_manifest",
            "retry_exhausted",
            "cancelled",
        } and not rerun_execution_manifest_has_durable_exit_state(data)
        if manifest_correlation_degraded:
            effective_data = dict(enrollment)
        else:
            effective_data = (
                {**data, **dict(enrollment)}
                if terminal_enrollment_overrides_skeleton
                else {**dict(enrollment), **data}
            )
        trusted_execution_data = {} if manifest_correlation_degraded else data
        if matched_enrollment_path is not None:
            effective_data["enrollment_path"] = str(matched_enrollment_path)
        try:
            sort_mtime = path.stat().st_mtime
        except OSError:
            sort_mtime = 0.0
        if matched_enrollment_path is not None:
            try:
                sort_mtime = max(sort_mtime, matched_enrollment_path.stat().st_mtime)
            except OSError:
                pass
        effective_status = str(effective_data.get("status") or "").strip().casefold()
        retry_posture = (
            rerun_retry_exhausted_recovery_posture(resolved, effective_data)
            if not manifest_correlation_degraded and effective_status in COMPLETED_WITH_FAILURES_STATUSES
            else {}
        )
        pending_posture = (
            rerun_pending_recovery_posture(resolved, effective_data)
            if not manifest_correlation_degraded and effective_status == "stopped_after_current"
            else {}
        )
        rows = rerun_manifest_queue_rows(
            resolved,
            path,
            effective_data,
            retry_posture=retry_posture,
            pending_posture=pending_posture,
            recovery_actions_allowed=not manifest_correlation_degraded,
        )
        waiting_restart_evidence = (
            rerun_waiting_restart_posture(resolved, effective_data)
            if not manifest_correlation_degraded and effective_status in WAITING_RESTART_STATUSES
            else {}
        )
        waiting_restart_count, waiting_restart_action_label = _apply_waiting_restart_actions(
            rows,
            waiting_restart_evidence,
        )
        row_counts = _row_status_counts(rows)
        queue_status_counts = _row_queue_status_counts(rows)
        destination_summary = _destination_summary(rows)
        remaining_pending_count = _remaining_pending_count(effective_data, row_counts)
        recoverable_pending_count = int(pending_posture.get("recoverable_count") or 0)
        unrecoverable_pending_count = int(pending_posture.get("unrecoverable_count") or 0)
        status = str(effective_data.get("status") or "")
        retry_exhausted_count = sum(
            1 for row in rows if str(row.get("lifecycle_state") or "").casefold() == "retry_exhausted"
        )
        recoverable_retry_exhausted_count = int(retry_posture.get("recoverable_count") or 0)
        unrecoverable_retry_exhausted_count = int(retry_posture.get("unrecoverable_count") or 0)
        manifest_key = _hash_text(str(path))
        can_continue_pending = (
            not manifest_correlation_degraded
            and status.casefold() == "stopped_after_current"
            and remaining_pending_count > 0
            and recoverable_pending_count > 0
        )
        can_retry_exhausted = (
            not manifest_correlation_degraded
            and status.casefold() in COMPLETED_WITH_FAILURES_STATUSES
            and recoverable_retry_exhausted_count > 0
        )
        available_actions: list[dict[str, Any]] = []
        if can_continue_pending:
            available_actions.append(
                {
                    "action": "continue_pending",
                    "label": "Continue Pending Rows",
                    "route": "/api/rerun/continue",
                    "request": {"manifest_key": manifest_key, "confirm_continue": True},
                    "confirmation_field": "confirm_continue",
                    "confirmation_prompt": "Continue pending CSV rerun rows only? Failed and review rows stay untouched.",
                    "requires_confirmation": False,
                    "request_id_required": True,
                    "scope": "batch_pending_only",
                    "backend_owned": True,
                    "selected_row_count": recoverable_pending_count,
                }
            )
        if can_retry_exhausted:
            available_actions.append(
                {
                    "action": "retry",
                    "label": f"Retry Exhausted Rows ({recoverable_retry_exhausted_count})",
                    "route": "/api/rerun/continue",
                    "request": {"manifest_key": manifest_key, "confirm_continue": True},
                    "confirmation_field": "confirm_continue",
                    "confirmation_prompt": "Retry only backend-qualified exhausted CSV rerun rows? Review rows stay untouched.",
                    "requires_confirmation": False,
                    "request_id_required": True,
                    "scope": "batch_retry_exhausted",
                    "backend_owned": True,
                }
            )
        correlation = rerun_correlation_evidence(
            resolved,
            effective_data,
            enrollment_path=matched_enrollment_path,
            manifest_path=path,
        )
        direct_live_count = direct_live_count_by_manifest[_path_key(path)]
        runtime_active = direct_live_count > 0
        manifests.append(
            {
                "manifest_key": manifest_key,
                "manifest_path": str(path),
                "batch_id": batch_id,
                "command_id": str(effective_data.get("command_id") or ""),
                "launch_id": str(effective_data.get("launch_id") or ""),
                "enrollment_path": str(matched_enrollment_path or ""),
                **correlation,
                "manifest_available": not manifest_correlation_degraded,
                "execution_manifest_available": True,
                "evidence_authority": (
                    "backend_enrollment_manifest_correlation_degraded"
                    if manifest_correlation_degraded
                    else "backend_enrollment_terminal_over_incomplete_execution_manifest"
                    if terminal_enrollment_overrides_skeleton
                    else "execution_manifest"
                ),
                "manifest_correlation_status": (
                    "degraded" if manifest_correlation_degraded else "matched"
                ),
                "runtime_active": runtime_active,
                "runtime_activity": {
                    "status": "active" if runtime_active else "none",
                    "evidence_source": "active_jobs",
                    "matched_count": direct_live_count,
                },
                "manifest_correlation_warnings": (
                    [
                        "Execution manifest correlation or its declared v2 path did not match durable evidence; "
                        "execution data is not authoritative and recovery actions are withheld."
                    ]
                    if manifest_correlation_degraded
                    else []
                ),
                "execution_manifest_status": str(data.get("status") or ""),
                "status": status,
                "created_at": str(effective_data.get("created_at") or ""),
                "started_at": str(effective_data.get("started_at") or ""),
                "completed_at": str(effective_data.get("completed_at") or ""),
                "stopped_at": str(effective_data.get("stopped_at") or ""),
                "current_chunk": effective_data.get("current_chunk"),
                "current_phase": str(
                    effective_data.get("current_phase")
                    or effective_data.get("phase")
                    or effective_data.get("status")
                    or enrollment.get("current_phase")
                    or ""
                ),
                "current_row_index": effective_data.get("current_row_index"),
                "last_transition_at": str(effective_data.get("last_transition_at") or ""),
                "execution_mode": str(trusted_execution_data.get("execution_mode") or ""),
                "destination_mode": str(trusted_execution_data.get("destination_mode") or ""),
                "original_policy": str(trusted_execution_data.get("original_policy") or ""),
                "collision_policy": str(trusted_execution_data.get("collision_policy") or ""),
                "window_size": trusted_execution_data.get("window_size"),
                "output_root": str(trusted_execution_data.get("output_root") or ""),
                "pending_publish_root": str(trusted_execution_data.get("pending_publish_root") or ""),
                "completed_jobs_manifest": str(trusted_execution_data.get("completed_jobs_manifest") or ""),
                "row_status_counts": row_counts,
                "queue_status_counts": queue_status_counts,
                "destination_summary": destination_summary,
                "remaining_pending_count": remaining_pending_count,
                "recoverable_pending_count": recoverable_pending_count,
                "unrecoverable_pending_count": unrecoverable_pending_count,
                "pending_recovery_posture": pending_posture,
                "can_continue_pending": can_continue_pending,
                "can_retry_exhausted": can_retry_exhausted,
                "available_actions": available_actions,
                "retry_exhausted_count": retry_exhausted_count,
                "recoverable_retry_exhausted_count": recoverable_retry_exhausted_count,
                "unrecoverable_retry_exhausted_count": unrecoverable_retry_exhausted_count,
                "retry_exhausted_action_label": (
                    f"Retry Exhausted Rows ({recoverable_retry_exhausted_count})"
                    if recoverable_retry_exhausted_count
                    else ""
                ),
                "waiting_restart_evidence": waiting_restart_evidence,
                "waiting_restart_count": waiting_restart_count,
                "can_retry_waiting_after_restart": (
                    waiting_restart_count > 0
                    and waiting_restart_evidence.get("manual_retry_available") is True
                ),
                "waiting_restart_action_label": waiting_restart_action_label,
                "stop_request_id": str(trusted_execution_data.get("stop_request_id") or ""),
                "stop_requested_at": str(trusted_execution_data.get("stop_requested_at") or ""),
                "stop_request_marker_path": str(trusted_execution_data.get("stop_request_marker_path") or ""),
                "safe_next_action": str(trusted_execution_data.get("safe_next_action") or ""),
                "rows": rows,
                "row_count": len(rows),
                "lifecycle_counts": rerun_lifecycle_counts(rows),
                "_sort_mtime": sort_mtime,
            }
        )
    for enrollment_path, enrollment in enrollment_items:
        batch_id = str(enrollment.get("batch_id") or enrollment_path.stem)
        if batch_id in represented_batches:
            continue
        expected_manifest = Path(str(enrollment.get("manifest_path") or (rerun_execution_manifest_root(resolved) / f"{batch_id}.json")))
        enrollment_data = {**enrollment, "enrollment_path": str(enrollment_path)}
        rows = rerun_manifest_queue_rows(resolved, expected_manifest, enrollment_data)
        row_counts = _row_status_counts(rows)
        queue_status_counts = _row_queue_status_counts(rows)
        status = str(enrollment.get("status") or "accepted")
        try:
            enrollment_mtime = enrollment_path.stat().st_mtime
        except OSError:
            enrollment_mtime = 0.0
        correlation = rerun_correlation_evidence(
            resolved,
            enrollment_data,
            enrollment_path=enrollment_path,
            manifest_path=expected_manifest,
        )
        direct_live_count = direct_live_count_by_manifest[_path_key(expected_manifest)]
        runtime_active = direct_live_count > 0
        manifests.append(
            {
                "manifest_key": _hash_text(str(expected_manifest)),
                "manifest_path": str(expected_manifest),
                "batch_id": batch_id,
                "command_id": str(enrollment.get("command_id") or ""),
                "launch_id": str(enrollment.get("launch_id") or ""),
                "enrollment_path": str(enrollment_path),
                **correlation,
                "manifest_available": False,
                "evidence_authority": "backend_enrollment",
                "runtime_active": runtime_active,
                "runtime_activity": {
                    "status": "active" if runtime_active else "none",
                    "evidence_source": "active_jobs",
                    "matched_count": direct_live_count,
                },
                "status": status,
                "created_at": str(enrollment.get("created_at") or ""),
                "started_at": str(enrollment.get("started_at") or ""),
                "completed_at": str(enrollment.get("completed_at") or ""),
                "stopped_at": str(enrollment.get("stopped_at") or ""),
                "current_chunk": enrollment.get("current_chunk"),
                "current_phase": str(enrollment.get("current_phase") or ""),
                "current_row_index": enrollment.get("current_row_index"),
                "last_transition_at": str(enrollment.get("last_transition_at") or ""),
                "execution_mode": str(enrollment.get("execution_mode") or ""),
                "destination_mode": str(enrollment.get("destination_mode") or ""),
                "original_policy": str(enrollment.get("original_policy") or ""),
                "collision_policy": str(enrollment.get("collision_policy") or ""),
                "window_size": enrollment.get("window_size"),
                "output_root": str(enrollment.get("output_root") or ""),
                "pending_publish_root": str(enrollment.get("pending_publish_root") or ""),
                "completed_jobs_manifest": str(enrollment.get("completed_jobs_manifest") or ""),
                "row_status_counts": row_counts,
                "queue_status_counts": queue_status_counts,
                "destination_summary": _destination_summary(rows),
                "remaining_pending_count": _remaining_pending_count(enrollment, row_counts),
                "recoverable_pending_count": 0,
                "unrecoverable_pending_count": 0,
                "pending_recovery_posture": {},
                "can_continue_pending": False,
                "can_retry_exhausted": False,
                "retry_exhausted_count": 0,
                "recoverable_retry_exhausted_count": 0,
                "unrecoverable_retry_exhausted_count": 0,
                "retry_exhausted_action_label": "",
                "waiting_restart_evidence": {},
                "waiting_restart_count": 0,
                "can_retry_waiting_after_restart": False,
                "waiting_restart_action_label": "",
                "stop_request_id": "",
                "stop_requested_at": "",
                "stop_request_marker_path": "",
                "safe_next_action": str(enrollment.get("automatic_next_action") or "Wait for execution manifest evidence."),
                "rows": rows,
                "row_count": len(rows),
                "lifecycle_counts": rerun_lifecycle_counts(rows),
                "_sort_mtime": enrollment_mtime,
            }
        )
    for live_job in live_jobs:
        batch_id = str(live_job.get("batch_id") or "")
        if not batch_id or batch_id in represented_batches:
            continue
        manifest_path = Path(live_job["manifest_path"])
        enrollment_path = Path(live_job["enrollment_path"])
        record = dict(live_job.get("record") or {})
        manifests.append(
            {
                "manifest_key": _hash_text(str(manifest_path)),
                "manifest_path": str(manifest_path),
                "batch_id": batch_id,
                "command_id": str(live_job.get("command_id") or ""),
                "launch_id": str(live_job.get("launch_id") or ""),
                "enrollment_path": str(enrollment_path),
                "manifest_available": False,
                "execution_manifest_available": False,
                "evidence_authority": "exact_live_active_job",
                "manifest_correlation_status": "active_job_only",
                "runtime_active": True,
                "runtime_activity": {
                    "status": "active",
                    "evidence_source": "active_jobs",
                    "matched_count": direct_live_count_by_manifest[_path_key(manifest_path)],
                },
                "status": str(record.get("status") or "active"),
                "created_at": str(record.get("launched_at") or ""),
                "started_at": str(record.get("launched_at") or ""),
                "completed_at": "",
                "stopped_at": "",
                "row_status_counts": {},
                "queue_status_counts": {},
                "remaining_pending_count": 0,
                "available_actions": [],
                "safe_next_action": "Wait for the correlated rerun manifest or enrollment evidence.",
                "rows": [],
                "row_count": 0,
                "lifecycle_counts": {},
                "_history_eligible": False,
                "_sort_mtime": float("inf"),
            }
        )
        represented_batches.add(batch_id)
    manifests.sort(key=lambda item: float(item.get("_sort_mtime") or 0.0), reverse=True)
    history_selected = [
        manifest for manifest in manifests if manifest.get("_history_eligible") is not False
    ][:limit]
    selected_manifest_paths = {
        _path_key(Path(str(manifest.get("manifest_path") or ""))) for manifest in history_selected
    }
    current_only = [
        manifest
        for manifest in manifests
        if manifest.get("runtime_active") is True
        and _path_key(Path(str(manifest.get("manifest_path") or ""))) not in selected_manifest_paths
    ]
    selected = history_selected + current_only
    for manifest in selected:
        manifest.pop("_sort_mtime", None)
        manifest.pop("_history_eligible", None)
    if scan_info is not None:
        scan_info.clear()
        scan_info.update(manifest_scan)
        scan_info["loaded_candidate_count"] = len(history_selected)
        scan_info["current_only_count"] = len(current_only)
    return selected


def _network_claim_key(job_id: object, worker_id: object, source_path: object) -> tuple[str, str, str]:
    source = _clean_text(source_path)
    return (
        _clean_text(job_id),
        _clean_text(worker_id),
        os.path.normcase(os.path.normpath(source)) if source else "",
    )


def _network_claim_registry_evidence(resolved: ResolvedPaths, service: Any | None) -> dict[str, Any]:
    timeout_seconds = _heartbeat_timeout_seconds(resolved) or 300
    state_dir = _runtime_state_dir(resolved, service or object())
    path = state_dir / "coordinator_inflight.json"
    evidence: dict[str, Any] = {
        "path": str(path),
        "status": "missing",
        "heartbeat_timeout_seconds": timeout_seconds,
        "claims": {},
        "warning": "",
    }
    if not path.is_file():
        return evidence
    registry = InFlightRegistry()
    try:
        loaded = registry.load(path)
    except Exception as exc:
        evidence.update(status="unavailable", warning=f"Coordinator in-flight evidence could not be read: {exc}")
        return evidence
    if not loaded:
        evidence.update(status="unavailable", warning="Coordinator in-flight evidence could not be read.")
        return evidence
    claims: dict[tuple[str, str, str], dict[str, Any]] = {}
    for claim in registry.active_claims_snapshot():
        key = _network_claim_key(claim.get("job_id"), claim.get("worker_id"), claim.get("source_path"))
        if not all(key):
            continue
        claims[key] = dict(claim)
    evidence.update(status="loaded", claims=claims)
    return evidence


def _network_manifest_runtime_activity(
    data: Mapping[str, Any],
    rows: list[dict[str, Any]],
    registry_evidence: Mapping[str, Any],
) -> dict[str, Any]:
    timeout_seconds = _network_nonnegative_int(registry_evidence.get("heartbeat_timeout_seconds")) or 300
    claims = dict(registry_evidence.get("claims") or {})
    matched_count = 0
    stale_count = 0
    unverified_count = 0
    claimed_row_count = 0
    for row in rows:
        active_claim = row.get("active_claim")
        if not isinstance(active_claim, Mapping):
            continue
        claimed_row_count += 1
        key = _network_claim_key(
            active_claim.get("job_id"),
            active_claim.get("worker_id"),
            row.get("source_path"),
        )
        claim = claims.get(key)
        if not isinstance(claim, Mapping):
            unverified_count += 1
            continue
        age = claim.get("heartbeat_age_seconds")
        if isinstance(age, int) and 0 <= age <= timeout_seconds:
            matched_count += 1
        elif isinstance(age, int) and age > timeout_seconds:
            stale_count += 1
        else:
            unverified_count += 1
    batch_open = data.get("batch_terminal") is not True and (
        _clean_text(data.get("status")).casefold() in NETWORK_RERUN_OPEN_STATUSES
        or any(row.get("is_terminal") is not True for row in rows)
    )
    if matched_count:
        status = "active"
    elif stale_count:
        status = "stale"
    elif batch_open:
        status = "unverified"
    else:
        status = "none"
    return {
        "status": status,
        "evidence_source": "coordinator_inflight",
        "evidence_path": _clean_text(registry_evidence.get("path")),
        "registry_status": _clean_text(registry_evidence.get("status")),
        "heartbeat_timeout_seconds": timeout_seconds,
        "claimed_row_count": claimed_row_count,
        "matched_claim_count": matched_count,
        "stale_claim_count": stale_count,
        "unverified_claim_count": unverified_count,
    }


def _network_manifest_entries(
    resolved: ResolvedPaths,
    *,
    service: Any | None = None,
    limit: int = 24,
    scan_info: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    root = _network_manifest_root(resolved)
    paths, manifest_scan = _safe_json_candidates(root, source="network_rerun_manifests")
    registry_evidence = _network_claim_registry_evidence(resolved, service)
    if registry_evidence.get("warning"):
        _merge_scan_warning(
            manifest_scan,
            _scan_warning(
                "coordinator_inflight",
                "network_claim_registry_unavailable",
                Path(str(registry_evidence.get("path") or "")),
                registry_evidence.get("warning"),
            ),
        )
    manifests: list[dict[str, Any]] = []
    for path in paths[:limit]:
        data = _read_json(path)
        if not isinstance(data, dict):
            _merge_scan_warning(
                manifest_scan,
                _scan_warning("network_rerun_manifests", "manifest_unreadable", path, "Network rerun manifest is unreadable."),
            )
            continue
        if str(data.get("schema_version") or "") != "desktop_rerun_network_batch.v1":
            _merge_scan_warning(
                manifest_scan,
                _scan_warning("network_rerun_manifests", "manifest_schema_invalid", path, "Unexpected Network rerun schema."),
            )
            continue
        rows = _network_batch_queue_rows(path, data)
        runtime_activity = _network_manifest_runtime_activity(data, rows, registry_evidence)
        batch_id = str(data.get("batch_id") or path.stem)
        lifecycle_counts = _network_lifecycle_counts(rows)
        available_actions = [
            dict(action)
            for row in rows
            for action in row.get("available_actions") or []
            if isinstance(action, Mapping) and _clean_text(action.get("route"))
        ]
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
                "terminal_at": str(data.get("terminal_at_utc") or ""),
                "completed_at": str(data.get("completed_at_utc") or ""),
                "failed_at": str(data.get("failed_at_utc") or ""),
                "review_required_at": str(data.get("review_required_at_utc") or ""),
                "batch_terminal": data.get("batch_terminal") is True,
                "runtime_active": runtime_activity["status"] == "active",
                "runtime_activity": runtime_activity,
                "queue_source": "network_csv_rerun",
                "uses_pipeline_start": False,
                "claim_provider_enabled": data.get("claim_provider_enabled") is True,
                "worker_execution_enabled": data.get("worker_execution_enabled") is True,
                "rows_claimable": data.get("rows_claimable") is True,
                "row_status_counts": _row_status_counts(rows),
                "queue_status_counts": _row_queue_status_counts(rows),
                "lifecycle_counts": lifecycle_counts,
                "terminal_row_count": _network_nonnegative_int(data.get("terminal_row_count")),
                "active_row_count": _network_nonnegative_int(data.get("active_row_count")),
                "retry_scheduled_row_count": _network_nonnegative_int(data.get("retry_scheduled_row_count")),
                "retry_exhausted_row_count": _network_nonnegative_int(data.get("retry_exhausted_row_count")),
                "review_row_count": _network_nonnegative_int(data.get("review_row_count")),
                "manual_recovery_row_count": _network_nonnegative_int(data.get("manual_recovery_row_count")),
                "remaining_pending_count": sum(
                    1 for row in rows if row.get("is_terminal") is not True
                ),
                "available_actions": available_actions,
                "row_count": len(rows),
                "rows": rows,
            }
        )
    if scan_info is not None:
        scan_info.clear()
        scan_info.update(manifest_scan)
        scan_info["loaded_candidate_count"] = len(manifests)
    return manifests


def rerun_results_payload(resolved: ResolvedPaths, *, service: Any | None = None, limit: int = 24) -> dict[str, Any]:
    candidate_limit = max(limit, 100)
    local_scan: dict[str, Any] = {}
    network_scan: dict[str, Any] = {}
    local_candidates = _manifest_entries(resolved, limit=candidate_limit, scan_info=local_scan)
    network_candidates = _network_manifest_entries(
        resolved,
        service=service,
        limit=candidate_limit,
        scan_info=network_scan,
    )
    manifests = local_candidates[:limit]
    network_manifests = network_candidates[:limit]
    current_local = _current_rerun_summary(
        local_candidates,
        queue_source="csv_rerun",
    )
    current_network = _current_rerun_summary(
        network_candidates,
        queue_source="network_csv_rerun",
        network=True,
    )
    csvs = recent_rerun_csv_candidates(resolved, service, limit=limit)
    for item in csvs:
        item["csv_key"] = _hash_text(str(item.get("path") or ""))
    local_row_count = sum(len(item.get("rows") or []) for item in manifests)
    network_row_count = sum(len(item.get("rows") or []) for item in network_manifests)
    row_count = local_row_count + network_row_count
    rows = [row for manifest in manifests for row in manifest.get("rows", [])]
    rows.extend(row for manifest in network_manifests for row in manifest.get("rows", []))
    queue_status_counts = _row_queue_status_counts(rows)
    local_lifecycle_counts = rerun_lifecycle_counts(
        [row for manifest in manifests for row in manifest.get("rows", []) if isinstance(row, Mapping)]
    )
    network_rows = cast(
        list[dict[str, Any]],
        [
            row
            for manifest in network_manifests
            for row in manifest.get("rows", [])
            if isinstance(row, Mapping)
        ],
    )
    network_queue_status_counts = _row_queue_status_counts(network_rows)
    network_lifecycle_counts = _network_lifecycle_counts(network_rows)
    scan_warnings = [
        dict(warning)
        for warning in [
            *(local_scan.get("scan_warnings") or []),
            *(network_scan.get("scan_warnings") or []),
        ][:RERUN_SCAN_WARNING_LIMIT]
        if isinstance(warning, Mapping)
    ]
    history_window = {
        "requested_limit": limit,
        "local": {
            "loaded_count": len(manifests),
            "discovered_candidate_count": int(local_scan.get("discovered_candidate_count") or 0),
            "scannable_candidate_count": int(local_scan.get("scannable_candidate_count") or 0),
            "skipped_candidate_count": int(local_scan.get("skipped_candidate_count") or 0),
            "truncated": int(local_scan.get("discovered_candidate_count") or 0) > len(manifests),
        },
        "network": {
            "loaded_count": len(network_manifests),
            "discovered_candidate_count": int(network_scan.get("discovered_candidate_count") or 0),
            "scannable_candidate_count": int(network_scan.get("scannable_candidate_count") or 0),
            "skipped_candidate_count": int(network_scan.get("skipped_candidate_count") or 0),
            "truncated": int(network_scan.get("discovered_candidate_count") or 0) > len(network_manifests),
        },
        "scan_warning_count": int(local_scan.get("warning_count") or 0)
        + int(network_scan.get("warning_count") or 0),
        "scan_warnings": scan_warnings,
    }
    return {
        "schema_version": RERUN_RESULTS_SCHEMA_VERSION,
        "manifest_root": str(_manifest_root(resolved) or ""),
        "network_manifest_root": str(_network_manifest_root(resolved) or ""),
        "history_window": history_window,
        "manifests": manifests,
        "network_manifests": network_manifests,
        "startup_reconciliation": read_rerun_startup_reconciliation(resolved),
        "rows": rows,
        "queue_state": {
            "schema_version": RERUN_QUEUE_STATE_SCHEMA_VERSION,
            "row_schema_version": RERUN_QUEUE_STATE_ROW_SCHEMA_VERSION,
            "queue_source": "csv_rerun",
            "contains_network_csv_rerun": bool(network_manifests),
            "uses_pipeline_start": False,
            "current_local": current_local,
            "current_network": current_network,
            "rows": rows,
            "row_count": row_count,
            "status_counts": queue_status_counts,
            "queue_status_counts": queue_status_counts,
            "lifecycle_counts": local_lifecycle_counts,
            "network_status_counts": network_queue_status_counts,
            "network_lifecycle_counts": network_lifecycle_counts,
            "available_statuses": [
                {"key": "pending", "label": "Pending"},
                {"key": "active", "label": "Active"},
                {"key": "waiting", "label": "Waiting"},
                {"key": "retrying", "label": "Retrying"},
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
            "lifecycle_counts": local_lifecycle_counts,
            "network_queue_status_counts": network_queue_status_counts,
            "network_lifecycle_counts": network_lifecycle_counts,
            "network_retry_scheduled_count": network_lifecycle_counts["retry_scheduled"],
            "network_retry_exhausted_count": network_lifecycle_counts["retry_exhausted"],
            "network_review_required_count": network_lifecycle_counts["review_required"],
            "network_terminal_count": network_lifecycle_counts["terminal"],
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
