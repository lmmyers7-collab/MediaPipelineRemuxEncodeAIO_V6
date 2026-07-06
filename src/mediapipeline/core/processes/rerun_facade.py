"""CSV rerun launch facade adapter."""

from __future__ import annotations

import hashlib
import json
import os
import uuid
from collections.abc import Callable
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
from mediapipeline.core.processes.rerun_control import (
    build_rerun_continue_pending_request,
    request_rerun_stop_after_current,
)
from mediapipeline.core.config.identity import config_operation_block_data, config_operation_block_message

RERUN_NETWORK_START_DRY_RUN_SCHEMA_VERSION = "desktop_rerun_network_start_dry_run.v1"
RERUN_NETWORK_START_DRY_RUN_COMMAND = "rerun.network.start_dry_run"
RERUN_NETWORK_START_SCHEMA_VERSION = "desktop_rerun_network_start.v1"
RERUN_NETWORK_START_COMMAND = "rerun.network.start"
RERUN_NETWORK_BATCH_SCHEMA_VERSION = "desktop_rerun_network_batch.v1"
RERUN_NETWORK_ACTIVE_BATCH_STATUSES = frozenset(
    {"starting", "running", "active", "stopping", "stopped_after_current", "paused", "claim_disabled"}
)


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
        preview_status = str(row.get("status") or ("claimable" if original_claimable else "blocked"))
        if original_claimable:
            status = "pending_claim_disabled"
        elif preview_status == "skipped":
            status = "skipped"
        else:
            status = "blocked"
        rows.append(
            {
                "schema_version": "desktop_rerun_network_batch_row.v1",
                "row_key": str(row.get("row_key") or ""),
                "row_index": row.get("row_index"),
                "source_path": str(row.get("source_path") or ""),
                "planned_output_path": str(row.get("planned_output_path") or ""),
                "library_id": str(row.get("library_id") or ""),
                "status": status,
                "preview_status": preview_status,
                "preview_claimable": original_claimable,
                "claimable": False,
                "claim_status": "claim_disabled_until_phase_4",
                "claim_disabled_reason": "Phase 3 creates coordinator batch state only; row claims are enabled in Phase 4.",
                "source_mapping": dict(row.get("source_mapping") or {}),
                "output_handoff": dict(row.get("output_handoff") or {}),
                "destination_policy": dict(row.get("destination_policy") or {}),
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
    return {
        "schema_version": RERUN_NETWORK_BATCH_SCHEMA_VERSION,
        "batch_id": str(dry_run_data.get("batch_id") or ""),
        "status": "claim_disabled",
        "phase": "phase_3_batch_state_without_worker_execution",
        "created_at_utc": created_at_utc,
        "updated_at_utc": created_at_utc,
        "command_id": command_id,
        "command": RERUN_NETWORK_START_COMMAND,
        "csv_path": str(preview.get("csv_path") or request.get("csv_path") or ""),
        "dry_run_fingerprint": str(dry_run_data.get("dry_run_fingerprint") or ""),
        "claim_provider_enabled": False,
        "claim_provider_status": "disabled_until_phase_4",
        "worker_execution_enabled": False,
        "destination_policy_application_enabled": False,
        "rows_claimable": False,
        "rows": rows,
        "counts": dict(preview.get("counts") or {}),
        "row_count": len(rows),
        "claim_disabled_row_count": sum(1 for row in rows if row.get("preview_claimable") is True),
        "precondition_results": list(dry_run_data.get("precondition_results") or []),
        "state_files": list(dry_run_data.get("state_files_would_write") or []),
        "would_not_touch": dict(dry_run_data.get("would_not_touch") or {}),
        "rollback_expectations": list(dry_run_data.get("rollback_expectations") or []),
        "operator_controls": {
            "stop_after_current": "not_applicable_until_phase_4_claims",
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
        preview_counts = dict(preview.get("counts") or {})
        claimable_rows = int(preview_counts.get("claimable_rows") or 0)
        row_keys = [str(row.get("row_key") or "") for row in preview.get("rows") or [] if row.get("claimable") is True]
        batch_id = _network_rerun_batch_id(str(preview.get("csv_path") or ""), row_keys)
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
                    "claim_provider_enabled": False,
                    "rows_claimable": False,
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
                message="Network CSV rerun batch state created with row claims disabled until Phase 4.",
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

    def start_rerun_csv_process(self, resolved: ResolvedPaths, request: dict[str, Any]) -> CommandResult:
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
        launch_lock, lock_message = self._acquire_process_launch_lock("CSV rerun start")
        if lock_message:
            return rerun_start_active_work_result(lock_message)
        try:
            block_message = self._active_work_block_message(resolved, "CSV rerun start")
            if block_message:
                return rerun_start_active_work_result(block_message)
            if needs_scoped_csv:
                scoped_info = materialize_scoped_rerun_csv(resolved, request, preview=preview, service=self.service)
                launch_csv_path = Path(str(scoped_info.get("scoped_csv_path") or csv_path))
                scoped_csv_path = launch_csv_path
            starter = getattr(self.service, "start_rerun_csv", None)
            if not callable(starter):
                raise RuntimeError("CSV rerun start service is not available.")
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
                show_console=False,
            )
            pid = int(getattr(proc, "pid", 0) or 0)
            launch_logs = ""
            log_method = getattr(self.service, "launch_log_summary", None)
            if callable(log_method):
                launch_logs = str(log_method() or "")
        except Exception as exc:
            return rerun_start_exception_result(exc)
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
        )

    def continue_rerun_pending_rows(self, resolved: ResolvedPaths, request: dict[str, Any]) -> CommandResult:
        error, continue_request, scoped_info = build_rerun_continue_pending_request(resolved, request)
        if error is not None:
            return error
        assert continue_request is not None
        assert scoped_info is not None
        launch = self.start_rerun_csv_process(resolved, continue_request)
        data = {
            "schema_version": "desktop_rerun_continue.v1",
            **dict(scoped_info),
            "launch": launch.to_mapping(),
            "launches_work": bool(launch.ok),
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
            message="Started CSV rerun continuation for pending rows only.",
            refresh_hint="snapshot",
            data=data,
        )

__all__ = [
    "RerunLaunchFacadeMixin",
]
