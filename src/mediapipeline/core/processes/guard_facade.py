"""Process close-readiness and active-work facade adapter."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import TYPE_CHECKING, Any, cast

from mediapipeline.core.kernel.dto_status import CloseReadinessDto
from mediapipeline.core.schedule.stop_watcher import schedule_stop_watcher_state_mapping
from mediapipeline.core.paths.contracts import ResolvedPaths
from mediapipeline.core.processes.tdarr_background import tdarr_matrix_background_close_evidence

from mediapipeline.core.processes.guard_policy import (
    audit_progress_indicates_active_work,
    close_readiness_fields,
    pipeline_progress_indicates_active_work,
)
from mediapipeline.core.processes.lifecycle_lease import LifecycleLeaseError, LifecycleLeaseStore
from mediapipeline.core.processes.spawn_runner import _consume_launch_cleanup_reconciliation_required

if TYPE_CHECKING:
    from mediapipeline.core.status.contracts import Snapshot


class ProcessGuardFacadeMixin:
    """Active-work and close-readiness policy shared by process commands."""

    service: object

    def _blocking_job_kinds_for_action(self, action: str) -> set[str] | None:
        normalized = str(action or "").strip().casefold()
        if normalized.startswith("audit "):
            return {"audit", "rerun_csv"}
        if normalized.startswith("pipeline "):
            return {"pipeline", "rerun_csv"}
        return None

    def _acquire_process_launch_lock(
        self,
        action: str,
        *,
        resolved: ResolvedPaths | None = None,
        command_id: str = "",
        resource_claims: list[str] | None = None,
    ) -> tuple[object | None, str]:
        lock = getattr(self, "_process_launch_lock", None)
        if lock is None:
            return None, ""
        try:
            acquired = lock.acquire(blocking=False)
        except Exception as exc:
            self._log_close_guard_exception("Process launch lock acquisition failed", exc)
            return None, f"{action} blocked because the process launch lock could not be verified: {exc}"
        if not acquired:
            return None, f"{action} blocked because another process launch command is already in progress."
        if resolved is None or resolved.state_root is None:
            return lock, ""
        try:
            lease = LifecycleLeaseStore(resolved.state_root).acquire(
                scope=action,
                command_id=command_id or "untracked-command",
                resource_claims=resource_claims,
            )
        except LifecycleLeaseError as exc:
            lock.release()
            return None, f"{action} blocked because the durable lifecycle lease could not be acquired: {exc}"
        return {"memory_lock": lock, "lease": lease, "transferred": False}, ""

    def _release_process_launch_lock(self, lock: object | None) -> None:
        if lock is None:
            return
        if isinstance(lock, dict):
            memory_lock = lock.get("memory_lock")
            lease = lock.get("lease")
            reconciliation_required = (
                lease is not None and _consume_launch_cleanup_reconciliation_required(lease)
            )
            if reconciliation_required:
                lock["transferred"] = True
            if lock.get("transferred") is not True and lease is not None and not reconciliation_required:
                try:
                    lease.release(outcome="launch_failed")
                except Exception as exc:
                    self._log_close_guard_exception("Lifecycle lease release failed", exc)
            lock = memory_lock
        release = getattr(lock, "release", None)
        if callable(release):
            try:
                release()
            except Exception as exc:
                self._log_close_guard_exception("Process launch lock release failed", exc)

    def _prepare_process_launch_lease(self, launch_guard: object | None) -> None:
        if not isinstance(launch_guard, dict):
            return
        lease = launch_guard.get("lease")
        setter = getattr(self.service, "_set_pending_lifecycle_lease", None)
        if lease is not None and callable(setter):
            setter(lease)

    def _set_process_launch_recovery_descriptor(
        self,
        launch_guard: object | None,
        *,
        route: str,
        request: dict[str, object],
    ) -> None:
        if not isinstance(launch_guard, dict):
            return
        lease = launch_guard.get("lease")
        setter = getattr(lease, "set_recovery_descriptor", None)
        if callable(setter):
            setter(route=route, request=request)

    def _transfer_process_launch_lease(self, launch_guard: object | None, proc: object) -> None:
        if not isinstance(launch_guard, dict):
            return
        lease = launch_guard.get("lease")
        if lease is None:
            return
        attached = getattr(proc, "_mediapipeline_lifecycle_lease", None)
        if attached is not lease:
            try:
                lease.activate(int(getattr(proc, "pid", 0) or 0))
                cast(Any, proc)._mediapipeline_lifecycle_lease = lease
            except Exception as exc:
                raise RuntimeError(f"Lifecycle lease could not be bound to launched process: {exc}") from exc
        launch_guard["transferred"] = True

    def get_close_readiness(self, resolved: ResolvedPaths, snapshot: Snapshot | None = None) -> CloseReadinessDto:
        pipeline_state = getattr(self, "_pipeline_state", None)
        state = str(pipeline_state(snapshot)) if snapshot is not None and callable(pipeline_state) else "unknown"
        block_message = self._active_work_block_message(resolved, "Shell close")
        return CloseReadinessDto(
            **close_readiness_fields(
                state=state,
                snapshot_available=snapshot is not None,
                block_message=block_message,
                continuous_watcher=self._schedule_stop_watcher_state_mapping(),
            )
        )

    def _active_work_block_message(
        self,
        resolved: ResolvedPaths,
        action: str,
        *,
        ignore_lifecycle_recovery_evidence: bool = False,
        ignore_queue_source_scan: bool = False,
        preempt_queue_source_scan: bool = False,
    ) -> str:
        if not ignore_lifecycle_recovery_evidence:
            recovery_reader = getattr(self, "get_recovery_status", None)
            if callable(recovery_reader):
                recovery = recovery_reader()
                recovery_status = str(recovery.get("status") or "idle").casefold()
                if recovery_status in {"reconciling", "recovering", "blocked"}:
                    return f"{action} blocked because backend recovery is {recovery_status}: {recovery.get('operator_action_required') or 'reconciliation is required.'}"
            if resolved.state_root is not None:
                lifecycle = LifecycleLeaseStore(resolved.state_root).status()
                lifecycle_status = str(lifecycle.get("status") or "unknown")
                lease_value = lifecycle.get("lease")
                lease: dict[str, Any] = dict(lease_value) if isinstance(lease_value, dict) else {}
                own_pending_reservation = (
                    lifecycle_status == "active"
                    and str(lease.get("scope") or "") == action
                    and int(lease.get("owner_pid") or 0) == os.getpid()
                    and int(lease.get("child_pid") or 0) <= 0
                )
                if lifecycle_status != "idle" and not own_pending_reservation:
                    return f"{action} blocked because backend lifecycle state is {lifecycle_status}: {lifecycle.get('reason') or 'reconciliation is required.'}"
        self._cleanup_stale_launch_guards(resolved, action)
        blocking_job_kinds = self._blocking_job_kinds_for_action(action)
        related_method = getattr(self.service, "find_related_pipeline_processes", None)
        if callable(related_method):
            try:
                related_processes = self._related_processes_for_action(
                    related_method,
                    resolved,
                    blocking_job_kinds=blocking_job_kinds,
                )
            except Exception as exc:
                self._log_close_guard_exception("Related process close-readiness verification failed", exc)
                return f"{action} blocked because related MediaPipeline processes could not be verified: {exc}"
            if related_processes:
                pids = sorted(str(getattr(proc, "pid", "?")) for proc in related_processes if str(getattr(proc, "pid", "?")).strip())
                pid_text = ", ".join(pids) if pids else "unknown"
                return f"{action} blocked because MediaPipeline process PID(s) {pid_text} are still running from this bundle."
        if str(action or "").strip().casefold().startswith("shell close"):
            tdarr_block = self._tdarr_matrix_background_block_message(resolved, action)
            if tdarr_block:
                return tdarr_block
        promotion_block = self._final_library_promotion_block_message(action)
        if promotion_block:
            return promotion_block
        if ignore_queue_source_scan and preempt_queue_source_scan:
            # Defer the mutating preemption request until every other active-work
            # guard has passed, so a launch rejected for another reason does not
            # unnecessarily cancel scan curation.
            queue_scan_block = ""
        elif ignore_queue_source_scan:
            coordination = getattr(
                self.service,
                "normal_run_once_queue_scan_block_message",
                None,
            )
            if callable(coordination):
                try:
                    queue_scan_block = str(
                        coordination(
                            action,
                            preempt=preempt_queue_source_scan,
                        )
                        or ""
                    )
                except Exception as exc:
                    self._log_close_guard_exception(
                        "Queue source scan Run Once coordination failed",
                        exc,
                    )
                    queue_scan_block = (
                        f"{action} blocked because queue source scan state "
                        f"could not be coordinated safely: {exc}"
                    )
            else:
                queue_scan_block = self._queue_source_scan_block_message(action)
        else:
            queue_scan_block = self._queue_source_scan_block_message(action)
        if queue_scan_block:
            return queue_scan_block
        local_rerun_block = self._local_csv_rerun_enrollment_block_message(resolved, action)
        if local_rerun_block:
            return local_rerun_block
        network_rerun_block = self._network_csv_rerun_batch_block_message(resolved, action)
        if network_rerun_block:
            return network_rerun_block
        if blocking_job_kinds is None or "pipeline" in blocking_job_kinds:
            watcher_block = self._schedule_stop_watcher_close_block_message(action)
            if watcher_block:
                return watcher_block
        if blocking_job_kinds is None or "pipeline" in blocking_job_kinds:
            progress_block = self._progress_block_message(resolved, action)
            if progress_block:
                return progress_block
        if blocking_job_kinds is None or "audit" in blocking_job_kinds:
            audit_block = self._audit_progress_block_message(resolved, action)
            if audit_block:
                return audit_block
        if ignore_queue_source_scan and preempt_queue_source_scan:
            coordination = getattr(
                self.service,
                "normal_run_once_queue_scan_block_message",
                None,
            )
            if not callable(coordination):
                return self._queue_source_scan_block_message(action)
            try:
                queue_scan_block = str(coordination(action, preempt=True) or "")
            except Exception as exc:
                self._log_close_guard_exception(
                    "Queue source scan Run Once coordination failed",
                    exc,
                )
                return (
                    f"{action} blocked because queue source scan state "
                    f"could not be coordinated safely: {exc}"
                )
            if queue_scan_block:
                return queue_scan_block
        return ""

    def _tdarr_matrix_background_block_message(self, resolved: ResolvedPaths, action: str) -> str:
        try:
            evidence = tdarr_matrix_background_close_evidence(Path(resolved.workspace_root))
        except Exception as exc:
            self._log_close_guard_exception("Tdarr Matrix close-readiness verification failed", exc)
            return f"{action} blocked because Tdarr Matrix background state could not be verified: {exc}"
        status = str(evidence.get("status") or "").casefold()
        if status == "active":
            pid = int(evidence.get("pid") or 0)
            run_id = str(evidence.get("run_id") or "unknown run")
            pid_text = f" PID {pid}" if pid > 0 else ""
            return f"{action} blocked because Tdarr Matrix background run {run_id}{pid_text} is still active."
        if status == "unavailable":
            reason = str(evidence.get("reason") or "unknown state")
            return f"{action} blocked because Tdarr Matrix background state could not be verified: {reason}"
        return ""

    def _related_processes_for_action(
        self,
        related_method: object,
        resolved: ResolvedPaths,
        *,
        blocking_job_kinds: set[str] | None,
    ) -> list[object]:
        if not callable(related_method):
            return []
        if blocking_job_kinds is None:
            return list(related_method(resolved))
        try:
            return list(related_method(resolved, job_kinds=blocking_job_kinds))
        except TypeError:
            return list(related_method(resolved))

    def _cleanup_stale_launch_guards(self, resolved: ResolvedPaths, action: str) -> None:
        cleanup = getattr(self.service, "cleanup_stale_launch_guards", None)
        if not callable(cleanup):
            return
        try:
            cleanup(resolved)
        except Exception as exc:
            self._log_close_guard_exception(f"{action} stale launch guard cleanup failed", exc)

    def _final_library_promotion_block_message(self, action: str) -> str:
        block_message = getattr(self.service, "final_library_promotion_active_block_message", None)
        if not callable(block_message):
            return ""
        try:
            return str(block_message(action) or "")
        except Exception as exc:
            self._log_close_guard_exception("Final-library promotion close-readiness verification failed", exc)
            return f"{action} blocked because final-library promotion state could not be verified: {exc}"

    def _queue_source_scan_block_message(self, action: str) -> str:
        block_message = getattr(self.service, "queue_source_scan_active_block_message", None)
        if not callable(block_message):
            return ""
        try:
            return str(block_message(action) or "")
        except Exception as exc:
            self._log_close_guard_exception("Queue source scan close-readiness verification failed", exc)
            return f"{action} blocked because queue source scan state could not be verified: {exc}"

    def _network_csv_rerun_batch_block_message(self, resolved: ResolvedPaths, action: str) -> str:
        state_root = resolved.state_root if resolved.state_root is not None else None
        if state_root is None and resolved.local_base is not None:
            state_root = resolved.local_base / "State"
        if state_root is None:
            return ""
        root = state_root / "Rerun" / "Network"
        if not root.exists():
            return ""
        active_statuses = {"starting", "running", "active", "stopping", "stopped_after_current", "paused", "claim_disabled"}
        try:
            paths = sorted(root.glob("*.json"))
        except OSError as exc:
            self._log_close_guard_exception("Network CSV rerun close-readiness verification failed", exc)
            return f"{action} blocked because network CSV rerun state could not be verified: {exc}"
        for path in paths:
            try:
                payload = json.loads(path.read_text(encoding="utf-8-sig"))
            except Exception as exc:
                self._log_close_guard_exception("Network CSV rerun state read failed", exc)
                return f"{action} blocked because network CSV rerun state file could not be verified: {path}"
            if not isinstance(payload, dict):
                continue
            if str(payload.get("schema_version") or "") != "desktop_rerun_network_batch.v1":
                continue
            status = str(payload.get("status") or "").strip().casefold()
            if status not in active_statuses:
                continue
            if (
                str(action or "").strip().casefold().startswith("shell close")
                and self._network_csv_rerun_waiting_close_safe(payload)
            ):
                state_getter = getattr(self, "_network_lifecycle_state_for", None)
                if callable(state_getter):
                    try:
                        coordinator_state = dict(state_getter("coordinator") or {})
                    except Exception as exc:
                        self._log_close_guard_exception(
                            "Network coordinator close-readiness verification failed",
                            exc,
                        )
                    else:
                        if str(coordinator_state.get("status") or "").casefold() == "stopped":
                            continue
            batch_id = str(payload.get("batch_id") or path.stem)
            claim_text = "claims disabled" if payload.get("claim_provider_enabled") is False else "claims may be active"
            return f"{action} blocked because network CSV rerun batch {batch_id} is {status} ({claim_text})."
        return ""

    def _local_csv_rerun_enrollment_block_message(
        self,
        resolved: ResolvedPaths,
        action: str,
    ) -> str:
        state_root = resolved.state_root
        if state_root is None and resolved.local_base is not None:
            state_root = resolved.local_base / "State"
        if state_root is None:
            return ""
        root = state_root / "Rerun" / "Local"
        if not root.exists():
            return ""
        try:
            paths = sorted(root.glob("*.json"))
        except OSError as exc:
            self._log_close_guard_exception("Local CSV rerun close-readiness verification failed", exc)
            return f"{action} blocked because local CSV rerun enrollment state could not be verified: {exc}"
        for path in paths:
            try:
                payload = json.loads(path.read_text(encoding="utf-8-sig"))
            except Exception as exc:
                self._log_close_guard_exception("Local CSV rerun enrollment read failed", exc)
                return f"{action} blocked because local CSV rerun enrollment could not be verified: {path}"
            if not isinstance(payload, dict):
                continue
            status = str(
                payload.get("lifecycle_state") or payload.get("status") or ""
            ).strip().casefold()
            if status != "spawn_transition_ambiguous":
                continue
            batch_id = str(payload.get("batch_id") or path.stem)
            pid = int(payload.get("pid") or 0)
            pid_text = f" PID {pid}" if pid > 0 else ""
            return (
                f"{action} blocked because local CSV rerun batch {batch_id}{pid_text} child exit "
                "is unverified; reconcile its ActiveJobs and enrollment evidence before closing."
            )
        return ""

    @staticmethod
    def _network_csv_rerun_waiting_close_safe(payload: dict[str, Any]) -> bool:
        rows = payload.get("rows")
        if not isinstance(rows, list) or not rows:
            return False
        waiting_statuses = {"retry_scheduled", "waiting", "waiting_for_source"}
        terminal_statuses = {
            "complete",
            "completed",
            "destination_policy_applied",
            "destination_policy_failed",
            "failed",
            "pending_publish",
            "published_non_overlap",
            "published_replace_final",
            "retry_exhausted",
            "review_required",
            "review_workspace",
            "skipped",
            "worker_failed_pending_reduction",
            "worker_review_pending_reduction",
        }
        for row in rows:
            if not isinstance(row, dict):
                return False
            status = str(row.get("status") or "").strip().casefold()
            active_claim = row.get("active_claim")
            if isinstance(active_claim, dict) and active_claim:
                return False
            if status == "destination_policy_applying":
                return False
            if status in waiting_statuses:
                if status == "retry_scheduled" and not str(
                    row.get("next_retry_at_utc") or row.get("next_retry_at") or ""
                ).strip():
                    return False
                continue
            if status in terminal_statuses:
                continue
            return False
        return True

    def _progress_block_message(self, resolved: ResolvedPaths, action: str) -> str:
        read_progress = getattr(self.service, "read_progress", None)
        is_stale = getattr(self.service, "is_progress_stale", None)
        if not callable(read_progress) or not callable(is_stale):
            return ""
        try:
            progress = read_progress(resolved)
            read_health = progress.get("ReadHealth") if isinstance(progress, dict) else None
            if isinstance(read_health, dict) and read_health.get("available") is False:
                return f"{action} blocked because pipeline progress is unavailable or invalid."
            if not progress or is_stale(progress):
                return ""
        except Exception as exc:
            self._log_close_guard_exception("Pipeline progress close-readiness verification failed", exc)
            return f"{action} blocked because pipeline progress could not be verified: {exc}"
        if pipeline_progress_indicates_active_work(progress):
            return f"{action} blocked because fresh pipeline progress indicates active work."
        return ""

    def _audit_progress_block_message(self, resolved: ResolvedPaths, action: str) -> str:
        read_progress = getattr(self.service, "read_audit_progress", None)
        is_stale = getattr(self.service, "is_audit_progress_stale", None)
        if not callable(read_progress) or not callable(is_stale):
            return ""
        try:
            audit_progress = read_progress(resolved)
            if not audit_progress or is_stale(audit_progress):
                return ""
        except Exception as exc:
            self._log_close_guard_exception("Audit progress close-readiness verification failed", exc)
            return f"{action} blocked because audit progress could not be verified: {exc}"
        if audit_progress_indicates_active_work(audit_progress):
            return f"{action} blocked because fresh audit progress indicates active work."
        return ""

    def _schedule_stop_watcher_close_block_message(self, action: str) -> str:
        state = self._schedule_stop_watcher_state_mapping()
        status = str(state.get("status", "") or "").strip().casefold()
        if status == "error":
            error = str(state.get("error") or "unknown error")
            self._log_close_guard_exception("Schedule-stop watcher close-readiness verification failed", RuntimeError(error))
            return f"{action} blocked because backend schedule-stop watcher state could not be verified: {error}"
        if status != "armed":
            return ""
        pid = int(str(state.get("pid", 0) or 0))
        deadline = str(state.get("deadline", "") or "").strip()
        pid_text = f" PID {pid}" if pid > 0 else ""
        deadline_text = f" until {deadline}" if deadline else ""
        if pid_text:
            return f"{action} blocked because the backend schedule-stop watcher is armed for{pid_text}{deadline_text}."
        return f"{action} blocked because the backend schedule-stop watcher is armed{deadline_text}."

    def _schedule_stop_watcher_state_mapping(self) -> dict[str, object]:
        return schedule_stop_watcher_state_mapping(getattr(self, "_schedule_stop_watcher", None))

    def _log_close_guard_exception(self, message: str, exc: Exception) -> None:
        logger = getattr(self.service, "logger", None)
        if logger is None:
            return
        try:
            logger.warning("%s: %s", message, exc, exc_info=True)
        except Exception:
            return

__all__ = [
    "ProcessGuardFacadeMixin",
]
