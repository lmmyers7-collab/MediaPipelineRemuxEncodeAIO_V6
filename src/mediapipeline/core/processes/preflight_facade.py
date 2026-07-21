"""Process launch preflight facade adapter."""

from __future__ import annotations

from collections.abc import Mapping
import os
from pathlib import Path
from typing import Any

from mediapipeline.core.config.settings_policy import settings_encoder_capability_report
from mediapipeline.core.kernel.dto_commands import CommandResult
from mediapipeline.core.kernel.runtime.subprocess_runner import run_capture
from mediapipeline.core.kernel.dto_base import JsonMap, json_safe
from mediapipeline.core.kernel.contracts import ContractError, QueuePlanSnapshot
from mediapipeline.core.paths.contracts import ResolvedPaths
from mediapipeline.core.paths.queue_input_fingerprint import queue_input_consistency
from mediapipeline.core.queue.freshness import (
    QUEUE_SNAPSHOT_FRESHNESS_CLOCK_SKEW_SECONDS,
    QUEUE_SNAPSHOT_FRESHNESS_DEFAULT_SECONDS,
    QUEUE_SNAPSHOT_FRESHNESS_MAX_SECONDS,
    QUEUE_SNAPSHOT_FRESHNESS_MIN_SECONDS,
    evaluate_queue_snapshot_freshness,
    normalize_queue_snapshot_freshness_seconds,
)

from mediapipeline.core.config.identity import config_identity_block_reasons
from mediapipeline.core.processes.audit_policy import AUDIT_LIBRARY_ROOT_ERROR, resolve_audit_library_root
from mediapipeline.core.processes.file_io import read_json_file
from mediapipeline.core.processes.pipeline_policy import (
    PIPELINE_EXTRA_ARGS_ERROR,
    PIPELINE_NETWORK_MODE_BLOCK_ERROR,
    PIPELINE_SLEEP_SECONDS_ERROR,
    configured_network_role,
    coordinator_also_encode_locally_enabled,
    is_supported_pipeline_start_mode,
    pipeline_start_network_mode_label,
    network_role_is_valid,
)
from mediapipeline.core.processes.launch_intent import normalize_pipeline_launch_intent
from mediapipeline.core.processes.rerun_policy import (
    CSV_RERUN_PATH_ERROR,
    rerun_lifecycle_errors,
    rerun_lifecycle_from_request,
    rerun_csv_path_from_request,
    rerun_dry_run_from_request,
    rerun_plan_only_from_request,
)
from mediapipeline.core.processes.rerun_preview import rerun_csv_preview_payload
from mediapipeline.core.processes.path_evidence import (
    LAUNCH_PATH_HEALTH_TIMEOUT_SECONDS,
    configured_path_health,
    path_evidence,
)
from mediapipeline.core.processes.schedule_policy import continuous_schedule_stop_watcher_preflight_check
from mediapipeline.core.processes.source_path_policy import SOURCE_ROOT_SCOPE_TEXT, queue_source_file_validation
from mediapipeline.core.processes.preflight_types import (
    preflight_check,
    preflight_counts,
    preflight_display_status,
    preflight_status,
)


LAUNCH_PREFLIGHT_SCHEMA_VERSION = "desktop_launch_preflight.v1"
LAUNCH_READINESS_SCHEMA_VERSION = "desktop_launch_readiness.v1"
LAUNCH_PREFLIGHT_TARGETS = frozenset({"pipeline", "audit", "rerun"})
LAUNCH_PREFLIGHT_PATH_HEALTH_TIMEOUT_SECONDS = LAUNCH_PATH_HEALTH_TIMEOUT_SECONDS
ENCODER_CAPABILITY_REFRESH_MAX_AGE_SECONDS = 7 * 24 * 60 * 60
ENCODER_CAPABILITY_REFRESH_TIMEOUT_SECONDS = 60.0
QUEUE_LAUNCH_SNAPSHOT_FRESHNESS_DEFAULT_SECONDS = QUEUE_SNAPSHOT_FRESHNESS_DEFAULT_SECONDS
QUEUE_LAUNCH_SNAPSHOT_FRESHNESS_MIN_SECONDS = QUEUE_SNAPSHOT_FRESHNESS_MIN_SECONDS
QUEUE_LAUNCH_SNAPSHOT_FRESHNESS_MAX_SECONDS = QUEUE_SNAPSHOT_FRESHNESS_MAX_SECONDS
QUEUE_LAUNCH_SNAPSHOT_CLOCK_SKEW_SECONDS = QUEUE_SNAPSHOT_FRESHNESS_CLOCK_SKEW_SECONDS



from mediapipeline.core.processes import preflight_support as _preflight_support
from mediapipeline.core.processes.preflight_support import *  # noqa: F403


def _encoder_capability_refresh_attempt(*args, **kwargs):
    original = _preflight_support.run_capture
    try:
        _preflight_support.run_capture = run_capture
        return _preflight_support._encoder_capability_refresh_attempt(*args, **kwargs)
    finally:
        _preflight_support.run_capture = original


