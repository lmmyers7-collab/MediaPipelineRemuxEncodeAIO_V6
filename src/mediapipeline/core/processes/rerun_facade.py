"""CSV rerun launch facade adapter."""

from __future__ import annotations

import hashlib
import json
import os
import threading
import uuid
from collections.abc import Callable, Mapping
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from mediapipeline.core.kernel.dto_commands import CommandResult
from mediapipeline.core.paths.contracts import ResolvedPaths
from mediapipeline.core.processes.pipeline_policy import (
    configured_network_role,
    network_role_is_valid,
)

from mediapipeline.core.processes.rerun_policy import (
    rerun_csv_path_missing_result,
    rerun_csv_path_from_request,
    rerun_dry_run_from_request,
    rerun_lifecycle_error_result,
    rerun_lifecycle_errors,
    rerun_lifecycle_from_request,
    rerun_plan_flags_are_supported,
    rerun_plan_mode_error_result,
    rerun_plan_only_from_request,
    rerun_start_active_work_result,
    rerun_start_config_blocked_result,
    rerun_start_exception_result,
    rerun_start_success_result,
)
from mediapipeline.core.processes.rerun_preview import (
    materialize_scoped_rerun_csv,
    request_needs_scoped_csv,
    rerun_csv_preview_payload,
    rerun_network_csv_preview_payload,
)
from mediapipeline.core.network.rerun_handoff import (
    network_rerun_assign_batch_handoff_paths,
    probe_network_rerun_handoff_root,
)
from mediapipeline.core.processes.rerun_control import (
    build_rerun_continue_pending_request,
    request_rerun_stop_after_current,
)
from mediapipeline.core.processes.rerun_lifecycle import (
    RerunCorrelation,
    create_rerun_enrollment,
    new_rerun_correlation,
    read_rerun_enrollment,
    record_rerun_spawn_transition_ambiguity,
    record_rerun_spawn_transition_failure,
    transition_rerun_enrollment,
)
from mediapipeline.core.processes.kill import _process_tree_cleanup_reconciliation_required
from mediapipeline.core.processes.spawn_runner import _launch_cleanup_reconciliation_required
from mediapipeline.core.config.identity import config_operation_block_data, config_operation_block_message

RERUN_NETWORK_START_DRY_RUN_SCHEMA_VERSION = "desktop_rerun_network_start_dry_run.v1"
RERUN_NETWORK_START_DRY_RUN_COMMAND = "rerun.network.start_dry_run"
RERUN_NETWORK_START_SCHEMA_VERSION = "desktop_rerun_network_start.v1"
RERUN_NETWORK_START_COMMAND = "rerun.network.start"
RERUN_NETWORK_BATCH_SCHEMA_VERSION = "desktop_rerun_network_batch.v1"
_RERUN_CONTINUE_LOCK = threading.RLock()
RERUN_NETWORK_ACTIVE_BATCH_STATUSES = frozenset(
    {"starting", "running", "active", "stopping", "stopped_after_current", "paused", "claim_disabled"}
)


def _spawn_stop_exit_verified(proc: Any, stop_result: str) -> bool:
    normalized = str(stop_result or "").strip().casefold()
    if any(
        marker in normalized
        for marker in (
            "timed out",
            "timeout",
            "could not be verified",
            "unable to verify",
            "still running",
            "kill_degraded",
            "nonzero",
            "non-zero",
            "already exited",
            "descendant state is unknown",
            "descendants unknown",
            "reported a failure",
            "failed",
        )
    ):
        return False
    poll = getattr(proc, "poll", None)
    if callable(poll):
        try:
            return poll() is not None
        except Exception:
            return False
    return any(marker in normalized for marker in ("stopped", "killed", "terminated"))


def _launch_guard_lease_evidence(launch_guard: object | None) -> tuple[object | None, int, bool]:
    if not isinstance(launch_guard, dict):
        return None, 0, False
    lease = launch_guard.get("lease")
    payload = getattr(lease, "payload", None)
    if not isinstance(payload, Mapping):
        return lease, 0, False
    try:
        child_pid = int(payload.get("child_pid") or 0)
    except (TypeError, ValueError):
        child_pid = 0
    return lease, child_pid, child_pid <= 0


def _network_rerun_precondition(key: str, status: str, evidence: str, guidance: str) -> dict[str, str]:
    return {
        "key": key,
        "status": status,
        "evidence": evidence,
        "guidance": guidance,
    }


def _network_rerun_state_root(resolved: ResolvedPaths) -> Path | None:
    if resolved.state_root is not None:
        return resolved.state_root / "Rerun" / "Network"
    if resolved.local_base is not None:
        return resolved.local_base / "State" / "Rerun" / "Network"
    return None


def _network_rerun_batch_id(csv_path: str, row_keys: list[str]) -> str:
    raw = "|".join([csv_path, *row_keys])
    digest = hashlib.sha256(raw.encode("utf-8", errors="replace")).hexdigest()[:16]
    return f"network-rerun-{digest}"


def _network_rerun_state_files(resolved: ResolvedPaths, batch_id: str) -> list[dict[str, str]]:
    root = _network_rerun_state_root(resolved)
    if root is None:
        return []
    return [
        {
            "key": "network_csv_rerun_batch",
            "path": str(root / f"{batch_id}.json"),
            "schema_version": RERUN_NETWORK_BATCH_SCHEMA_VERSION,
            "purpose": "Coordinator-owned CSV rerun batch and row state for future claim providers.",
        }
    ]


def _network_rerun_active_batch_count(resolved: ResolvedPaths) -> tuple[int, str]:
    root = _network_rerun_state_root(resolved)
    if root is None:
        return 0, "network CSV rerun state root is unavailable"
    if not root.exists():
        return 0, f"network CSV rerun state root does not exist: {root}"
    active_count = 0
    inspected = 0
    for path in root.glob("*.json"):
        inspected += 1
        try:
            payload = json.loads(path.read_text(encoding="utf-8-sig"))
        except Exception:
            continue
        if not isinstance(payload, dict):
            continue
        status = str(payload.get("status") or "").strip().casefold()
        if status in RERUN_NETWORK_ACTIVE_BATCH_STATUSES:
            active_count += 1
    return active_count, f"inspected={inspected}; active={active_count}; root={root}"


