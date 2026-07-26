"""Read-only Network CSV rerun row projection helpers."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from copy import deepcopy
from pathlib import Path
from typing import Any, cast

from mediapipeline.core.processes.rerun_results_support import (
    RERUN_QUEUE_STATE_ROW_SCHEMA_VERSION,
    _clean_text,
    _first_text,
    _hash_text,
    _queue_status_for_row,
    _string_list,
)
from mediapipeline.core.processes.source_probe import run_source_probe


def _network_row_key(batch_id: str, row_key: str, state_path: Path) -> str:
    raw = str(row_key or "").strip()
    if raw:
        return f"network:{batch_id}:{raw}"
    return f"network:{batch_id}:{_hash_text(str(state_path))}"


def _network_reducer_result(row: Mapping[str, Any]) -> dict[str, Any]:
    raw = row.get("reducer_result")
    return deepcopy(cast(dict[str, Any], raw)) if isinstance(raw, Mapping) else {}


def _network_worker_result(row: Mapping[str, Any]) -> dict[str, Any]:
    raw = row.get("worker_result")
    return deepcopy(cast(dict[str, Any], raw)) if isinstance(raw, Mapping) else {}


def _network_verified_output(
    row: Mapping[str, Any],
    worker_result: Mapping[str, Any],
    reducer_result: Mapping[str, Any],
) -> str:
    text = _first_text(row, "verified_output_path", "review_output_path")
    if text:
        return text
    output = reducer_result.get("output_artifact") if isinstance(reducer_result, Mapping) else None
    if isinstance(output, Mapping):
        text = _clean_text(output.get("path"))
        if text:
            return text
    return _clean_text(worker_result.get("output_path"))


def _network_output_probe(path_text: str) -> dict[str, Any]:
    path_raw = _clean_text(path_text)
    evidence: dict[str, Any] = {
        "path": path_raw,
        "status": "not_supplied",
        "exists": False,
        "is_file": False,
        "stale": False,
        "error": "",
    }
    if not path_raw:
        return evidence
    try:
        probe = run_source_probe("stat", Path(path_raw), timeout_seconds=2.0)
    except FileNotFoundError:
        evidence["status"] = "missing"
    except (TimeoutError, PermissionError, OSError) as exc:
        evidence.update({"status": "access_failed", "stale": True, "error": str(exc)})
    else:
        is_file = probe.get("kind") == "file"
        evidence.update(
            {
                "status": "ok" if is_file else "not_file",
                "exists": is_file,
                "is_file": is_file,
                "size_bytes": _network_nonnegative_int(probe.get("size")),
            }
        )
    return evidence


def _network_lifecycle_counts(rows: Sequence[Mapping[str, Any]]) -> dict[str, int]:
    counts = {
        "total": len(rows),
        "executable": 0,
        "blocked": 0,
        "waiting": 0,
        "retrying": 0,
        "staged": 0,
        "active": 0,
        "completed": 0,
        "failed": 0,
        "review": 0,
        "pending_publish": 0,
        "pending": 0,
        "retry_scheduled": 0,
        "retry_exhausted": 0,
        "review_required": 0,
        "skipped": 0,
        "terminal": 0,
    }
    for row in rows:
        status = _clean_text(row.get("status")).casefold()
        if row.get("is_terminal") is True:
            counts["terminal"] += 1
        if status in {"pending_claim", "retryable"}:
            counts["executable"] += 1
            counts["pending"] += 1
        elif status in {"blocked", "invalid", "source_missing", "source_identity_changed"}:
            counts["blocked"] += 1
        elif status == "retry_scheduled":
            counts["waiting"] += 1
            counts["retrying"] += 1
            counts["retry_scheduled"] += 1
        elif status == "staged":
            counts["staged"] += 1
        elif status in {"claimed", "destination_policy_applying", "running", "active", "worker_completed_pending_reduction"}:
            counts["active"] += 1
        elif status in {
            "complete",
            "completed",
            "done",
            "success",
            "succeeded",
            "destination_policy_applied",
            "published_non_overlap",
            "published_replace_final",
        }:
            counts["completed"] += 1
        elif status in {"skipped", "disabled"}:
            counts["skipped"] += 1
        elif status == "retry_exhausted":
            counts["failed"] += 1
            counts["retry_exhausted"] += 1
        elif status in {"failed", "destination_policy_failed", "worker_failed_pending_reduction"}:
            counts["failed"] += 1
        elif status in {"review_required", "review_workspace", "worker_review_pending_reduction"}:
            counts["review"] += 1
            counts["review_required"] += 1
        elif status in {"pending_publish", "parked"}:
            counts["pending_publish"] += 1
    return counts


def _network_nonnegative_int(value: Any) -> int:
    try:
        return max(0, int(value or 0))
    except (TypeError, ValueError):
        return 0


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
            row_index = int(cast(Any, raw_row.get("row_index")))
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
        output_probe = _network_output_probe(verified_output)
        output_artifact = reducer_result.get("output_artifact") if isinstance(reducer_result, Mapping) else {}
        destination_policy = raw_row.get("destination_policy")
        pending_manifest_path = _clean_text(raw_row.get("pending_publish_manifest_path")) or _clean_text(
            destination_result.get("pending_publish_manifest_path")
        )
        pending_payload_path = _clean_text(raw_row.get("pending_publish_payload_path")) or _clean_text(
            destination_result.get("pending_publish_payload_path")
        )
        published_path = _clean_text(raw_row.get("published_path")) or _clean_text(destination_result.get("published_path"))
        attempt_count = _network_nonnegative_int(raw_row.get("attempt_count"))
        retry_count = _network_nonnegative_int(raw_row.get("retry_count"))
        retry_limit = _network_nonnegative_int(raw_row.get("retry_limit"))
        reason_code = _clean_text(raw_row.get("reason_code") or reducer_result.get("reason_code"))
        what = _clean_text(raw_row.get("what") or reducer_result.get("what"))
        why = _clean_text(
            raw_row.get("why") or raw_row.get("last_error") or reducer_result.get("why") or reducer_result.get("reason")
        )
        when = _clean_text(raw_row.get("when") or reducer_result.get("when") or reducer_result.get("reduced_at_utc"))
        next_action = _clean_text(
            raw_row.get("next_action") or raw_row.get("automatic_next_action") or reducer_result.get("next_action")
        )
        operator_action = _clean_text(
            raw_row.get("operator_action")
            or raw_row.get("available_operator_action")
            or reducer_result.get("operator_action")
        )
        timeline = [deepcopy(item) for item in raw_row.get("timeline") or [] if isinstance(item, Mapping)]
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
            "attempt_count": attempt_count,
            "retry_count": retry_count,
            "retry_limit": retry_limit,
            "retry_after_seconds": _network_nonnegative_int(raw_row.get("retry_after_seconds")),
            "next_retry_at": _clean_text(raw_row.get("next_retry_at_utc") or raw_row.get("next_retry_at")),
            "next_retry_at_utc": _clean_text(raw_row.get("next_retry_at_utc") or raw_row.get("next_retry_at")),
            "manual_recovery_required": raw_row.get("manual_recovery_required") is True,
            "manual_recovery_available": raw_row.get("manual_recovery_available") is True,
            "operator_action_required": raw_row.get("operator_action_required") is True,
            "reason_code": reason_code,
            "last_error": _clean_text(raw_row.get("last_error") or reducer_result.get("reason")),
            "what": what,
            "why": why,
            "when": when,
            "next_action": next_action,
            "automatic_next_action": _clean_text(raw_row.get("automatic_next_action")),
            "operator_action": operator_action,
            "available_operator_action": _clean_text(raw_row.get("available_operator_action") or operator_action),
            "first_failure": deepcopy(raw_row.get("first_failure")) if isinstance(raw_row.get("first_failure"), Mapping) else {},
            "last_failure": deepcopy(raw_row.get("last_failure")) if isinstance(raw_row.get("last_failure"), Mapping) else {},
            "timeline": timeline,
            "retry_history": [deepcopy(item) for item in raw_row.get("retry_history") or [] if isinstance(item, Mapping)],
            "attempt_history": [deepcopy(item) for item in raw_row.get("attempt_history") or [] if isinstance(item, Mapping)],
            "source_replay_evidence": (
                deepcopy(raw_row.get("source_replay_evidence"))
                if isinstance(raw_row.get("source_replay_evidence"), Mapping)
                else {}
            ),
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
            "source_content_sha256": _clean_text(raw_row.get("source_content_sha256")),
            "source_content_sha256_algorithm": _clean_text(raw_row.get("source_content_sha256_algorithm")),
            "source_content_hash_evidence": (
                deepcopy(raw_row.get("source_content_hash_evidence"))
                if isinstance(raw_row.get("source_content_hash_evidence"), Mapping)
                else {}
            ),
            "reason": status_model["reason"] or _clean_text(reducer_result.get("reason")),
            "blocking_reason": status_model["blocking_reason"],
            "warning_reason": status_model["warning_reason"] or _clean_text(reducer_result.get("reason")),
            "audit_issue_codes": _clean_text(raw_row.get("audit_issue_codes")),
            "audit_issue_code_list": _string_list(raw_row.get("audit_issue_codes")),
            "media_kind": _clean_text(raw_row.get("media_kind")),
            "can_open_output": output_probe.get("is_file") is True,
            "output_probe": output_probe,
            "output_evidence_stale": output_probe.get("stale") is True,
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
                "attempt_count": attempt_count,
                "retry_count": retry_count,
                "retry_limit": retry_limit,
                "reason_code": reason_code,
                "first_failure": (
                    deepcopy(raw_row.get("first_failure"))
                    if isinstance(raw_row.get("first_failure"), Mapping)
                    else {}
                ),
                "last_failure": (
                    deepcopy(raw_row.get("last_failure")) if isinstance(raw_row.get("last_failure"), Mapping) else {}
                ),
            },
            "available_actions": [],
        }
        row["lifecycle_evidence"] = {
            "schema_version": "desktop_rerun_network_lifecycle_evidence.v1",
            "state": status,
            "terminal": row["is_terminal"],
            "what": what,
            "why": why,
            "when": when,
            "next": next_action,
            "operator_action": operator_action,
            "reason_code": reason_code,
            "attempt": {
                "count": attempt_count,
                "retry_count": retry_count,
                "retry_limit": retry_limit,
                "next_retry_at_utc": row["next_retry_at_utc"],
            },
            "timeline": timeline,
            "source_replay_evidence": dict(row["source_replay_evidence"]),
            "evidence_links": {"manifest": str(state_path)},
        }
        if status == "retry_exhausted" and row["manual_recovery_available"]:
            row["available_actions"].append(
                {
                    "action": "retry",
                    "label": "Request manual retry",
                    "route": "/api/rerun/network/retry",
                    "confirmation_field": "confirm_retry",
                    "confirmation_prompt": "Retry this exhausted Network row after verifying the source is restored?",
                    "requires_confirmation": False,
                    "request": {
                        "batch_id": batch_id,
                        "row_key": raw_row_key,
                        "confirm_retry": True,
                        "reason": "operator_requested_retry_after_source_restore",
                    },
                    "request_id_required": True,
                    "reason_required": True,
                    "backend_owned": True,
                }
            )
        elif row["operator_action_required"]:
            row["available_actions"].append(
                {
                    "action": "review",
                    "label": "Review evidence",
                    "route": "",
                    "backend_owned": True,
                }
            )
        rows.append(row)
    return rows


__all__ = (
    "_network_row_key",
    "_network_reducer_result",
    "_network_worker_result",
    "_network_verified_output",
    "_network_output_probe",
    "_network_lifecycle_counts",
    "_network_nonnegative_int",
    "_network_batch_queue_rows",
)