def _encoder_capability_report_with_auto_refresh(*args, **kwargs):
    original = _preflight_support.run_capture
    try:
        _preflight_support.run_capture = run_capture
        return _preflight_support._encoder_capability_report_with_auto_refresh(*args, **kwargs)
    finally:
        _preflight_support.run_capture = original

class ProcessFacadeMixin:
    """Process launch preflight helpers."""

    service: object

    def refresh_encoder_capability_report(
        self,
        resolved: ResolvedPaths,
        request: dict[str, Any],
    ) -> CommandResult:
        """Regenerate bounded encoder evidence without launching media work."""

        report = _encoder_capability_report_with_auto_refresh(
            resolved,
            refresh_requested=True,
            force_refresh=True,
        )
        refresh = report.get("auto_refresh") if isinstance(report.get("auto_refresh"), dict) else {}
        ok = bool(refresh.get("ok")) and bool(refresh.get("attempted"))
        return CommandResult(
            command="diagnostics.encoder_capabilities.refresh",
            ok=ok,
            message=(
                "Encoder capability diagnostic refreshed."
                if ok
                else str(refresh.get("message") or "Encoder capability diagnostic refresh failed.")
            ),
            severity="info" if ok else "error",
            warnings=list(report.get("errors") or []),
            errors=[] if ok else [str(refresh.get("message") or "Encoder capability diagnostic refresh failed.")],
            refresh_hint="diagnostics",
            data={
                "encoder_capability_report": json_safe(report),
                "writes_diagnostic_artifact": True,
                "launches_media_processing": False,
                "source_media_mutation": False,
            },
        )

    def get_launch_preflight(self, resolved: ResolvedPaths, request: dict[str, Any]) -> JsonMap:
        target = str(request.get("target") or "pipeline").strip().casefold()
        if target == "csv":
            target = "rerun"
        if target not in LAUNCH_PREFLIGHT_TARGETS:
            checks = [
                _preflight_check(
                    "target",
                    "Launch target",
                    "blocked",
                    f"target={target or '(empty)'}",
                    "Use target pipeline, audit, or rerun.",
                    detail=[f"Allowed targets: {', '.join(sorted(LAUNCH_PREFLIGHT_TARGETS))}"],
                )
            ]
            return self._launch_preflight_payload(target or "unknown", request, checks, start_route="")
        if target == "pipeline":
            checks, normalized, start_route = self._pipeline_launch_preflight_checks(resolved, request)
        elif target == "audit":
            checks, normalized, start_route = self._audit_launch_preflight_checks(resolved, request)
        else:
            checks, normalized, start_route = self._rerun_launch_preflight_checks(resolved, request)
        return self._launch_preflight_payload(target, normalized, checks, start_route=start_route)

    def _launch_preflight_payload(
        self,
        target: str,
        request: dict[str, Any],
        checks: list[dict[str, Any]],
        *,
        start_route: str,
    ) -> JsonMap:
        status = _preflight_status(checks)
        blocked = sum(1 for check in checks if check.get("status") == "blocked")
        review = sum(1 for check in checks if check.get("status") in {"review", "high review", "unknown"})
        can_request_start = blocked == 0
        final_authority = "Backend start routes remain authoritative; this preflight does not reserve locks, launch processes, mutate config, write control flags, or touch media files."
        return json_safe(
            {
                "schema_version": LAUNCH_PREFLIGHT_SCHEMA_VERSION,
                "target": target,
                "start_route": start_route,
                "status": status,
                "can_request_start": can_request_start,
                "final_authority": final_authority,
                "blocked_count": blocked,
                "review_count": review,
                "counts": _preflight_counts(checks),
                "operator_readiness": _preflight_operator_readiness(
                    target=target,
                    start_route=start_route,
                    status=status,
                    can_request_start=can_request_start,
                    checks=checks,
                    final_authority=final_authority,
                ),
                "request": request,
                "checks": checks,
            }
        )

    def _process_launch_lock_preflight_check(self, label: str) -> dict[str, Any]:
        lock, lock_message = self._acquire_process_launch_lock(label)
        if lock_message:
            return _preflight_check(
                "process_launch_lock",
                "Process launch lock",
                "blocked",
                lock_message,
                "Wait for the current backend launch command to finish before submitting another start request.",
            )
        self._release_process_launch_lock(lock)
        return _preflight_check(
            "process_launch_lock",
            "Process launch lock",
            "ready",
            "Launch lock is currently available.",
            "Start route will re-check the lock at submission time.",
        )

    def _active_work_preflight_check(self, resolved: ResolvedPaths, action: str) -> dict[str, Any]:
        block_message = self._active_work_block_message(resolved, action)
        if block_message:
            return _preflight_check(
                "active_work",
                "Active work guard",
                "blocked",
                block_message,
                "Do not start additional work until active processing completes or backend-owned controls intentionally stop/pause it.",
            )
        return _preflight_check(
            "active_work",
            "Active work guard",
            "ready",
            "No active-work block is currently reported.",
            "Start route will re-check active work at submission time.",
        )

    def _normal_queue_scope_preflight_check(
        self,
        resolved: ResolvedPaths,
        *,
        retain_accepted_rows: bool = False,
    ) -> dict[str, Any]:
        # Run Once accepts the backend-owned dry-run membership as one immutable
        # workload.  Public Queue filters, pagination, selection, and render
        # limits never participate in this check.
        return self._normal_queue_scope_snapshot_preview_check(
            resolved,
            retain_accepted_rows=retain_accepted_rows,
        )

    def _normal_queue_scope_snapshot_preview_check(
        self,
        resolved: ResolvedPaths,
        *,
        retain_accepted_rows: bool = False,
    ) -> dict[str, Any]:
        """Validate the backend Queue plan accepted by standard Run Once."""
        raw_freshness = (resolved.config_data or {}).get(
            "QueueLaunchSnapshotFreshnessSeconds",
            QUEUE_LAUNCH_SNAPSHOT_FRESHNESS_DEFAULT_SECONDS,
        )
        freshness_seconds = normalize_queue_snapshot_freshness_seconds(raw_freshness)
        preview_age_detail: list[Any] = []
        scan_blocker = getattr(self.service, "queue_source_scan_active_block_message", None)
        if callable(scan_blocker):
            try:
                scan_message = str(scan_blocker("Run Once preflight") or "").strip()
            except Exception as exc:
                return _preflight_check(
                    "normal_queue_scope",
                    "Normal queue scope",
                    "blocked",
                    f"Queue scan state could not be verified: {exc}",
                    "Refresh the Main Queue before starting Run Once.",
                    detail=["queue_scan_state_unknown"],
                )
            if scan_message:
                return _preflight_check(
                    "normal_queue_scope",
                    "Normal queue scope",
                    "blocked",
                    scan_message,
                    "Wait for the queue scan to finish, then refresh preflight.",
                    detail=["queue_scan_running"],
                )

        scan_status_reader = getattr(self.service, "read_queue_scan_status", None)
        scan_status = scan_status_reader(resolved) if callable(scan_status_reader) else {}
        if not isinstance(scan_status, Mapping) or str(scan_status.get("status") or "").casefold() != "completed":
            return _preflight_check(
                "normal_queue_scope",
                "Normal queue scope",
                "blocked",
                "A completed backend Queue dry-run is required before Run Once.",
                "Run Queue scan and wait for it to complete before launching.",
                detail=["queue_scan_not_completed"],
            )
        if str(scan_status.get("mode") or "").casefold() == "inventory_only":
            return _preflight_check(
                "normal_queue_scope",
                "Normal queue scope",
                "blocked",
                "The latest Queue scan contains inventory only, not an authoritative dry-run plan.",
                "Run the full Queue scan before launching.",
                detail=["queue_scan_inventory_only"],
            )

        snapshot_path = resolved.queue_snapshot_path
        if snapshot_path is None or not snapshot_path.is_file():
            return _preflight_check(
                "normal_queue_scope",
                "Normal queue scope",
                "blocked",
                "No normal queue snapshot is available.",
                "Refresh the Main Queue before Run Once; missing evidence does not prove the queue is empty.",
                detail=["queue_snapshot_missing"],
            )
        try:
            snapshot = read_json_file(snapshot_path, retries=1)
        except Exception as exc:
            return _preflight_check(
                "normal_queue_scope",
                "Normal queue scope",
                "blocked",
                f"Normal queue snapshot is unreadable: {snapshot_path} ({type(exc).__name__}).",
                "Refresh the Main Queue before Run Once.",
                detail=["queue_snapshot_unreadable", f"read_error={type(exc).__name__}"],
            )
        if not isinstance(snapshot, Mapping):
            return _preflight_check(
                "normal_queue_scope",
                "Normal queue scope",
                "blocked",
                f"Normal queue snapshot is unreadable: {snapshot_path}",
                "Refresh the Main Queue before Run Once.",
                detail=["queue_snapshot_unreadable"],
            )
        try:
            snapshot_contract = QueuePlanSnapshot.from_mapping(snapshot)
        except ContractError:
            return _preflight_check(
                "normal_queue_scope",
                "Normal queue scope",
                "blocked",
                f"Normal queue snapshot failed contract validation: {snapshot_path}",
                "Refresh the Main Queue before Run Once.",
                detail=["queue_snapshot_invalid"],
            )
        def path_key(value: object) -> str:
            text = str(value or "").strip()
            return os.path.normcase(os.path.normpath(text)) if text else ""

        expected = {
            "config_path": path_key(resolved.config_path),
            "source_movies": path_key(resolved.source_movies),
            "source_tv": path_key(resolved.source_tv),
        }
        actual = {
            "config_path": path_key(snapshot_contract.config_path),
            "source_movies": path_key(snapshot_contract.source_movies),
            "source_tv": path_key(snapshot_contract.source_tv),
        }
        mismatches = [key for key in expected if actual[key] != expected[key]]
        if mismatches:
            return _preflight_check(
                "normal_queue_scope",
                "Normal queue scope",
                "blocked",
                f"Queue snapshot does not match the active scope: {', '.join(mismatches)}.",
                "Refresh the Main Queue for the active config and source roots.",
                detail=[
                    "queue_snapshot_scope_mismatch",
                    *preview_age_detail,
                    *[
                        f"{key}: snapshot={actual[key] or '(empty)'}; active={expected[key] or '(empty)'}"
                        for key in mismatches
                    ],
                ],
            )
        if snapshot_contract.queue_snapshot_origin != "dry_run":
            return _preflight_check(
                "normal_queue_scope",
                "Normal queue scope",
                "blocked",
                f"Latest Queue snapshot origin is {snapshot_contract.queue_snapshot_origin or 'unknown'}, not a backend dry-run.",
                "Run Queue scan before launching.",
                detail=["queue_snapshot_origin_not_dry_run", *preview_age_detail],
            )
        scan_request_id = str(scan_status.get("queue_preview_request_id") or "").strip()
        if not snapshot_contract.queue_preview_request_id or snapshot_contract.queue_preview_request_id != scan_request_id:
            return _preflight_check(
                "normal_queue_scope",
                "Normal queue scope",
                "blocked",
                "Queue snapshot request identity does not match the completed scan.",
                "Run Queue scan again before launching.",
                detail=["queue_snapshot_request_mismatch", *preview_age_detail],
            )
        wall_now_provider = getattr(self.service, "queue_snapshot_freshness_wall_now", None)
        monotonic_provider = getattr(self.service, "queue_snapshot_freshness_monotonic_now", None)
        anchor_provider = getattr(self.service, "queue_snapshot_freshness_anchor", None)
        freshness = evaluate_queue_snapshot_freshness(
            snapshot_path,
            snapshot,
            scan_status,
            freshness_seconds=freshness_seconds,
            **({"wall_now": wall_now_provider()} if callable(wall_now_provider) else {}),
            **({"monotonic_now": monotonic_provider()} if callable(monotonic_provider) else {}),
            anchor=anchor_provider() if callable(anchor_provider) else None,
        )
        preview_age_detail = [
            "preview_age_policy=advisory",
            "launch_revalidation=runtime_queue_rebuild_and_fingerprint",
            *[
                str(item)
                for item in freshness.detail
                if not str(item).startswith("preview_age_policy=")
                and str(item) != freshness.reason_code
            ],
        ]
        if not freshness.fresh:
            if freshness.reason_code.endswith("_stale"):
                preview_age_detail.append("preview_age=older_than_preference")
            elif "future" in freshness.reason_code or "clock" in freshness.reason_code:
                preview_age_detail.append("preview_age=clock_skewed")
            else:
                preview_age_detail.append("preview_age=unavailable")
        consistency = queue_input_consistency(resolved, snapshot)
        if consistency["status"] != "current":
            changed_inputs = [str(item) for item in consistency.get("changed_inputs") or []]
            changed_text = ", ".join(changed_inputs) if changed_inputs else "unavailable input evidence"
            return _preflight_check(
                "normal_queue_scope",
                "Normal queue scope",
                "blocked",
                f"Queue snapshot input fingerprint is {consistency['status']}: {changed_text}.",
                "Run Queue scan again after changing config/library profiles, priority or hold state, manual order/strategy, or file overrides.",
                detail=[
                    "queue_snapshot_inputs_not_current",
                    *[f"queue_input_mismatch:{name}" for name in changed_inputs],
                    consistency,
                ],
            )
        pending_health = snapshot_contract.pending_publish_index_health
        if str(pending_health.get("status") or "ready").casefold() == "blocked":
            return _preflight_check(
                "normal_queue_scope",
                "Normal queue scope",
                "blocked",
                "Pending-publish index health is blocked; Queue safety cannot be established.",
                "Repair the pending-publish evidence, then run Queue scan again.",
                detail=["pending_publish_index_blocked", dict(pending_health)],
            )
        pending_backpressure = snapshot_contract.pending_publish_backpressure
        if pending_backpressure.get("blocked") is True:
            return _preflight_check(
                "normal_queue_scope",
                "Normal queue scope",
                "blocked",
                f"Pending-publish backpressure blocks new Queue work: {pending_backpressure.get('block_reason') or 'threshold reached'}.",
                "Drain or repair Pending Publish, then run Queue scan again.",
                detail=["pending_publish_backpressure_blocked", dict(pending_backpressure)],
            )
        if not snapshot_contract.queue_plan_fingerprint:
            return _preflight_check(
                "normal_queue_scope",
                "Normal queue scope",
                "blocked",
                "Queue dry-run snapshot is missing its execution plan fingerprint.",
                "Run Queue scan with the current backend before launching.",
                detail=["queue_plan_fingerprint_missing"],
            )
        runnable_count = max(0, snapshot_contract.runnable_count)
        accepted_count = len(snapshot_contract.accepted_run_rows)
        if runnable_count > 0 and accepted_count != runnable_count:
            missing = accepted_count == 0
            return _preflight_check(
                "normal_queue_scope",
                "Normal queue scope",
                "blocked",
                (
                    "Queue dry-run snapshot has no accepted Run Once membership."
                    if missing
                    else f"Queue dry-run accepted membership count {accepted_count} does not match runnable_count {runnable_count}."
                ),
                "Refresh the Main Queue with the current backend before launching Run Once.",
                detail=[
                    "queue_snapshot_accepted_rows_missing" if missing else "queue_snapshot_accepted_rows_invalid",
                    *preview_age_detail,
                    f"snapshot_path={snapshot_path}",
                ],
            )
        unverified_name_rows = [
            row.run_queue_index
            for row in snapshot_contract.accepted_run_rows
            if not row.has_verified_planned_display_name
        ]
        if unverified_name_rows:
            return _preflight_check(
                "normal_queue_scope",
                "Normal queue scope",
                "blocked",
                "Queue dry-run accepted membership lacks verified production naming-plan evidence.",
                "Refresh the Main Queue with the current backend before launching Run Once.",
                detail=[
                    "queue_snapshot_planned_display_name_evidence_missing",
                    f"positions={','.join(str(position) for position in unverified_name_rows[:20])}",
                    *preview_age_detail,
                    f"snapshot_path={snapshot_path}",
                ],
            )
        if runnable_count > 0 and not snapshot_contract.accepted_run_rows_fingerprint:
            return _preflight_check(
                "normal_queue_scope",
                "Normal queue scope",
                "blocked",
                "Queue dry-run accepted membership lacks a content fingerprint.",
                "Refresh the Main Queue with the current backend before launching Run Once.",
                detail=[
                    "queue_snapshot_accepted_fingerprint_missing",
                    *preview_age_detail,
                    f"snapshot_path={snapshot_path}",
                ],
            )
        if runnable_count > 0 and not snapshot_contract.accepted_run_rows_fingerprint_is_valid:
            return _preflight_check(
                "normal_queue_scope",
                "Normal queue scope",
                "blocked",
                "Queue dry-run accepted membership does not match its content fingerprint.",
                "Refresh the Main Queue; altered membership or naming evidence cannot launch.",
                detail=[
                    "queue_snapshot_accepted_fingerprint_mismatch",
                    *preview_age_detail,
                    f"snapshot_path={snapshot_path}",
                ],
            )
        if runnable_count == 0:
            return _preflight_check(
                "normal_queue_scope",
                "Normal queue scope",
                "blocked",
                "Validated backend queue plan has zero runnable rows.",
                "Refresh the Main Queue or choose a specific Single File; Run Once has no work to start.",
                detail=["no_runnable_work", *preview_age_detail, f"snapshot_path={snapshot_path}"],
            )
        ready_check = _preflight_check(
            "normal_queue_scope",
            "Normal queue scope",
            "ready",
            f"Validated backend queue plan has {runnable_count} runnable row(s); preview age is advisory.",
            "Run Once will rebuild backend-owned queue scope and stop before media dispatch if the active plan fingerprint changed.",
            detail=[
                *preview_age_detail,
                f"snapshot_path={snapshot_path}",
                f"queue_plan_fingerprint={snapshot_contract.queue_plan_fingerprint}",
            ],
        )
        ready_check["queue_plan_fingerprint"] = snapshot_contract.queue_plan_fingerprint
        ready_check["queue_preview_request_id"] = snapshot_contract.queue_preview_request_id
        if retain_accepted_rows:
            # Internal launch-only handoff. Public preflight keeps the uncapped
            # workload in the backend snapshot and never serializes it into UI.
            ready_check["_accepted_run_rows"] = tuple(snapshot_contract.accepted_run_rows)
        return ready_check

    def _config_identity_preflight_check(self, resolved: ResolvedPaths) -> dict[str, Any]:
        identity = dict(getattr(resolved, "config_identity", {}) or {})
        reasons = config_identity_block_reasons(identity)
        if reasons:
            return _preflight_check(
                "config_identity",
                "Active config identity",
                "blocked",
                str(identity.get("operator_status") or "Config is not ready."),
                "Restore a verified operator PSD1 before launching.",
                detail=reasons + [f"config_path={identity.get('config_path') or resolved.config_path}"],
            )
        if identity:
            return _preflight_check(
                "config_identity",
                "Active config identity",
                "ready",
                f"key_count={identity.get('key_count')}; sha256={str(identity.get('sha256') or '')[:16]}",
                "Start route will re-check the active config identity before launch.",
                detail=[f"config_path={identity.get('config_path') or resolved.config_path}"],
            )
        return _preflight_check(
            "config_identity",
            "Active config identity",
            "unknown",
            "Config identity evidence is not available in this resolved path snapshot.",
            "Refresh the backend Settings workspace before launch.",
        )

    def _configured_path_health_preflight_check(
        self,
        resolved: ResolvedPaths,
        *,
        path_health: dict[str, Any] | None = None,
    ) -> dict[str, Any] | None:
        health = path_health or configured_path_health(resolved)
        if not health.get("rows"):
            return None
        operator_status = str(health.get("operator_status") or "unknown").casefold()
        if operator_status == "ready":
            status = "ready"
        elif operator_status == "blocked":
            status = "high review"
        elif operator_status == "review":
            status = "review"
        else:
            status = "unknown"
        issue_lines = [
            str(line)
            for line in health.get("summary_lines", [])
            if str(line).strip()
        ]
        return _preflight_check(
            "configured_path_health",
            "Configured server/folder health",
            status,
            str(health.get("operator_summary") or "Configured path health is incomplete."),
            "Resolve unreachable configured source/output/scratch roots before pressing Start.",
            detail=issue_lines[:10],
        )

    def _launch_path_health_for_resolved(self, resolved: ResolvedPaths) -> dict[str, Any]:
        return configured_path_health(
            resolved,
            timeout_seconds=LAUNCH_PREFLIGHT_PATH_HEALTH_TIMEOUT_SECONDS,
        )

    def _autonomy_health_preflight_check(
        self,
        resolved: ResolvedPaths,
        *,
        path_health: dict[str, Any] | None = None,
        actual_mode: str = "",
    ) -> dict[str, Any]:
        health = self._autonomy_health_for_resolved(resolved, path_health=path_health)
        status = str(health.get("overall_status") or "unknown").casefold()
        recovery_drain_mode = actual_mode == "drain_pending_pushes"
        if status == "ready":
            check_status = "ready"
        elif status == "blocked":
            check_status = "review" if recovery_drain_mode else "blocked"
        else:
            check_status = "review"
        blockers = [item for item in health.get("blockers", []) if isinstance(item, dict)]
        review_items = [item for item in health.get("review_items", []) if isinstance(item, dict)]
        detail = [
            f"overall_status={status}",
            f"blocked_count={len(blockers)}",
            f"review_count={len(review_items)}",
        ]
        evidence = [
            f"overall_status={status}",
            f"can_start_new_work={'yes' if status != 'blocked' else 'no'}",
        ]
        if recovery_drain_mode:
            evidence.append("recovery_drain_mode=yes")
            evidence.append("can_attempt_pending_drain=yes")
        if blockers:
            first_blocker = blockers[0]
            blocker_code = str(first_blocker.get("code") or "").strip()
            blocker_message = str(first_blocker.get("message") or "").strip()
            if blocker_code:
                evidence.append(f"blocker={blocker_code}")
            if blocker_message:
                evidence.append(f"reason={blocker_message}")
        recovery_actions: list[dict[str, Any]] = []
        for item in blockers[:5]:
            detail.append(f"{item.get('code')}: {item.get('message')}")
            recovery_action = item.get("recovery_action")
            if isinstance(recovery_action, dict):
                recovery_actions.append(json_safe(recovery_action))
                detail.append(f"recovery_action={recovery_action.get('kind')}: {recovery_action.get('label')}")
        if not recovery_actions:
            for item in review_items[:5]:
                recovery_action = item.get("recovery_action")
                if isinstance(recovery_action, dict):
                    recovery_actions.append(json_safe(recovery_action))
                    detail.append(f"recovery_action={recovery_action.get('kind')}: {recovery_action.get('label')}")
                    break
        return _preflight_check(
            "autonomy_health",
            "Autonomy health gate",
            check_status,
            "; ".join(evidence),
            str(
                "Pending-publish drain is recovery work; autonomy byte pressure still blocks new queue/encode work but does not block drain attempts."
                if recovery_drain_mode and status == "blocked"
                else (health.get("launch_gate") if isinstance(health.get("launch_gate"), dict) else {}).get("safe_next_action")
                or "Review autonomy health before unattended launch."
            ),
            detail=detail,
            recovery_actions=recovery_actions,
        )

    def _pipeline_launch_preflight_checks(
        self,
        resolved: ResolvedPaths,
        request: dict[str, Any],
    ) -> tuple[list[dict[str, Any]], dict[str, Any], str]:
        intent = normalize_pipeline_launch_intent(resolved, request)
        config = intent.config
        mode = intent.mode
        normalized = intent.normalized_request()
        normalized["sleep_seconds"] = intent.sleep_seconds if intent.sleep_seconds is not None else request.get("sleep_seconds")
        single_file_check = _single_file_scope_preflight_check(resolved, normalized["single_file"])
        if intent.single_file_validation is not None:
            single_file_check["detail"] = [json_safe(intent.single_file_validation)]
            normalized["single_file_validation"] = intent.single_file_validation
        checks: list[dict[str, Any]] = [
            _network_role_preflight_check(config),
            _preflight_check(
                "mode",
                "Pipeline mode",
                "ready" if is_supported_pipeline_start_mode(mode) else "blocked",
                f"mode={mode or '(empty)'}",
                "Use one of continuous, once, validate, or drain_pending_pushes.",
                detail=[] if is_supported_pipeline_start_mode(mode) else ["Invalid modes are rejected before schedule or active-work checks.", "Error: mode must be continuous, once, validate, or drain_pending_pushes."],
            ),
            _preflight_check(
                "sleep_seconds",
                "Sleep interval",
                "ready" if intent.sleep_error is None else "blocked",
                f"sleep_seconds={normalized['sleep_seconds']}",
                "Use a whole number of seconds; backend start will clamp valid values to at least one second.",
                detail=[] if intent.sleep_error is None else [PIPELINE_SLEEP_SECONDS_ERROR],
            ),
            _preflight_check(
                "extra_args",
                "Extra arguments",
                "ready" if intent.extra_args_error is None else "blocked",
                f"extra_args_present={bool(intent.extra_args)}; allow_extra_args=False",
                "Keep local API launches on structured fields; extra pipeline arguments are not accepted by the Local API.",
                detail=[] if intent.extra_args_error is None else [PIPELINE_EXTRA_ARGS_ERROR],
            ),
            single_file_check,
        ]
        if mode == "once" and not normalized["single_file"]:
            checks.append(self._normal_queue_scope_preflight_check(resolved))
        if is_supported_pipeline_start_mode(mode):
            schedule_gate = self._resolve_pipeline_start_schedule_gate(mode, request)
            normalized["actual_mode"] = str(schedule_gate.get("mode") or mode)
            normalized["schedule"] = schedule_gate.get("data") or {}
            checks.append(
                _preflight_check(
                    "schedule_gate",
                    "Schedule gate",
                    "ready" if bool(schedule_gate.get("ok")) else "blocked",
                    f"ok={bool(schedule_gate.get('ok'))}; actual_mode={normalized['actual_mode']}; override={normalized['schedule_override'] or 'none'}",
                    "Respect the schedule gate or choose an explicit override before start.",
                    detail=[str(schedule_gate.get("message") or "Schedule gate is currently allowing this request."), json_safe(schedule_gate.get("data") or {})],
                )
            )
            checks.append(
                continuous_schedule_stop_watcher_preflight_check(
                    requested_mode=mode,
                    actual_mode=normalized["actual_mode"],
                    request=request,
                    schedule_gate=schedule_gate,
                    backend_watcher_available=self._pipeline_schedule_stop_watcher_available(),
                )
            )
        else:
            normalized["actual_mode"] = mode
        checks.extend(
            [
                self._process_launch_lock_preflight_check("Pipeline preflight"),
                self._config_identity_preflight_check(resolved),
            ]
        )
        path_health = self._launch_path_health_for_resolved(resolved)
        path_health_check = self._configured_path_health_preflight_check(resolved, path_health=path_health)
        if path_health_check is not None:
            checks.append(path_health_check)
        checks.append(
            _encoder_capability_report_preflight_check(
                resolved,
                refresh_requested=False,
            )
        )
        checks.append(
            self._autonomy_health_preflight_check(
                resolved,
                path_health=path_health,
                actual_mode=str(normalized.get("actual_mode") or mode),
            )
        )
        checks.extend(
            [
                self._active_work_preflight_check(resolved, "Pipeline preflight"),
                _preflight_check(
                    "service_start",
                    "Pipeline service",
                    "ready" if _service_callable(self.service, "start_pipeline") else "blocked",
                    f"start_pipeline callable={_service_callable(self.service, 'start_pipeline')}",
                    "Backend start requires the existing service pipeline launcher.",
                ),
                _preflight_check(
                    "runtime_prep_boundary",
                    "Runtime prep boundary",
                    "ready",
                    "Preflight intentionally does not clear stale progress, remove flags, write launch state, or call runtime prep.",
                    "Start route will perform runtime/control prep immediately before launching.",
                ),
            ]
        )
        return checks, normalized, "/api/pipeline/start"

    def _audit_launch_preflight_checks(
        self,
        resolved: ResolvedPaths,
        request: dict[str, Any],
    ) -> tuple[list[dict[str, Any]], dict[str, Any], str]:
        library_root = resolve_audit_library_root(request, resolved.config_data)
        path = Path(library_root) if library_root else None
        evidence, details = path_evidence(path)
        normalized = {
            "target": "audit",
            "library_root": library_root,
            "include_sidecars": bool(request.get("include_sidecars", False)),
            "show_console": bool(request.get("show_console", False)),
        }
        checks = [
            _preflight_check(
                "library_root",
                "Audit library root",
                "blocked" if not library_root else "ready" if evidence == "exists" else "review",
                f"library_root={library_root or '(empty)'}; path={evidence}",
                "Provide a library root or configured Outsource path before audit start.",
                detail=details if library_root else [AUDIT_LIBRARY_ROOT_ERROR],
            ),
            self._process_launch_lock_preflight_check("Audit preflight"),
            self._config_identity_preflight_check(resolved),
            self._active_work_preflight_check(resolved, "Audit preflight"),
            _preflight_check(
                "service_start",
                "Audit service",
                "ready" if _service_callable(self.service, "start_audit") else "blocked",
                f"start_audit callable={_service_callable(self.service, 'start_audit')}",
                "Backend start requires the existing service audit launcher.",
            ),
            _preflight_check(
                "runtime_prep_boundary",
                "Runtime prep boundary",
                "ready",
                "Preflight intentionally does not clear audit progress, write launch state, or call runtime prep.",
                "Start route will perform audit runtime prep immediately before launching.",
            ),
        ]
        return checks, normalized, "/api/audit/start"

    def _rerun_launch_preflight_checks(
        self,
        resolved: ResolvedPaths,
        request: dict[str, Any],
    ) -> tuple[list[dict[str, Any]], dict[str, Any], str]:
        csv_path = rerun_csv_path_from_request(request)
        lifecycle = rerun_lifecycle_from_request(request)
        lifecycle_errors = rerun_lifecycle_errors(lifecycle)
        dry_run = rerun_dry_run_from_request(request)
        plan_only = rerun_plan_only_from_request(request)
        evidence, details = path_evidence(csv_path)
        preview_check: dict[str, Any]
        if csv_path is None:
            preview_check = _preflight_check(
                "csv_rerun_rows",
                "CSV rerun row scope",
                "blocked",
                "CSV preview unavailable; csv_path is empty.",
                "Provide an existing CSV path before checking rerun row readiness.",
                detail=[CSV_RERUN_PATH_ERROR],
            )
        else:
            preview_request = dict(request)
            preview_request["csv_path"] = str(csv_path)
            try:
                preview = rerun_csv_preview_payload(resolved, preview_request, service=self.service)
            except Exception as exc:  # pragma: no cover - defensive preflight guard
                preview_check = _preflight_check(
                    "csv_rerun_rows",
                    "CSV rerun row scope",
                    "blocked",
                    f"CSV preview failed: {exc}",
                    "Fix the CSV path or row data before starting rerun.",
                    detail=[str(exc)],
                )
            else:
                preview_status = str(preview.get("status") or "blocked").casefold()
                if preview_status == "ready":
                    row_status = "ready"
                elif preview_status == "review":
                    row_status = "review"
                else:
                    row_status = "blocked"
                counts = preview.get("counts") if isinstance(preview.get("counts"), dict) else {}
                detail_items: list[Any] = []
                if counts:
                    detail_items.append(counts)
                detail_items.extend(str(item) for item in preview.get("errors") or [] if str(item).strip())
                detail_items.extend(str(item) for item in preview.get("warnings") or [] if str(item).strip())
                preview_check = _preflight_check(
                    "csv_rerun_rows",
                    "CSV rerun row scope",
                    row_status,
                    (
                        f"preview={preview_status}; rows={counts.get('total_rows', 0)}; "
                        f"effective={counts.get('effective_scoped_rows', 0)}; "
                        f"blocked={counts.get('blocked_rows', 0)}; "
                        f"blocked_scoped={counts.get('blocked_scoped_rows', 0)}; "
                        f"relative={counts.get('relative_source_rows', 0)}; "
                        f"missing_files={counts.get('missing_file_rows', 0)}; "
                        f"invalid_extensions={counts.get('invalid_extension_rows', 0)}"
                    ),
                    "Fix blocked CSV rows or choose a scope that excludes them before starting rerun.",
                    detail=detail_items[:24],
                )
        normalized = {
            "target": "rerun",
            "csv_path": str(csv_path or ""),
            "dry_run": dry_run,
            "plan_only": plan_only,
            "stage_mode": lifecycle.stage_mode,
            "original_mode": lifecycle.original_mode,
            "return_mode": lifecycle.return_mode,
            "execution_mode": lifecycle.execution_mode,
            "destination_mode": lifecycle.destination_mode,
            "collision_policy": lifecycle.collision_policy,
            "window_size": lifecycle.window_size,
            "confirm_replace_final": lifecycle.confirm_replace_final,
            "confirm_source_overwrite": lifecycle.confirm_source_overwrite,
            "show_console": False,
        }
        checks = [
            _preflight_check(
                "csv_path",
                "CSV path",
                "blocked" if csv_path is None else "ready" if evidence == "exists" else "review",
                f"csv_path={csv_path or '(empty)'}; path={evidence}",
                "Provide an existing CSV path exported from audit/rerun tooling before start.",
                detail=details if csv_path is not None else [CSV_RERUN_PATH_ERROR],
            ),
            _preflight_check(
                "lifecycle_policy",
                "CSV rerun lifecycle policy",
                "ready" if not lifecycle_errors else "blocked",
                (
                    f"execution={lifecycle.execution_mode}; destination={lifecycle.destination_mode}; "
                    f"collision={lifecycle.collision_policy}; source_original=keep; "
                    f"source_overwrite_confirmed={lifecycle.confirm_source_overwrite}; "
                    f"window={lifecycle.window_size}; dry_run={dry_run}; plan_only={plan_only}"
                ),
                "Use one-at-a-time by default; destination/collision determine verified-output placement, and source-path overwrite requires explicit confirmation.",
                detail=lifecycle_errors,
            ),
            self._process_launch_lock_preflight_check("CSV rerun preflight"),
            self._config_identity_preflight_check(resolved),
            self._active_work_preflight_check(resolved, "CSV rerun preflight"),
            preview_check,
            _preflight_check(
                "service_start",
                "CSV rerun service",
                "ready" if _service_callable(self.service, "start_rerun_csv") else "blocked",
                f"start_rerun_csv callable={_service_callable(self.service, 'start_rerun_csv')}",
                "Backend start requires the existing service CSV rerun launcher.",
            ),
            _preflight_check(
                "media_safety_policy",
                "Media safety policy",
                "ready",
                "execution-safe default is one-at-a-time copy to scratch, verified output, then destination policy application.",
                "Rerun remains backend-owned; final replacement and confirmed source-path overwrite are delayed until output proof and confirmations.",
            ),
        ]
        return checks, normalized, "/api/rerun/start"