def _coerce_minimum_worker_count(request: dict[str, Any]) -> int:
    raw = request.get("minimum_worker_count", request.get("min_worker_count", 0))
    try:
        return max(0, int(raw or 0))
    except (TypeError, ValueError):
        return 0


def _network_rerun_now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _network_rerun_dry_run_fingerprint(data: dict[str, Any]) -> str:
    basis = {
        "schema_version": data.get("schema_version"),
        "candidate_command": data.get("candidate_command"),
        "batch_id": data.get("batch_id"),
        "safe_to_apply": data.get("safe_to_apply"),
        "precondition_results": data.get("precondition_results"),
        "preview": data.get("preview"),
        "state_files_would_write": data.get("state_files_would_write"),
        "worker_availability": data.get("worker_availability"),
        "request_summary": data.get("request_summary"),
    }
    encoded = json.dumps(basis, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(encoded.encode("utf-8", errors="replace")).hexdigest()


def _network_rerun_state_path(state_files: list[dict[str, str]]) -> Path | None:
    if not state_files:
        return None
    raw_path = str(state_files[0].get("path") or "").strip()
    if not raw_path:
        return None
    return Path(raw_path)


def _network_rerun_state_path_evidence(state_files: list[dict[str, str]]) -> tuple[bool, str]:
    state_path = _network_rerun_state_path(state_files)
    if state_path is None:
        return False, "network CSV rerun batch state path is unavailable"
    if state_path.exists():
        return False, f"network CSV rerun batch state path already exists: {state_path}"
    return True, f"network CSV rerun batch state path is available: {state_path}"


def _network_rerun_batch_rows(preview: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for row in preview.get("rows") or []:
        if not isinstance(row, dict):
            continue
        original_claimable = row.get("claimable") is True
        skipped = row.get("skipped") is True
        preview_status = str(
            row.get("local_preview_status")
            or ("skipped" if skipped else "claimable" if original_claimable else "blocked")
        )
        row_claimable = original_claimable and row.get("start_ready") is True
        if row_claimable:
            status = "pending_claim"
        elif skipped:
            status = "skipped"
        else:
            status = "review_required"
        terminal = status in {"skipped", "review_required"}
        rows.append(
            {
                "schema_version": "desktop_rerun_network_batch_row.v1",
                "row_key": str(row.get("row_key") or ""),
                "row_index": row.get("row_index"),
                "source_path": str(row.get("source_path") or ""),
                "source_size": row.get("source_size") or 0,
                "source_mtime_utc": str(row.get("source_mtime_utc") or ""),
                "source_identity_v2": str(row.get("source_identity_v2") or ""),
                "source_identity_v2_algorithm": str(row.get("source_identity_v2_algorithm") or ""),
                "source_content_sha256": str(row.get("source_content_sha256") or ""),
                "source_content_sha256_algorithm": str(
                    row.get("source_content_sha256_algorithm") or ""
                ),
                "source_content_hash_evidence": dict(
                    row.get("source_content_hash_evidence") or {}
                ),
                "planned_output_path": str(row.get("planned_output_path") or ""),
                "library_id": str(row.get("library_id") or ""),
                "media_kind": str(row.get("media_kind") or ""),
                "audit_issue_codes": str(row.get("audit_issue_codes") or ""),
                "final_output_path": str(row.get("final_output_path") or ""),
                "final_output_source": str(row.get("final_output_source") or ""),
                "final_output_source_field": str(row.get("final_output_source_field") or ""),
                "status": status,
                "preview_status": preview_status,
                "preview_claimable": original_claimable,
                "claimable": row_claimable,
                "claim_status": (
                    "pending_claim"
                    if row_claimable
                    else "skipped"
                    if skipped
                    else "review_required"
                ),
                "terminal": terminal,
                "manual_recovery_required": status == "review_required",
                "operator_action_required": status == "review_required",
                "claim_disabled_reason": "" if row_claimable else "Row is not start-ready for Network CSV rerun worker claims.",
                "source_mapping": dict(row.get("source_mapping") or {}),
                "output_handoff": dict(row.get("output_handoff") or {}),
                "destination_policy": dict(row.get("destination_policy") or {}),
                "rule_decision": dict(row.get("rule_decision") or {}),
                "rerun_rule_id": str(row.get("rerun_rule_id") or ""),
                "rerun_rule_label": str(row.get("rerun_rule_label") or ""),
                "rerun_rule_status": str(row.get("rerun_rule_status") or ""),
                "rerun_rule_reason": str(row.get("rerun_rule_reason") or ""),
                "rerun_rule_destination_behavior": str(row.get("rerun_rule_destination_behavior") or ""),
                "rerun_rule_replacement_eligible": row.get("rerun_rule_replacement_eligible") is True,
                "rerun_rule_required_confirmations": [
                    str(item)
                    for item in row.get("rerun_rule_required_confirmations") or []
                    if str(item or "").strip()
                ],
                "rerun_rule_runtime_options": dict(row.get("rerun_rule_runtime_options") or {}),
                "blockers": [str(item) for item in row.get("blockers") or []],
                "warnings": [str(item) for item in row.get("warnings") or []],
            }
        )
    return rows


def _network_rerun_batch_payload(
    *,
    dry_run_data: dict[str, Any],
    request: dict[str, Any],
    command_id: str,
    created_at_utc: str,
) -> dict[str, Any]:
    preview = dict(dry_run_data.get("preview") or {})
    rows = _network_rerun_batch_rows(preview)
    claimable_count = sum(1 for row in rows if row.get("claimable") is True)
    skipped_count = sum(1 for row in rows if str(row.get("status") or "") == "skipped")
    review_count = sum(1 for row in rows if str(row.get("status") or "") == "review_required")
    terminal_count = sum(1 for row in rows if row.get("terminal") is True)
    active_count = max(0, len(rows) - terminal_count)
    batch_status = "active"
    if rows and active_count == 0:
        batch_status = "review_required" if review_count else "completed_with_skips" if skipped_count else "complete"
    return {
        "schema_version": RERUN_NETWORK_BATCH_SCHEMA_VERSION,
        "batch_id": str(dry_run_data.get("batch_id") or ""),
        "status": batch_status,
        "phase": "phase_4b_csv_row_claim_execution",
        "created_at_utc": created_at_utc,
        "updated_at_utc": created_at_utc,
        "command_id": command_id,
        "command": RERUN_NETWORK_START_COMMAND,
        "csv_path": str(preview.get("csv_path") or request.get("csv_path") or ""),
        "dry_run_fingerprint": str(dry_run_data.get("dry_run_fingerprint") or ""),
        "execution_mode": str(preview.get("execution_mode") or request.get("execution_mode") or ""),
        "destination_mode": str(preview.get("destination_mode") or request.get("destination_mode") or ""),
        "collision_policy": str(preview.get("collision_policy") or request.get("collision_policy") or ""),
        "lifecycle": dict(preview.get("lifecycle") or {}),
        "request_summary": {
            "reason_present": bool(str(request.get("reason") or "").strip()),
            "minimum_worker_count": _coerce_minimum_worker_count(request),
            "confirm_replace_final": request.get("confirm_replace_final") is True,
            "confirm_source_overwrite": request.get("confirm_source_overwrite") is True,
        },
        "claim_provider_enabled": True,
        "claim_provider_status": "enabled_csv_rerun_row_claims",
        "worker_execution_enabled": True,
        "destination_policy_application_enabled": True,
        "rows_claimable": claimable_count > 0,
        "output_handoff": dict(dry_run_data.get("output_handoff") or preview.get("output_handoff") or {}),
        "handoff_probe": dict(dry_run_data.get("handoff_probe") or {}),
        "rows": rows,
        "counts": dict(preview.get("counts") or {}),
        "row_count": len(rows),
        "claimable_row_count": claimable_count,
        "claim_disabled_row_count": len(rows) - claimable_count,
        "skipped_row_count": skipped_count,
        "review_row_count": review_count,
        "terminal_row_count": terminal_count,
        "active_row_count": active_count,
        "batch_terminal": bool(rows) and active_count == 0,
        "precondition_results": list(dry_run_data.get("precondition_results") or []),
        "state_files": list(dry_run_data.get("state_files_would_write") or []),
        "would_not_touch": dict(dry_run_data.get("would_not_touch") or {}),
        "rollback_expectations": list(dry_run_data.get("rollback_expectations") or []),
        "operator_controls": {
            "stop_after_current": "future_control_route",
            "cancel_not_started": "future_control_route",
            "continue_pending": "future_control_route",
        },
    }


def _network_rerun_write_batch_state(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
    try:
        temp.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True, allow_nan=False) + "\n",
            encoding="utf-8",
            newline="",
        )
        os.replace(temp, path)
    finally:
        try:
            temp.unlink(missing_ok=True)
        except OSError:
            pass


def _network_rerun_cleanup_batch_state(path: Path) -> str:
    try:
        path.unlink(missing_ok=True)
    except OSError as exc:
        return f"state_cleanup_failed: {exc}"
    return "state_cleanup_ok"


class RerunLaunchFacadeMixin:
    """CSV rerun process start command adapter for the application facade."""

    def preview_rerun_csv(self, resolved: ResolvedPaths, request: dict[str, Any]) -> dict[str, Any]:
        return rerun_csv_preview_payload(resolved, request, service=self.service)

    def preview_network_rerun_csv(self, resolved: ResolvedPaths, request: dict[str, Any]) -> dict[str, Any]:
        return rerun_network_csv_preview_payload(resolved, request, service=self.service)

    def dry_run_network_rerun_csv_start(self, resolved: ResolvedPaths, request: dict[str, Any]) -> CommandResult:
        preview = self.preview_network_rerun_csv(resolved, request)
        config = dict(resolved.config_data or {})
        role = configured_network_role(config)
        role_valid = network_role_is_valid(role)
        preconditions = [
            _network_rerun_precondition(
                "NetworkRole_is_coordinator",
                "pass" if role == "coordinator" and role_valid else "blocked",
                f"configured NetworkRole={role or '(empty)'}; valid={'yes' if role_valid else 'no'}",
                "Save NetworkRole=coordinator before starting a network CSV rerun batch.",
            )
        ]
        lifecycle_state: dict[str, Any] = {}
        state_getter = getattr(self, "_network_lifecycle_state_for", None)
        if callable(state_getter):
            try:
                lifecycle_state = dict(state_getter("coordinator") or {})
            except Exception as exc:
                lifecycle_state = {"status": "unknown", "error": str(exc)}
        lifecycle_running = str(lifecycle_state.get("status") or "stopped") == "running"
        preconditions.append(
            _network_rerun_precondition(
                "coordinator_lifecycle_running",
                "pass" if lifecycle_running else "blocked",
                f"coordinator_lifecycle_status={lifecycle_state.get('status') or 'stopped'}",
                "Start the Network coordinator lifecycle before creating a network CSV rerun batch.",
            )
        )
        try:
            active_work_block = self._active_work_block_message(resolved, "Network CSV rerun start")
        except Exception as exc:
            active_work_block = f"Active-work guard could not be verified: {exc}"
        preconditions.append(
            _network_rerun_precondition(
                "backend_close_readiness_safe",
                "blocked" if active_work_block else "pass",
                active_work_block or "No local pipeline, audit, rerun, queue scan, or promotion block is currently reported.",
                "Stop or finish conflicting local work before starting a network CSV rerun batch.",
            )
        )
        active_batches, active_batch_evidence = _network_rerun_active_batch_count(resolved)
        preconditions.append(
            _network_rerun_precondition(
                "no_existing_network_csv_rerun_batch",
                "blocked" if active_batches else "pass",
                active_batch_evidence,
                "Stop or continue the existing network CSV rerun batch before starting another one.",
            )
        )
        row_keys = [str(row.get("row_key") or "") for row in preview.get("rows") or [] if row.get("claimable") is True]
        batch_id = _network_rerun_batch_id(str(preview.get("csv_path") or ""), row_keys)
        preview = network_rerun_assign_batch_handoff_paths(preview, batch_id)
        preview_counts = dict(preview.get("counts") or {})
        claimable_rows = int(preview_counts.get("claimable_rows") or 0)
        start_ready_rows = int(preview_counts.get("start_ready_rows") or 0)
        state_files = _network_rerun_state_files(resolved, batch_id)
        preconditions.append(
            _network_rerun_precondition(
                "network_preview_has_claimable_rows",
                "pass" if preview.get("status") != "blocked" and claimable_rows > 0 else "blocked",
                (
                    f"preview_status={preview.get('status')}; claimable_rows={claimable_rows}; "
                    f"blocked_rows={preview_counts.get('blocked_rows') or 0}; "
                    f"destination_policy_risk_rows={preview_counts.get('destination_policy_risk_rows') or 0}"
                ),
                "Resolve CSV row, lifecycle, confirmation, collision, and destination policy blockers before starting.",
            )
        )
        preconditions.append(
            _network_rerun_precondition(
                "network_rerun_handoff_ready",
                "pass" if claimable_rows > 0 and start_ready_rows == claimable_rows else "blocked",
                (
                    f"handoff_status={(preview.get('output_handoff') or {}).get('status') or 'unknown'}; "
                    f"claimable_rows={claimable_rows}; start_ready_rows={start_ready_rows}; "
                    f"output_handoff_ready_rows={preview_counts.get('output_handoff_ready_rows') or 0}"
                ),
                "Configure NetworkRerunHandoffRoot outside source/output/LocalBase/Pending Publish roots before starting.",
            )
        )
        strong_hash_unavailable = int(
            preview_counts.get("source_content_sha256_unavailable_rows") or 0
        )
        preconditions.append(
            _network_rerun_precondition(
                "network_source_content_sha256_ready",
                "pass" if claimable_rows > 0 and strong_hash_unavailable == 0 else "blocked",
                (
                    f"claimable_rows={claimable_rows}; "
                    f"strong_hash_ready_rows={preview_counts.get('source_content_sha256_ready_rows') or 0}; "
                    f"strong_hash_unavailable_rows={strong_hash_unavailable}"
                ),
                "Restore source access and rerun preview so the backend can capture a full SHA-256 baseline.",
            )
        )
        state_path_available, state_path_evidence = _network_rerun_state_path_evidence(state_files)
        preconditions.append(
            _network_rerun_precondition(
                "network_batch_state_path_available",
                "pass" if state_path_available else "blocked",
                state_path_evidence,
                "Use an available coordinator state root and avoid replacing existing network CSV rerun batch evidence.",
            )
        )
        worker_evidence: dict[str, Any]
        try:
            worker_evidence = self.get_network_workers(resolved).to_mapping()
        except Exception as exc:
            worker_evidence = {"error": str(exc), "total_count": 0, "active_count": 0, "idle_count": 0, "warnings": [str(exc)]}
        minimum_workers = _coerce_minimum_worker_count(request)
        observed_workers = int(worker_evidence.get("total_count") or 0)
        worker_status = "pass" if observed_workers else "review"
        if minimum_workers > 0:
            worker_status = "pass" if observed_workers >= minimum_workers else "blocked"
        preconditions.append(
            _network_rerun_precondition(
                "worker_availability_evidence",
                worker_status,
                f"observed_workers={observed_workers}; minimum_requested={minimum_workers}; active={worker_evidence.get('active_count') or 0}; idle={worker_evidence.get('idle_count') or 0}",
                "Workers are advisory unless minimum_worker_count is requested; verify workers are polling before confirmed execution phases.",
            )
        )
        handoff_root = dict(preview.get("output_handoff") or {})
        remote_worker_required = minimum_workers > 0 or observed_workers > 0
        remote_handoff_status = "pass"
        if remote_worker_required and handoff_root.get("remote_worker_compatible") is not True:
            remote_handoff_status = "blocked"
        elif handoff_root.get("coordinator_local_only") is True:
            remote_handoff_status = "review"
        preconditions.append(
            _network_rerun_precondition(
                "network_rerun_handoff_remote_worker_compatible",
                remote_handoff_status,
                (
                    f"path_kind={handoff_root.get('path_kind') or 'missing'}; "
                    f"remote_worker_compatible={'yes' if handoff_root.get('remote_worker_compatible') is True else 'no'}; "
                    f"observed_workers={observed_workers}; minimum_requested={minimum_workers}"
                ),
                "Use a UNC/shared NetworkRerunHandoffRoot before allowing remote workers to claim CSV rerun rows.",
            )
        )
        blocked = [row for row in preconditions if row.get("status") == "blocked"]
        data = {
            "schema_version": RERUN_NETWORK_START_DRY_RUN_SCHEMA_VERSION,
            "candidate_command": "rerun.network.start",
            "dry_run_only": True,
            "effect": "none",
            "preview_route": "/api/rerun/network-preview",
            "confirmed_route": "/api/rerun/network/start",
            "batch_id": batch_id,
            "safe_to_apply": not blocked,
            "precondition_results": preconditions,
            "preview": preview,
            "output_handoff": handoff_root,
            "worker_availability": {
                "minimum_requested": minimum_workers,
                "observed_total": observed_workers,
                "active_count": int(worker_evidence.get("active_count") or 0),
                "idle_count": int(worker_evidence.get("idle_count") or 0),
                "warnings": [str(item) for item in worker_evidence.get("warnings") or []],
            },
            "lifecycle_state": lifecycle_state,
            "dry_run_writes": [],
            "state_files_would_write": state_files,
            "confirmed_route_would_write": [
                "command_journal_entry",
                "network_csv_rerun_batch_state",
            ],
            "would_not_touch": {
                "source_media": "no read/write/delete/rename/move",
                "scratch_media": "no create/delete/cleanup",
                "output_media": "no create/delete/overwrite/publish",
                "normal_queue": "no enqueue/dequeue/reorder",
                "network_claims": "no worker claim/done/release mutation",
                "pending_publish": "no manifest write, drain, repair, move, delete, or publish",
                "completed_manifest": "no acceptance ledger writes",
            },
            "rollback_expectations": [
                "Confirmed start should remove the batch state file if journal/state creation fails before exposure.",
                "No source, output, pending-publish, completed, or normal queue rollback is required for this dry-run.",
            ],
            "request_summary": {
                "reason_present": bool(str(request.get("reason") or "").strip()),
                "minimum_worker_count": minimum_workers,
                "confirm_replace_final": request.get("confirm_replace_final") is True,
                "confirm_source_overwrite": request.get("confirm_source_overwrite") is True,
            },
            "touches_media": False,
            "writes_queue": False,
            "writes_network_state": False,
            "launches_work": False,
        }
        data["dry_run_fingerprint"] = _network_rerun_dry_run_fingerprint(data)
        data["operator_confirmation_scope"] = (
            "Submit dry_run_fingerprint with confirm_start=true to /api/rerun/network/start. "
            "The confirmed route recomputes backend evidence and rejects stale or mismatched proof."
        )
        return CommandResult(
            command=RERUN_NETWORK_START_DRY_RUN_COMMAND,
            ok=True,
            severity="info" if data["safe_to_apply"] else "warning",
            message=(
                "Network CSV rerun start dry-run completed; "
                f"safe_to_apply={'yes' if data['safe_to_apply'] else 'no'}."
            ),
            warnings=[] if data["safe_to_apply"] else ["One or more network CSV rerun start preconditions are blocked."],
            errors=[],
            refresh_hint="snapshot",
            data=data,
        )

    def start_network_rerun_csv_batch(
        self,
        resolved: ResolvedPaths,
        request: dict[str, Any],
        *,
        journal_recorder: Callable[[dict[str, Any], dict[str, Any] | None], None] | None = None,
    ) -> CommandResult:
        if request.get("confirm_start") is not True:
            dry_run = self.dry_run_network_rerun_csv_start(resolved, request).to_mapping()
            data = {
                **dict(dry_run.get("data") or {}),
                "schema_version": RERUN_NETWORK_START_SCHEMA_VERSION,
                "dry_run_only": False,
                "state_written": False,
                "cleanup_result": "not_started_confirmation_missing",
            }
            return CommandResult(
                command=RERUN_NETWORK_START_COMMAND,
                ok=False,
                severity="error",
                message="Network CSV rerun start requires confirm_start=true.",
                errors=["confirm_start_required"],
                refresh_hint="snapshot",
                data=data,
            )
        supplied_fingerprint = str(request.get("dry_run_fingerprint") or "").strip()
        if not supplied_fingerprint:
            dry_run = self.dry_run_network_rerun_csv_start(resolved, request).to_mapping()
            data = {
                **dict(dry_run.get("data") or {}),
                "schema_version": RERUN_NETWORK_START_SCHEMA_VERSION,
                "dry_run_only": False,
                "state_written": False,
                "cleanup_result": "not_started_dry_run_fingerprint_missing",
            }
            return CommandResult(
                command=RERUN_NETWORK_START_COMMAND,
                ok=False,
                severity="error",
                message="Network CSV rerun start requires a matching dry_run_fingerprint.",
                errors=["dry_run_fingerprint_required"],
                refresh_hint="snapshot",
                data=data,
            )
        if journal_recorder is None:
            return CommandResult(
                command=RERUN_NETWORK_START_COMMAND,
                ok=False,
                severity="error",
                message="Network CSV rerun start requires strict command journal evidence before state is exposed.",
                errors=["strict_command_journal_recorder_unavailable"],
                refresh_hint="snapshot",
                data={
                    "schema_version": RERUN_NETWORK_START_SCHEMA_VERSION,
                    "dry_run_only": False,
                    "state_written": False,
                    "cleanup_result": "not_started_command_journal_unavailable",
                    "touches_media": False,
                    "writes_queue": False,
                    "writes_network_state": False,
                    "launches_work": False,
                },
            )
        launch_lock, lock_message = self._acquire_process_launch_lock("Network CSV rerun start")
        if lock_message:
            return CommandResult(
                command=RERUN_NETWORK_START_COMMAND,
                ok=False,
                severity="error",
                message=lock_message,
                errors=["duplicate_command_guard"],
                refresh_hint="snapshot",
                data={
                    "schema_version": RERUN_NETWORK_START_SCHEMA_VERSION,
                    "dry_run_only": False,
                    "state_written": False,
                    "cleanup_result": "not_started_duplicate_command_guard",
                    "touches_media": False,
                    "writes_queue": False,
                    "writes_network_state": False,
                    "launches_work": False,
                },
            )
        try:
            dry_run = self.dry_run_network_rerun_csv_start(resolved, request).to_mapping()
            dry_run_data = dict(dry_run.get("data") or {})
            expected_fingerprint = str(dry_run_data.get("dry_run_fingerprint") or "").strip()
            base_data = {
                **dry_run_data,
                "schema_version": RERUN_NETWORK_START_SCHEMA_VERSION,
                "dry_run_only": False,
                "state_written": False,
                "requested_dry_run_fingerprint": supplied_fingerprint,
                "expected_dry_run_fingerprint": expected_fingerprint,
                "cleanup_result": "not_started",
                "touches_media": False,
                "writes_queue": False,
                "writes_network_state": False,
                "launches_work": False,
            }
            if supplied_fingerprint != expected_fingerprint:
                return CommandResult(
                    command=RERUN_NETWORK_START_COMMAND,
                    ok=False,
                    severity="error",
                    message="dry_run_fingerprint does not match current network CSV rerun start evidence.",
                    errors=["dry_run_fingerprint_mismatch"],
                    refresh_hint="snapshot",
                    data={**base_data, "cleanup_result": "not_started_dry_run_fingerprint_mismatch"},
                )
            blocked = [row for row in dry_run_data.get("precondition_results") or [] if row.get("status") == "blocked"]
            if blocked:
                return CommandResult(
                    command=RERUN_NETWORK_START_COMMAND,
                    ok=False,
                    severity="error",
                    message="Network CSV rerun start blocked by backend preconditions.",
                    errors=[str(row.get("key") or "precondition_blocked") for row in blocked],
                    refresh_hint="snapshot",
                    data={**base_data, "cleanup_result": "not_started_preconditions_blocked"},
                )
            handoff_probe = probe_network_rerun_handoff_root(dict(dry_run_data.get("output_handoff") or {}))
            if handoff_probe.get("ok") is not True:
                return CommandResult(
                    command=RERUN_NETWORK_START_COMMAND,
                    ok=False,
                    severity="error",
                    message="Network CSV rerun start could not prove coordinator handoff create/list/read/delete access.",
                    errors=["network_rerun_handoff_probe_failed"],
                    refresh_hint="snapshot",
                    data={
                        **base_data,
                        "handoff_probe": handoff_probe,
                        "cleanup_result": "not_started_handoff_probe_failed",
                    },
                )
            dry_run_data["handoff_probe"] = handoff_probe
            base_data["handoff_probe"] = handoff_probe
            state_path = _network_rerun_state_path(list(dry_run_data.get("state_files_would_write") or []))
            if state_path is None:
                return CommandResult(
                    command=RERUN_NETWORK_START_COMMAND,
                    ok=False,
                    severity="error",
                    message="Network CSV rerun start could not resolve the coordinator batch state path.",
                    errors=["network_batch_state_path_unavailable"],
                    refresh_hint="snapshot",
                    data={**base_data, "cleanup_result": "not_started_state_path_unavailable"},
                )
            command_id = uuid.uuid4().hex
            created_at = _network_rerun_now()
            state_payload = _network_rerun_batch_payload(
                dry_run_data=dry_run_data,
                request=request,
                command_id=command_id,
                created_at_utc=created_at,
            )
            try:
                _network_rerun_write_batch_state(state_path, state_payload)
            except Exception as exc:
                return CommandResult(
                    command=RERUN_NETWORK_START_COMMAND,
                    ok=False,
                    severity="error",
                    message=f"Network CSV rerun batch state write failed: {exc}",
                    errors=[f"network_batch_state_write_failed: {exc}"],
                    refresh_hint="snapshot",
                    data={**base_data, "command_id": command_id, "cleanup_result": "state_write_failed"},
                )
            result_data = {
                **base_data,
                "command_id": command_id,
                "batch_id": state_payload["batch_id"],
                "state_written": True,
                "state_file": {
                    "path": str(state_path),
                    "schema_version": RERUN_NETWORK_BATCH_SCHEMA_VERSION,
                    "status": state_payload["status"],
                },
                "state_after": {
                    "batch_id": state_payload["batch_id"],
                    "status": state_payload["status"],
                    "claim_provider_enabled": True,
                    "worker_execution_enabled": True,
                    "rows_claimable": state_payload["rows_claimable"],
                    "row_count": state_payload["row_count"],
                },
                "cleanup_result": "ok",
                "writes_network_state": True,
                "network_state_write_scope": ["network_csv_rerun_batch_state"],
            }
            result = CommandResult(
                command=RERUN_NETWORK_START_COMMAND,
                ok=True,
                severity="info",
                message="Network CSV rerun batch state created with handoff evidence and CSV row claims enabled.",
                refresh_hint="snapshot",
                data=result_data,
            )
            try:
                journal_recorder(result.to_mapping(), request)
            except Exception as exc:
                cleanup_result = _network_rerun_cleanup_batch_state(state_path)
                return CommandResult(
                    command=RERUN_NETWORK_START_COMMAND,
                    ok=False,
                    severity="error",
                    message="Network CSV rerun start failed after state write: command journal write failed.",
                    errors=[f"command_journal_write_failed: {exc}"],
                    refresh_hint="snapshot",
                    data={
                        **result_data,
                        "state_written": state_path.exists(),
                        "cleanup_result": f"command_journal_failed_{cleanup_result}",
                        "writes_network_state": state_path.exists(),
                    },
                )
            result.data["strict_command_journal_recorded"] = True
            return result
        finally:
            self._release_process_launch_lock(launch_lock)

    def request_rerun_stop_after_current(self, resolved: ResolvedPaths, request: dict[str, Any]) -> CommandResult:
        return request_rerun_stop_after_current(resolved, request)

    def start_rerun_csv_process(
        self,
        resolved: ResolvedPaths,
        request: dict[str, Any],
        *,
        _recovery_metadata: dict[str, Any] | None = None,
    ) -> CommandResult:
        config_identity = dict(getattr(resolved, "config_identity", {}) or {})
        if config_identity.get("blocks_operations") is True:
            return rerun_start_config_blocked_result(
                config_operation_block_message(config_identity, "CSV rerun start"),
                config_operation_block_data(config_identity),
            )
        csv_path = rerun_csv_path_from_request(request)
        if csv_path is None:
            return rerun_csv_path_missing_result()
        lifecycle = rerun_lifecycle_from_request(request)
        lifecycle_errors = rerun_lifecycle_errors(lifecycle)
        if lifecycle_errors:
            return rerun_lifecycle_error_result(lifecycle_errors)
        dry_run = rerun_dry_run_from_request(request)
        plan_only = rerun_plan_only_from_request(request)
        if not rerun_plan_flags_are_supported(dry_run, plan_only):
            return rerun_plan_mode_error_result()
        preview = self.preview_rerun_csv(resolved, request)
        if preview.get("status") == "blocked":
            return CommandResult(
                command="rerun.start",
                ok=False,
                message=str(preview.get("message") or "CSV rerun preview is blocked."),
                severity="error",
                errors=[str(item) for item in preview.get("errors") or []] or [str(preview.get("message") or "CSV rerun preview is blocked.")],
                warnings=[str(item) for item in preview.get("warnings") or []],
                refresh_hint="",
                data=preview,
            )
        launch_csv_path = csv_path
        scoped_csv_path = None
        scoped_info: dict[str, Any] = {}
        needs_scoped_csv = request_needs_scoped_csv(request, preview)
        command_id = str(request.get("_command_id") or "").strip() or uuid.uuid4().hex
        launch_lock, lock_message = self._acquire_process_launch_lock(
            "CSV rerun start",
            resolved=resolved,
            command_id=command_id,
            resource_claims=[str(csv_path)],
        )
        if lock_message:
            return rerun_start_active_work_result(lock_message)
        correlation: RerunCorrelation | None = None
        enrollment_path: Path | None = None
        manifest_path: Path | None = None
        proc: Any | None = None
        persisted_lifecycle_state = ""
        spawn_cleanup_exit_unverified = False
        spawn_cleanup_detail = ""
        try:
            self._set_process_launch_recovery_descriptor(launch_lock, route="/api/rerun/start", request=request)
            block_message = self._active_work_block_message(resolved, "CSV rerun start")
            if block_message:
                return rerun_start_active_work_result(block_message)
            if needs_scoped_csv:
                scoped_info = materialize_scoped_rerun_csv(resolved, request, preview=preview, service=self.service)
                launch_csv_path = Path(str(scoped_info.get("scoped_csv_path") or csv_path))
                scoped_csv_path = launch_csv_path
            if not plan_only:
                correlation = new_rerun_correlation(resolved, command_id=command_id)
                enrollment_path = correlation.enrollment_path
                manifest_path = correlation.manifest_path
                enrollment_lifecycle = {
                    "execution_mode": lifecycle.execution_mode,
                    "destination_mode": lifecycle.destination_mode,
                    "original_policy": lifecycle.original_policy,
                    "collision_policy": lifecycle.collision_policy,
                    "window_size": lifecycle.window_size,
                    "stage_mode": lifecycle.stage_mode,
                    "original_mode": lifecycle.original_mode,
                    "return_mode": lifecycle.return_mode,
                }
                if _recovery_metadata:
                    enrollment_lifecycle.update(dict(_recovery_metadata))
                create_rerun_enrollment(
                    resolved,
                    correlation=correlation,
                    csv_path=launch_csv_path,
                    source_csv_path=csv_path,
                    dry_run=dry_run,
                    lifecycle=enrollment_lifecycle,
                )
            starter = getattr(self.service, "start_rerun_csv", None)
            if not callable(starter):
                raise RuntimeError("CSV rerun start service is not available.")
            self._prepare_process_launch_lease(launch_lock)
            proc = starter(
                resolved=resolved,
                csv_path=launch_csv_path,
                dry_run=dry_run,
                plan_only=plan_only,
                stage_mode=lifecycle.stage_mode,
                original_mode=lifecycle.original_mode,
                return_mode=lifecycle.return_mode,
                execution_mode=lifecycle.execution_mode,
                destination_mode=lifecycle.destination_mode,
                original_policy=lifecycle.original_policy,
                collision_policy=lifecycle.collision_policy,
                window_size=lifecycle.window_size,
                confirm_replace_final=lifecycle.confirm_replace_final,
                confirm_source_overwrite=lifecycle.confirm_source_overwrite,
                confirm_original_policy=lifecycle.confirm_original_policy,
                confirm_delete_original=lifecycle.confirm_delete_original,
                command_id=correlation.command_id if correlation is not None else command_id,
                launch_id=correlation.launch_id if correlation is not None else "",
                batch_id=correlation.batch_id if correlation is not None else "",
                enrollment_path=enrollment_path,
                manifest_path=manifest_path,
                show_console=False,
            )
            self._transfer_process_launch_lease(launch_lock, proc)
            pid = int(getattr(proc, "pid", 0) or 0)
            launch_logs = ""
            log_method = getattr(self.service, "launch_log_summary", None)
            if callable(log_method):
                launch_logs = str(log_method() or "")
            if enrollment_path is not None:
                try:
                    transitioned = transition_rerun_enrollment(
                        enrollment_path,
                        "process_spawned",
                        expected_states={"accepted"},
                        pid=pid,
                        logs=launch_logs,
                    )
                except Exception:
                    transitioned = read_rerun_enrollment(enrollment_path)
                if transitioned is None:
                    transitioned = read_rerun_enrollment(enrollment_path)
                persisted_lifecycle_state = str(
                    (transitioned or {}).get("lifecycle_state")
                    or (transitioned or {}).get("status")
                    or ""
                ).strip()
                persisted_state_key = persisted_lifecycle_state.casefold()
                if persisted_state_key in {
                    "complete",
                    "completed",
                    "completed_with_failures",
                    "completed_with_failed_rows",
                    "failed",
                    "failed_before_manifest",
                    "retry_exhausted",
                    "cancelled",
                }:
                    raise RuntimeError(
                        "CSV rerun process exited before the start response completed; "
                        f"durable enrollment state is {persisted_lifecycle_state}."
                    )
                spawn_proven_states = {
                    "process_spawned",
                    "starting",
                    "staging",
                    "processing",
                    "waiting",
                    "waiting_for_source",
                    "retry_scheduled",
                    "retrying",
                }
                if persisted_state_key not in spawn_proven_states:
                    stop_detail = " safe child stop was requested"
                    stop_result = ""
                    stop_evidence_unverified = False
                    try:
                        kill_tree = getattr(self.service, "kill_process_tree", None)
                        if callable(kill_tree):
                            stop_result = str(
                                kill_tree(proc, "CSV rerun enrollment transition failure") or ""
                            )
                        else:
                            kill = getattr(proc, "kill", None)
                            if callable(kill):
                                kill()
                                stop_evidence_unverified = True
                                stop_detail = (
                                    " direct root-process stop was requested, but descendant exit was not verified"
                                )
                            else:
                                stop_evidence_unverified = True
                                stop_detail = " spawned process did not expose a safe stop method"
                    except Exception as exc:
                        stop_evidence_unverified = True
                        stop_detail = f" safe child stop failed: {exc}"
                    failure_reason = (
                        "The child process was started, but its process-spawn lifecycle transition was not "
                        f"durably persisted;{stop_detail}. {stop_result}".strip()
                    )
                    exit_verified = not stop_evidence_unverified and _spawn_stop_exit_verified(
                        proc,
                        stop_result,
                    )
                    if exit_verified:
                        record_rerun_spawn_transition_failure(
                            enrollment_path,
                            reason=failure_reason,
                        )
                    else:
                        spawn_cleanup_exit_unverified = True
                        spawn_cleanup_detail = (
                            f"{failure_reason} Child exit is unverified, so duplicate work remains blocked."
                        )
                        record_rerun_spawn_transition_ambiguity(
                            enrollment_path,
                            reason=spawn_cleanup_detail,
                            pid=pid or None,
                        )
                    raise RuntimeError(
                        "CSV rerun enrollment did not durably prove the process-spawn transition "
                        f"(state={persisted_lifecycle_state or '<unavailable>'});{stop_detail}."
                    )
        except Exception as exc:
            process_tree_reconciliation_required = False
            if proc is not None:
                try:
                    process_tree_reconciliation_required = (
                        _process_tree_cleanup_reconciliation_required(proc)
                    )
                except Exception:
                    process_tree_reconciliation_required = True
            cleanup_reconciliation_required = bool(
                process_tree_reconciliation_required or spawn_cleanup_exit_unverified
            )
            reconciliation_guidance = (
                "Child or descendant exit remains unverified; preserve the enrollment, keep duplicate launch "
                "blocked, and reconcile the correlated process evidence before retrying."
                if cleanup_reconciliation_required
                else ""
            )
            if enrollment_path is not None:
                try:
                    current = read_rerun_enrollment(enrollment_path) or {}
                    current_state = str(
                        current.get("lifecycle_state") or current.get("status") or ""
                    ).strip().casefold()
                    if current_state in {"accepted", "process_spawned"}:
                        lease, lease_child_pid, lease_reserved_without_child = _launch_guard_lease_evidence(
                            launch_lock
                        )
                        cleanup_reconciliation_required = bool(
                            cleanup_reconciliation_required
                            or (
                                lease is not None
                                and _launch_cleanup_reconciliation_required(lease)
                            )
                        )
                        if cleanup_reconciliation_required:
                            reconciliation_guidance = (
                                "Child or descendant exit remains unverified; preserve the enrollment, keep "
                                "duplicate launch blocked, and reconcile the correlated process evidence before retrying."
                            )
                        try:
                            proc_pid = int(getattr(proc, "pid", 0) or 0)
                        except (TypeError, ValueError):
                            proc_pid = 0
                        pid = proc_pid or lease_child_pid
                        process_exit_verified = bool(
                            proc is not None
                            and not cleanup_reconciliation_required
                            and _spawn_stop_exit_verified(proc, "")
                        )
                        lease_exit_verified = bool(
                            proc is None
                            and lease_child_pid > 0
                            and getattr(lease, "released", False) is True
                            and not cleanup_reconciliation_required
                        )
                        pre_spawn_failure_verified = bool(
                            proc is None
                            and lease_reserved_without_child
                            and not cleanup_reconciliation_required
                        )
                        if process_exit_verified or lease_exit_verified or pre_spawn_failure_verified:
                            transition_rerun_enrollment(
                                enrollment_path,
                                "failed_before_manifest",
                                expected_states={"accepted", "process_spawned"},
                                reason_code="rerun_process_spawn_failed",
                                reason=str(exc),
                                pid=pid or None,
                                extra_fields={
                                    "process_exit_verified": True,
                                    "duplicate_launch_blocked": False,
                                },
                            )
                        else:
                            record_rerun_spawn_transition_ambiguity(
                                enrollment_path,
                                reason=(
                                    f"CSV rerun start failed with an ambiguous child outcome: {exc}. "
                                    f"{spawn_cleanup_detail or reconciliation_guidance or 'Child exit is unverified, so duplicate work remains blocked.'}"
                                ),
                                pid=pid or None,
                            )
                except Exception:
                    pass
            reported_exc: Exception = exc
            if reconciliation_guidance:
                reported_exc = RuntimeError(f"{exc} {reconciliation_guidance}")
            result = rerun_start_exception_result(reported_exc)
            if correlation is not None:
                enrollment = read_rerun_enrollment(correlation.enrollment_path) or {}
                result.data.update(
                    {
                        "command_id": correlation.command_id,
                        "launch_id": correlation.launch_id,
                        "batch_id": correlation.batch_id,
                        "enrollment_path": str(correlation.enrollment_path),
                        "manifest_path": str(correlation.manifest_path),
                        "durably_enrolled": correlation.enrollment_path.exists(),
                        "inserted_into_normal_queue": False,
                        "queue_source": "csv_rerun",
                        "uses_pipeline_start": False,
                        "lifecycle_state": str(
                            enrollment.get("lifecycle_state") or enrollment.get("status") or ""
                        ),
                    }
                )
            return result
        finally:
            self._release_process_launch_lock(launch_lock)
        return rerun_start_success_result(
            csv_path=launch_csv_path,
            dry_run=dry_run,
            plan_only=plan_only,
            stage_mode=lifecycle.stage_mode,
            original_mode=lifecycle.original_mode,
            return_mode=lifecycle.return_mode,
            execution_mode=lifecycle.execution_mode,
            destination_mode=lifecycle.destination_mode,
            original_policy=lifecycle.original_policy,
            collision_policy=lifecycle.collision_policy,
            window_size=lifecycle.window_size,
            confirm_replace_final=lifecycle.confirm_replace_final,
            confirm_source_overwrite=lifecycle.confirm_source_overwrite,
            pid=pid,
            launch_logs=launch_logs,
            source_csv_path=csv_path,
            scoped_csv_path=scoped_csv_path,
            scope=dict(preview.get("scope") or scoped_info.get("scope") or {}),
            preview_counts=dict(preview.get("counts") or {}),
            command_id=correlation.command_id if correlation is not None else command_id,
            launch_id=correlation.launch_id if correlation is not None else "",
            batch_id=correlation.batch_id if correlation is not None else "",
            enrollment_path=enrollment_path,
            manifest_path=manifest_path,
            durably_enrolled=enrollment_path is not None,
            lifecycle_state=persisted_lifecycle_state or ("process_spawned" if correlation is not None else ""),
        )

    def continue_rerun_pending_rows(self, resolved: ResolvedPaths, request: dict[str, Any]) -> CommandResult:
        with _RERUN_CONTINUE_LOCK:
            error, continue_request, scoped_info = build_rerun_continue_pending_request(resolved, request)
            if error is not None:
                return error
            assert continue_request is not None
            assert scoped_info is not None
            recovery_metadata = {
                key: scoped_info[key]
                for key in (
                    "recovery_request_id",
                    "recovery_key",
                    "recovery_root_key",
                    "recovery_generation",
                    "recovery_supersedes_enrollment_path",
                    "recovery_supersedes_recovery_key",
                    "recovery_supersedes_batch_id",
                    "recovery_source_command_id",
                    "recovery_source_launch_id",
                    "recovery_source_batch_id",
                    "recovery_source_manifest_path",
                    "recovery_source_manifest_key",
                    "recovery_scope",
                    "recovery_row_selectors",
                )
                if key in scoped_info
            }
            launch = self.start_rerun_csv_process(
                resolved,
                continue_request,
                _recovery_metadata=recovery_metadata,
            )
        launch_mapping = launch.to_mapping()
        launch_data = dict(launch_mapping.get("data") or {})
        data = {
            "schema_version": "desktop_rerun_continue.v1",
            **dict(scoped_info),
            "launch": launch_mapping,
            "launches_work": bool(launch.ok),
            "durably_enrolled": launch_data.get("durably_enrolled") is True,
            "command_id": str(launch_data.get("command_id") or ""),
            "launch_id": str(launch_data.get("launch_id") or ""),
            "batch_id": str(launch_data.get("batch_id") or ""),
            "enrollment_path": str(launch_data.get("enrollment_path") or ""),
            "manifest_path": str(launch_data.get("manifest_path") or ""),
        }
        if not launch.ok:
            return CommandResult(
                command="rerun.continue",
                ok=False,
                severity=launch.severity,
                message=launch.message,
                warnings=list(launch.warnings),
                errors=list(launch.errors),
                refresh_hint=launch.refresh_hint,
                data=data,
            )
        return CommandResult(
            command="rerun.continue",
            ok=True,
            severity="info",
            message="Accepted CSV rerun continuation; the scoped batch was durably enrolled and its process spawned.",
            refresh_hint="snapshot",
            data=data,
        )

__all__ = [
    "RerunLaunchFacadeMixin",
]
