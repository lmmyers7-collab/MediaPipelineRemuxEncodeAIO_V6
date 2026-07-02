"""Process close-readiness and active-work facade adapter."""

from __future__ import annotations

from typing import TYPE_CHECKING

from mediapipeline.core.kernel.dto_status import CloseReadinessDto
from mediapipeline.core.schedule.stop_watcher import schedule_stop_watcher_state_mapping
from mediapipeline.core.paths.contracts import ResolvedPaths

from mediapipeline.core.processes.guard_policy import (
    audit_progress_indicates_active_work,
    close_readiness_fields,
    pipeline_progress_indicates_active_work,
)

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

    def _acquire_process_launch_lock(self, action: str) -> tuple[object | None, str]:
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
        return lock, ""

    def _release_process_launch_lock(self, lock: object | None) -> None:
        if lock is None:
            return
        try:
            lock.release()  # type: ignore[attr-defined]
        except Exception as exc:
            self._log_close_guard_exception("Process launch lock release failed", exc)

    def get_close_readiness(self, resolved: ResolvedPaths, snapshot: Snapshot | None = None) -> CloseReadinessDto:
        state = self._pipeline_state(snapshot) if snapshot is not None else "unknown"
        block_message = self._active_work_block_message(resolved, "Shell close")
        return CloseReadinessDto(
            **close_readiness_fields(
                state=state,
                snapshot_available=snapshot is not None,
                block_message=block_message,
                continuous_watcher=self._schedule_stop_watcher_state_mapping(),
            )
        )

    def _active_work_block_message(self, resolved: ResolvedPaths, action: str) -> str:
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
        promotion_block = self._final_library_promotion_block_message(action)
        if promotion_block:
            return promotion_block
        queue_scan_block = self._queue_source_scan_block_message(action)
        if queue_scan_block:
            return queue_scan_block
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

    def _progress_block_message(self, resolved: ResolvedPaths, action: str) -> str:
        read_progress = getattr(self.service, "read_progress", None)
        is_stale = getattr(self.service, "is_progress_stale", None)
        if not callable(read_progress) or not callable(is_stale):
            return ""
        try:
            progress = read_progress(resolved)
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
        pid = int(state.get("pid", 0) or 0)
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
